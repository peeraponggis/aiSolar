@echo off
rem Git Sync - menu (Desktop shortcut points here)
chcp 65001 >nul
title Git Sync
:menu
cls
echo ==========================================
echo    Git Sync  -  LungPee  (all repos)
echo ==========================================
echo    1  Pull  - download latest from GitHub
echo    2  Push  - commit + upload to GitHub
echo    3  Status - show every repo
echo    4  Edit repo list (repos.txt)
echo    0  Exit
echo ==========================================
set "c="
set /p c=Select 1-4 / 0 : 
if "%c%"=="1" powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0git-sync.ps1" -Mode Pull & pause & goto menu
if "%c%"=="2" powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0git-sync.ps1" -Mode Push & pause & goto menu
if "%c%"=="3" powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0git-sync.ps1" -Mode Status & pause & goto menu
if "%c%"=="4" start "" notepad "%~dp0repos.txt" & goto menu
if "%c%"=="0" exit /b 0
goto menu
