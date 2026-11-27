@echo off
chcp 65001 >nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0lib\02-asca.ps1" %*
if errorlevel 1 pause
