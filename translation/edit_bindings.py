#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
edit_bindings.py - คีย์ลัดแก้ไขข้อความ (วาง/คัดลอก/ตัด/เลือกทั้งหมด) ที่ใช้ได้ทุกภาษาแป้นพิมพ์
+ เมนูคลิกขวา บน Entry/Text/Combobox ทุกตัวในหน้าต่างหลัก

Tk ผูก Ctrl+V/C/X/A กับ "ตัวอักษร" v/c/x/a เมื่อแป้นพิมพ์อยู่ที่ภาษาไทย keysym เป็นอักษรไทย
จึงวาง/คัดลอกไม่ได้ แก้โดยดูรหัสปุ่มจริง (keycode 86=V 67=C 88=X 65=A) เฉพาะกรณีที่ keysym
ไม่ใช่อักษรละติน (ภาษาอังกฤษปล่อยให้ Tk จัดการเอง)

แยกออกจาก run_gui() เพราะไม่มีสถานะร่วมกับ GUI ส่วนอื่นเลย ใช้แค่ root.bind_all() ผูกกับ
ทุกวิดเจ็ตในหน้าต่างทันทีตอนเรียก setup_edit_bindings(root) ครั้งเดียว
"""
import tkinter as tk
from tkinter import ttk

EDIT_KEYS = {86: "<<Paste>>", 67: "<<Copy>>", 88: "<<Cut>>", 65: "<<SelectAll>>"}


def setup_edit_bindings(root):
    def ctrl_edit(event):
        w = event.widget
        if event.keysym.lower() in ("v", "c", "x", "a") or event.keycode not in EDIT_KEYS:
            return
        if not isinstance(w, (tk.Entry, ttk.Entry, tk.Text, ttk.Combobox)):
            return
        action = EDIT_KEYS[event.keycode]
        if action == "<<SelectAll>>":
            if isinstance(w, tk.Text):
                w.tag_add("sel", "1.0", "end")
            else:
                w.select_range(0, "end"); w.icursor("end")
        else:
            w.event_generate(action)
        return "break"
    root.bind_all("<Control-KeyPress>", ctrl_edit, add="+")

    edit_menu = tk.Menu(root, tearoff=0)
    edit_target = {"w": None}

    def menu_do(action):
        w = edit_target["w"]
        if w is None:
            return
        if action == "selectall":
            if isinstance(w, tk.Text):
                w.tag_add("sel", "1.0", "end")
            else:
                w.select_range(0, "end"); w.icursor("end")
        else:
            w.event_generate({"paste": "<<Paste>>", "copy": "<<Copy>>", "cut": "<<Cut>>"}[action])
    for label, act in (("วาง", "paste"), ("คัดลอก", "copy"), ("ตัด", "cut"), ("เลือกทั้งหมด", "selectall")):
        edit_menu.add_command(label=label, command=lambda a=act: menu_do(a))

    def show_edit_menu(event):
        w = event.widget
        if isinstance(w, (tk.Entry, ttk.Entry, tk.Text, ttk.Combobox)):
            edit_target["w"] = w; w.focus_set()
            try:
                edit_menu.tk_popup(event.x_root, event.y_root)
            finally:
                edit_menu.grab_release()
            return "break"
    root.bind_all("<Button-3>", show_edit_menu, add="+")
