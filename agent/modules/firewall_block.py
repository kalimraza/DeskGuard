# agent/modules/firewall_block.py
# ─────────────────────────────────────────────────────────────────────────────
# Adds Windows Firewall OUTBOUND BLOCK rules for every app in the blacklist.
# Rules survive reboots. Runs at agent startup.
# Requires service to run as SYSTEM (which it does).
# ─────────────────────────────────────────────────────────────────────────────

import os, sys, subprocess, logging
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config

logger = logging.getLogger("firewall_block")
RULE_PREFIX = "DSKG_BLOCK_"


def _run(cmd: list) -> tuple:
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def _existing_rules() -> set:
    rc, out = _run(["netsh", "advfirewall", "firewall", "show", "rule",
                    "name=all", "dir=out"])
    rules = set()
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("Rule Name:") and RULE_PREFIX in line:
            name = line.split("Rule Name:", 1)[1].strip()
            rules.add(name)
    return rules


def _add_rule_by_path(rule_name: str, path: str) -> bool:
    rc, _ = _run([
        "netsh", "advfirewall", "firewall", "add", "rule",
        f"name={rule_name}",
        "dir=out", "action=block", "enable=yes",
        f"program={path}",
        "profile=any",
        "description=Blocked by DeskGuard",
    ])
    return rc == 0


def _add_rule_by_ip(rule_name: str, ip_range: str) -> bool:
    rc, _ = _run([
        "netsh", "advfirewall", "firewall", "add", "rule",
        f"name={rule_name}",
        "dir=out", "action=block", "enable=yes",
        "protocol=any",
        f"remoteip={ip_range}",
        "profile=any",
        "description=Blocked by DeskGuard",
    ])
    return rc == 0


def apply_firewall_blocks(app_list: list = None):
    apps = app_list or config.APP_BLACKLIST
    existing = _existing_rules()
    added = 0

    search_dirs = [
        os.environ.get("PROGRAMFILES",       r"C:\Program Files"),
        os.environ.get("PROGRAMFILES(X86)",  r"C:\Program Files (x86)"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "WhatsApp"),
        os.path.join(os.environ.get("APPDATA",      ""), "WhatsApp"),
        os.path.join(os.environ.get("APPDATA",      ""), "Telegram Desktop"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Discord"),
    ]

    for app in apps:
        rule_name = f"{RULE_PREFIX}{app.replace('.exe','').upper()}"
        if rule_name in existing:
            continue

        blocked = False
        for d in search_dirs:
            if not os.path.isdir(d):
                continue
            for root, dirs, files in os.walk(d):
                for f in files:
                    if f.lower() == app.lower():
                        full_path = os.path.join(root, f)
                        if _add_rule_by_path(rule_name, full_path):
                            logger.info(f"Firewall blocked: {full_path}")
                            blocked = True
                            added += 1
                            break
                if blocked:
                    break

    if added > 0:
        logger.info(f"Added {added} new firewall block rules.")
    else:
        logger.info("Firewall rules already up to date.")


def block_whatsapp_specifically():
    """Block WhatsApp by exe path AND by Meta IP ranges."""
    appdata_local = os.environ.get("LOCALAPPDATA", "")
    candidate_dirs = [
        os.path.join(appdata_local, "WhatsApp"),
        os.path.join(appdata_local, "Programs", "WhatsApp"),
        r"C:\Program Files\WhatsApp",
        r"C:\Program Files (x86)\WhatsApp",
    ]

    for d in candidate_dirs:
        if not os.path.isdir(d):
            continue
        for root, dirs, files in os.walk(d):
            for f in files:
                if f.lower().endswith(".exe"):
                    full_path = os.path.join(root, f)
                    rule_name = f"{RULE_PREFIX}WA_{abs(hash(full_path)) % 100000}"
                    _add_rule_by_path(rule_name, full_path)
                    logger.info(f"WhatsApp blocked: {full_path}")

    # Block Meta/WhatsApp IP ranges
    wa_ranges = [
        "31.13.24.0/21",  "31.13.64.0/18",   "66.220.144.0/20",
        "69.63.176.0/20", "69.171.224.0/19",  "74.119.76.0/22",
        "129.134.0.0/16", "157.240.0.0/16",   "163.70.128.0/17",
        "179.60.192.0/22","185.60.216.0/22",  "204.15.20.0/22",
    ]
    for ip in wa_ranges:
        rule_name = f"{RULE_PREFIX}WA_IP_{ip.replace('/','_').replace('.','_')}"
        if _add_rule_by_ip(rule_name, ip):
            logger.debug(f"WhatsApp IP blocked: {ip}")

    logger.info(f"WhatsApp IP ranges blocked ({len(wa_ranges)} ranges).")


def remove_all_firewall_blocks():
    """Remove all DeskGuard firewall rules. Called on uninstall."""
    existing = _existing_rules()
    if not existing:
        logger.info("No DeskGuard firewall rules found.")
        return

    removed = 0
    for rule in existing:
        rc, _ = _run(["netsh", "advfirewall", "firewall", "delete",
                      "rule", f"name={rule}"])
        if rc == 0:
            removed += 1

    logger.info(f"Removed {removed}/{len(existing)} firewall rules.")
    print(f"  Firewall: removed {removed} block rules.")


def start():
    apply_firewall_blocks()
    block_whatsapp_specifically()
    logger.info("Firewall block module started.")
