@echo off
title DeskGuard — Status Check
echo.
echo ============================================
echo  DeskGuard — Status Check
echo ============================================
echo.

echo [1] Service status:
sc query WinTelemetryHost
echo.

echo [2] Screenshot helper running:
tasklist | findstr pythonw
echo.

echo [3] Last 30 lines of log:
set LOGFILE=%PROGRAMDATA%\WinTelemetryHost\svc.log
if exist "%LOGFILE%" (
    powershell -Command "Get-Content '%LOGFILE%' -Tail 30"
) else (
    echo Log not found: %LOGFILE%
)
echo.

echo [4] DB file:
set DBFILE=%PROGRAMDATA%\WinTelemetryHost\sys_perf.db
if exist "%DBFILE%" (
    powershell -Command "(Get-Item '%DBFILE%').Length / 1MB | ForEach-Object { 'Size: ' + [math]::Round($_, 2) + ' MB' }"
) else (
    echo DB not found yet.
)
echo.

echo [5] Active firewall rules:
netsh advfirewall firewall show rule name=all dir=out | findstr DeskGuard
echo.

pause
