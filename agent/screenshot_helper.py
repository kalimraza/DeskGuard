# agent/screenshot_helper.py
# Runs in USER session (not SYSTEM) so it can capture the real desktop.
# Auto-started via registry Run key and Task Scheduler at every login.

import os, sys, time, ctypes, logging
from datetime import datetime, timezone

# Hide console window immediately
try:
    hwnd = ctypes.windll.kernel32.GetConsoleWindow()
    if hwnd:
        ctypes.windll.user32.ShowWindow(hwnd, 0)
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

os.makedirs(config.SCREENSHOT_DIR, exist_ok=True)
os.makedirs(config.DATA_DIR, exist_ok=True)

logging.basicConfig(
    filename=os.path.join(config.DATA_DIR, "ss_helper.log"),
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s: %(message)s"
)
log = logging.getLogger("ss_helper")


def capture_gdi():
    """Capture desktop using Windows GDI BitBlt — most reliable method."""
    import win32gui, win32ui, win32con, win32api
    from PIL import Image

    hwnd   = win32gui.GetDesktopWindow()
    width  = win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN)
    height = win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN)
    left   = win32api.GetSystemMetrics(win32con.SM_XVIRTUALSCREEN)
    top    = win32api.GetSystemMetrics(win32con.SM_YVIRTUALSCREEN)

    hwnd_dc = win32gui.GetWindowDC(hwnd)
    mfc_dc  = win32ui.CreateDCFromHandle(hwnd_dc)
    save_dc = mfc_dc.CreateCompatibleDC()
    bitmap  = win32ui.CreateBitmap()
    bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
    save_dc.SelectObject(bitmap)
    save_dc.BitBlt((0,0),(width,height), mfc_dc, (left,top),
                   win32con.SRCCOPY | 0x40000000)  # CAPTUREBLT

    info = bitmap.GetInfo()
    bits = bitmap.GetBitmapBits(True)
    img  = Image.frombuffer("RGB", (info["bmWidth"], info["bmHeight"]),
                            bits, "raw", "BGRX", 0, 1)

    win32gui.DeleteObject(bitmap.GetHandle())
    save_dc.DeleteDC()
    mfc_dc.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwnd_dc)
    return img


def capture_mss():
    """Fallback using mss library."""
    import mss
    from PIL import Image
    with mss.mss() as sct:
        monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
        raw = sct.grab(monitor)
        return Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")


def capture():
    try:
        ts  = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        out = os.path.join(config.SCREENSHOT_DIR,
                           f"{config.MACHINE_NAME}_{ts}_scheduled.jpg")
        try:
            img    = capture_gdi()
            method = "GDI"
        except Exception as e1:
            log.warning(f"GDI failed ({e1}), trying mss...")
            try:
                img    = capture_mss()
                method = "mss"
            except Exception as e2:
                log.error(f"Both methods failed. GDI:{e1} mss:{e2}")
                return

        # Check for blank image
        extrema = img.convert("L").getextrema()
        if extrema[0] == extrema[1]:
            log.warning(f"Image appears blank (all pixels={extrema[0]}). Saving anyway.")

        w = int(img.width * 0.75)
        h = int(img.height * 0.75)
        img.resize((w, h), img.LANCZOS).save(
            out, "JPEG", quality=config.SCREENSHOT_QUALITY, optimize=True)
        log.info(f"[{method}] {os.path.basename(out)} ({w}x{h})")

    except Exception as e:
        log.error(f"Capture error: {e}", exc_info=True)


log.info(f"Screenshot helper started. Interval:{config.SCREENSHOT_INTERVAL}s")
log.info(f"Saving to: {config.SCREENSHOT_DIR}")
capture()

while True:
    time.sleep(config.SCREENSHOT_INTERVAL)
    capture()
