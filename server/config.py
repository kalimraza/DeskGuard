# server/config.py
import os

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./deskguard.db")
HOST         = os.environ.get("HOST", "0.0.0.0")
PORT         = int(os.environ.get("PORT", 8000))
DEBUG        = os.environ.get("DEBUG", "false").lower() == "true"

# Screenshot storage: "db" stores in SQLite (easy), "disk" saves to SCREENSHOTS_DIR
SCREENSHOT_STORAGE = os.environ.get("SCREENSHOT_STORAGE", "disk")
SCREENSHOTS_DIR    = os.environ.get("SCREENSHOTS_DIR", "./screenshots")

# Auto-generate alert for these severities
ALERT_ON_SEVERITIES = {"critical", "high"}
