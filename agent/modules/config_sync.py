# agent/modules/config_sync.py  — polls server for config updates
import os, sys, time, threading, logging
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config

logger = logging.getLogger("config_sync")
_current_version = 0

_session = requests.Session()
_session.headers.update({
    "Authorization": f"Bearer {config.API_KEY}",
    "X-Machine":     config.MACHINE_NAME,
})

_SCALARS = {
    "SCREENSHOT_INTERVAL": "SCREENSHOT_INTERVAL",
    "SCREENSHOT_QUALITY":  "SCREENSHOT_QUALITY",
    "SCREENSHOT_ON_SWITCH":"SCREENSHOT_ON_SWITCH",
    "UPLOAD_EVERY":        "UPLOAD_EVERY",
    "CONFIG_SYNC_EVERY":   "CONFIG_SYNC_EVERY",
    "USB_BLOCK_MODE":      "USB_BLOCK_MODE",
    "KEYLOG_ENABLED":      "KEYLOG_ENABLED",
    "KEYLOG_FLUSH_EVERY":  "KEYLOG_FLUSH_EVERY",
    "LOCAL_FLUSH_EVERY":   "LOCAL_FLUSH_EVERY",
    "IDLE_THRESHOLD_SECONDS":"IDLE_THRESHOLD_SECONDS",
    "ACTIVITY_POLL_INTERVAL":"ACTIVITY_POLL_INTERVAL",
    "WEBSITE_BLOCKER_ENABLED":"WEBSITE_BLOCKER_ENABLED",
}
_LISTS = {
    "APP_BLACKLIST":        "APP_BLACKLIST",
    "WEBSITE_BLOCKLIST":    "WEBSITE_BLOCKLIST",
    "USB_WHITELIST_SERIALS":"USB_WHITELIST_SERIALS",
    "KEYLOG_APPS":          "KEYLOG_APPS",
}


def _apply(new_cfg: dict):
    global _current_version
    server_version = new_cfg.get("version", 0)
    if server_version <= _current_version:
        return

    logger.info(f"Applying config v{_current_version}→{server_version}")

    for key, attr in _SCALARS.items():
        if key in new_cfg:
            old = getattr(config, attr, None)
            if old != new_cfg[key]:
                setattr(config, attr, new_cfg[key])
                logger.info(f"  {attr}: {old} → {new_cfg[key]}")

    for key, attr in _LISTS.items():
        if key in new_cfg:
            setattr(config, attr, new_cfg[key])
            logger.info(f"  {attr}: {len(new_cfg[key])} entries")

    if "WEBSITE_BLOCKLIST" in new_cfg:
        try:
            from modules import website_blocker
            website_blocker.apply_blocklist(new_cfg["WEBSITE_BLOCKLIST"])
        except Exception as e:
            logger.error(f"Blocklist apply failed: {e}")

    if "APP_BLACKLIST" in new_cfg:
        try:
            from modules import app_blocker, firewall_block
            app_blocker._BLACKLIST = {n.lower() for n in new_cfg["APP_BLACKLIST"]}
            firewall_block.apply_firewall_blocks(new_cfg["APP_BLACKLIST"])
        except Exception as e:
            logger.error(f"Blacklist apply failed: {e}")

    _current_version = server_version


def _sync():
    try:
        resp = _session.get(f"{config.SERVER_URL}/api/config",
                            params={"version": _current_version}, timeout=15)
        if resp.status_code == 204:
            logger.debug("Config unchanged.")
        elif resp.status_code == 200:
            _apply(resp.json())
        else:
            logger.warning(f"Config sync: HTTP {resp.status_code}")
    except requests.exceptions.ConnectionError:
        logger.warning("Config sync: server unreachable.")
    except Exception as e:
        logger.error(f"Config sync error: {e}")


def _loop():
    time.sleep(30)
    while True:
        _sync()
        time.sleep(config.CONFIG_SYNC_EVERY)


def start():
    t = threading.Thread(target=_loop, daemon=True, name="ConfigSyncThread")
    t.start()
    logger.info(f"Config sync started (every {config.CONFIG_SYNC_EVERY}s).")
