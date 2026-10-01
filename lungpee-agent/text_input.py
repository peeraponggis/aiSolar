#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
text_input.py - หน้าต่างพิมพ์ถามลุงพีแบบค้างอยู่ตลอด (persistent) ไม่ใช่ป๊อปอัปที่ปิดตัวเองทันที
ที่ถามเสร็จ - ผู้ใช้ขอให้ "ขึ้นค้างไว้เลย" หลังเห็นว่าป๊อปอัปแบบเดิมปิดไปทันทีหลังถามแต่ละครั้ง

ใช้พิมพ์แทนการพูดได้ตลอดเวลา (ไม่ต้องรอให้ถอดเสียงล้มเหลวก่อน) อยู่มุมขวาล่างจอ เหนือ
อวตาร (avatar.py) ขึ้นไปหน่อยไม่ให้ซ้อนกัน กด "ซ่อน" เพื่อซ่อนชั่วคราวได้ กดจากเมนูถาดระบบ/
ตอนถอดเสียงล้มเหลวเพื่อเรียกกลับมา (โชว์พร้อมข้อความคำแนะนำที่ต่างกันไปตามสถานการณ์)
"""
import tkinter as tk


class TextInputPopup:
    def __init__(self, root, on_submit):
        self.root = root
        self.on_submit = on_submit

        self.win = tk.Toplevel(root)
        self.win.title("พิมพ์ถามลุงพี")
        self.win.attributes("-topmost", True)
        self.win.resizable(False, False)
        self.win.protocol("WM_DELETE_WINDOW", self.hide)   # กดปิดมุมขวาบน = แค่ซ่อน ไม่ทำลายหน้าต่างทิ้ง

        body = tk.Frame(self.win, padx=14, pady=12)
        body.pack()
        self.hint_var = tk.StringVar(value="พิมพ์คำถามหรือคำสั่งถึงลุงพีได้เลยครับ")
        tk.Label(body, textvariable=self.hint_var, font=("Segoe UI", 10), wraplength=360, justify="left").pack(anchor="w")
        self.text_var = tk.StringVar()
        self.entry = tk.Entry(body, textvariable=self.text_var, font=("Segoe UI", 11), width=42)
        self.entry.pack(pady=(8, 10), fill="x")

        btns = tk.Frame(body)
        btns.pack(fill="x")
        tk.Button(btns, text="ถาม", command=self._submit, width=10).pack(side="left")
        tk.Button(btns, text="ซ่อน", command=self.hide, width=10).pack(side="left", padx=(8, 0))

        self.entry.bind("<Return>", lambda e: self._submit())
        # Tkinter Entry รองรับ Ctrl+C/V/X (copy/paste/cut) อยู่แล้วโดยปริยาย แต่ไม่มี Ctrl+A
        # (select all) มาให้ - ต้อง bind เพิ่มเอง ไม่งั้นกด Ctrl+A แล้วจะไม่มีอะไรเกิดขึ้น
        self.entry.bind("<Control-a>", self._select_all)
        self.entry.bind("<Control-A>", self._select_all)
        self._position()

    def _select_all(self, event):
        self.entry.select_range(0, "end")
        self.entry.icursor("end")
        return "break"   # กัน Entry วิ่งพิมพ์ตัว "a" ทับที่เลือกไว้ซ้ำ

    def _position(self):
        self.win.update_idletasks()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        w, h = self.win.winfo_reqwidth(), self.win.winfo_reqheight()
        self.win.geometry(f"+{sw - w - 24}+{sh - h - 280}")   # มุมขวาล่าง เหนืออวตารขึ้นไปหน่อยไม่ให้ซ้อนกัน

    def _submit(self):
        text = self.text_var.get().strip()
        if not text:
            return
        self.text_var.set("")
        self.on_submit(text)

    def set_hint(self, text):
        self.hint_var.set(text)

    def show(self, hint=None):
        if hint:
            self.set_hint(hint)
        self._position()
        self.win.deiconify()
        self.win.lift()
        self.entry.focus_set()

    def hide(self):
        self.win.withdraw()
