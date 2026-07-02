# server/main.py — DeskGuard Central Server
import os, base64, secrets, logging, json
from datetime import datetime
from typing import Any

from fastapi import FastAPI, Depends, HTTPException, Header
from sqlalchemy.orm import Session

import config, database
from database import (Machine, MachineConfig, ActivityEvent, UrlVisit, Screenshot,
                      AppViolation, UsbEvent, KeylogSession, Alert, get_db)
from auth import verify_agent

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("server")

database.init_db()
os.makedirs(config.SCREENSHOTS_DIR, exist_ok=True)

app = FastAPI(title="DeskGuard", docs_url=None, redoc_url=None)

ADMIN_KEY = os.environ.get("ADMIN_API_KEY", "changeme-set-in-env")


def _require_admin(x_admin_key: str = Header(...)):
    if x_admin_key != ADMIN_KEY:
        raise HTTPException(403, "Invalid admin key")


def _maybe_alert(db, machine, severity, category, message, ref_table="", ref_id=0):
    if severity in config.ALERT_ON_SEVERITIES:
        db.add(Alert(machine=machine, severity=severity, category=category,
                     message=message, ref_table=ref_table, ref_id=ref_id))


def _save_screenshot(db, machine, item):
    try:
        image_bytes = base64.b64decode(item.get("data_b64",""))
        captured_str = item.get("captured_utc","")
        try:
            captured = datetime.fromisoformat(captured_str.replace("Z","+00:00"))
        except Exception:
            captured = datetime.utcnow()

        if config.SCREENSHOT_STORAGE == "disk":
            date_dir = os.path.join(config.SCREENSHOTS_DIR, machine,
                                    captured.strftime("%Y-%m-%d"))
            os.makedirs(date_dir, exist_ok=True)
            filepath = os.path.join(date_dir, item.get("filename", f"{captured.timestamp()}.jpg"))
            with open(filepath,"wb") as f: f.write(image_bytes)
            db.add(Screenshot(machine=machine, filename=filepath,
                              captured_utc=captured, reason=item.get("reason","")))
        else:
            db.add(Screenshot(machine=machine, filename=item.get("filename",""),
                              captured_utc=captured, reason=item.get("reason",""),
                              image_data=image_bytes))
    except Exception as e:
        logger.error(f"Screenshot save error: {e}")


# ── Config helper ─────────────────────────────────────────────────────────────

def _get_effective_config(machine_name: str, db: Session) -> dict:
    """Merge default config with machine-specific overrides."""
    default_row = db.query(MachineConfig).filter_by(machine="__default__").first()
    machine_row = db.query(MachineConfig).filter_by(machine=machine_name).first()

    merged = json.loads(default_row.config_json) if default_row else {}
    version = default_row.version if default_row else 1

    if machine_row:
        overrides = json.loads(machine_row.config_json)
        merged.update(overrides)
        version = max(version, machine_row.version)

    merged["version"] = version
    return merged


# ── Agent endpoints ───────────────────────────────────────────────────────────

@app.get("/api/config")
def get_config(
    client_version: int = 0,
    machine: Machine = Depends(verify_agent),
    db: Session = Depends(get_db)
):
    """Agent polls this to get its current config. Returns 204 if unchanged."""
    cfg = _get_effective_config(machine.name, db)
    if cfg.get("version", 0) <= client_version:
        from fastapi.responses import Response
        return Response(status_code=204)
    return cfg


@app.post("/api/ingest")
async def ingest(
    payload: dict[str, Any],
    machine: Machine = Depends(verify_agent),
    db: Session = Depends(get_db),
):
    saved = {"activity":0,"urls":0,"screenshots":0,
             "app_violations":0,"usb_events":0,"keylog":0}
    name = machine.name
    machine.last_seen = datetime.utcnow()

    for item in payload.get("activity",[]):
        try:
            db.add(ActivityEvent(
                machine=name, app=item.get("app",""), exe=item.get("exe",""),
                window_title=item.get("window_title",""),
                start_utc=datetime.fromisoformat(item["start_utc"].replace("Z","+00:00")),
                end_utc=datetime.fromisoformat(item["end_utc"].replace("Z","+00:00")),
                idle=item.get("idle",False)
            )); saved["activity"]+=1
        except Exception as e: logger.warning(f"Activity: {e}")

    for item in payload.get("urls",[]):
        try:
            db.add(UrlVisit(
                machine=name, browser=item.get("browser",""),
                url=item.get("url",""), title=item.get("title",""),
                visited_utc=datetime.fromisoformat(item["visited_utc"].replace("Z","+00:00"))
            )); saved["urls"]+=1
        except Exception as e: logger.warning(f"URL: {e}")

    for item in payload.get("screenshots",[]):
        _save_screenshot(db, name, item); saved["screenshots"]+=1

    for item in payload.get("app_violations",[]):
        try:
            av = AppViolation(
                machine=name, app_name=item.get("app_name",""),
                exe_path=item.get("exe_path",""), username=item.get("username",""),
                pid=item.get("pid",0), killed=item.get("killed",False),
                detected_utc=datetime.fromisoformat(item["detected_utc"].replace("Z","+00:00")),
                severity=item.get("severity","high")
            )
            db.add(av); db.flush()
            _maybe_alert(db, name, av.severity, "app_violation",
                         f"Blacklisted app '{av.app_name}' on {name}",
                         "app_violations", av.id)
            saved["app_violations"]+=1
        except Exception as e: logger.warning(f"Violation: {e}")

    for item in payload.get("usb_events",[]):
        try:
            ue = UsbEvent(
                machine=name, drive_letter=item.get("drive_letter",""),
                volume_serial=item.get("volume_serial",""),
                device_serial=item.get("device_serial",""),
                whitelisted=item.get("whitelisted",False),
                action=item.get("action","none"),
                detected_utc=datetime.fromisoformat(item["detected_utc"].replace("Z","+00:00")),
                severity=item.get("severity","critical")
            )
            db.add(ue); db.flush()
            if not ue.whitelisted:
                _maybe_alert(db, name, ue.severity, "usb",
                             f"Unauthorized USB on {name} (drive={ue.drive_letter})",
                             "usb_events", ue.id)
            saved["usb_events"]+=1
        except Exception as e: logger.warning(f"USB: {e}")

    for item in payload.get("keylog",[]):
        try:
            db.add(KeylogSession(
                machine=name, app=item.get("app",""), text_enc=item.get("text_enc",""),
                start_utc=datetime.fromisoformat(item["start_utc"].replace("Z","+00:00")),
                end_utc=datetime.fromisoformat(item["end_utc"].replace("Z","+00:00"))
            )); saved["keylog"]+=1
        except Exception as e: logger.warning(f"Keylog: {e}")

    db.commit()
    logger.info(f"Ingest from {name}: {saved}")
    return {"status":"ok","saved":saved}


