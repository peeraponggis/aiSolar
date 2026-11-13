@echo off
title GAS Monitor - ลุงพี
cd /d "%~dp0"

:: Install dependencies if needed
pip show pyserial >nul 2>&1 || pip install -r requirements.txt -q

:: Launch
python gas_monitor.py
pause
