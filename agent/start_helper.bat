@echo off
echo Starting screenshot helper...
start "" /B pythonw screenshot_helper.py
timeout /t 2 /nobreak >nul
echo Done. Check ss_helper.log for status.
