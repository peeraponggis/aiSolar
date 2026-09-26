@echo off
chcp 65001 >nul
title RAG Server (knowledge auto-index)
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
echo ====================================
echo  RAG Server - auto-index knowledge/
echo  serve http://localhost:5002
echo  (เปิดค้างไว้ แล้วใช้ chat.html)
echo ====================================
python -u rag_server.py
pause
