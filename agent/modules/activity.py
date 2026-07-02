# agent/modules/activity.py
import os, sys, time, threading, logging
from datetime import datetime, timezone
import win32gui, win32process, win32api
import psutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config

logger = logging.getLogger("activity")
_events: list = []
_events_lock = threading.Lock()


def _get_foreground_info() -> dict:
    try:
        hwnd     = win32gui.GetForegroundWindow()
        title    = win32gui.GetWindowText(hwnd)
        _, pid   = win32process.GetWindowThreadProcessId(hwnd)
        proc     = psutil.Process(pid)
        return {"app": proc.name(), "title": title, "pid": pid, "exe": proc.exe()}
    except Exception:
        return {"app": "unknown", "title": "", "pid": 0, "exe": ""}


def _get_idle_seconds() -> float:
    try:
        info = win32api.GetLastInputInfo()
        tick = win32api.GetTickCount()
        return (tick - info) / 1000.0
    except Exception:
        return 0.0


def _loop():
    current = None
    while True:
        try:
            now     = datetime.now(timezone.utc).isoformat()
            info    = _get_foreground_info()
            idle    = _get_idle_seconds() >= config.IDLE_THRESHOLD_SECONDS
            wkey    = f"{info['app']}::{info['title']}"

            if current is None:
                current = {"machine": config.MACHINE_NAME, "app": info["app"],
                           "exe": info["exe"], "window_title": info["title"],
                           "start_utc": now, "end_utc": now, "idle": idle}
            elif (info["app"] != current["app"] or
                  info["title"] != current["window_title"] or
                  idle != current["idle"]):
                current["end_utc"] = now
                with _events_lock:
                    _events.append(current)
                current = {"machine": config.MACHINE_NAME, "app": info["app"],
                           "exe": info["exe"], "window_title": info["title"],
                           "start_utc": now, "end_utc": now, "idle": idle}
            else:
                current["end_utc"] = now
        except Exception as e:
            logger.error(f"Activity poll error: {e}")
        time.sleep(config.ACTIVITY_POLL_INTERVAL)


def flush() -> list:
    with _events_lock:
        e = list(_events)
        _events.clear()
    return e


def start():
    t = threading.Thread(target=_loop, daemon=True, name="ActivityThread")
    t.start()
    logger.info("Activity tracking module started.")