# ── Admin: Machine management ─────────────────────────────────────────────────

@app.post("/admin/machines", dependencies=[Depends(_require_admin)])
def create_machine(body: dict, db: Session = Depends(get_db)):
    name = body.get("name","").strip()
    if not name: raise HTTPException(400,"name required")
    if db.query(Machine).filter_by(name=name).first():
        raise HTTPException(409,f"Machine '{name}' exists")
    api_key = secrets.token_urlsafe(32)
    db.add(Machine(name=name, api_key=api_key, notes=body.get("notes","")))
    db.commit()
    return {"name":name,"api_key":api_key}


@app.get("/admin/machines", dependencies=[Depends(_require_admin)])
def list_machines(db: Session = Depends(get_db)):
    return [{"name":m.name,"active":m.active,"last_seen":m.last_seen,"notes":m.notes}
            for m in db.query(Machine).all()]


@app.delete("/admin/machines/{name}", dependencies=[Depends(_require_admin)])
def deactivate_machine(name: str, db: Session = Depends(get_db)):
    m = db.query(Machine).filter_by(name=name).first()
    if not m: raise HTTPException(404)
    m.active = False; db.commit()
    return {"message":f"Machine '{name}' deactivated."}


# ── Admin: Config management ──────────────────────────────────────────────────

@app.get("/admin/config/{machine}", dependencies=[Depends(_require_admin)])
def get_machine_config(machine: str, db: Session = Depends(get_db)):
    """Get effective config for a machine (default + overrides merged)."""
    return _get_effective_config(machine, db)


@app.post("/admin/config/{machine}", dependencies=[Depends(_require_admin)])
def set_machine_config(machine: str, body: dict, db: Session = Depends(get_db)):
    """
    Set config values for a machine (or '__default__' for all machines).
    Only the keys provided are updated. Pass 'reset: true' to clear overrides.
    """
    if body.get("reset"):
        row = db.query(MachineConfig).filter_by(machine=machine).first()
        if row: db.delete(row); db.commit()
        return {"message": f"Config for '{machine}' reset to default."}

    row = db.query(MachineConfig).filter_by(machine=machine).first()
    if row:
        existing = json.loads(row.config_json)
        existing.update({k:v for k,v in body.items() if k != "reset"})
        row.config_json = json.dumps(existing)
        row.version     += 1
        row.updated_at  = datetime.utcnow()
    else:
        cfg = {k:v for k,v in body.items() if k != "reset"}
        db.add(MachineConfig(machine=machine, config_json=json.dumps(cfg), version=1))

    # Also bump default version so all machines re-fetch
    if machine == "__default__":
        default_row = db.query(MachineConfig).filter_by(machine="__default__").first()
        if default_row: default_row.version += 1

    db.commit()
    return {"message": f"Config updated for '{machine}'.",
            "effective": _get_effective_config(machine, db)}


# ── Admin: Alerts ─────────────────────────────────────────────────────────────

@app.get("/admin/alerts", dependencies=[Depends(_require_admin)])
def get_alerts(acknowledged: bool = False, db: Session = Depends(get_db)):
    alerts = db.query(Alert).filter_by(acknowledged=acknowledged)\
               .order_by(Alert.created_at.desc()).limit(200).all()
    return [{"id":a.id,"machine":a.machine,"severity":a.severity,
             "category":a.category,"message":a.message,"created_at":a.created_at}
            for a in alerts]


@app.post("/admin/alerts/{alert_id}/acknowledge", dependencies=[Depends(_require_admin)])
def ack_alert(alert_id: int, db: Session = Depends(get_db)):
    a = db.query(Alert).get(alert_id)
    if not a: raise HTTPException(404)
    a.acknowledged = True; db.commit()
    return {"message":"Acknowledged"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=config.HOST, port=config.PORT,
                reload=config.DEBUG, log_level="info")
