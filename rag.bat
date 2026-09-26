@echo off
chcp 65001 >nul
title RAG ถาม-ตอบเอกสาร (Ollama)
cd /d "%~dp0"
echo ====================================
echo  RAG ถาม-ตอบเอกสาร knowledge
echo  embed: bge-m3  ตอบ: qwen2.5:7b
echo ====================================
python rag_gui.py
pause
