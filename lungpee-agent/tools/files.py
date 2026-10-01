#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/files.py - จัดการไฟล์พื้นฐาน
list_dir/read_file = Tier A (อ่านอย่างเดียว), write_file = Tier B (เขียนทับของเดิมจะถูกยกเป็น
Tier C โดย safety.py ที่ตรวจว่าไฟล์มีอยู่ก่อนแล้วหรือไม่), delete_file = Tier C เสมอ
"""
import logging
import os

log = logging.getLogger(__name__)
MAX_READ_CHARS = 8000


def list_dir(path):
    try:
        entries = os.listdir(path)
        return {"ok": True, "entries": entries[:200], "truncated": len(entries) > 200}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def read_file(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(MAX_READ_CHARS + 1)
        truncated = len(content) > MAX_READ_CHARS
        return {"ok": True, "content": content[:MAX_READ_CHARS], "truncated": truncated}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def write_file(path, content):
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


def delete_file(path):
    try:
        os.remove(path)
        return {"ok": True, "message": f"ลบ {path} แล้ว"}
    except Exception as e:
        log.warning("ลบไฟล์ %s ไม่สำเร็จ", path, exc_info=True)
        return {"ok": False, "error": str(e)}
