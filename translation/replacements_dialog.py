#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
replacements_dialog.py - กล่องโต้ตอบจัดการ "คำแทนภาษาอังกฤษ -> คำอ่านไทย" สำหรับเสียงอ่าน (TTS)

แก้ปัญหาที่เสียงอ่าน (edge-tts/SAPI) อ่านตัวย่อภาษาอังกฤษเฉพาะทาง (เช่น ABAC, AAO, BOD5)
ไม่ถูกต้อง (พยายามสะกดทั้งคำแทนที่จะอ่านแบบถอดเสียง) ให้ผู้ใช้เพิ่ม/แก้/ลบคำอ่านเองได้ตรงๆ
เป็นหลัก - ปุ่ม "ให้ AI แนะนำ" ช่วยร่างคำอ่านเบื้องต้นจากโมเดลที่เชื่อมต่ออยู่เท่านั้น ไม่บันทึก
อัตโนมัติ ผู้ใช้ต้องตรวจ/แก้ก่อนกดบันทึกเสมอ (โมเดลอาจเดาผิดสำหรับคำเฉพาะทาง)

ไฟล์ดิกชันนารี (replacements.json) ใช้ร่วมกับโปรเจกต์ yt (ดู tts_engine.py's REPLACEMENTS_FILE)
อยู่แล้ว - แก้ที่นี่มีผลกับเสียงอ่านของทั้งสองโปรแกรม
"""
import json
import logging
import os
import threading
import tkinter as tk
from tkinter import ttk

from engine import chat_stream, clean_output
from tts_engine import REPLACEMENTS_FILE, load_replacements

log = logging.getLogger(__name__)


def save_replacements(data):
    os.makedirs(os.path.dirname(REPLACEMENTS_FILE), exist_ok=True)
    tmp = REPLACEMENTS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)
    os.replace(tmp, REPLACEMENTS_FILE)


def open_replacements_dialog(root, fam, small_font, st):
    data = load_replacements()
    dlg = tk.Toplevel(root); dlg.title("คำแทนภาษาอังกฤษ (English → Thai phonetic)")
    dlg.transient(root); dlg.grab_set()
    dlg.geometry("600x580")
    body = ttk.Frame(dlg, padding=12); body.pack(fill="both", expand=True)

    ttk.Label(body, text="คำแทนภาษาอังกฤษ → คำอ่านไทย (ใช้ตอนอ่านออกเสียงคำแปล)",
             font=(fam, 10, "bold")).pack(anchor="w")
    ttk.Label(body, text="แก้ไฟล์นี้มีผลกับเสียงอ่านของโปรแกรมนี้และโปรแกรม yt ด้วย (ใช้ไฟล์ร่วมกัน)",
             font=small_font, foreground="#777", wraplength=560, justify="left").pack(anchor="w", pady=(0, 8))

    list_frame = ttk.Frame(body); list_frame.pack(fill="both", expand=True)
    tree = ttk.Treeview(list_frame, columns=("en", "th"), show="headings", height=14)
    tree.heading("en", text="คำอังกฤษ"); tree.heading("th", text="คำอ่านไทย")
    tree.column("en", width=180); tree.column("th", width=340)
    tree.pack(side="left", fill="both", expand=True)
    sb = ttk.Scrollbar(list_frame, command=tree.yview); sb.pack(side="right", fill="y")
    tree.config(yscrollcommand=sb.set)

    def refresh():
        tree.delete(*tree.get_children())
        for en in sorted(data.keys(), key=str.lower):
            tree.insert("", "end", iid=en, values=(en, data[en]))
    refresh()

    row = ttk.Frame(body); row.pack(fill="x", pady=(8, 2))
    ttk.Label(row, text="คำอังกฤษ:").grid(row=0, column=0, sticky="w")
    en_var = tk.StringVar()
    ttk.Entry(row, textvariable=en_var, width=20).grid(row=0, column=1, padx=(4, 12))
    ttk.Label(row, text="คำอ่านไทย:").grid(row=0, column=2, sticky="w")
    th_var = tk.StringVar()
    ttk.Entry(row, textvariable=th_var, width=30).grid(row=0, column=3, padx=(4, 0))

    msg_var = tk.StringVar()
    ttk.Label(body, textvariable=msg_var, font=small_font, foreground="#0E6B5B").pack(anchor="w", pady=(4, 6))

    def on_select(_=None):
        sel = tree.selection()
        if sel:
            en_var.set(sel[0]); th_var.set(data[sel[0]])
    tree.bind("<<TreeviewSelect>>", on_select)

    def do_suggest():
        word = en_var.get().strip()
        if not word:
            msg_var.set("พิมพ์คำอังกฤษก่อน"); return
        if not st.get("model"):
            msg_var.set("ยังไม่ได้เชื่อมต่อโมเดล"); return
        suggest_btn.state(["disabled"]); msg_var.set("กำลังถามโมเดล ...")
        examples = list(data.items())[:8]
        ex_text = "\n".join(f"{e} -> {t}" for e, t in examples)
        prompt = ("ต่อไปนี้คือตัวอย่างคำอังกฤษกับคำอ่านไทยแบบถอดเสียง (ใช้ขีด - คั่นพยางค์):\n" + ex_text +
                 f"\n\nช่วยถอดเสียงคำว่า \"{word}\" เป็นคำอ่านไทยแบบเดียวกัน "
                 "ตอบคำอ่านไทยคำเดียวเท่านั้น ห้ามอธิบายเพิ่ม ห้ามใส่เครื่องหมายคำพูด")
        model = st["model"]

        def job():
            try:
                buf = []
                gen = chat_stream(model, [{"role": "user", "content": prompt}], 0.2)
                while True:
                    try:
                        piece = next(gen)
                    except StopIteration:
                        break
                    buf.append(piece)
                out = clean_output("".join(buf)).strip().strip('"').strip("'").split("\n")[0]
                dlg.after(0, lambda: (th_var.set(out),
                                      msg_var.set("ตรวจคำอ่านที่แนะนำก่อนกด '+ เพิ่ม/บันทึก'"),
                                      suggest_btn.state(["!disabled"])))
            except Exception as e:
                log.exception("ขอคำแนะนำคำอ่านผิดพลาด (model=%s)", model)
                dlg.after(0, lambda: (msg_var.set("ขอคำแนะนำไม่สำเร็จ: " + str(e)[:160]),
                                      suggest_btn.state(["!disabled"])))
        threading.Thread(target=job, daemon=True).start()

    def do_add():
        en = en_var.get().strip(); th = th_var.get().strip()
        if not en or not th:
            msg_var.set("กรอกทั้งคำอังกฤษและคำอ่านไทยก่อน"); return
        data[en] = th
        try:
            save_replacements(data)
        except Exception as e:
            log.warning("บันทึก replacements.json ไม่ได้ (%s)", REPLACEMENTS_FILE, exc_info=True)
            msg_var.set("บันทึกไม่สำเร็จ: " + str(e)[:160]); return
        refresh(); msg_var.set(f"บันทึก: {en} -> {th}")

    def do_delete():
        sel = tree.selection()
        if not sel:
            msg_var.set("เลือกรายการที่จะลบก่อน"); return
        en = sel[0]
        data.pop(en, None)
        try:
            save_replacements(data)
        except Exception as e:
            log.warning("บันทึก replacements.json ไม่ได้ (%s)", REPLACEMENTS_FILE, exc_info=True)
            msg_var.set("บันทึกไม่สำเร็จ: " + str(e)[:160]); return
        refresh(); en_var.set(""); th_var.set(""); msg_var.set(f"ลบ: {en}")

    btns = ttk.Frame(body); btns.pack(fill="x", pady=(4, 0))
    suggest_btn = ttk.Button(btns, text="✨ ให้ AI แนะนำคำอ่าน", command=do_suggest); suggest_btn.pack(side="left")
    ttk.Button(btns, text="+ เพิ่ม/บันทึก", command=do_add).pack(side="left", padx=(8, 0))
    ttk.Button(btns, text="ลบรายการที่เลือก", command=do_delete).pack(side="left", padx=(8, 0))
    ttk.Button(btns, text="ปิด", command=dlg.destroy).pack(side="right")
    dlg.update_idletasks()
    dlg.geometry(f"+{root.winfo_rootx() + 60}+{root.winfo_rooty() + 60}")
