# agent/modules/usb_guard.py
import os, sys, time, threading, logging, subprocess
from datetime import datetime, timezone
import wmi
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config

logger = logging.getLogger("usb_guard")
_events: list = []
_events_lock  = threading.Lock()
_known_drives: set = set()


def _get_removable_drives() -> dict:
    drives = {}
    try:
        c = wmi.WMI()
        for disk in c.Win32_LogicalDisk(DriveType=2):
            drives[disk.DeviceID] = disk.VolumeSerialNumber or ""
    except Exception as e:
        logger.debug(f"WMI error: {e}")
    return drives


def _get_device_serial(drive_letter: str) -> str:
    try:
        c = wmi.WMI()
        for p in c.Win32_LogicalDiskToPartition():
            if p.Dependent.DeviceID == drive_letter:
                idx = p.Antecedent.DiskIndex
                for d in c.Win32_DiskDrive(Index=idx):
                    return (d.SerialNumber or "").strip()
    except Exception:
        pass
    return ""


def _eject(drive_letter: str):
    try:
        script = (f'$s=New-Object -ComObject Shell.Application;'
                  f'$d=$s.Namespace("{drive_letter}\\");$d.Self.InvokeVerb("Eject")')
        subprocess.run(["powershell", "-NoProfile", "-WindowStyle", "Hidden",
                        "-Command", script], capture_output=True, timeout=10)
        logger.info(f"Drive {drive_letter} ejected.")
    except Exception as e:
        logger.error(f"Eject {drive_letter}: {e}")


def _loop():
    global _known_drives
    _known_drives = set(_get_removable_drives().keys())
    while True:
        try:
            time.sleep(config.USB_POLL_INTERVAL)
            current = _get_removable_drives()
            new_drives = set(current.keys()) - _known_drives
            for letter in new_drives:
                vol_serial = current[letter]
                dev_serial = _get_device_serial(letter)
                check      = dev_serial or vol_serial
                whitelisted = check in config.USB_WHITELIST_SERIALS
                logger.warning(f"USB: {letter} serial={check} whitelisted={whitelisted}")
                event = {
                    "machine":       config.MACHINE_NAME,
                    "drive_letter":  letter,
                    "volume_serial": vol_serial,
                    "device_serial": dev_serial,
                    "whitelisted":   whitelisted,
                    "action":        "none",
                    "detected_utc":  datetime.now(timezone.utc).isoformat(),
                    "severity":      "low" if whitelisted else "critical",
                }
                if not whitelisted and config.USB_BLOCK_MODE == "block":
                    _eject(letter)
                    event["action"] = "ejected"
                with _events_lock:
                    _events.append(event)
            _known_drives = set(current.keys())
        except Exception as e:
            logger.error(f"USB guard error: {e}")


def flush() -> list:
    with _events_lock:
        e = list(_events)
        _events.clear()
    return e


def start():
    if not config.USB_GUARD_ENABLED:
        logger.info("USB guard disabled.")
        return
    t = threading.Thread(target=_loop, daemon=True, name="USBGuardThread")
    t.start()
    logger.info(f"USB guard started (mode: {config.USB_BLOCK_MODE}).")
