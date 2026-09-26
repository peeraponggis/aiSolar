@echo off
title YT Shorts Automation
echo.
echo   ==========================================
echo      YT Shorts Automation
echo      Starting AI video pipeline...
echo   ==========================================
echo.

set "ROOT=%~dp0"

REM --- Start Ollama if not already running ---
tasklist /fi "imagename eq ollama.exe" 2>nul | find /i "ollama.exe" >nul
if errorlevel 1 (
    echo [*] Starting Ollama server...
    set "OLLAMA_MODELS=F:\LocalAI\models"
    set "OLLAMA_HOST=127.0.0.1:11434"
    set "OLLAMA_FLASH_ATTENTION=1"
    set "OLLAMA_KV_CACHE_TYPE=q8_0"
    set "OLLAMA_ORIGINS=*"
    start "Ollama Server" /min "F:\LocalAI\ollama\ollama.exe" serve
    timeout /t 5 /nobreak >nul
) else (
    echo [*] Ollama already running
)

REM --- Start FastAPI server ---
echo [*] Starting YT Shorts server on port 5000...
cd /d "%ROOT%"
start "YT Shorts Server" /min python -m uvicorn app.app:app --host 127.0.0.1 --port 5000 --reload

echo [*] Waiting for server to start...
timeout /t 4 /nobreak >nul

REM --- Open browser ---
echo [*] Opening dashboard...
start "" "http://127.0.0.1:5000"

echo.
echo   ==========================================
echo      Ready! Dashboard opened in browser.
echo      http://127.0.0.1:5000
echo.
echo      Keep this window open while using.
echo   ==========================================
echo.
cmd /k
