#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hotkey.py - คีย์ลัดทั่วเครื่อง (global hotkey) กดครั้งเดียวเพื่อพูดคุยกับลุงพี

ตัดแบบง่ายมาจากแพทเทิร์น RegisterHotKey ที่ใช้ใน F:/LocalAI/translation/win_hooks.py (ตัด
ส่วน mouse hook ที่ไม่เกี่ยวข้องออก เหลือแค่ global hotkey อย่างเดียว) ลอง Ctrl+Alt+L ก่อน
("L" = Lung pee) ถ้าโปรแกรมอื่นจองไว้แล้วให้สลับไป Ctrl+Alt+K แทน
"""
import ctypes
import logging

log = logging.getLogger(__name__)

MOD_ALT, MOD_CONTROL, MOD_NOREPEAT = 0x0001, 0x0002, 0x4000
WM_HOTKEY = 0x0312


class MSG(ctypes.Structure):
    _fields_ = [("hwnd", ctypes.c_void_p), ("message", ctypes.c_uint), ("wParam", ctypes.c_size_t),
                ("lParam", ctypes.c_ssize_t), ("time", ctypes.c_uint),
                ("pt_x", ctypes.c_long), ("pt_y", ctypes.c_long)]


def hotkey_thread(on_hotkey, status_cb=None):
    """รันใน daemon thread แยก: ลงทะเบียนคีย์ลัดแล้ววนอ่าน message loop ของเธรดนี้ตลอดอายุโปรแกรม"""
    user32 = ctypes.windll.user32
    hot_ok = None
    for key in ("L", "K"):
        if user32.RegisterHotKey(None, 1, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, ord(key)):
            hot_ok = "Ctrl+Alt+" + key; break
    if not hot_ok:
        log.warning("ลงทะเบียนคีย์ลัด Ctrl+Alt+L/K ไม่สำเร็จ (โปรแกรมอื่นอาจจองไว้)")
    if status_cb:
        status_cb(hot_ok)
    msg = MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        if msg.message == WM_HOTKEY:
            on_hotkey()
