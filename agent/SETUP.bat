@echo off
:: ─────────────────────────────────────────────────────────────────
:: DeskGuard — Setup Launcher
:: Double-click this file to start the setup wizard.
:: It will ask for admin rights automatically.
:: ─────────────────────────────────────────────────────────────────

:: Auto-elevate to Administrator
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting administrator privileges...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

:: Change to script directory
cd /d "%~dp0"

:: Check Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo ============================================================
    echo  ERROR: Python is not installed or not in PATH.
    echo.
    echo  Please install Python 3.10+ from https://python.org
    echo  Make sure to check "Add Python to PATH" during install.
    echo ============================================================
    echo.
    pause
    exit /b 1
)

:: Launch the Python setup wizard
python setup_wizard.py
pause
