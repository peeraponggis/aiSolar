#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/files.py - จัดการไฟล์พื้นฐาน
list_dir/read_file = Tier A (อ่านอย่างเดียว), write_file = Tier B (เขียนทับของเดิมจะถูกยกเป็น
Tier C โดย safety.py ที่ตรวจว่าไฟล์มีอยู่ก่อนแล้วหรือไม่), delete_file = Tier C เสมอ
"""
import logging
import os
import re
import time

log = logging.getLogger(__name__)
MAX_READ_CHARS = 8000
_PS_ENV_RE = re.compile(r"\$env:(\w+)", re.IGNORECASE)


def _normalize_path(path):
    """โมเดลมักเขียน path แบบ PowerShell ($env:USERPROFILE) เพราะเพิ่งใช้ run_shell มา แต่
    os.listdir/open ของ Python ไม่เข้าใจ syntax นี้ - แปลง $env:NAME -> ค่าจริงก่อน พร้อมรองรับ
    ~ และ %NAME% (os.path.expanduser/expandvars) ให้ด้วยเผื่อโมเดลเขียนแบบอื่น"""
    path = _PS_ENV_RE.sub(lambda m: os.environ.get(m.group(1), m.group(0)), path or "")
    return os.path.expanduser(os.path.expandvars(path))


def list_dir(path):
    try:
        entries = os.listdir(_normalize_path(path))
        return {"ok": True, "entries": entries[:200], "truncated": len(entries) > 200}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def read_file(path):
    try:
        with open(_normalize_path(path), "r", encoding="utf-8", errors="replace") as f:
            content = f.read(MAX_READ_CHARS + 1)
        truncated = len(content) > MAX_READ_CHARS
        return {"ok": True, "content": content[:MAX_READ_CHARS], "truncated": truncated}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def write_file(path, content):
    path = _normalize_path(path)
    try:
        dirname = os.path.dirname(os.path.abspath(path))
        if dirname:
            os.makedirs(dirname, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content or "")
        return {"ok": True, "message": f"บันทึก {path} แล้ว"}
    except Exception as e:
        log.warning("เขียนไฟล์ %s ไม่สำเร็จ", path, exc_info=True)
        return {"ok": False, "error": str(e)}


def find_file(name, root=None, max_results=20, max_seconds=15):
    """ค้นหาไฟล์/โฟลเดอร์ที่ชื่อมีคำว่า name (ไม่สนตัวพิมพ์เล็ก-ใหญ่) แบบ recursive ทั้งต้นไม้
    โฟลเดอร์เดียว ไม่ต้องให้โมเดลวนเรียก list_dir เองทีละชั้น (ซึ่งไม่น่าเชื่อถือกับโมเดลเล็ก) จำกัด
    เวลาค้นหาไม่ให้ค้างนานถ้าโฟลเดอร์ใหญ่เกินไป"""
    root = _normalize_path(root) if root else os.path.expanduser("~")
    name_l = (name or "").lower()
    results = []
    t0 = time.time()
    try:
        for dirpath, dirnames, filenames in os.walk(root):
            if time.time() - t0 > max_seconds:
                return {"ok": True, "results": results, "truncated": True,
                        "note": f"ค้นหาเกิน {max_seconds} วินาที หยุดก่อนครบทุกโฟลเดอร์"}
            for entry in dirnames + filenames:
                if name_l in entry.lower():
                    results.append(os.path.join(dirpath, entry))
                    if len(results) >= max_results:
                        return {"ok": True, "results": results, "truncated": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True, "results": results, "truncated": False}


def delete_file(path):
    path = _normalize_path(path)
    try:
        os.remove(path)
        return {"ok": True, "message": f"ลบ {path} แล้ว"}
    except Exception as e:
        log.warning("ลบไฟล์ %s ไม่สำเร็จ", path, exc_info=True)
        return {"ok": False, "error": str(e)}
