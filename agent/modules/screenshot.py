# agent/modules/screenshot.py
# ─────────────────────────────────────────────────────────────────────────────
# Captures screenshots periodically and on window-switch events.
# Saves compressed JPEG to local buffer; uploader picks them up.
# ─────────────────────────────────────────────────────────────────────────────

import io
import os
import time
import threading
import logging
from datetime import datetime

import mss
import mss.tools
from PIL import Image

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config

logger = logging.getLogger("screenshot")

_last_active_window = None   # Used by activity module to trigger on-switch captures


def capture_screenshot(reason: str = "scheduled") -> str | None:
    """
    Capture all monitors, stitch into one image, save as JPEG.
    Returns the saved file path, or None on failure.
    """
    try:
        os.makedirs(config.SCREENSHOT_DIR, exist_ok=True)

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename  = f"{config.MACHINE_NAME}_{timestamp}_{reason}.jpg"
        filepath  = os.path.join(config.SCREENSHOT_DIR, filename)

        with mss.mss() as sct:
            # Capture all monitors combined
            monitor = sct.monitors[0]   # index 0 = all monitors combined
            raw     = sct.grab(monitor)
            img     = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")

        # Downscale slightly to save bandwidth (75% of original)
        new_w = int(img.width  * 0.75)
        new_h = int(img.height * 0.75)
        img   = img.resize((new_w, new_h), Image.LANCZOS)

        img.save(filepath, "JPEG", quality=config.SCREENSHOT_QUALITY, optimize=True)
        logger.debug(f"Screenshot saved: {filepath}")
        return filepath

    except Exception as e:
        logger.error(f"Screenshot failed: {e}")
        return None


def _screenshot_loop():
    """Periodic screenshot loop — runs in its own thread."""
    while True:
        try:
            time.sleep(config.SCREENSHOT_INTERVAL)
            capture_screenshot("scheduled")
        except Exception as e:
            logger.error(f"Screenshot loop error: {e}")


def trigger_on_window_switch(new_window: str):
    """
    Called by the activity module when the foreground window changes.
    Captures a screenshot immediately if SCREENSHOT_ON_SWITCH is enabled.
    """
    global _last_active_window
    if config.SCREENSHOT_ON_SWITCH and new_window != _last_active_window:
        _last_active_window = new_window
        capture_screenshot("switch")


def start():
    """Start the screenshot capture thread."""
    # Capture one immediately at startup
    capture_screenshot("startup")

    t = threading.Thread(target=_screenshot_loop, daemon=True, name="ScreenshotThread")
    t.start()
    logger.info("Screenshot module started.")
