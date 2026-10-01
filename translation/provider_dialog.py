#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
provider_dialog.py - กล่องโต้ตอบ "⚙ ผู้ให้บริการ": เลือกเส้นทางแปล (ในเครื่อง/API ออนไลน์/อัตโนมัติ),
ตั้งค่า API ที่รองรับรูปแบบ OpenAI (base URL/คีย์/โมเดล) พร้อมปุ่มทดสอบ และดาวน์โหลด/ติดตั้ง
โมเดลในเครื่องผ่าน Ollama จากในแอปโดยตรง

แยกออกจาก run_gui() เพราะเป็นหน้าต่างลอย (Toplevel) ที่มีสถานะของตัวเองครบในตัว ไม่แตะ
ตัวแปรของหน้าต่างหลักเลย ยกเว้นตอนบันทึก/ดาวน์โหลดเสร็จที่ต้องเรียก connect() ให้โปรแกรม
หลักเชื่อมต่อใหม่ (ส่งเข้ามาเป็น callback)
"""
import logging
import threading
import time
import tkinter as tk
import webbrowser
from tkinter import ttk

from engine import (
    API_PRESETS, DEFAULT_MODEL, clean_output, find_ollama_exe, list_models,
    list_models_openai, pull_model, stream_chat_openai,
)

log = logging.getLogger(__name__)


def open_provider_dialog(root, fam, small_font, settings, save_settings, connect):
    a = dict(settings.get("api") or {})
    dlg = tk.Toplevel(root); dlg.title("ผู้ให้บริการโมเดล"); dlg.transient(root); dlg.grab_set(); dlg.resizable(False, False)
    body = ttk.Frame(dlg, padding=14); body.pack(fill="both", expand=True)
    ttk.Label(body, text="เส้นทางที่ใช้แปล", font=(fam, 10, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 4))
    mode_var = tk.StringVar(value=a.get("mode", "auto"))
    mf = ttk.Frame(body); mf.grid(row=1, column=0, columnspan=3, sticky="w")
    for val, txt in (("auto", "อัตโนมัติ: ใช้โมเดลในเครื่อง ถ้าไม่มีให้ใช้ API"), ("local", "ในเครื่องเท่านั้น (Ollama)"), ("api", "API ออนไลน์เท่านั้น")):
        ttk.Radiobutton(mf, text=txt, value=val, variable=mode_var).pack(anchor="w")
    ttk.Separator(body).grid(row=2, column=0, columnspan=3, sticky="ew", pady=10)
    ttk.Label(body, text="ผู้ให้บริการ (API รูปแบบ OpenAI)", font=(fam, 10, "bold")).grid(row=3, column=0, sticky="w", pady=(0, 4))
    preset_var = tk.StringVar(value=a.get("preset") if a.get("preset") in API_PRESETS else list(API_PRESETS)[0])
    preset_cb = ttk.Combobox(body, textvariable=preset_var, values=list(API_PRESETS), state="readonly", width=52)
    preset_cb.grid(row=4, column=0, columnspan=3, sticky="w")
    note_var = tk.StringVar(); ttk.Label(body, textvariable=note_var, font=small_font, foreground="#555", wraplength=520, justify="left").grid(row=5, column=0, columnspan=3, sticky="w", pady=(2, 6))
    ttk.Label(body, text="Base URL:").grid(row=6, column=0, sticky="w")
    base_var = tk.StringVar(value=a.get("base", "")); ttk.Entry(body, textvariable=base_var, width=52).grid(row=6, column=1, columnspan=2, sticky="w", pady=2)
    ttk.Label(body, text="API key:").grid(row=7, column=0, sticky="w")
    key_var = tk.StringVar(value=a.get("key", "")); key_ent = ttk.Entry(body, textvariable=key_var, width=52, show="•"); key_ent.grid(row=7, column=1, columnspan=2, sticky="w", pady=2)
    show_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(body, text="แสดงคีย์", variable=show_var, command=lambda: key_ent.config(show="" if show_var.get() else "•")).grid(row=8, column=1, sticky="w")
    link = ttk.Label(body, text="", foreground="#1a5fb4", cursor="hand2", font=small_font); link.grid(row=8, column=2, sticky="w")
    ttk.Label(body, text="โมเดล:").grid(row=9, column=0, sticky="w")
    model_v = tk.StringVar(value=a.get("model", ""))
    mcb = ttk.Combobox(body, textvariable=model_v, width=40); mcb.grid(row=9, column=1, sticky="w", pady=2)
    msg_var = tk.StringVar(); ttk.Label(body, textvariable=msg_var, font=small_font, foreground="#0E6B5B", wraplength=520, justify="left").grid(row=11, column=0, columnspan=3, sticky="w", pady=(6, 0))

    def apply_preset(_=None):
        p = API_PRESETS[preset_var.get()]
        if p["base"]:
            base_var.set(p["base"])
        mcb["values"] = p["models"]
        if p["models"] and (not model_v.get() or model_v.get() not in p["models"] and a.get("preset") != preset_var.get()):
            model_v.set(p["models"][0])
        note_var.set(p["note"])
        link.config(text=("สมัคร/ขอคีย์: " + p["signup"]) if p["signup"] else "")
        link.bind("<Button-1>", lambda e, u=p["signup"]: webbrowser.open(u) if u else None)
    preset_cb.bind("<<ComboboxSelected>>", apply_preset); apply_preset()

    def load_models():
        if not (base_var.get().strip() and key_var.get().strip()):
            msg_var.set("ใส่ Base URL และ API key ก่อน"); return
        msg_var.set("กำลังโหลดรายการโมเดล ...")

        def job():
            try:
                ids = list_models_openai(base_var.get().strip(), key_var.get().strip())
                dlg.after(0, lambda: (mcb.configure(values=ids), msg_var.set(f"โหลดได้ {len(ids)} โมเดล เลือกจากรายการได้")))
            except Exception as e:
                log.warning("โหลดรายการโมเดลจาก %s ไม่ได้", base_var.get().strip(), exc_info=True)
                dlg.after(0, lambda: msg_var.set("โหลดรายการไม่ได้: " + str(e)[:160]))
        threading.Thread(target=job, daemon=True).start()
    ttk.Button(body, text="โหลดรายการโมเดล", command=load_models).grid(row=9, column=2, sticky="w", padx=(6, 0))

    def test_api():
        b, k, m = base_var.get().strip(), key_var.get().strip(), model_v.get().strip()
        if not (b and k and m):
            msg_var.set("ใส่ Base URL, API key และโมเดลให้ครบก่อน"); return
        msg_var.set("กำลังทดสอบ ...")

        def job():
            try:
                t0 = time.time()
                out = "".join(stream_chat_openai(b, k, m, [{"role": "user", "content": "แปลเป็นอังกฤษ: สวัสดี ตอบเฉพาะคำแปล"}], 0.2))
                dlg.after(0, lambda: msg_var.set(f"สำเร็จใน {time.time()-t0:.1f} วินาที · ตอบว่า: {clean_output(out)[:80]}"))
            except Exception as e:
                log.warning("ทดสอบ API %s (โมเดล %s) ไม่ผ่าน", b, m, exc_info=True)
                dlg.after(0, lambda: msg_var.set("ทดสอบไม่ผ่าน: " + str(e)[:200]))
        threading.Thread(target=job, daemon=True).start()

    def save():
        settings["api"] = {"mode": mode_var.get(), "preset": preset_var.get(), "base": base_var.get().strip(),
                           "key": key_var.get().strip(), "model": model_v.get().strip()}
        save_settings(); dlg.destroy(); connect()
    # ---- โมเดลในเครื่อง: ดาวน์โหลดผ่าน Ollama จากในแอป (สำหรับเครื่องที่ติดตั้งแล้วยังไม่มีโมเดล)
    ttk.Separator(body).grid(row=14, column=0, columnspan=3, sticky="ew", pady=10)
    ttk.Label(body, text="โมเดลในเครื่อง (Ollama)", font=(fam, 10, "bold")).grid(row=15, column=0, sticky="w", pady=(0, 4))
    local_info = tk.StringVar()
    ttk.Label(body, textvariable=local_info, font=small_font, foreground="#555", wraplength=520, justify="left").grid(row=16, column=0, columnspan=3, sticky="w")
    ttk.Label(body, text="ชื่อโมเดล:").grid(row=17, column=0, sticky="w")
    pull_v = tk.StringVar(value=DEFAULT_MODEL)
    pull_cb = ttk.Combobox(body, textvariable=pull_v, width=40, values=[DEFAULT_MODEL, "scb10x/llama3.2-typhoon2-3b-instruct", "maternion/spark-x2.5:4b-q4_K_M", "qwen2.5:7b-instruct"])
    pull_cb.grid(row=17, column=1, sticky="w", pady=2)
    pull_btn = ttk.Button(body, text="ดาวน์โหลด/ติดตั้ง"); pull_btn.grid(row=17, column=2, sticky="w", padx=(6, 0))
    pull_msg = tk.StringVar(); ttk.Label(body, textvariable=pull_msg, font=small_font, foreground="#0E6B5B", wraplength=520, justify="left").grid(row=18, column=0, columnspan=3, sticky="w", pady=(4, 0))

    def refresh_local_info():
        exe = find_ollama_exe(); ms = list_models()
        if ms is None:
            local_info.set(("พบ Ollama ที่ " + exe + " แต่เซิร์ฟเวอร์ยังไม่ทำงาน (กด F5 ในหน้าหลักเพื่อให้โปรแกรมเปิดให้)") if exe
                           else "ไม่พบ Ollama ในเครื่อง: ติดตั้งจาก https://ollama.com/download/windows หรือรัน Install-LocalTranslator.bat แล้วกลับมากดดาวน์โหลดที่นี่")
        else:
            local_info.set(f"Ollama ทำงานอยู่ · มีโมเดลในเครื่อง {len(ms)} ตัว" + (": " + ", ".join(ms[:4]) + (" ..." if len(ms) > 4 else "") if ms else " (ยังไม่มี) กดดาวน์โหลดด้านล่าง ~2.5 GB ต้องต่ออินเทอร์เน็ต"))
    refresh_local_info()

    def do_pull():
        name = pull_v.get().strip()
        if not name:
            return
        if list_models() is None:
            pull_msg.set("Ollama ยังไม่ทำงาน กด F5 ในหน้าหลักก่อน หรือติดตั้ง Ollama"); return
        pull_btn.state(["disabled"]); pull_msg.set(f"กำลังดาวน์โหลด {name} ...")

        def prog(status, pct, done, tot):
            txt = f"{status}" + (f" {pct}% ({done/1e9:.2f}/{tot/1e9:.2f} GB)" if pct is not None else "")
            dlg.after(0, lambda: pull_msg.set(txt))

        def job():
            try:
                pull_model(name, prog)
                dlg.after(0, lambda: (pull_msg.set(f"ติดตั้ง {name} เสร็จแล้ว โปรแกรมจะเชื่อมต่อใหม่"), refresh_local_info(), pull_btn.state(["!disabled"]), connect()))
            except Exception as e:
                log.warning("ดาวน์โหลดโมเดล %s ไม่สำเร็จ", name, exc_info=True)
                dlg.after(0, lambda: (pull_msg.set("ดาวน์โหลดไม่สำเร็จ: " + str(e)[:200]), pull_btn.state(["!disabled"])))
        threading.Thread(target=job, daemon=True).start()
    pull_btn.config(command=do_pull)

    bf = ttk.Frame(body); bf.grid(row=12, column=0, columnspan=3, sticky="e", pady=(12, 0))
    ttk.Button(bf, text="ทดสอบการเชื่อมต่อ", command=test_api).pack(side="left", padx=(0, 8))
    ttk.Button(bf, text="บันทึกและใช้งาน", style="Big.TButton", command=save).pack(side="left", padx=(0, 8))
    ttk.Button(bf, text="ยกเลิก", command=dlg.destroy).pack(side="left")
    ttk.Label(body, text="คีย์ถูกเก็บใน settings.json ข้างโปรแกรม (ไม่ส่งไปที่อื่นนอกจากผู้ให้บริการที่เลือก)", font=small_font, foreground="#777").grid(row=13, column=0, columnspan=3, sticky="w", pady=(8, 0))
    bf.grid_configure(row=19)   # แถวปุ่มบันทึกอยู่ล่างสุด ใต้ส่วนโมเดลในเครื่อง
    dlg.update_idletasks()
    dlg.geometry(f"+{root.winfo_rootx() + 80}+{root.winfo_rooty() + 80}")
