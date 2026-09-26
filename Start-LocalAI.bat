@echo off
setlocal
title LocalAI Ollama Portable

set "ROOT=%~dp0"
set "OLLAMA_MODELS=%ROOT%models"
set "OLLAMA_HOME=%ROOT%ollama-data"
set "HOME=%ROOT%ollama-data"
set "OLLAMA_HOST=127.0.0.1:11434"
set "OLLAMA_FLASH_ATTENTION=1"
set "OLLAMA_KV_CACHE_TYPE=q8_0"
set "OLLAMA_ORIGINS=*"
set OLLAMA_ORIGINS=*
set "OLLAMA_KEEP_ALIVE=5m"
set "OLLAMA_EXE=%ROOT%ollama\ollama.exe"

echo ============================================================
echo   LocalAI - Portable Ollama
echo   ROOT   : %ROOT%
echo   MODELS : %OLLAMA_MODELS%
echo ============================================================
echo.

if not exist "%OLLAMA_MODELS%" mkdir "%OLLAMA_MODELS%"
if not exist "%ROOT%ollama-data" mkdir "%ROOT%ollama-data"

if not exist "%OLLAMA_EXE%" goto noollama

echo [*] Starting Ollama server...
start "Ollama Server" /min "%OLLAMA_EXE%" serve

echo [*] Starting Neural TTS server (Premwadee/Niwat, needs Python + internet)...
start "LocalAI TTS" /min python "%ROOT%tts-server.py"

echo [*] Waiting for servers...
timeout /t 6 /nobreak >nul

REM ---------- ASC ENTERPRISES Copilot: เตรียม typhoon2.5-qwen3-4b ----------
REM เพิ่มโดย ASC ENTERPRISES - ตรวจว่ามีโมเดลที่ Copilot ใช้ไหม ถ้าไม่มีให้โหลดให้เลย
set "ASC_MODEL=scb10x/typhoon2.5-qwen3-4b:latest"
"%OLLAMA_EXE%" list | findstr /i /l "typhoon2.5-qwen3-4b" >nul
if not errorlevel 1 goto asc_model_ok
echo [*] ASC Copilot: ยังไม่มี typhoon2.5-qwen3-4b - กำลังดาวน์โหลด ~2.5 GB ...
"%OLLAMA_EXE%" pull %ASC_MODEL%
goto asc_model_done
:asc_model_ok
echo [*] ASC Copilot: พบ typhoon2.5-qwen3-4b แล้ว
:asc_model_done

echo [*] Opening chat page...
REM Open via http://localhost so microphone/voice works in Chrome (file:// blocks mic)
where python >nul 2>nul
if errorlevel 1 goto openfile
start "" "http://127.0.0.1:11435/"
goto opened
:openfile
start "" "%ROOT%ui\chat.html"
:opened

echo.
echo ============================================================
echo   Ready. The chat page opened in your browser.
echo.
echo   First time only - pull models by typing here:
echo     "%OLLAMA_EXE%" pull scb10x/typhoon2.5-qwen3-4b   ^(ASC Copilot^)
echo     "%OLLAMA_EXE%" pull qwen2.5-coder:7b
echo     "%OLLAMA_EXE%" pull qwen2.5-coder:3b
echo     "%OLLAMA_EXE%" pull bge-m3
echo     "%OLLAMA_EXE%" pull moondream
echo.
echo   Keep this window open while using. Server runs here.
echo ============================================================
echo.
cmd /k
goto end

:noollama
echo [!] Ollama not found at:
echo     %OLLAMA_EXE%
echo.
echo     Download ollama-windows-amd64.zip from ollama.com/download/windows
echo     and extract it so that the file above exists.
echo.
pause

:end
