#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
float_icon.py - ไอคอนลอยโปร่งใสที่โผล่ขึ้นเมื่อผู้ใช้ลากคลุม/ดับเบิลคลิกเลือกข้อความ
ในโปรแกรมใดก็ได้ (ตรวจจากเธรด mouse hook ใน win_hooks.py) คลิกไอคอนแล้วจำลอง Ctrl+C
แล้วส่งข้อความที่คัดลอกได้เข้าคิวงานหลักของ run_gui เพื่อแปลทันที

แยกออกจาก run_gui() เพราะเป็นฟีเจอร์ที่เห็นภาพรวมได้ง่าย (สร้างหน้าต่างลอยของตัวเอง
มีสถานะแอนิเมชัน/ตำแหน่ง/ตัวจับเวลาเป็นของตัวเอง) จุดเชื่อมกับส่วนอื่นมีแค่: show()/maybe_hide()
ที่ pump() เรียกเมื่อ mouse hook รายงานมา, และ is_own_window() ที่ win_event_thread ใช้ถามกลับ
ว่าคลิกนั้นอยู่ในหน้าต่างโปรแกรมเราเอง/บนไอคอนลอยหรือเปล่า (ถ้าใช่จะไม่โชว์ไอคอนซ้อน)
"""
import ctypes
import math
import os
import threading
import time
import tkinter as tk

from win_hooks import GA_ROOT, build_float_frames, make_noactivate, send_ctrl_c


class FloatIcon:
    SIZE, FRAMES = 56, 16
    KEY = "#010203"          # สีคีย์ที่ Windows ทำให้โปร่งใส

    def __init__(self, root, base, fam, q, worker, float_var):
        self.root = root
        self.q = q
        self.worker = worker
        self.float_var = float_var
        self.state = {"hwnd": None, "timer": None, "shown_at": 0, "anim": None, "x": 0, "y": 0, "tick": 0}

        self.frames = build_float_frames(self.SIZE, self.FRAMES, self.KEY)
        if not self.frames:
            try:
                self.frames = [tk.PhotoImage(file=os.path.join(base, "translator.png")).subsample(5)]
            except Exception:
                self.frames = []

        self.win = tk.Toplevel(root)
        self.win.title("translator-float-icon")
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.withdraw()
        self.win.configure(background=self.KEY)
        try:
            self.win.attributes("-transparentcolor", self.KEY)
        except Exception:
            pass
        self.btn = tk.Label(self.win, image=self.frames[0] if self.frames else None,
                            text="" if self.frames else "แปล", background=self.KEY,
                            foreground="#56E0D8", cursor="hand2", borderwidth=0, padx=0, pady=0,
                            font=(fam, 10, "bold"))
        self.btn.pack()
        self.btn.bind("<Button-1>", self._clicked)

    def _animate(self):
        if self.win.state() == "withdrawn":
            self.state["anim"] = None; return
        t = self.state["tick"] = self.state["tick"] + 1
        if self.frames:
            self.btn.configure(image=self.frames[t % len(self.frames)])          # เปลี่ยนสีวน
        bounce = int(abs(math.sin(t / 5.0)) * 10)                                # เด้งขึ้นลง 10 px
        self.win.geometry(f"+{self.state['x']}+{self.state['y'] - bounce}")
        self.state["anim"] = self.root.after(70, self._animate)

    def _hwnd(self):
        if self.state["hwnd"] is None:
            try:
                self.state["hwnd"] = make_noactivate(self.win.winfo_id())
            except Exception:
                self.state["hwnd"] = 0
        return self.state["hwnd"]

    def show(self, x, y):
        if not self.float_var.get() or self.worker["busy"]:
            return
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        w = h = self.SIZE
        px, py = min(x + 14, sw - w - 4), min(y + 18, sh - h - 4)
        self.state["x"], self.state["y"] = px, py
        self.win.geometry(f"+{px}+{py}"); self.win.deiconify(); self.win.lift(); self.win.attributes("-topmost", True)
        self._hwnd()
        self.state["shown_at"] = time.time()
        if self.state["timer"]:
            self.root.after_cancel(self.state["timer"])
        self.state["timer"] = self.root.after(5000, self.hide)
        if not self.state["anim"]:
            self._animate()

    def hide(self):
        if self.state["timer"]:
            self.root.after_cancel(self.state["timer"]); self.state["timer"] = None
        if self.state["anim"]:
            self.root.after_cancel(self.state["anim"]); self.state["anim"] = None
        self.win.withdraw()

    def maybe_hide(self):
        """เรียกจาก pump() เมื่อ mouse hook รายงานว่าคลิกนอกไอคอน - ซ่อนเฉพาะถ้าโชว์มาแล้วสักพัก
        (กันกรณีเพิ่งคลิกไอคอนเอง event คลิกเดียวกันมาถึง pump ช้ากว่าแล้วไปซ่อนไอคอนที่เพิ่งโชว์)"""
        if self.win.state() != "withdrawn" and time.time() - self.state["shown_at"] > 0.3:
            self.hide()

    def _clicked(self, _=None):
        self.hide()
        threading.Thread(target=lambda: (send_ctrl_c(), time.sleep(0.25), self.q.put(("hotkey",))),
                         daemon=True).start()

    def is_own_window(self, fg_hwnd, x, y):
        """คลิกในหน้าต่างโปรแกรมเราหรือบนไอคอนลอยเอง ไม่ต้องแสดงไอคอน"""
        try:
            user32 = ctypes.windll.user32
            ours = user32.GetAncestor(self.root.winfo_id(), GA_ROOT)
            if fg_hwnd == ours:
                return True
            if self.win.state() != "withdrawn":
                fx, fy = self.win.winfo_rootx(), self.win.winfo_rooty()
                if fx - 2 <= x <= fx + self.win.winfo_width() + 2 and fy - 2 <= y <= fy + self.win.winfo_height() + 2:
                    return True
        except Exception:
            pass
        return False
