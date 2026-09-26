@echo off
chcp 65001 >nul
title YK Yeekee Predictor + RAG

echo ============================================================
echo   YK Yeekee Predictor + RAG - Auto Start
echo ============================================================
echo.

set "SCRIPT_DIR=%~dp0"
set "DATA_DIR=%SCRIPT_DIR%.."
set "RAG_DIR=F:\LocalAI"

:: --- Live server (5001) ---
netstat -ano 2>nul | findstr ":5001 " | findstr "LISTENING" >nul 2>nul
if %errorlevel%==0 goto live_ok
echo [..] Starting yk_live_server.py ...
start "YK Live Server" cmd /k "cd /d %SCRIPT_DIR% && python yk_live_server.py"
timeout /t 3 /nobreak >nul
:live_ok
echo [OK] Live server  : port 5001

:: --- Web server (8765) ---
netstat -ano 2>nul | findstr ":8765 " | findstr "LISTENING" >nul 2>nul
if %errorlevel%==0 goto web_ok
echo [..] Starting web server 8765 ...
start "YK Web Server" cmd /k "cd /d %DATA_DIR% && python -m http.server 8765"
timeout /t 2 /nobreak >nul
:web_ok
echo [OK] Web server   : port 8765

:: --- RAG server (5002) ---
netstat -ano 2>nul | findstr ":5002 " | findstr "LISTENING" >nul 2>nul
if %errorlevel%==0 goto rag_ok
if not exist "%RAG_DIR%\rag_server.py" goto rag_skip
echo [..] Starting RAG Server ...
start "RAG Server" cmd /k "cd /d %RAG_DIR% && python -u rag_server.py"
timeout /t 2 /nobreak >nul
goto rag_ok
:rag_skip
echo [--] Skip RAG Server - not found: %RAG_DIR%\rag_server.py
:rag_ok
echo [OK] RAG server   : port 5002

echo.
echo   Opening browser...
timeout /t 1 /nobreak >nul
start "" "http://localhost:8765/yeekee_predictor_artifact.html"

echo.
echo [OK] All systems running!
echo   Live Server : http://localhost:5001/
echo   Web App     : http://localhost:8765/yeekee_predictor_artifact.html
echo   RAG Server  : http://localhost:5002/  chat.html + knowledge
echo.
echo Press any key to exit this window. Servers keep running.
pause >nul
