@echo off
chcp 65001 >nul
title ASC ปล่อยรุ่น (dashboard)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0lib\dashboard.ps1"
if errorlevel 1 pause
