@echo off
chcp 65001 >nul
REM อัปเดต Skill ของลุงพี: git pull repo aiSolar แล้วรัน install-skills.ps1 — รันซ้ำได้ ทั้ง laptop / home server · โดย ลุงพี
REM ใช้: ดับเบิลคลิกไฟล์นี้ (<ไดรฟ์>:\LocalAI\skills\install-skills.bat)
setlocal
set "SKILLS=%~dp0"
set "REPO=%~dp0.."

echo [1/2] git pull %REPO%
git -C "%REPO%" pull --rebase --autostash
if errorlevel 1 (
    git -C "%REPO%" rebase --abort >nul 2>&1
    echo.
    echo *** git pull ไม่สำเร็จ ^(conflict หรือเน็ต/สิทธิ์ GitHub^) — ยังไม่ได้ติดตั้ง skill
    echo *** ให้ Claude ช่วยแก้ แล้วค่อยรันไฟล์นี้ใหม่
    pause
    exit /b 1
)

echo.
echo [2/2] ติดตั้ง skill
powershell -NoProfile -ExecutionPolicy Bypass -File "%SKILLS%install-skills.ps1"
if errorlevel 1 (
    echo *** ติดตั้ง skill ไม่สำเร็จ
    pause
    exit /b 1
)

echo.
pause
