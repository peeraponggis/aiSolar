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
    API_PRESETS, DEFAULT_MODEL, HUB_PRESETS, clean_output, env_key, find_ollama_exe, hub_add_provider, list_models, load_hub_presets, preset_nokey,
    list_models_openai, pull_model, stream_chat_openai,
)

log = logging.getLogger(__name__)


def open_provider_dialog(root, fam, small_font, settings, save_settings, connect):
    a = dict(settings.get("api") or {})
    load_hub_presets()   # รายการจากศูนย์ผู้ให้บริการล่าสุด (เผื่อเพิ่ม/แก้ใน Multi Tools ระหว่างเปิดโปรแกรม)
    dlg = tk.Toplevel(root); dlg.title("ผู้ให้บริการโมเดล"); dlg.transient(root); dlg.grab_set(); dlg.resizable(False, False)
    body = ttk.Frame(dlg, padding=14); body.pack(fill="both", expand=True)
    ttk.Label(body, text="เส้นทางที่ใช้แปล", font=(fam, 10, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 4))
    mode_var = tk.StringVar(value=a.get("mode", "auto"))
    mf = ttk.Frame(body); mf.grid(row=1, column=0, columnspan=3, sticky="w")
    for val, txt in (("auto", "อัตโนมัติ: ใช้ API ถ้าไม่มี (หรือ API ล้ม) ให้ใช้โมเดลในเครื่อง"), ("local", "ในเครื่องเท่านั้น (Ollama)"), ("api", "API ออนไลน์เท่านั้น")):
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
        if p.get("nokey"):
            key_var.set("")
            msg_var.set("ผู้ให้บริการนี้ไม่ใช้คีย์ — เว้นช่อง API key ว่างไว้")
        elif p.get("key_env"):
            if preset_var.get() != a.get("preset"):
                key_var.set("")   # ไม่ส่งคีย์ของผู้ให้บริการเดิมไปยังผู้ให้บริการนี้
            found = bool(env_key(p["key_env"]))
            msg_var.set(f"เว้นช่อง API key ว่างไว้ได้ · พบคีย์ในตัวแปร {p['key_env']} ✓" if found
                        else f"ไม่พบตัวแปร {p['key_env']} — ตั้งใน PowerShell: [Environment]::SetEnvironmentVariable('{p['key_env']}', 'คีย์', 'User') หรือกรอกคีย์ในช่องด้านบน")
        else:
            msg_var.set("")
    preset_cb.bind("<<ComboboxSelected>>", apply_preset); apply_preset()

    def current_key():
        return key_var.get().strip() or env_key(API_PRESETS[preset_var.get()].get("key_env"))

    def load_models():
        if not (base_var.get().strip() and (current_key() or preset_nokey(preset_var.get()))):
            msg_var.set("ใส่ Base URL และ API key ก่อน"); return
        msg_var.set("กำลังโหลดรายการโมเดล ...")

        def job():
            try:
                ids = list_models_openai(base_var.get().strip(), current_key())
                dlg.after(0, lambda: (mcb.configure(values=ids), msg_var.set(f"โหลดได้ {len(ids)} โมเดล เลือกจากรายการได้")))
            except Exception as e:
                log.warning("โหลดรายการโมเดลจาก %s ไม่ได้", base_var.get().strip(), exc_info=True)
                dlg.after(0, lambda: msg_var.set("โหลดรายการไม่ได้: " + str(e)[:160]))
        threading.Thread(target=job, daemon=True).start()
    ttk.Button(body, text="โหลดรายการโมเดล", command=load_models).grid(row=9, column=2, sticky="w", padx=(6, 0))

    def test_api():
        b, k, m = base_var.get().strip(), current_key(), model_v.get().strip()
        if not (b and (k or preset_nokey(preset_var.get())) and m):
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
    ttk.Label(body, text="คีย์ที่กรอกถูกเก็บใน settings.json ข้างโปรแกรม (ไม่ส่งไปที่อื่นนอกจากผู้ให้บริการที่เลือก) · เว้นว่างได้ถ้าผู้ให้บริการอ่านคีย์จากตัวแปร Windows", font=small_font, foreground="#777").grid(row=13, column=0, columnspan=3, sticky="w", pady=(8, 0))
    # ---- เพิ่มผู้ให้บริการเข้าศูนย์ผู้ให้บริการ (ทะเบียนกลางที่ ลุงพี AI / Multi Tools ใช้ร่วมกัน) — ปุ่มด่วนแบบหน้าตั้งค่าของ ลุงพี AI
    ttk.Separator(body).grid(row=20, column=0, columnspan=3, sticky="ew", pady=10)
    ttk.Label(body, text="เพิ่มผู้ให้บริการเข้าศูนย์ผู้ให้บริการ (ใช้ร่วมกับ ลุงพี AI / Multi Tools — คีย์เก็บในตัวแปร Windows)", font=(fam, 10, "bold")).grid(row=21, column=0, columnspan=3, sticky="w", pady=(0, 4))
    hb = ttk.Frame(body); hb.grid(row=22, column=0, columnspan=3, sticky="w")
    h_preset = tk.StringVar(value="")
    h_name, h_base, h_env, h_key = (tk.StringVar() for _ in range(4))
    hf = ttk.Frame(body); hf.grid(row=23, column=0, columnspan=3, sticky="w", pady=(6, 0))
    ttk.Label(hf, text="ชื่อ:").grid(row=0, column=0, sticky="w"); ttk.Entry(hf, textvariable=h_name, width=30).grid(row=0, column=1, sticky="w", padx=(4, 10))
    ttk.Label(hf, text="ตัวแปรคีย์:").grid(row=0, column=2, sticky="w"); ttk.Entry(hf, textvariable=h_env, width=22).grid(row=0, column=3, sticky="w", padx=4)
    ttk.Label(hf, text="Base URL:").grid(row=1, column=0, sticky="w"); ttk.Entry(hf, textvariable=h_base, width=30).grid(row=1, column=1, sticky="w", padx=(4, 10), pady=2)
    ttk.Label(hf, text="API key:").grid(row=1, column=2, sticky="w"); ttk.Entry(hf, textvariable=h_key, width=22, show="•").grid(row=1, column=3, sticky="w", padx=4, pady=2)
    h_msg = tk.StringVar(); ttk.Label(body, textvariable=h_msg, font=small_font, foreground="#0E6B5B", wraplength=520, justify="left").grid(row=24, column=0, columnspan=3, sticky="w", pady=(4, 0))
    hf.grid_remove()

    def pick_hub(key):
        p = HUB_PRESETS[key]; h_preset.set(key)
        h_name.set(p["name"]); h_base.set(p["base"]); h_env.set(p["key_env"]); h_key.set("")
        hf.grid()
        h_msg.set(("กรอก API key แล้วกด เพิ่ม" + (f" · สมัคร/ขอคีย์: {p['signup']}" if p["signup"] else "")) if key != "custom"
                  else "ใส่ชื่อ, Base URL ที่ลงท้าย /v1 และชื่อตัวแปรคีย์ (เว้นว่างถ้าบริการไม่ใช้คีย์)")

    def add_hub():
        try:
            label = hub_add_provider(h_preset.get(), h_name.get(), h_base.get(), h_env.get(), h_key.get())
        except Exception as e:
            h_msg.set("เพิ่มไม่สำเร็จ: " + str(e)[:200]); return
        h_key.set(""); hf.grid_remove()
        preset_cb["values"] = list(API_PRESETS); preset_var.set(label); apply_preset()
        h_msg.set(f"เพิ่ม {label} แล้ว — เลือกอยู่ในช่องผู้ให้บริการด้านบน กด 'โหลดรายการโมเดล' แล้วบันทึกและใช้งาน")
    for key, txt in (("openrouter", "＋ OpenRouter"), ("groq", "＋ Groq"), ("gemini", "＋ Gemini"), ("openai", "＋ OpenAI"), ("typhoon", "＋ OpenTyphoon"), ("custom", "＋ กำหนดเอง")):
        ttk.Button(hb, text=txt, command=lambda k=key: pick_hub(k)).pack(side="left", padx=(0, 6))
    ttk.Button(hf, text="เพิ่ม", command=add_hub).grid(row=0, column=4, rowspan=2, sticky="w", padx=(8, 0))
    bf.grid_configure(row=25)   # แถวปุ่มบันทึกอยู่ล่างสุด
    dlg.update_idletasks()
    dlg.geometry(f"+{root.winfo_rootx() + 80}+{root.winfo_rooty() + 80}")
