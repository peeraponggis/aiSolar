#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
avatar.py - หน้าต่างลอยแสดงอวตารหุ่นยนต์ลุงพีแบบเปลี่ยนสีวนตอนฟัง/คิด/พูด แทนที่จะมีแต่เสียง
ลอยๆ ไม่มีอะไรให้เห็นเลยว่ากำลังทำงานอยู่หรือเปล่า (ก่อนหน้านี้ลุงพีเป็นแค่ไอคอนเล็กๆ ในถาดระบบ)

เป็น Toplevel ไม่มีกรอบหน้าต่าง (borderless) อยู่บนสุดเสมอ มุมขวาล่างจอ เหนือถาดระบบเล็กน้อย
โชว์พร้อมแอนิเมชันเปลี่ยนสีตัวหุ่นยนต์วนไปเรื่อยๆ (ดู robot_icon.py) เมื่อเริ่มฟัง/คิด/พูด แล้ว
ซ่อนกลับอัตโนมัติเมื่อพูดจบ
"""
import logging
import tkinter as tk

from robot_icon import build_color_frames

log = logging.getLogger(__name__)


class AvatarWindow:
    SIZE = 140
    FRAMES = 16
    FRAME_MS = 80   # ความเร็วไล่สี (ยิ่งน้อยยิ่งเปลี่ยนสีเร็ว)

    def __init__(self, root):
        self.root = root
        self.win = tk.Toplevel(root)
        self.win.withdraw()
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        try:
            self.win.attributes("-alpha", 0.97)
        except Exception:
            pass

        self.frames = build_color_frames(self.SIZE, self.FRAMES)
        self._tick = 0
        self._anim_job = None

        frame = tk.Frame(self.win, bg="#111214", highlightthickness=0)
        frame.pack()
        self.img_label = tk.Label(frame, image=self.frames[0] if self.frames else None, bg="#111214")
        self.img_label.pack(padx=2, pady=(2, 0))
        self.status_var = tk.StringVar(value="")
        tk.Label(frame, textvariable=self.status_var, bg="#111214", fg="#E5F9F3",
                font=("Segoe UI", 10, "bold"), padx=10, pady=6).pack()

    def _position(self):
        self.win.update_idletasks()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        w, h = self.win.winfo_reqwidth(), self.win.winfo_reqheight()
        self.win.geometry(f"+{sw - w - 24}+{sh - h - 72}")

    def _animate(self):
        if self.win.state() == "withdrawn" or not self.frames:
            self._anim_job = None
            return
        self._tick = (self._tick + 1) % len(self.frames)
        self.img_label.configure(image=self.frames[self._tick])
        self._anim_job = self.root.after(self.FRAME_MS, self._animate)

    def show(self, status):
        self.status_var.set(status)
        self._position()
        self.win.deiconify()
        self.win.lift()
        self.win.attributes("-topmost", True)
        if self._anim_job is None:
            self._animate()

    def hide(self):
        if self._anim_job is not None:
            self.root.after_cancel(self._anim_job)
            self._anim_job = None
        self.win.withdraw()
