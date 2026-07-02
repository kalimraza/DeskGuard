@echo off
title DeskGuard — Log Viewer
set LOGFILE=%PROGRAMDATA%\WinTelemetryHost\svc.log

if not exist "%LOGFILE%" (
    echo Log not found: %LOGFILE%
    pause & exit /b
)

echo.
echo ============================================
echo  DeskGuard — Log Viewer
echo ============================================
echo.
echo  [1] Show ALL logs
echo  [2] Show last 50 lines
echo  [3] Show last 100 lines
echo  [4] Live tail (Ctrl+C to stop)
echo  [5] Errors and Warnings only
echo  [6] Today's logs only
echo  [7] Search by keyword
echo  [8] Open in Notepad
echo.
set /p choice=Choose [1-8]: 

if "%choice%"=="1" ( type "%LOGFILE%" )
if "%choice%"=="2" ( powershell -Command "Get-Content '%LOGFILE%' -Tail 50" )
if "%choice%"=="3" ( powershell -Command "Get-Content '%LOGFILE%' -Tail 100" )
if "%choice%"=="4" ( powershell -Command "Get-Content '%LOGFILE%' -Wait -Tail 20" )
if "%choice%"=="5" ( powershell -Command "Get-Content '%LOGFILE%' | Where-Object { $_ -match '\[ERROR\]|\[WARNING\]' }" )
if "%choice%"=="6" ( powershell -Command "$t=Get-Date -Format 'yyyy-MM-dd'; Get-Content '%LOGFILE%' | Where-Object { $_ -match $t }" )
if "%choice%"=="7" ( set /p kw=Keyword: && powershell -Command "Get-Content '%LOGFILE%' | Where-Object { $_ -match '%kw%' }" )
if "%choice%"=="8" ( notepad "%LOGFILE%" & exit /b )

echo.
pause
