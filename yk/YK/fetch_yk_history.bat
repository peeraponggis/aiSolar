@echo off
chcp 65001 >nul
title YK History Fetcher
cd /d "%~dp0"
echo ====================================
echo  YK History Fetcher
echo  ดึงประวัติยี่กี cat888 ย้อนหลัง
echo ====================================
python yk_fetch_history.py
pause
