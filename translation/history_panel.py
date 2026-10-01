#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
history_panel.py - แผงประวัติการแปล (ซ่อน/โชว์ได้ใต้กล่องข้อความ) รายการที่แปลไปแล้ว
ดับเบิลคลิกรายการเพื่อโหลดกลับเข้าช่องต้นทาง/ปลายทาง

แยกออกจาก run_gui() เพราะเป็นบล็อกแยกชัดเจน (สร้างแผงของตัวเอง มีสถานะเปิด/ปิดเป็นของ
ตัวเอง) จุดเชื่อมกับส่วนอื่นมีแค่: ปุ่ม "ประวัติ" ที่ถูกสร้างไว้ก่อนแล้วในแถบหัว (ตำแหน่งปุ่ม
มีผลต่อลำดับการจัดวาง จึงยังสร้างที่ translator.py เหมือนเดิม แล้วส่งเข้ามาให้ผูก command),
ตัวแปร history/save_history ที่ workflow การแปลหลักใช้ร่วมกัน, และ notify_new_entry() ที่
เรียกหลังแปลเสร็จแต่ละครั้งเพื่อรีเฟรชแผงถ้าเปิดอยู่
"""
import tkinter as tk
from tkinter import ttk

from engine import LEVELS


class HistoryPanel:
    def __init__(self, root, btn, bottom_box, small_font, history, src, dst):
        self.root = root
        self.btn = btn
        self.bottom_box = bottom_box
        self.history = history
        self.src = src
        self.dst = dst
        self.shown = False

        self.btn.config(command=self.toggle)

        self.frame = ttk.Frame(root, padding=(10, 0, 10, 6))
        self.list = tk.Listbox(self.frame, height=6, font=small_font, activestyle="none")
        self.list.pack(side="left", fill="both", expand=True)
        hsb = ttk.Scrollbar(self.frame, command=self.list.yview); hsb.pack(side="right", fill="y")
        self.list.config(yscrollcommand=hsb.set)
        self.list.bind("<Double-Button-1>", self._load_item)

    def refresh(self):
        self.list.delete(0, "end")
        for h in reversed(self.history[-60:]):
            s = h["src"].replace("\n", " ")[:60]; d = h["dst"].replace("\n", " ")[:60]
            self.list.insert("end", f"[{LEVELS.get(h.get('level'), LEVELS['general'])['label']}] {s}  →  {d}")

    def toggle(self):
        self.shown = not self.shown
        if self.shown:
            self.refresh()
            self.frame.pack(side="bottom", fill="x", padx=10, pady=(0, 6), before=self.bottom_box)
            self.btn.config(text="ประวัติ ▴")
        else:
            self.frame.pack_forget(); self.btn.config(text="ประวัติ ▾")

    def _load_item(self, _=None):
        sel = self.list.curselection()
        if not sel:
            return
        h = list(reversed(self.history[-60:]))[sel[0]]
        self.src.delete("1.0", "end"); self.src.insert("1.0", h["src"])
        self.dst.delete("1.0", "end"); self.dst.insert("1.0", h["dst"])

    def notify_new_entry(self):
        """เรียกจาก workflow การแปลหลัก หลังมีการแปลใหม่ถูกบันทึกลง history - รีเฟรชถ้าแผงเปิดอยู่"""
        if self.shown:
            self.refresh()
