# DeskGuard

Stealth employee monitoring system for Windows endpoints with a central Python API server.

## Architecture

```
Windows Endpoints                    Ubuntu Server
┌─────────────────────┐             ┌──────────────────────────┐
│  Python Agent       │  HTTPS/JWT  │  FastAPI Server          │
│  (Windows Service)  │ ──────────► │  + SQLite Database       │
│                     │             │  + CLI Reporting Tool     │
│  Modules:           │             └──────────────────────────┘
│  ├─ screenshots     │
│  ├─ activity track  │
│  ├─ url tracker     │
│  ├─ app blocker     │
│  ├─ website blocker │
│  ├─ usb guard       │
│  └─ keylogger       │
└─────────────────────┘
```

## Project Structure

```
deskguard/
├── agent/                        # Deploy on each Windows machine
│   ├── agent.py                  # Main service entry point
│   ├── config.py                 # Agent configuration
│   ├── installer.py              # Silent install/uninstall as Windows Service
│   ├── modules/
│   │   ├── screenshot.py         # Periodic screenshot capture
│   │   ├── activity.py           # Foreground window & app tracking
│   │   ├── url_tracker.py        # Browser history extraction
│   │   ├── app_blocker.py        # Kill blacklisted processes
│   │   ├── website_blocker.py    # Block sites via hosts file
│   │   ├── usb_guard.py          # Detect & block USB storage
│   │   ├── keylogger.py          # Keystroke capture (scoped)
│   │   └── uploader.py           # Batch upload to server
│   └── requirements.txt
├── server/
│   ├── main.py                   # FastAPI application
│   ├── database.py               # SQLAlchemy models + SQLite
│   ├── schemas.py                # Pydantic request/response models
│   ├── auth.py                   # JWT authentication
│   ├── cli.py                    # CLI reporting tool (run on server)
│   ├── config.py                 # Server configuration
│   └── requirements.txt
└── deploy/
    ├── install_agent.bat         # Run as Admin on Windows endpoint
    └── setup_server.sh           # Server setup script
```

## Quick Start

### 1. Server Setup (Ubuntu)
```bash
cd server
pip install -r requirements.txt
python main.py
```

### 2. Agent Deployment (Windows - Run as Administrator)
```bat
cd agent
pip install -r requirements.txt
python installer.py install
```

### 3. CLI Reporting (on server)
```bash
python cli.py machines          # List all reporting machines
python cli.py activity --machine DESKTOP-ABC --date 2025-01-15
python cli.py screenshots --machine DESKTOP-ABC
python cli.py alerts            # Show unacknowledged alerts
python cli.py dlp               # DLP violation log
```

## Security Notes
- All agent-to-server communication uses HTTPS + JWT token
- API key is embedded in agent config (per-machine)
- Screenshots stored server-side only, never on endpoint disk after upload
- Keylog data encrypted before transmission
- Agent service disguised as "Windows Telemetry Host Service"
