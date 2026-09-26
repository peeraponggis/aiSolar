@echo off
setlocal
title Local Translator - Install (Ollama + Thai model)

REM ============================================================
REM  Install-LocalTranslator.bat  (run once on a new PC)
REM  1) find Ollama (install it first from ollama.com if missing)
REM  2) start the Ollama server
REM  3) download the Thai translation model (~2.5 GB, first time only)
REM  4) create a Desktop shortcut and start Local Translator
REM  Needs: Windows 10/11, internet for step 3, ~3 GB free disk
REM  Better with an NVIDIA GPU (4 GB VRAM or more); works on CPU but slower
REM ============================================================

set "MODEL=scb10x/typhoon2.5-qwen3-4b:latest"
set "MODELKEY=typhoon2.5-qwen3-4b"
set "APP=%~dp0LocalTranslator.exe"
set "OLLAMA_EXE="

echo ============================================================
echo   Local Translator - Setup
echo   Model: %MODEL%
echo ============================================================
echo.
if not exist "%APP%" (
  echo [!] LocalTranslator.exe not found next to this file.
  goto fail
)

echo [1/4] Looking for Ollama ...
where ollama >nul 2>nul
if not errorlevel 1 set "OLLAMA_EXE=ollama"
if defined OLLAMA_EXE goto found
if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" set "OLLAMA_EXE=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
if defined OLLAMA_EXE goto found
if exist "%ProgramFiles%\Ollama\ollama.exe" set "OLLAMA_EXE=%ProgramFiles%\Ollama\ollama.exe"
if defined OLLAMA_EXE goto found
if exist "%~dp0ollama\ollama.exe" set "OLLAMA_EXE=%~dp0ollama\ollama.exe"
if defined OLLAMA_EXE goto found
echo     [!] Ollama is not installed on this PC.
echo         1. Download OllamaSetup.exe from https://ollama.com/download/windows
echo         2. Install it (default options)
echo         3. Run this file again
echo.
echo     Press Enter to open the download page.
pause >nul
start "" "https://ollama.com/download/windows"
goto fail
:found
echo     [OK] %OLLAMA_EXE%

echo [2/4] Starting Ollama server ...
curl -s -m 3 http://127.0.0.1:11434/api/version >nul 2>&1
if not errorlevel 1 goto srv_ok
set "OLLAMA_ORIGINS=*"
start "Ollama Server" /min "%OLLAMA_EXE%" serve
set _w=0
:waitsrv
timeout /t 1 /nobreak >nul
curl -s -m 2 http://127.0.0.1:11434/api/version >nul 2>&1
if not errorlevel 1 goto srv_ok
set /a _w+=1
if %_w% LSS 30 goto waitsrv
echo     [!] Ollama did not start within 30 s. Open the Ollama app, then run this file again.
goto fail
:srv_ok
echo     [OK] server ready

echo [3/4] Checking model ...
"%OLLAMA_EXE%" list | findstr /i "%MODELKEY%" >nul
if not errorlevel 1 goto have_model
echo     Downloading ~2.5 GB (first time only, needs internet) ...
"%OLLAMA_EXE%" pull %MODEL%
if errorlevel 1 (
  echo     [!] Download failed. Check internet / firewall, then run this file again.
  goto fail
)
echo     [OK] model downloaded
goto model_done
:have_model
echo     [OK] model already installed
:model_done

echo [4/4] Creating Desktop shortcut and starting the app ...
powershell -NoProfile -Command "$d=[Environment]::GetFolderPath('Desktop');$s=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $d 'Local Translator.lnk'));$s.TargetPath='%APP%';$s.WorkingDirectory='%~dp0';$s.IconLocation='%~dp0translator.ico,0';$s.Description='Local Translator - Thai/English (offline model)';$s.Save()" >nul 2>&1
start "" "%APP%"
echo.
echo ============================================================
echo   Done. Use the "Local Translator" shortcut on the Desktop.
echo   Tick "auto start" inside the app if you want it at logon.
echo   Keep Ollama running in the background (it starts itself).
echo ============================================================
echo.
pause
exit /b 0

:fail
echo.
pause
exit /b 1
