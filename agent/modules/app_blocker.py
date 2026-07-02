# agent/modules/app_blocker.py
import os, sys, time, threading, logging
from datetime import datetime, timezone
import psutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config

logger = logging.getLogger("app_blocker")
_violations: list = []
_violations_lock = threading.Lock()
_BLACKLIST = {name.lower() for name in config.APP_BLACKLIST}


def _check_and_kill():
    for proc in psutil.process_iter(["pid", "name", "exe", "username"]):
        try:
            name = (proc.info["name"] or "").lower()
            if name not in _BLACKLIST:
                continue
            pid  = proc.info["pid"]
            exe  = proc.info["exe"] or ""
            user = proc.info["username"] or ""
            logger.warning(f"Blacklisted app: {name} (PID {pid}) — killing.")
            try:
                proc.kill()
                killed = True
            except psutil.AccessDenied:
                logger.error(f"Cannot kill {name}: Access Denied.")
                killed = False

            with _violations_lock:
                _violations.append({
                    "machine":      config.MACHINE_NAME,
                    "app_name":     name,
                    "exe_path":     exe,
                    "username":     user,
                    "pid":          pid,
                    "killed":       killed,
                    "detected_utc": datetime.now(timezone.utc).isoformat(),
                    "severity":     "high",
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass


def _loop():
    while True:
        try:
            _check_and_kill()
        except Exception as e:
            logger.error(f"App blocker error: {e}")
        time.sleep(15)


def flush() -> list:
    with _violations_lock:
        v = list(_violations)
        _violations.clear()
    return v


def start():
    t = threading.Thread(target=_loop, daemon=True, name="AppBlockerThread")
    t.start()
    logger.info("App blocker module started.")
