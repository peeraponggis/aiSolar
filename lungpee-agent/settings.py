#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
settings.py - บันทึก/โหลดการตั้งค่าลุงพีแบบถาวร (ข้ามเซสชัน)

บันทึกเฉพาะ fields ที่ควร persist: voice, rate, model, notes
ไม่บันทึก history เพื่อ privacy — history รีเซ็ตทุกครั้งที่เปิดโปรแกรม
"""
import json
import logging
import os

log = logging.getLogger(__name__)

_SETTINGS_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "lungpee-agent")
_SETTINGS_FILE = os.path.join(_SETTINGS_DIR, "settings.json")

_DEFAULTS = {
    "voice": "ปัตตรา (ในเครื่อง เร็ว ออฟไลน์)",  # SAPI offline เร็วที่สุด
    "rate": "ปกติ",
    "model": "",
    "online_model": "",  # "<ผู้ให้บริการ>::<โมเดล>" จากศูนย์ผู้ให้บริการ — ว่าง = ใช้โมเดลในเครื่อง
    "notes": "",  # ข้อมูลที่ผู้ใช้ขอให้จำ ("จำไว้ว่า...")
}


def load() -> dict:
    """โหลด settings จากไฟล์ คืน dict ที่รวม defaults เข้าไปด้วย"""
    try:
        with open(_SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {**_DEFAULTS, **data}
    except FileNotFoundError:
        return dict(_DEFAULTS)
    except Exception:
        log.warning("โหลด settings ไม่สำเร็จ — ใช้ค่าเริ่มต้น", exc_info=True)
        return dict(_DEFAULTS)


def save(st: dict):
    """บันทึกเฉพาะ fields ที่ต้องการ persist"""
    to_save = {k: st[k] for k in ("voice", "rate", "model", "online_model", "notes") if k in st}
    try:
        os.makedirs(_SETTINGS_DIR, exist_ok=True)
        with open(_SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(to_save, f, ensure_ascii=False, indent=2)
        log.debug("บันทึก settings สำเร็จ: %s", _SETTINGS_FILE)
    except Exception:
        log.warning("บันทึก settings ไม่สำเร็จ", exc_info=True)
