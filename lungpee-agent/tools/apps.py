#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/apps.py - เปิดโปรแกรมที่ติดตั้งในเครื่อง (Tier A - ความเสี่ยงต่ำ, รันได้เลยถ้าอยู่ใน
รายชื่อโปรแกรมที่รู้จัก ดู safety.ALLOWED_APPS สำหรับรายชื่อที่อนุญาต)
"""
import logging
import subprocess

log = logging.getLogger(__name__)

# ชื่อที่ผู้ใช้อาจพูด -> ชื่อ exe จริงที่สั่งเปิดได้ตรงๆ ผ่าน PATH/App Paths ของ Windows
KNOWN_APPS = {
    "notepad": "notepad.exe", "โน้ตแพด": "notepad.exe",
    "calculator": "calc.exe", "calc": "calc.exe", "เครื่องคิดเลข": "calc.exe",
    "explorer": "explorer.exe", "file explorer": "explorer.exe", "ตัวจัดการไฟล์": "explorer.exe",
    "paint": "mspaint.exe", "wordpad": "write.exe",
    "chrome": "chrome.exe", "google chrome": "chrome.exe",
    "edge": "msedge.exe", "msedge": "msedge.exe",
    "code": "code.exe", "vscode": "code.exe", "visual studio code": "code.exe",
}


def launch_app(name):
    key = (name or "").strip().lower()
    target = KNOWN_APPS.get(key, name)
    if not target:
        return {"ok": False, "error": "ไม่ได้ระบุชื่อโปรแกรม"}
    try:
        subprocess.Popen(target, shell=True)
        return {"ok": True, "message": f"เปิด {name} แล้ว"}
    except Exception as e:
        log.warning("เปิดโปรแกรม %s ไม่สำเร็จ", name, exc_info=True)
        return {"ok": False, "error": str(e)}
