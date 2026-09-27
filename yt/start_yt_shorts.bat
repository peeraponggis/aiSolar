@echo off
title YT Shorts Automation
cd /d F:\LocalAI\yt
start "" http://localhost:5000
python -m uvicorn app.app:app --host 127.0.0.1 --port 5000
pause
