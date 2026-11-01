@echo off
rem HyperFrames บน F: ทั้งหมด (ห้ามเขียนลง C:) · ปิด telemetry · โดย ลุงพี
rem ใช้แทน npx hyperframes เช่น  hf check  /  hf render -o renders\card.mp4 --variables "{...}"
set "USERPROFILE=F:\LocalAI\tools\hyperframes-home"
set "npm_config_cache=F:\LocalAI\.npm-cache"
set "PUPPETEER_CACHE_DIR=F:\LocalAI\tools\puppeteer-cache"
set "HYPERFRAMES_EXTRACT_CACHE_DIR=F:\LocalAI\tmp\hf-cache"
set "TEMP=F:\LocalAI\tmp"
set "TMP=F:\LocalAI\tmp"
set "DO_NOT_TRACK=1"
set "HYPERFRAMES_NO_TELEMETRY=1"
set "HYPERFRAMES_SKIP_SKILLS=1"
set "PATH=F:\LocalAI\tools\ffmpeg;%PATH%"
cd /d "%~dp0"
npx --yes hyperframes@0.8.225 %*
