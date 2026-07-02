# agent/modules/local_store.py
import os, sys, sqlite3, logging, threading
from datetime import datetime, timezone
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config

logger = logging.getLogger("local_store")
_lock  = threading.Lock()


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(config.LOCAL_DB_PATH, timeout=10, check_same_thread=False)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA synchronous=NORMAL")
    return c


def init_db():
    os.makedirs(config.DATA_DIR, exist_ok=True)
    with _lock:
        c = _conn()
        c.executescript("""
            CREATE TABLE IF NOT EXISTS activity_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                machine TEXT, app TEXT, exe TEXT, window_title TEXT,
                start_utc TEXT, end_utc TEXT, idle INTEGER DEFAULT 0,
                saved_at TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_act ON activity_events(machine, start_utc);

            CREATE TABLE IF NOT EXISTS url_visits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                machine TEXT, browser TEXT, url TEXT, title TEXT,
                visited_utc TEXT, saved_at TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_url ON url_visits(machine, visited_utc);

            CREATE TABLE IF NOT EXISTS screenshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                machine TEXT, filename TEXT, captured_utc TEXT,
                reason TEXT, image_data BLOB,
                saved_at TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_ss ON screenshots(machine, captured_utc);

            CREATE TABLE IF NOT EXISTS app_violations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                machine TEXT, app_name TEXT, exe_path TEXT, username TEXT,
                pid INTEGER, killed INTEGER DEFAULT 0,
                detected_utc TEXT, severity TEXT, acknowledged INTEGER DEFAULT 0,
                saved_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS usb_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                machine TEXT, drive_letter TEXT, volume_serial TEXT,
                device_serial TEXT, whitelisted INTEGER DEFAULT 0,
                action TEXT, detected_utc TEXT, severity TEXT,
                acknowledged INTEGER DEFAULT 0,
                saved_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS keylog_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                machine TEXT, app TEXT, text_enc TEXT,
                start_utc TEXT, end_utc TEXT,
                saved_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                machine TEXT, severity TEXT, category TEXT,
                message TEXT, ref_table TEXT, ref_id INTEGER,
                acknowledged INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY, value TEXT
            );
        """)
        c.commit()
        c.close()
    logger.info(f"Local DB initialised: {config.LOCAL_DB_PATH}")


def _alert_if_needed(c, machine, severity, category, message, ref_table="", ref_id=0):
    if severity in ("critical", "high"):
        c.execute("""INSERT INTO alerts (machine,severity,category,message,ref_table,ref_id)
                     VALUES (?,?,?,?,?,?)""",
                  (machine, severity, category, message, ref_table, ref_id))


def save_activity(events: list):
    if not events: return
    with _lock:
        c = _conn()
        c.executemany("""INSERT INTO activity_events
            (machine,app,exe,window_title,start_utc,end_utc,idle)
            VALUES (:machine,:app,:exe,:window_title,:start_utc,:end_utc,:idle)""", events)
        c.commit(); c.close()


def save_urls(visits: list):
    if not visits: return
    with _lock:
        c = _conn()
        c.executemany("""INSERT INTO url_visits
            (machine,browser,url,title,visited_utc)
            VALUES (:machine,:browser,:url,:title,:visited_utc)""", visits)
        c.commit(); c.close()


def save_screenshot(machine: str, filepath: str, captured_utc: str, reason: str):
    try:
        with open(filepath, "rb") as f:
            data = f.read()
        os.remove(filepath)
    except Exception as e:
        logger.error(f"Screenshot read error {filepath}: {e}")
        return
    with _lock:
        c = _conn()
        c.execute("""INSERT INTO screenshots (machine,filename,captured_utc,reason,image_data)
                     VALUES (?,?,?,?,?)""",
                  (machine, os.path.basename(filepath), captured_utc, reason, data))
        c.commit(); c.close()


def save_app_violations(violations: list):
    if not violations: return
    with _lock:
        c = _conn()
        for v in violations:
            cur = c.execute("""INSERT INTO app_violations
                (machine,app_name,exe_path,username,pid,killed,detected_utc,severity)
                VALUES (?,?,?,?,?,?,?,?)""",
                (v["machine"], v["app_name"], v.get("exe_path",""), v.get("username",""),
                 v.get("pid",0), int(v.get("killed",False)),
                 v["detected_utc"], v.get("severity","high")))
            _alert_if_needed(c, v["machine"], v.get("severity","high"),
                             "app_violation",
                             f"Blacklisted app '{v['app_name']}' on {v['machine']}",
                             "app_violations", cur.lastrowid)
        c.commit(); c.close()


def save_usb_events(events: list):
    if not events: return
    with _lock:
        c = _conn()
        for e in events:
            cur = c.execute("""INSERT INTO usb_events
                (machine,drive_letter,volume_serial,device_serial,whitelisted,action,detected_utc,severity)
                VALUES (?,?,?,?,?,?,?,?)""",
                (e["machine"], e.get("drive_letter",""), e.get("volume_serial",""),
                 e.get("device_serial",""), int(e.get("whitelisted",False)),
                 e.get("action","none"), e["detected_utc"], e.get("severity","critical")))
            if not e.get("whitelisted"):
                _alert_if_needed(c, e["machine"], e.get("severity","critical"),
                                 "usb",
                                 f"Unauthorized USB on {e['machine']} drive={e.get('drive_letter')}",
                                 "usb_events", cur.lastrowid)
        c.commit(); c.close()


def save_keylog(sessions: list):
    if not sessions: return
    with _lock:
        c = _conn()
        c.executemany("""INSERT INTO keylog_sessions (machine,app,text_enc,start_utc,end_utc)
                         VALUES (:machine,:app,:text_enc,:start_utc,:end_utc)""", sessions)
        c.commit(); c.close()


def get_db_size_mb() -> float:
    try:
        return os.path.getsize(config.LOCAL_DB_PATH) / (1024 * 1024)
    except Exception:
        return 0.0
