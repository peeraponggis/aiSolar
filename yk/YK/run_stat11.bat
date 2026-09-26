@echo off
cd /d "%~dp0"

REM Check LIVE server; start it if not running, then wait 20s
netstat -ano 2>nul | findstr ":5001 " | findstr "LISTENING" >nul 2>nul
if not %errorlevel%==0 (
    echo [%date% %time%] LIVE server not running - starting...>> stat11_cron.log
    start "YK Live Server" cmd /k "cd /d "%~dp0" ^&^& python yk_live_server.py"
    timeout /t 20 /nobreak >nul
)

echo ============================================>> stat11_cron.log
echo [%date% %time%] running yk_stat_signals.py>> stat11_cron.log
chcp 65001 >nul
python yk_stat_signals.py >> stat11_cron.log 2>&1
echo.>> stat11_cron.log
