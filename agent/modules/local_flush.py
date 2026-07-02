# agent/modules/local_flush.py  — used when MODE = "local"
import os, sys, glob, time, logging, threading
from datetime import datetime, timezone
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config
from modules import activity, url_tracker, app_blocker, usb_guard, keylogger, local_store

logger = logging.getLogger("local_flush")


def _flush_screenshots():
    for path in sorted(glob.glob(os.path.join(config.SCREENSHOT_DIR, "*.jpg"))):
        try:
            fname = os.path.basename(path)
            parts = fname.replace(".jpg", "").split("_")
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


def _cycle():
    try:
        local_store.save_activity(activity.flush())
        local_store.save_urls(url_tracker.flush())
        local_store.save_app_violations(app_blocker.flush())
        local_store.save_usb_events(usb_guard.flush())
        local_store.save_keylog(keylogger.flush())
        _flush_screenshots()
        logger.debug(f"Local flush done. DB: {local_store.get_db_size_mb():.1f} MB")
    except Exception as e:
        logger.error(f"Local flush error: {e}")


def _loop():
    while True:
        time.sleep(config.LOCAL_FLUSH_EVERY)
        _cycle()


def start():
    local_store.init_db()
    t = threading.Thread(target=_loop, daemon=True, name="LocalFlushThread")
    t.start()
    logger.info("Local flush started.")
