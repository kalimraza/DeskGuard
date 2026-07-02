@echo off
title DeskGuard — Install
echo.
echo ============================================
echo  DeskGuard — Install
echo  Right-click this file, Run as administrator
echo ============================================
echo.

net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Please right-click and choose "Run as administrator"
    pause & exit /b 1
)

echo [1/3] Installing Python dependencies...
pip install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo ERROR: pip install failed. Is Python installed?
    pause & exit /b 1
)
echo Done.

echo [2/3] Installing Windows service...
python installer.py install
if %errorlevel% neq 0 (
    echo ERROR: Service install failed.
    pause & exit /b 1
)

echo [3/3] Verifying...
timeout /t 3 /nobreak >nul
sc query WinTelemetryHost | find "RUNNING" >nul
if %errorlevel% equ 0 (
    echo.
    echo ============================================
    echo  SUCCESS - Service is running
    echo  Logs: %PROGRAMDATA%\WinTelemetryHost\svc.log
    echo  Run check.bat anytime to see status
    echo ============================================
) else (
    echo.
    echo WARNING: Service installed but may not be running.
    echo Run check.bat to diagnose.
)
echo.
pause
