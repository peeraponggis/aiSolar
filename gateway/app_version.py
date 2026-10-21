# -*- coding: utf-8 -*-
"""ข้อมูลเวอร์ชันของโปรแกรม — ปรับด้วย F:\\LocalAI\\bump_version.py ทุกครั้งที่แก้ไข (อย่าแก้ตัวเลขด้วยมือ)"""
APP_NAME = "ลุงพี AI Gateway"
VERSION = "1.4.0"
CREATED = "2026-09-27"
UPDATED = "2026-10-21"
AUTHOR = "ลุงพี"
CHANGELOG = [  # ใหม่สุดอยู่บน: (เวอร์ชัน, วันที่, สรุป)
    ("1.4.0", "2026-10-21", "คลังความรู้ใช้ผล OCR: หน้าภาพสแกนและหน้าที่ฟอนต์ไทยเก่าถอดเพี้ยน ใช้ข้อความจาก ocr_knowledge.py (Typhoon OCR/Tesseract/KKU); reindex แบบ force:false จัดเฉพาะไฟล์ที่เปลี่ยน"),
    ("1.3.5", "2026-10-21", "คลังความรู้: สร้างได้ทีละรอบ (เดิมรอบตอนเปิดกับรอบสั่ง reindex ทำซ้อนกัน), cache มีเวอร์ชัน เปลี่ยนวิธีแบ่งข้อความแล้ว embed ใหม่เอง, บันทึก cache ทุกไฟล์ที่เสร็จ"),
    ("1.3.4", "2026-10-21", "คลังความรู้: แบ่งย่อหน้ายาว (ตาราง/CSV) ไม่ให้เกิน 800 ตัวอักษร (เดิมยาวถึง 70,000 ตัว Ollama ตอบ 500) และแปลงรหัสสระ/วรรณยุกต์ของ PDF ไทยรุ่นเก่าเป็นตัวอักษรไทยมาตรฐาน"),
    ("1.3.3", "2026-10-21", "คลังความรู้: ไฟล์ที่ embed ไม่สำเร็จ (เช่น Ollama ปิด/อัปเดตอยู่) ไม่ถูกจำเป็น 0 chunks อีกต่อไป — ลองใหม่รอบหน้า"),
    ("1.3.2", "2026-10-18", "image_runner ใช้คิว GPU ใน local_image.py ร่วมกับ AI-Bridge-Launcher"),
    ("1.3.1", "2026-10-18", "แก้เวลาสร้างภาพแสดง undefined"),
    ("1.3.0", "2026-10-18", "สร้างภาพ (/api/image) ด้วยระบบเดียวกับ AI-Bridge-Launcher เก็บภาพที่ clip_bank\\img"),
    ("1.2.0", "2026-10-18", "เพิ่มเส้นทาง KKU gen.ai (/api/kku/v1) และ /api/version"),
    ("1.1.0", "2026-10-15", "edge-tts 7.3.1 แก้เสียง Neural ใช้ไม่ได้ (403)"),
    ("1.0.0", "2026-09-27", "เวอร์ชันแรก"),
]

_TH_MONTHS = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]


def thai_date(iso):
    y, m, d = (int(x) for x in iso.split("-"))
    return f"{d} {_TH_MONTHS[m - 1]} {y + 543}"


def about_text():
    return (f"{APP_NAME} v{VERSION} · สร้าง {thai_date(CREATED)} · "
            f"ปรับปรุงล่าสุด {thai_date(UPDATED)} · โดย {AUTHOR}")


def info():
    return {"name": APP_NAME, "version": VERSION, "created": CREATED, "updated": UPDATED,
            "author": AUTHOR, "changelog": [list(c) for c in CHANGELOG]}
