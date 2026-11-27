@echo off
rem Git Sync - Pull all repos at once (see README.md)
chcp 65001 >nul
title Git Sync - Pull All
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0git-sync.ps1" -Mode Pull
echo.
pause
