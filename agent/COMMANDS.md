# DeskGuard — Complete Command Reference

All commands must be run from:
  C:\Users\kalim\Downloads\deskguard\agent\

Open CMD as Administrator for service commands.
Viewer/data commands can be run as normal user.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 SERVICE CONTROL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Install service (run once):
  python installer.py install

Start service:
  sc start WinTelemetryHost

Stop service:
  sc stop WinTelemetryHost

Restart service:
  sc stop WinTelemetryHost && sc start WinTelemetryHost

Check service status:
  sc query WinTelemetryHost

Uninstall completely:
  python installer.py remove

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 SCREENSHOT HELPER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

The screenshot helper starts AUTOMATICALLY on every Windows login.
No manual steps needed after install.

It runs as the logged-in user (not SYSTEM) so it can capture
the real desktop — this is why it's separate from the main service.

Only needed for troubleshooting:

  Check helper is running:
    tasklist | findstr pythonw

  Check helper log:
    type %PROGRAMDATA%\WinTelemetryHost\ss_helper.log

  Manually restart helper (if it crashed):
    start_helper.bat

  Check Task Scheduler entry:
    schtasks /query /tn WinPerfMonHelper

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 LOGS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

View logs (menu):
  viewlogs.bat

View all logs at once:
  type %PROGRAMDATA%\WinTelemetryHost\svc.log

Live log tail (auto-updates):
  powershell -Command "Get-Content '%PROGRAMDATA%\WinTelemetryHost\svc.log' -Wait -Tail 30"

View errors and warnings only:
  powershell -Command "Get-Content '%PROGRAMDATA%\WinTelemetryHost\svc.log' | Where-Object { $_ -match '\[ERROR\]|\[WARNING\]' }"

Clear log file:
  echo. > %PROGRAMDATA%\WinTelemetryHost\svc.log

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 VIEWING DATA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

List all dates that have data:
  python viewer.py dates

Today's summary:
  python viewer.py summary

Summary for a specific date:
  python viewer.py summary --date 2026-07-01

Activity log (what apps were open):
  python viewer.py activity --date 2026-07-01
  python viewer.py activity --date 2026-07-01 --limit 200

App usage time (ranked):
  python viewer.py apps --date 2026-07-01

URLs visited:
  python viewer.py urls --date 2026-07-01
  python viewer.py urls --date 2026-07-01 --limit 500

App violations (blacklisted apps that were killed):
  python viewer.py violations

USB events:
  python viewer.py usb

Alerts (unacknowledged):
  python viewer.py alerts

All alerts including acknowledged:
  python viewer.py alerts --all

Acknowledge an alert:
  python viewer.py ack --id 5

Keylog sessions (encrypted):
  python viewer.py keylog --date 2026-07-01

Keylog sessions (decrypted):
  set MONITOR_FERNET_KEY=your-key-here
  python viewer.py keylog --date 2026-07-01 --decrypt

Database info (file size, record counts):
  python viewer.py dbinfo

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 SCREENSHOTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Export screenshots for a date:
  python viewer.py screens --date 2026-07-01 --out-dir C:\IT\shots

Export to desktop:
  python viewer.py screens --date 2026-07-01 --out-dir %USERPROFILE%\Desktop\shots

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 EXPORT & REPORTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Export full text report for a date:
  python viewer.py export --date 2026-07-01 --out C:\IT\report_kalim.txt

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 DATABASE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DB file location:
  %PROGRAMDATA%\WinTelemetryHost\sys_perf.db

Clear all data (wipe DB):
  sc stop WinTelemetryHost
  python cleardata.py
  sc start WinTelemetryHost

Shrink DB file after clearing:
  python -c "import sqlite3,os; c=sqlite3.connect(os.path.join(os.environ['PROGRAMDATA'],'WinTelemetryHost','sys_perf.db'),isolation_level=None); c.execute('VACUUM'); c.close(); print('Done.')"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 CONFIGURATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Config file location:
  agent\config.py

After any config change, restart the service:
  sc stop WinTelemetryHost && sc start WinTelemetryHost

Key settings in config.py:
  MODE                  = "local"   (local DB) or "server" (upload to server)
  SCREENSHOT_INTERVAL   = 180       (seconds between screenshots)
  SCREENSHOT_QUALITY    = 60        (JPEG quality 1-95)
  UPLOAD_EVERY          = 300       (flush to DB every N seconds)
  USB_BLOCK_MODE        = "alert"   (alert only) or "block" (eject drive)
  KEYLOG_ENABLED        = True      (enable/disable keylogger)
  APP_BLACKLIST         = [...]     (add/remove app names to block)
  WEBSITE_BLOCKLIST     = [...]     (add/remove domains to block)

Add a website to blocklist (edit config.py then):
  sc stop WinTelemetryHost && sc start WinTelemetryHost

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 STATUS CHECK (run anytime)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Full status check:
  check.bat

Quick one-line status:
  sc query WinTelemetryHost | findstr STATE

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 DEBUG / TEST (foreground mode, no service)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Run agent in foreground to see all output live:
  sc stop WinTelemetryHost
  python agent.py debug

Stop debug mode:
  Ctrl+C

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 FILE LOCATIONS SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Service log:        %PROGRAMDATA%\WinTelemetryHost\svc.log
  Screenshot log:     %PROGRAMDATA%\WinTelemetryHost\ss_helper.log
  Database:           %PROGRAMDATA%\WinTelemetryHost\sys_perf.db
  Screenshot buffer:  %PROGRAMDATA%\WinTelemetryHost\cache\img\
  Failed uploads:     %PROGRAMDATA%\WinTelemetryHost\retry\

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 DAILY ROUTINE (IT Admin)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Morning check:
  python viewer.py alerts
  python viewer.py summary --date 2026-07-01

Review a specific employee's day:
  python viewer.py summary    --date 2026-07-01
  python viewer.py activity   --date 2026-07-01
  python viewer.py urls       --date 2026-07-01
  python viewer.py screens    --date 2026-07-01 --out-dir C:\IT\shots
  python viewer.py export     --date 2026-07-01 --out C:\IT\report.txt
