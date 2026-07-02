# agent/modules/website_blocker.py
import os, sys, logging, re, subprocess
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config

logger = logging.getLogger("website_blocker")

HOSTS_PATH   = r"C:\Windows\System32\drivers\etc\hosts"
BLOCK_IP     = "0.0.0.0"
MARKER_START = "# ===DeskGuard-MONITOR-START==="
MARKER_END   = "# ===DeskGuard-MONITOR-END==="


def _read_hosts() -> str:
    try:
        with open(HOSTS_PATH, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.error(f"Cannot read hosts file: {e}")
        return ""


def _write_hosts(content: str) -> bool:
    try:
        with open(HOSTS_PATH, "w", encoding="utf-8") as f:
            f.write(content)
        return True
    except PermissionError:
        logger.error("Cannot write hosts file: run service as SYSTEM.")
        return False
    except Exception as e:
        logger.error(f"Cannot write hosts file: {e}")
        return False


def _flush_dns():
    try:
        subprocess.run(["ipconfig", "/flushdns"], capture_output=True)
        logger.debug("DNS cache flushed.")
    except Exception:
        pass


def apply_blocklist(domains: list = None) -> bool:
    if not config.WEBSITE_BLOCKER_ENABLED:
        logger.info("Website blocker disabled (WEBSITE_BLOCKER_ENABLED=False).")
        return True

    if domains is None:
        domains = config.WEBSITE_BLOCKLIST

    current = _read_hosts()
    pattern = re.compile(
        rf"{re.escape(MARKER_START)}.*?{re.escape(MARKER_END)}",
        re.DOTALL
    )
    clean = pattern.sub("", current).rstrip()

    lines = [MARKER_START]
    for d in domains:
        d = d.strip().lower()
        if d:
            lines.append(f"{BLOCK_IP}  {d}")
    lines.append(MARKER_END)

    new_content = clean + "\n\n" + "\n".join(lines) + "\n"
    ok = _write_hosts(new_content)
    if ok:
        logger.info(f"Hosts file updated: {len(domains)} domains blocked.")
        _flush_dns()
    return ok


def remove_blocklist() -> bool:
    """Always runs on uninstall regardless of WEBSITE_BLOCKER_ENABLED."""
    current = _read_hosts()
    pattern = re.compile(
        rf"\n*{re.escape(MARKER_START)}.*?{re.escape(MARKER_END)}\n*",
        re.DOTALL
    )
    cleaned = pattern.sub("\n", current)
    ok = _write_hosts(cleaned)
    if ok:
        logger.info("Hosts file: DeskGuard entries removed.")
        _flush_dns()
    return ok


def update_from_server(new_domains: list) -> bool:
    return apply_blocklist(new_domains)


def start():
    if not config.WEBSITE_BLOCKER_ENABLED:
        logger.info("Website blocker skipped — hosts file will not be modified.")
        return
    ok = apply_blocklist()
    if not ok:
        logger.warning("Website blocker: hosts file could not be written.")
