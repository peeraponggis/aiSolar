#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
robot_icon.py - วาดไอคอนหุ่นยนต์ลุงพีแบบเปลี่ยนสีวนไปเรื่อยๆ (ใช้เป็นอวตารตอนฟัง/คิด/พูด)

พอร์ต draw_robot() มาจาก F:/LocalAI/translation/make_icon.py ตรงๆ (ไฟล์เดียวกับที่ Local
Translator ใช้วาดไอคอนลอยตอนเลือกข้อความ - win_hooks.py's build_float_frames) เพิ่มฟังก์ชัน
build_color_frames() สร้างชุดเฟรมสีไล่ไปรอบวงล้อสี (hue) ให้ avatar.py เอาไปสลับเฟรมทำแอนิเมชัน
"""
import base64
import colorsys
import io
import logging

from PIL import Image, ImageDraw, ImageTk

log = logging.getLogger(__name__)


def draw_robot(size=1024, bg=True, accent=(86, 224, 216, 255), glow=None):
    """หุ่นยนต์ขาว หน้าจอดำ ตาและปากสี accent
    bg=True วาดวงกลมพื้นดำ / bg=False พื้นโปร่งใส glow=สี วาดวงแหวนเรืองแสงรอบตัว"""
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

    d.rounded_rectangle([60 * u, 118 * u, 140 * u, 172 * u], radius=int(34 * u), fill=white)
    d.rounded_rectangle([60 * u, 118 * u, 140 * u, 130 * u], radius=int(6 * u), fill=shade)

    d.line([100 * u, 34 * u, 100 * u, 52 * u], fill=white, width=int(3.5 * u))
    d.ellipse([94 * u, 26 * u, 106 * u, 38 * u], fill=white)

    d.rounded_rectangle([48 * u, 50 * u, 152 * u, 120 * u], radius=int(34 * u), fill=white)
    d.rounded_rectangle([60 * u, 60 * u, 140 * u, 110 * u], radius=int(22 * u), fill=dark)
    for cx in (84, 116):
        d.ellipse([(cx - 9) * u, 74 * u, (cx + 9) * u, 92 * u], fill=cyan)
        d.ellipse([(cx - 3) * u, 77 * u, (cx + 2) * u, 82 * u], fill=(210, 255, 252, 255))
    d.arc([86 * u, 84 * u, 114 * u, 104 * u], start=15, end=165, fill=cyan, width=int(3.5 * u))
    d.rounded_rectangle([40 * u, 76 * u, 50 * u, 96 * u], radius=int(4 * u), fill=shade)
    d.rounded_rectangle([150 * u, 76 * u, 160 * u, 96 * u], radius=int(4 * u), fill=shade)
    return im


def build_color_frames(size=140, n=16):
    """คืน list ของ ImageTk.PhotoImage จำนวน n เฟรม ไล่สี accent/glow ไปรอบวงล้อสี (hue 0-1)
    คืน [] ถ้าวาดไม่สำเร็จ (ไม่ให้ทำให้โปรแกรมเปิดไม่ได้)"""
    try:
        out = []
        for i in range(n):
            r, g, b = colorsys.hsv_to_rgb(i / n, 0.75, 1.0)
            col = (int(r * 255), int(g * 255), int(b * 255), 255)
            im = draw_robot(256, bg=True, accent=col, glow=col).resize((size, size), Image.LANCZOS)
            out.append(ImageTk.PhotoImage(im))
        return out
    except Exception:
        log.warning("สร้างเฟรมไอคอนหุ่นยนต์สีไม่สำเร็จ", exc_info=True)
        return []
