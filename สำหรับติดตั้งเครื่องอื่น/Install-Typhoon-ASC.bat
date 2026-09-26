@echo off
chcp 65001 >nul
setlocal
title ASC ENTERPRISES - ติดตั้งผู้ช่วย AI ในเครื่อง (typhoon2-3b)

REM ============================================================
REM  Install-Typhoon-ASC.bat
REM  ติดตั้งโมเดล typhoon2-3b ให้ Copilot ของ ASC ENTERPRISES ใช้งานในเครื่อง
REM  ใช้กับเครื่องใหม่ที่ยังไม่เคยตั้งค่าอะไรเลย
REM
REM  ต้องมี: Windows 10/11 · อินเทอร์เน็ต · พื้นที่ว่าง ~3 GB
REM  แนะนำ: การ์ดจอ NVIDIA VRAM 4 GB ขึ้นไป (ไม่มีก็ใช้ได้ แต่ช้ากว่ามาก)
REM ============================================================

set "MODEL=scb10x/llama3.2-typhoon2-3b-instruct:latest"
set "MODELKEY=llama3.2-typhoon2-3b-instruct"
set "OLLAMA_ORIGINS=*"
set "OLLAMA_EXE="

echo ============================================================
echo   ASC ENTERPRISES - ติดตั้งผู้ช่วย AI ในเครื่อง
echo   โมเดล: typhoon2-3b (ภาษาไทย ~1.9 GB)
echo ============================================================
echo.

REM ---------- 1) หา ollama ----------
echo [1/5] ค้นหา Ollama ...
where ollama >nul 2>nul
if not errorlevel 1 set "OLLAMA_EXE=ollama"
if defined OLLAMA_EXE goto found
if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" set "OLLAMA_EXE=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
if defined OLLAMA_EXE goto found
if exist "%ProgramFiles%\Ollama\ollama.exe" set "OLLAMA_EXE=%ProgramFiles%\Ollama\ollama.exe"
if defined OLLAMA_EXE goto found
if exist "%~dp0ollama\ollama.exe" set "OLLAMA_EXE=%~dp0ollama\ollama.exe"
if defined OLLAMA_EXE goto found

echo     [!] ไม่พบ Ollama ในเครื่องนี้
echo.
echo     กรุณาติดตั้งก่อน แล้วรันไฟล์นี้ใหม่:
echo       1. เปิด https://ollama.com/download/windows
echo       2. ดาวน์โหลด OllamaSetup.exe แล้วติดตั้งตามปกติ
echo       3. กลับมาดับเบิลคลิกไฟล์นี้อีกครั้ง
echo.
echo     กด Enter เพื่อเปิดหน้าดาวน์โหลดให้เลย
pause >nul
start "" "https://ollama.com/download/windows"
goto fail

:found
echo     [OK] พบที่: %OLLAMA_EXE%

REM ---------- 2) เปิดเซิร์ฟเวอร์ ----------
echo [2/5] ตรวจเซิร์ฟเวอร์ ...
curl -s -m 3 http://127.0.0.1:11434/api/version >nul 2>&1
if not errorlevel 1 goto srv_running
echo     กำลังเปิด Ollama server ...
start "Ollama Server" /min "%OLLAMA_EXE%" serve
set _w=0
:waitsrv
timeout /t 1 /nobreak >nul
curl -s -m 2 http://127.0.0.1:11434/api/version >nul 2>&1
if not errorlevel 1 goto srv_ok
set /a _w+=1
if %_w% LSS 30 goto waitsrv
echo     [!] เปิดเซิร์ฟเวอร์ไม่สำเร็จ - ลองเปิดโปรแกรม Ollama เองแล้วรันไฟล์นี้ใหม่
goto fail
:srv_ok
echo     [OK] เซิร์ฟเวอร์พร้อม
goto srv_done
:srv_running
echo     [OK] เซิร์ฟเวอร์ทำงานอยู่แล้ว
:srv_done

REM ---------- 3) โหลดโมเดล ----------
echo [3/5] ตรวจโมเดล ...
"%OLLAMA_EXE%" list | findstr /i "%MODELKEY%" >nul
if not errorlevel 1 goto have_model
echo     กำลังดาวน์โหลด ~1.9 GB (ครั้งแรกเท่านั้น) ...
"%OLLAMA_EXE%" pull %MODEL%
if errorlevel 1 goto pullfail
echo     [OK] ดาวน์โหลดเสร็จ
goto model_done
:have_model
echo     [OK] มีโมเดลอยู่แล้ว
:model_done

REM ---------- 4) ทดสอบว่าเรียก tool ได้จริง ----------
echo [4/5] ทดสอบการเรียกเครื่องมือ (tool calling) ...
curl -s -m 300 http://127.0.0.1:11434/api/chat -H "Content-Type: application/json" -d "{\"model\":\"%MODEL%\",\"stream\":false,\"keep_alive\":\"30m\",\"tools\":[{\"type\":\"function\",\"function\":{\"name\":\"get_state\",\"description\":\"อ่านค่าปัจจุบันของโครงการ\",\"parameters\":{\"type\":\"object\",\"properties\":{}}}}],\"messages\":[{\"role\":\"user\",\"content\":\"ขอดูค่าปัจจุบันของโครงการ\"}]}" > "%TEMP%\asc_typhoon_test.json"
findstr /i "tool_calls" "%TEMP%\asc_typhoon_test.json" >nul
if errorlevel 1 goto tool_warn
echo     [OK] เรียกเครื่องมือได้
goto tool_done
:tool_warn
echo     [!] รอบนี้โมเดลไม่ได้เรียกเครื่องมือ - ใช้งานต่อได้ แต่คำสั่งบางอย่างอาจต้องกดปุ่มเอง
:tool_done
del "%TEMP%\asc_typhoon_test.json" >nul 2>&1

REM ---------- 5) เสร็จ ----------
echo [5/5] เสร็จแล้ว
echo.
curl -s http://127.0.0.1:11434/api/ps
echo.
echo.
echo ============================================================
echo   ติดตั้งเรียบร้อย
echo.
echo   วิธีใช้:
echo     1. เปิดแอป ASC ENTERPRISES
echo     2. ไปเมนู "ตั้งค่า" - ผู้ช่วย AI (Copilot)
echo     3. เลือกผู้ให้บริการ "Ollama" แล้วกดปุ่มรีเฟรช
echo        โมเดล typhoon2-3b จะถูกเลือกให้เองอัตโนมัติ
echo.
echo   ข้อควรรู้:
echo     - ต้องเปิดแอปผ่าน localhost เท่านั้น
echo       เว็บ HTTPS สาธารณะถูกเบราว์เซอร์บล็อกไม่ให้เรียก localhost
echo     - ปล่อยให้ Ollama ทำงานค้างไว้ระหว่างใช้แอป
echo     - อยากให้โหลดเร็วตอนเปิดครั้งแรก ให้รันไฟล์นี้ซ้ำได้เลย ไม่โหลดใหม่
echo ============================================================
echo.
pause
exit /b 0

:pullfail
echo     [!] ดาวน์โหลดไม่สำเร็จ - ตรวจอินเทอร์เน็ต/ไฟร์วอลล์ แล้วรันไฟล์นี้ใหม่

:fail
echo.
pause
exit /b 1
