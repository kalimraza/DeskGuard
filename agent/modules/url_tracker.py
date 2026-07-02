# agent/modules/url_tracker.py
import os, sys, time, shutil, sqlite3, threading, logging
from datetime import datetime, timezone
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config

logger = logging.getLogger("url_tracker")
_visits: list = []
_visits_lock  = threading.Lock()
_last_poll: dict = {}

APPDATA  = os.environ.get("APPDATA", "")
LOCALAPP = os.environ.get("LOCALAPPDATA", "")

BROWSER_PATHS = {
    "chrome": os.path.join(LOCALAPP, "Google", "Chrome", "User Data", "Default", "History"),
    "edge":   os.path.join(LOCALAPP, "Microsoft", "Edge",  "User Data", "Default", "History"),
    "opera":  os.path.join(APPDATA,  "Opera Software", "Opera Stable", "History"),
}


def _firefox_path():
    profiles = os.path.join(APPDATA, "Mozilla", "Firefox", "Profiles")
    if not os.path.isdir(profiles):
        return None
    for e in os.listdir(profiles):
        if e.endswith((".default-release", ".default")):
            db = os.path.join(profiles, e, "places.sqlite")
            if os.path.isfile(db):
                return db
    return None


def _chromium_ts(ts):
    try:
        epoch_diff = 11644473600
        return datetime.fromtimestamp((ts / 1_000_000) - epoch_diff,
                                      tz=timezone.utc).isoformat()
    except Exception:
        return datetime.now(timezone.utc).isoformat()


def _read_chromium(db_path, browser):
    results = []
    tmp = db_path + ".tmp"
    try:
        shutil.copy2(db_path, tmp)
    except Exception as e:
        logger.debug(f"Cannot copy {browser} DB: {e}")
        return results
    try:
        last = _last_poll.get(browser, time.time() - config.URL_POLL_INTERVAL * 2)
        cutoff = int((last + 11644473600) * 1_000_000)
        c = sqlite3.connect(tmp)
        for row in c.execute(
            "SELECT url,title,last_visit_time FROM urls WHERE last_visit_time>? ORDER BY last_visit_time LIMIT 500",
            (cutoff,)
        ).fetchall():
            results.append({"machine": config.MACHINE_NAME, "browser": browser,
                            "url": row[0], "title": row[1] or "",
                            "visited_utc": _chromium_ts(row[2])})
        c.close()
    except Exception as e:
        logger.error(f"Read {browser}: {e}")
    finally:
        try: os.remove(tmp)
        except: pass
    return results


def _read_firefox(db_path):
    results = []
    tmp = db_path + ".tmp"
    try:
        shutil.copy2(db_path, tmp)
    except Exception as e:
        logger.debug(f"Cannot copy Firefox DB: {e}")
        return results
    try:
        last   = _last_poll.get("firefox", time.time() - config.URL_POLL_INTERVAL * 2)
        cutoff = int(last * 1_000_000)
        c = sqlite3.connect(tmp)
        for row in c.execute("""
            SELECT p.url, p.title, v.visit_date
            FROM moz_historyvisits v JOIN moz_places p ON p.id=v.place_id
            WHERE v.visit_date>? ORDER BY v.visit_date LIMIT 500
        """, (cutoff,)).fetchall():
            visited = datetime.fromtimestamp(row[2] / 1_000_000, tz=timezone.utc).isoformat()
            results.append({"machine": config.MACHINE_NAME, "browser": "firefox",
                            "url": row[0], "title": row[1] or "",
                            "visited_utc": visited})
        c.close()
    except Exception as e:
        logger.error(f"Read Firefox: {e}")
    finally:
        try: os.remove(tmp)
        except: pass
    return results


def _poll():
    new = []
    for browser, path in BROWSER_PATHS.items():
        if path and os.path.isfile(path):
            new.extend(_read_chromium(path, browser))
        _last_poll[browser] = time.time()
    fp = _firefox_path()
    if fp:
        new.extend(_read_firefox(fp))
        _last_poll["firefox"] = time.time()
    if new:
        with _visits_lock:
            _visits.extend(new)
        logger.debug(f"URL tracker: {len(new)} new visits.")


def _loop():
    while True:
        try:
            time.sleep(config.URL_POLL_INTERVAL)
            _poll()
        except Exception as e:
            logger.error(f"URL tracker error: {e}")


def flush() -> list:
    with _visits_lock:
        v = list(_visits)
        _visits.clear()
    return v


def start():
    _poll()
    t = threading.Thread(target=_loop, daemon=True, name="URLTrackerThread")
    t.start()
    logger.info("URL tracker module started.")
