#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/apps.py - เปิดโปรแกรมที่ติดตั้งในเครื่อง (Tier A - ความเสี่ยงต่ำ, รันได้เลยถ้าอยู่ใน
รายชื่อโปรแกรมที่รู้จัก ดู safety.ALLOWED_APPS สำหรับรายชื่อที่อนุญาต)

ลำดับการหา: KNOWN_APPS (exe บน PATH) -> ทางลัดใน Start Menu (ครอบคลุมโปรแกรมที่ติดตั้ง
ในโฟลเดอร์มีเลขเวอร์ชัน เช่น LINE\\bin\\26.5.0.3975\\LINE.exe ที่ไม่อยู่บน PATH)
"""
import glob
import logging
import os
import shutil
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

# ชื่อภาษาไทย/ที่ถอดเสียงเพี้ยนบ่อย -> ชื่อที่ใช้ค้นใน Start Menu
ALIASES = {"ไลน์": "line", "ไลน": "line", "ไล้": "line", "ฟรีแคด": "freecad"}

_START_MENU_DIRS = [
    os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs"),
    os.path.join(os.environ.get("ProgramData", ""), r"Microsoft\Windows\Start Menu\Programs"),
]
_SKIP_WORDS = ("uninstall", "ถอนการติดตั้ง", "documentation", "manual", "readme", "help")


def _find_start_menu_shortcut(query):
    """คะแนน: ชื่อตรงเป๊ะ > ชื่อขึ้นต้นด้วยคำค้น > ชื่อโฟลเดอร์ตรง > มีคำค้นอยู่ในชื่อ - กันกรณี
    "line" ไปเจอ "Python (command line)" หรือ "Online Documentation" ก่อน LINE.lnk จริง"""
    q = query.lower()
    best, best_score = None, 0
    for d in _START_MENU_DIRS:
        for lnk in glob.glob(os.path.join(d, "**", "*.lnk"), recursive=True):
            base = os.path.splitext(os.path.basename(lnk))[0].lower()
            folder = os.path.basename(os.path.dirname(lnk)).lower()
            if any(w in base for w in _SKIP_WORDS):
                continue
            if base == q:
                score = 4
            elif base.startswith(q + " ") or q.startswith(base + " "):
                score = 3
            elif folder == q or folder.startswith(q + " "):
                score = 2
            elif q in base:
                score = 1
            else:
                continue
            if score > best_score:
                best, best_score = lnk, score
    return best


def launch_app(name):
    raw = (name or "").strip()
    if not raw:
        return {"ok": False, "error": "ไม่ได้ระบุชื่อโปรแกรม"}
    key = ALIASES.get(raw.lower(), raw.lower())

    exe = KNOWN_APPS.get(key)
    if exe:
        if shutil.which(exe):
            subprocess.Popen([exe])
            return {"ok": True, "message": f"เปิด {raw} แล้ว"}
        try:   # ไม่อยู่บน PATH แต่อาจลงทะเบียนใน App Paths (เช่น chrome.exe) - ลองก่อน fuzzy match
            os.startfile(exe)
            return {"ok": True, "message": f"เปิด {raw} แล้ว"}
        except OSError:
            pass

    lnk = _find_start_menu_shortcut(key)
    if lnk:
        try:
            os.startfile(lnk)
            return {"ok": True, "message": f"เปิด {os.path.splitext(os.path.basename(lnk))[0]} แล้ว"}
        except OSError as e:
            log.warning("เปิดทางลัด %s ไม่สำเร็จ", lnk, exc_info=True)
            return {"ok": False, "error": str(e)}
    return {"ok": False, "error": f"ไม่พบโปรแกรมชื่อ {raw} ในเครื่อง"}
