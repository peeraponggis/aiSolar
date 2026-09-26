@echo off
chcp 65001 >nul
title Lek Dang Scraper - กวาดเลขดัง
cd /d "%~dp0"
echo ====================================
echo  กวาดเลขดัง (เลขเด็ด) จากเว็บ
echo  สรุปว่าเลขไหนถูกพูดถึงมากสุด
echo ====================================
python lek_dang_scraper.py
pause
