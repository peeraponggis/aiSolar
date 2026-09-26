@echo off
chcp 65001 >nul
title Lek Dang Correlation Test
cd /d "%~dp0"
echo ====================================
echo  ทดสอบ Correlation เลขดัง vs ผลจริง
echo ====================================
python lek_dang_correlate.py
pause
