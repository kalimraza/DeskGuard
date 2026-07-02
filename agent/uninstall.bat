@echo off
title DeskGuard — Uninstall
echo.
echo Stopping and removing service...
python installer.py remove
echo.
echo Done. Log and DB files remain at: %PROGRAMDATA%\WinTelemetryHost\
echo Delete that folder manually for full cleanup.
echo.
pause
