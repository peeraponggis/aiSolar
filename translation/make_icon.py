# -*- coding: utf-8 -*-
"""
make_icon.py - สร้าง translator.ico สำหรับโปรแกรมแปล
    python make_icon.py                วาดไอคอนหุ่นยนต์ขาว ตาฟ้า พื้นดำ (ค่าเริ่มต้น)
    python make_icon.py myrobot.png    แปลงรูป PNG/JPG ของคุณเองเป็นไอคอน (ตัดขอบโปร่งใส + ทำเป็นสี่เหลี่ยมจัตุรัสให้)
ได้ไฟล์ translator.ico (16-256 px) และ translator.png (ตัวอย่าง 256 px) ในโฟลเดอร์นี้
"""
import os
import sys
from PIL import Image, ImageDraw

BASE = os.path.dirname(os.path.abspath(__file__))
OUT_ICO = os.path.join(BASE, "translator.ico")
OUT_PNG = os.path.join(BASE, "translator.png")
SIZES = [16, 24, 32, 48, 64, 128, 256]


def draw_robot(size=1024, bg=True, accent=(86, 224, 216, 255), glow=None):
    """หุ่นยนต์ขาว หน้าจอดำ ตาและปากสี accent (ตามรูปตัวอย่างของผู้ใช้)
    bg=True วาดวงกลมพื้นดำ (ไอคอนไฟล์) / bg=False พื้นโปร่งใส (ไอคอนลอย)
    glow=สี วาดวงแหวนเรืองแสงรอบตัว (ใช้ทำเฟรมแอนิเมชัน)"""
    s = size
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    u = s / 200.0  # หน่วยออกแบบ 200x200
    white, shade, dark, cyan = (245, 246, 244, 255), (205, 208, 212, 255), (32, 34, 38, 255), tuple(accent)

    if bg:
        d.ellipse([4 * u, 4 * u, 196 * u, 196 * u], fill=(17, 18, 20, 255))      # พื้นหลังวงกลมดำ
        d.ellipse([62 * u, 168 * u, 138 * u, 182 * u], fill=(40, 42, 46, 255))   # เงาใต้ตัว
    if glow:
        g = tuple(glow[:3])
        for i, a in enumerate((40, 70, 110)):
            pad = (14 - i * 4) * u
            d.ellipse([48 * u - pad, 50 * u - pad, 152 * u + pad, 120 * u + pad], outline=g + (a,), width=int(4 * u))

    # ลำตัว (ครึ่งวงรีล่าง)
    d.rounded_rectangle([60 * u, 118 * u, 140 * u, 172 * u], radius=int(34 * u), fill=white)
    d.rounded_rectangle([60 * u, 118 * u, 140 * u, 130 * u], radius=int(6 * u), fill=shade)  # ไหล่มีเงา

    # เสาอากาศ
    d.line([100 * u, 34 * u, 100 * u, 52 * u], fill=white, width=int(3.5 * u))
    d.ellipse([94 * u, 26 * u, 106 * u, 38 * u], fill=white)

    # หัว
    d.rounded_rectangle([48 * u, 50 * u, 152 * u, 120 * u], radius=int(34 * u), fill=white)
    # หน้าจอดำ
    d.rounded_rectangle([60 * u, 60 * u, 140 * u, 110 * u], radius=int(22 * u), fill=dark)
    # ตา
    for cx in (84, 116):
        d.ellipse([(cx - 9) * u, 74 * u, (cx + 9) * u, 92 * u], fill=cyan)
        d.ellipse([(cx - 3) * u, 77 * u, (cx + 2) * u, 82 * u], fill=(210, 255, 252, 255))
    # ปากยิ้ม
    d.arc([86 * u, 84 * u, 114 * u, 104 * u], start=15, end=165, fill=cyan, width=int(3.5 * u))
    # หูข้าง
    d.rounded_rectangle([40 * u, 76 * u, 50 * u, 96 * u], radius=int(4 * u), fill=shade)
    d.rounded_rectangle([150 * u, 76 * u, 160 * u, 96 * u], radius=int(4 * u), fill=shade)
    return im


def from_file(path):
    im = Image.open(path).convert("RGBA")
    bbox = im.getbbox()
    if bbox:
        im = im.crop(bbox)
    w, h = im.size
    side = int(max(w, h) * 1.08)
    sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    sq.paste(im, ((side - w) // 2, (side - h) // 2), im)
    return sq


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else None
    im = from_file(src) if src else draw_robot()
    im = im.resize((1024, 1024), Image.LANCZOS)
    im.save(OUT_ICO, format="ICO", sizes=[(x, x) for x in SIZES])
    im.resize((256, 256), Image.LANCZOS).save(OUT_PNG)
    print("saved", OUT_ICO, "and", OUT_PNG, "(from %s)" % (src or "built-in drawing"))


if __name__ == "__main__":
    main()
