@echo off
chcp 65001 >nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0lib\09-homeguard.ps1" %*
if errorlevel 1 pause
