#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
flow_layout.py - เฟรมจัดวิดเจ็ตแบบไหล (flow layout) สำหรับ tkinter: เรียงซ้ายไปขวา
เต็มความกว้างแล้วขึ้นบรรทัดใหม่เอง ใช้แทน pack/grid ตรงๆ เพื่อไม่ให้ปุ่มหลุดขอบ
เมื่อย่อ/ขยายหน้าต่าง แยกออกจาก translator.py เพราะไม่มีสถานะร่วมกับ GUI ส่วนอื่นเลย
"""
import tkinter as tk
from tkinter import ttk


class Flow(ttk.Frame):
    """เฟรมจัดวิดเจ็ตแบบไหล: เรียงซ้ายไปขวา เต็มความกว้างแล้วขึ้นบรรทัดใหม่"""
    def __init__(self, master, padding=(0, 0, 0, 0), **kw):
        super().__init__(master, **kw)
        p = padding if isinstance(padding, (tuple, list)) else (padding,) * 4
        self.pad = (p + p)[:4] if len(p) < 4 else tuple(p[:4])     # (ซ้าย, บน, ขวา, ล่าง)
        self.items = []; self._pending = None; self._last = None
        self.bind("<Configure>", lambda e: self.schedule())
        master.bind("<Configure>", lambda e: self.schedule(), add="+")

    def add(self, w, padx=(0, 6), pady=(0, 4)):
        self.items.append((w, padx, pady)); self.schedule(); return w

    def clear(self):
        for w, _, _ in self.items:
            w.destroy()
        self.items = []; self._last = None

    def schedule(self):
        if self._pending is None:
            self._pending = self.after_idle(self.relayout)

    def relayout(self):
        """วางด้วย place ทีละชิ้น (ไม่ใช้ grid เพราะคอลัมน์จะยืดตามชิ้นที่กว้างสุด ทำให้ตำแหน่งจริงล้นขอบ)"""
        self._pending = None
        top = self.winfo_toplevel()
        if top.winfo_width() < 50:
            return
        # พื้นที่ที่ใช้ได้ = ขอบขวาของหน้าต่าง - ตำแหน่งซ้ายของเฟรมนี้ (พาเรนต์อาจ "ขอ" กว้างเกินหน้าต่าง จึงไม่ใช้ความกว้างพาเรนต์)
        width = top.winfo_width() - (self.winfo_rootx() - top.winfo_rootx()) - 20 - self.pad[0] - self.pad[2]
        if self.winfo_width() > 50:
            width = min(width, self.winfo_width() - self.pad[0] - self.pad[2])
        x = y = row_h = 0; plan = []
        for w, padx, pady in self.items:
            rw, rh = w.winfo_reqwidth(), w.winfo_reqheight()
            need = rw + padx[0] + padx[1]
            if x > 0 and x + need > width:
                x = 0; y += row_h; row_h = 0
            plan.append((w, self.pad[0] + x + padx[0], self.pad[1] + y + pady[0]))
            x += need; row_h = max(row_h, rh + pady[0] + pady[1])
        total_h = self.pad[1] + y + row_h + self.pad[3]
        key = (tuple((id(w), px, py) for w, px, py in plan), total_h)
        if key == self._last:
            return
        self._last = key
        for w, px, py in plan:
            w.place(x=px, y=py)
        self.configure(height=total_h)
