@echo off
rem Git Sync - Commit + push all repos at once (asks per repo, see README.md)
chcp 65001 >nul
title Git Sync - Push All
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0git-sync.ps1" -Mode Push
echo.
pause
