# -*- coding: utf-8 -*-
"""ข้อมูลเวอร์ชันของโปรแกรม — ปรับด้วย F:\\LocalAI\\bump_version.py ทุกครั้งที่แก้ไข (อย่าแก้ตัวเลขด้วยมือ)"""
APP_NAME = "ลุงพี AI Gateway"
VERSION = "1.2.0"
CREATED = "2026-09-27"
UPDATED = "2026-10-18"
AUTHOR = "ลุงพี"
CHANGELOG = [  # ใหม่สุดอยู่บน: (เวอร์ชัน, วันที่, สรุป)
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
