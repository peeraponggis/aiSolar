@echo off
chcp 65001 >nul
setlocal
title ASC Copilot - Typhoon2.5 Qwen3 4B (local)

REM ============================================================
REM  Start-Typhoon.bat - เปิด Ollama + เตรียม typhoon2.5-qwen3-4b ให้พร้อมใช้กับ ASC ENTERPRISES
REM  ทำ 4 ขั้น: เปิดเซิร์ฟเวอร์ถ้ายังไม่เปิด -> ตรวจโมเดล -> ดาวน์โหลดถ้าไม่มี -> อุ่นเข้า VRAM
REM  หมายเหตุ: ห้ามใส่ label หรือ %ตัวแปร% ที่เปลี่ยนค่าไว้ในบล็อกวงเล็บ - cmd แปลค่าตอน parse
REM ============================================================

set "ROOT=%~dp0"
set "OLLAMA_MODELS=%ROOT%models"
set "OLLAMA_HOME=%ROOT%ollama-data"
set "HOME=%ROOT%ollama-data"
set "OLLAMA_HOST=127.0.0.1:11434"
set "OLLAMA_FLASH_ATTENTION=1"
set "OLLAMA_KV_CACHE_TYPE=q8_0"
set "OLLAMA_ORIGINS=*"
set "OLLAMA_KEEP_ALIVE=30m"
set "OLLAMA_EXE=%ROOT%ollama\ollama.exe"
set "MODEL=scb10x/typhoon2.5-qwen3-4b:latest"
set "MODELKEY=typhoon2.5-qwen3-4b"

echo ============================================================
echo   ASC ENTERPRISES Copilot - Typhoon2.5 Qwen3 4B
echo   MODELS : %OLLAMA_MODELS%
echo ============================================================
echo.

if not exist "%OLLAMA_EXE%" goto noollama

REM ---------- 1) เซิร์ฟเวอร์ ----------
curl -s -m 2 http://127.0.0.1:11434/api/version >nul 2>&1
if not errorlevel 1 goto srv_running
echo [1/4] เปิด Ollama server ...
start "Ollama Server" /min "%OLLAMA_EXE%" serve
set _w=0
:waitsrv
timeout /t 1 /nobreak >nul
curl -s -m 2 http://127.0.0.1:11434/api/version >nul 2>&1
if not errorlevel 1 goto srv_ok
set /a _w+=1
if %_w% LSS 20 goto waitsrv
echo     [!] เปิดเซิร์ฟเวอร์ไม่สำเร็จภายใน 20 วินาที
goto fail
:srv_ok
echo     [OK] เซิร์ฟเวอร์พร้อม
goto srv_done
:srv_running
echo [1/4] Ollama ทำงานอยู่แล้ว
:srv_done

REM ---------- 2) ตรวจโมเดล ----------
echo [2/4] ตรวจโมเดล %MODEL%
"%OLLAMA_EXE%" list | findstr /i /l "%MODELKEY%" >nul
if not errorlevel 1 goto have_model
echo [3/4] ยังไม่มี - กำลังดาวน์โหลด ~2.5 GB ใช้เวลาสักครู่ ...
"%OLLAMA_EXE%" pull %MODEL%
if errorlevel 1 goto pullfail
echo     [OK] ดาวน์โหลดเสร็จ
goto model_done
:have_model
echo [3/4] มีโมเดลอยู่แล้ว ข้ามการดาวน์โหลด
:model_done

REM ---------- 3) อุ่นเครื่อง ----------
echo [4/4] อุ่นเครื่องโมเดลเข้าหน่วยความจำ ...
curl -s -m 180 http://127.0.0.1:11434/api/chat -H "Content-Type: application/json" -d "{\"model\":\"%MODEL%\",\"stream\":false,\"keep_alive\":\"30m\",\"options\":{\"num_ctx\":8192},\"messages\":[{\"role\":\"user\",\"content\":\"ok\"}]}" >nul
echo.
echo ---------- โมเดลที่โหลดอยู่ตอนนี้ ----------
curl -s http://127.0.0.1:11434/api/ps
echo.
echo.
echo ============================================================
echo   พร้อมใช้งาน
echo   เปิดแอป ASC ENTERPRISES ผ่าน localhost แล้ว Copilot จะใช้ตัวนี้เอง
echo   (เว็บ HTTPS สาธารณะเรียก localhost ไม่ได้ ต้องเปิดผ่าน localhost)
echo ============================================================
echo.
pause
exit /b 0

:noollama
echo [!] ไม่พบ ollama.exe ที่ %OLLAMA_EXE%
echo     ดาวน์โหลด ollama-windows-amd64.zip จาก ollama.com/download/windows
echo     แล้วแตกไฟล์ให้ได้ path ข้างบน
goto fail

:pullfail
echo     [!] ดาวน์โหลดไม่สำเร็จ - ตรวจอินเทอร์เน็ตแล้วรันไฟล์นี้ใหม่

:fail
echo.
pause
exit /b 1
