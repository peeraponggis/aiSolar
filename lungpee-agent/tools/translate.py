#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/translate.py - แปลไฟล์ข้อความด้วยโมเดลเดียวกับที่ลุงพีคุยด้วย (Tier B - เขียนไฟล์ใหม่
แต่ไม่ได้ทับไฟล์ต้นฉบับ เว้นแต่ผู้ใช้ระบุ output_path เป็นไฟล์เดิมเอง ซึ่ง safety.py จะยกระดับ
เป็น Tier C ให้อัตโนมัติเหมือน write_file ปกติ)

ไม่ได้ import engine.py ของ Local Translator ตรงๆ (lungpee-agent ตั้งใจไม่พึ่งโค้ดข้ามโปรเจกต์
สด) แต่เขียน prompt แปลภาษาแบบง่ายของตัวเอง ใช้ ollama_client.chat() เดียวกับที่ agent.py ใช้
"""
import logging
import os

import ollama_client

log = logging.getLogger(__name__)
MAX_TRANSLATE_CHARS = 6000


def _build_messages(text, to_lang):
    target = "ภาษาไทย" if to_lang == "th" else "English"
    return [
        {"role": "system", "content": f"แปลข้อความที่ผู้ใช้ส่งมาเป็น{target} ให้ความหมายถูกต้องเป็นธรรมชาติ "
                                      "ตอบเฉพาะคำแปลเท่านั้น ห้ามอธิบายเพิ่มหรือใส่หมายเหตุ /no_think"},
        {"role": "user", "content": text},
    ]


def _default_output_path(path, to_lang):
    base, ext = os.path.splitext(path)
    suffix = "_th" if to_lang == "th" else "_en"
    return f"{base}{suffix}{ext}"


def translate_file(path, to="th", output_path=None, model=None):
    if not model:
        return {"ok": False, "error": "ยังไม่ได้เชื่อมต่อโมเดล"}
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
    except Exception as e:
        return {"ok": False, "error": f"อ่านไฟล์ {path} ไม่ได้: {e}"}
    if len(text) > MAX_TRANSLATE_CHARS:
        return {"ok": False, "error": f"ไฟล์ยาวเกิน {MAX_TRANSLATE_CHARS} ตัวอักษร (ไฟล์นี้ {len(text)} ตัวอักษร) - ยังไม่รองรับไฟล์ยาวขนาดนี้"}
    if not text.strip():
        return {"ok": False, "error": "ไฟล์นี้ไม่มีข้อความให้แปล"}
    try:
        result = ollama_client.chat(model, _build_messages(text, to), temperature=0.3)
        translated = ollama_client.clean_output(result["content"])
    except Exception as e:
        log.exception("แปลไฟล์ %s ผิดพลาด", path)
        return {"ok": False, "error": str(e)}
    out_path = output_path or _default_output_path(path, to)
    try:
        dirname = os.path.dirname(os.path.abspath(out_path))
        if dirname:
            os.makedirs(dirname, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(translated)
    except Exception as e:
        return {"ok": False, "error": f"บันทึกไฟล์แปล {out_path} ไม่ได้: {e}"}
    return {"ok": True, "output_path": out_path, "message": f"แปลแล้ว บันทึกที่ {out_path}"}
