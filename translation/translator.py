#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Local Translator - โปรแกรมช่วยแปลบนเดสก์ท็อป ใช้โมเดลในเครื่องผ่าน Ollama
โมเดลหลัก: scb10x/typhoon2.5-qwen3-4b (ไทย-อังกฤษ, รัน 100% บน GPU 4GB)

เปิดด้วยทางลัด "แปลภาษา Local" (เรียก LocalTranslator.exe) หรือรันจากซอร์สโค้ด:
    python translator.py                       เปิดหน้าต่างโปรแกรม (เปิด Ollama ให้เองถ้ายังไม่ทำงาน)
    python translator.py --cli "ข้อความ"        แปลใน console (ทดสอบ)
    python translator.py --cli --level engineering --to en "ข้อความ"

    python translator.py --minimized            เปิดแบบย่อหน้าต่าง (ใช้กับ Startup)

ฟีเจอร์: เลือกระดับการแปล 6 แบบ, ตรวจภาษาต้นทางอัตโนมัติ, สตรีมคำแปล,
ไอคอนลอยเมื่อลากคลุมข้อความในโปรแกรมใดก็ได้ (คลิกแล้วแปลทันที),
คีย์ลัด Ctrl+Alt+T, เฝ้าคลิปบอร์ด, พจนานุกรมศัพท์ glossary.txt, ประวัติ history.json,
เสียงอ่านคำแปล (edge-tts เปรมวดี/นิวัฒน์ + ตารางคำอ่าน + โคลนเสียง จากโปรเจกต์ F:/LocalAI/yt)
"""
import argparse
import ctypes
import json
import logging
import math
import os
import queue
import re
import sys
import threading
import time
import urllib.error
import urllib.request

FROZEN = bool(getattr(sys, "frozen", False))          # รันจาก exe ที่สร้างด้วย PyInstaller
BASE = os.path.dirname(sys.executable) if FROZEN else os.path.dirname(os.path.abspath(__file__))
log = logging.getLogger(__name__)

# ---------------------------------------------------------------- โมดูลย่อย (แยกจาก translator.py)
from app_log import setup_logging
from autostart import autostart_enabled, set_autostart as _set_autostart
from flow_layout import Flow
from clipboard_hotkey import ClipboardHotkey
from edit_bindings import setup_edit_bindings
from float_icon import FloatIcon
from history_panel import HistoryPanel
from model_connection import ModelConnection
from provider_dialog import open_provider_dialog
from qa_panel import QAPanel
from replacements_dialog import open_replacements_dialog
from speech_controller import SpeechController
from engine import (
    DEFAULT_QUESTIONS, GLOSSARY_FILE, HISTORY_FILE,
    LANGS, LEVEL_ORDER, LEVELS, MAX_HISTORY, SETTINGS_FILE,
    build_messages, chat_stream, clean_output, detect_lang,
    glossary_for, load_glossary, run_cli,
)
from tts_engine import (
    TTS_RATES, TTS_VOICES, Player,
    apply_replacements, list_clone_profiles, load_replacements,
    sapi_synthesize, tts_synthesize,
)
from win_hooks import KEYEVENTF_KEYUP, VK_MENU, win_event_thread

# ---------------------------------------------------------------- GUI
MUTEX_NAME = "Local\\ThaiLocalTranslator.single"


def acquire_single_instance():
    """กันเปิดซ้อนหลายชุด (ทำให้ไอคอนลอยหลายตัวและเสียงอ่านซ้อนกัน) ถ้ามีอยู่แล้วให้ดึงหน้าต่างเดิมขึ้นมาแทน"""
    k32 = ctypes.windll.kernel32
    k32.CreateMutexW.restype = ctypes.c_void_p
    handle = k32.CreateMutexW(None, False, MUTEX_NAME)
    if k32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        u = ctypes.windll.user32
        u.FindWindowW.restype = ctypes.c_void_p
        h = u.FindWindowW(None, "Local Translator - แปลภาษาด้วยโมเดลในเครื่อง")
        if h:
            u.ShowWindow(ctypes.c_void_p(h), 9)
            u.keybd_event(VK_MENU, 0, 0, 0); u.SetForegroundWindow(ctypes.c_void_p(h)); u.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
        return False
    return handle


def run_gui(minimized=False):
    import tkinter as tk
    from tkinter import ttk, font as tkfont, messagebox

    if not acquire_single_instance():
        return

    # ให้พิกัดของ mouse hook (พิกเซลจริง) ตรงกับพิกัดของ Tk บนจอที่ตั้ง scaling 125/150%
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    root = tk.Tk()
    try:
        root.tk.call("tk", "scaling", ctypes.windll.user32.GetDpiForSystem() / 72.0)
    except Exception:
        pass
    root.title("Local Translator - แปลภาษาด้วยโมเดลในเครื่อง")
    root.geometry("1240x800")
    root.minsize(720, 520)
    for ico in (os.path.join(BASE, "translator.ico"), os.path.join(BASE, "..", "lung_pee.ico")):
        try:
            root.iconbitmap(ico); break
        except Exception:
            continue

    fams = set(tkfont.families())
    fam = next((f for f in ("Sarabun", "Leelawadee UI", "Segoe UI", "Tahoma") if f in fams), "TkDefaultFont")
    ui_font = (fam, 11)
    text_font = (fam, 13)
    small_font = (fam, 9)
    root.option_add("*Font", ui_font)
    style = ttk.Style(root)
    try:
        style.theme_use("vista")
    except Exception:
        pass
    style.configure("TButton", padding=(10, 5))
    style.configure("Big.TButton", padding=(16, 8), font=(fam, 11, "bold"))

    # ---------- state
    settings = {"level": "general", "direction": "auto", "topmost": False, "clipwatch": False, "model": "",
                "floaticon": True, "autospeak": False, "ttsVoice": "เปรมวดี (หญิง)", "ttsRate": "ปกติ",
                "questions": list(DEFAULT_QUESTIONS), "qaOpen": False, "qaAutoSpeak": False,
                "api": {"mode": "auto", "preset": "OpenTyphoon (SCB10X, ปรับจูนภาษาไทย - แนะนำ)", "base": "", "key": "", "model": ""}}
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            settings.update(json.load(f))
    except FileNotFoundError:
        pass
    except Exception:
        log.warning("อ่าน settings.json ไม่ได้ (%s) - ใช้ค่าเริ่มต้นแทน", SETTINGS_FILE, exc_info=True)
    if not isinstance(settings.get("questions"), list):
        settings["questions"] = list(DEFAULT_QUESTIONS)
    settings["questions"] = [str(x).strip() for x in settings["questions"] if str(x).strip()]
    history = []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)
    except FileNotFoundError:
        pass
    except Exception:
        log.warning("อ่าน history.json ไม่ได้ (%s) - เริ่มประวัติใหม่", HISTORY_FILE, exc_info=True)
    glossary = load_glossary()
    q = queue.Queue()
    worker = {"thread": None, "stop": threading.Event(), "busy": False}
    st = {"models": [], "model": "", "last_result": "", "last_clip": None, "hotkey_ok": None}

    def save_settings():
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(settings, f, ensure_ascii=False, indent=1)
        except Exception:
            log.warning("บันทึก settings.json ไม่ได้ (%s)", SETTINGS_FILE, exc_info=True)

    def save_history():
        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(history[-MAX_HISTORY:], f, ensure_ascii=False, indent=1)
        except Exception:
            log.warning("บันทึก history.json ไม่ได้ (%s)", HISTORY_FILE, exc_info=True)

    # ---------- เปิดอัตโนมัติเมื่อเปิดเครื่อง (ดู autostart.py)
    def set_autostart(enable):
        _set_autostart(enable, FROZEN, BASE, os.path.abspath(__file__), set_status)

    # ==================== เลย์เอาต์มาตรฐาน ====================
    # หลักการ: (1) ทุกแถวปุ่ม/ตัวเลือกใช้ Flow = ไหลลงบรรทัดใหม่เมื่อความกว้างไม่พอ ไม่มีปุ่มถูกตัด
    #          (2) แถบสถานะ แถวปุ่ม และแผงถามโมเดล จองพื้นที่ด้านล่างก่อน ช่องข้อความรับพื้นที่ที่เหลือ
    #          (3) ส่วน "ตัวเลือก" และ "ถามโมเดล" ย่อ/ขยายได้ด้วยปุ่มของตัวเอง โปรแกรมจำสถานะไว้
    # (Flow อยู่ใน flow_layout.py - import ไว้ด้านบนของไฟล์)

    # ---------- แถบสถานะ (จองที่ล่างสุดก่อนทุกส่วน)
    status_bar = Flow(root, padding=(10, 2, 10, 6)); status_bar.pack(fill="x", side="bottom")
    status_var = tk.StringVar(value="กำลังเชื่อมต่อ Ollama ...")
    status_bar.add(ttk.Label(status_bar, textvariable=status_var, font=small_font, foreground="#444"), padx=(0, 20))
    hotkey_var = tk.StringVar(value="")
    status_bar.add(ttk.Label(status_bar, textvariable=hotkey_var, font=small_font, foreground="#0E6B5B"))

    def set_status(msg):
        status_var.set(msg)

    # กล่องล่าง = แถวปุ่มหลัก + แผงถามโมเดล จองพื้นที่ต่อจากแถบสถานะ (ช่องข้อความเป็นส่วนเดียวที่หดเมื่อหน้าต่างเล็ก)
    bottom_box = ttk.Frame(root); bottom_box.pack(side="bottom", fill="x")

    # ---------- แถวหัว: ย่อ/ขยายตัวเลือก · สรุประดับที่เลือก · ประวัติ · glossary
    hdr = Flow(root, padding=(10, 6, 10, 0)); hdr.pack(fill="x", before=bottom_box)   # ลำดับจองพื้นที่: แถบสถานะ, แถวหัว, กล่องล่าง(ปุ่ม+ถามโมเดล), ตัวเลือก, ช่องข้อความ(หดได้)
    opts_btn = ttk.Button(hdr, text="▾ ตัวเลือก", command=lambda: toggle_opts()); hdr.add(opts_btn)
    level_summary = tk.StringVar()
    hdr.add(ttk.Label(hdr, textvariable=level_summary, font=small_font, foreground="#555"), padx=(0, 16))
    hist_btn = ttk.Button(hdr, text="ประวัติ ▾"); hdr.add(hist_btn)  # command ผูกใน HistoryPanel ด้านล่าง
    hdr.add(ttk.Button(hdr, text="glossary", command=lambda: os.startfile(GLOSSARY_FILE) if os.path.exists(GLOSSARY_FILE) else None))
    hdr.add(ttk.Button(hdr, text="🔊 คำอ่านภาษาอังกฤษ",
                       command=lambda: open_replacements_dialog(root, fam, small_font, st)))
    hdr.add(ttk.Button(hdr, text="⚙ ผู้ให้บริการ", command=lambda: show_provider_dialog()), padx=(12, 6))

    # ---------- ส่วนตัวเลือก (ย่อ/ขยายได้)
    opts = ttk.Frame(root, padding=(10, 2, 10, 2))
    lf = ttk.LabelFrame(opts, text=" ระดับการแปล ", padding=(8, 2)); lf.pack(fill="x")
    lvl_flow = Flow(lf); lvl_flow.pack(fill="x")
    level_var = tk.StringVar(value=settings["level"] if settings["level"] in LEVELS else "general")
    for key in LEVEL_ORDER:
        lvl_flow.add(ttk.Radiobutton(lvl_flow, text=LEVELS[key]["label"], value=key, variable=level_var,
                                     command=lambda: (settings.update(level=level_var.get()), save_settings(), show_desc())), padx=(0, 14))
    desc_var = tk.StringVar()
    desc_lbl = ttk.Label(lf, textvariable=desc_var, font=small_font, foreground="#555", wraplength=900, justify="left"); desc_lbl.pack(anchor="w")
    lf.bind("<Configure>", lambda e: desc_lbl.configure(wraplength=max(300, e.width - 30)))

    def show_desc():
        desc_var.set(LEVELS[level_var.get()]["desc"])
        level_summary.set("ระดับ: " + LEVELS[level_var.get()]["label"])
    show_desc()

    row2 = Flow(opts); row2.pack(fill="x", pady=(4, 0))
    f_dir = ttk.Frame(row2); ttk.Label(f_dir, text="ทิศทาง:").pack(side="left")
    DIRS = [("auto", "ตรวจอัตโนมัติ (ไทย ⇄ อังกฤษ)"), ("th2en", "ไทย → อังกฤษ"), ("en2th", "อังกฤษ → ไทย")]
    dir_var = tk.StringVar(value=dict(DIRS).get(settings["direction"], DIRS[0][1]))
    dir_cb = ttk.Combobox(f_dir, textvariable=dir_var, values=[d[1] for d in DIRS], state="readonly", width=26); dir_cb.pack(side="left", padx=(4, 0))
    dir_cb.bind("<<ComboboxSelected>>", lambda e: (settings.update(direction=next(k for k, v in DIRS if v == dir_var.get())), save_settings()))
    row2.add(f_dir, padx=(0, 16))
    f_model = ttk.Frame(row2); ttk.Label(f_model, text="โมเดล:").pack(side="left")
    model_var = tk.StringVar(value="กำลังเชื่อมต่อ Ollama...")
    model_cb = ttk.Combobox(f_model, textvariable=model_var, state="readonly", width=36); model_cb.pack(side="left", padx=(4, 0))
    row2.add(f_model)

    # ---------- เชื่อมต่อ/สลับเส้นทางโมเดล (ดู model_connection.py) - สร้างจริงทีหลังหลัง start_translate
    # ถูกนิยามแล้ว (ใช้ใน on_ready callback ของ TRANSLATOR_SPEAK_DEMO)

    row3 = Flow(opts); row3.pack(fill="x", pady=(2, 0))
    topmost_var = tk.BooleanVar(value=settings["topmost"])
    clip_var = tk.BooleanVar(value=settings["clipwatch"])
    float_var = tk.BooleanVar(value=settings["floaticon"])
    auto_var = tk.BooleanVar(value=autostart_enabled())

    def apply_topmost():
        root.attributes("-topmost", topmost_var.get()); settings["topmost"] = topmost_var.get(); save_settings()
    row3.add(ttk.Checkbutton(row3, text="อยู่บนสุดเสมอ", variable=topmost_var, command=apply_topmost), padx=(0, 12))
    row3.add(ttk.Checkbutton(row3, text="เฝ้าคลิปบอร์ด (แปลเองทุกครั้งที่กด Ctrl+C)", variable=clip_var,
                             command=lambda: (settings.update(clipwatch=clip_var.get()), save_settings())), padx=(0, 12))
    row3.add(ttk.Checkbutton(row3, text="ไอคอนลอยเมื่อลากคลุมข้อความ (คลิกไอคอนแล้วแปล)", variable=float_var,
                             command=lambda: (settings.update(floaticon=float_var.get()), save_settings())), padx=(0, 12))
    row3.add(ttk.Checkbutton(row3, text="เปิดอัตโนมัติเมื่อเปิดเครื่อง", variable=auto_var,
                             command=lambda: set_autostart(auto_var.get())))

    def toggle_opts(force=None):
        want = (not settings.get("optsOpen", True)) if force is None else force
        settings["optsOpen"] = want; save_settings()
        if want:
            opts.pack(fill="x", after=bottom_box); opts_btn.config(text="▴ ตัวเลือก")   # อยู่ใต้แถวหัว แต่จองพื้นที่หลังกล่องล่าง (หน้าต่างเตี้ยจะหดตัวเลือกก่อนปุ่มหลัก)
        else:
            opts.pack_forget(); opts_btn.config(text="▾ ตัวเลือก")
    toggle_opts(settings.get("optsOpen", True))

    # ---------- แถวปุ่มหลัก (จองที่ด้านล่าง เหนือแถบสถานะ ไหลลงบรรทัดใหม่ได้)
    btns = Flow(bottom_box, padding=(10, 6, 10, 2)); btns.pack(fill="x")
    translate_btn = ttk.Button(btns, text="แปล  (Ctrl+Enter)", style="Big.TButton", command=lambda: start_translate()); btns.add(translate_btn)
    stop_btn = ttk.Button(btns, text="หยุด", command=lambda: (worker["stop"].set(), speech.stop_speech(), set_status("หยุดแล้ว"))); btns.add(stop_btn)  # หยุดทั้งการแปลและเสียงอ่าน ใช้ได้ตลอด
    btns.add(ttk.Button(btns, text="แปลอีกสำนวน", command=lambda: start_translate(variant=True)))
    btns.add(ttk.Button(btns, text="⇄ สลับ", command=lambda: swap()))
    btns.add(ttk.Button(btns, text="วาง+แปล", command=lambda: clip_hotkey.paste_and_translate()))
    btns.add(ttk.Button(btns, text="คัดลอก", command=lambda: clip_hotkey.copy_result()))
    btns.add(ttk.Button(btns, text="ล้าง", command=lambda: (src.delete("1.0", "end"), dst.delete("1.0", "end"))))
    # ปุ่ม "ถามโมเดล" ถูกสร้างโดย QAPanel เอง (ดูด้านล่าง หลังจากสร้าง src/dst/worker/st/q ครบ)

    # ---------- ช่องข้อความซ้าย-ขวา (รับพื้นที่ที่เหลือ ลากเส้นแบ่งกลางได้)
    pane = ttk.PanedWindow(root, orient="horizontal"); pane.pack(fill="both", expand=True, padx=10, pady=(4, 0))
    left = ttk.Frame(pane, padding=(0, 0, 4, 0)); right = ttk.Frame(pane, padding=(4, 0, 0, 0))
    pane.add(left, weight=1); pane.add(right, weight=1)

    src_lbl = tk.StringVar(value="ข้อความต้นทาง")
    ttk.Label(left, textvariable=src_lbl, font=(fam, 10, "bold")).pack(anchor="w")
    src = tk.Text(left, wrap="word", font=text_font, undo=True, padx=8, pady=6, relief="solid", borderwidth=1, height=3, width=20)
    src.pack(fill="both", expand=True)
    dst_lbl = tk.StringVar(value="คำแปล")
    ttk.Label(right, textvariable=dst_lbl, font=(fam, 10, "bold")).pack(anchor="w")
    tts_row = Flow(right, padding=(0, 6, 0, 0)); tts_row.pack(side="bottom", fill="x")   # แถวเสียงอยู่ใต้ช่องคำแปลเสมอ
    dst = tk.Text(right, wrap="word", font=text_font, padx=8, pady=6, relief="solid", borderwidth=1, background="#F7F8F4", height=3, width=20)
    dst.pack(fill="both", expand=True)
    dst.tag_configure("speaking", background="#FFE58A")

    # ---------- แถวเสียงอ่าน (ฟังก์ชันจากโปรเจกต์ yt)
    tts_row.add(ttk.Button(tts_row, text="🔊 อ่านคำแปล", command=lambda: speech.speak_text(dst.get("1.0", "end"), highlight=True)), padx=(0, 4))
    tts_row.add(ttk.Button(tts_row, text="⏹", width=3, command=lambda: speech.stop_speech()), padx=(0, 8))
    voice_names = list(TTS_VOICES.keys())
    clone_profiles = list_clone_profiles()
    voice_names += [f"โคลน: {p.get('name', p['id'])}" for p in clone_profiles]
    clone_ids = {f"โคลน: {p.get('name', p['id'])}": p["id"] for p in clone_profiles}
    tts_voice_var = tk.StringVar(value=settings["ttsVoice"] if settings["ttsVoice"] in voice_names else voice_names[0])
    vcb = ttk.Combobox(tts_row, textvariable=tts_voice_var, values=voice_names, state="readonly", width=15); tts_row.add(vcb, padx=(0, 4))
    vcb.bind("<<ComboboxSelected>>", lambda e: (settings.update(ttsVoice=tts_voice_var.get()), save_settings(), speech.warm_up()))
    tts_rate_var = tk.StringVar(value=settings["ttsRate"] if settings["ttsRate"] in TTS_RATES else "ปกติ")
    rcb = ttk.Combobox(tts_row, textvariable=tts_rate_var, values=list(TTS_RATES.keys()), state="readonly", width=7); tts_row.add(rcb)
    rcb.bind("<<ComboboxSelected>>", lambda e: (settings.update(ttsRate=tts_rate_var.get()), save_settings()))
    autospeak_var = tk.BooleanVar(value=settings["autospeak"])
    tts_row.add(ttk.Checkbutton(tts_row, text="อ่านอัตโนมัติ", variable=autospeak_var,
                                command=lambda: (settings.update(autospeak=autospeak_var.get()), save_settings())))

    # ---------- history panel แบบซ่อน/โชว์ได้ (ดู history_panel.py)
    history_panel = HistoryPanel(root, hist_btn, bottom_box, small_font, history, src, dst)

    # ==================== Q&A: ถามโมเดลเกี่ยวกับข้อความหลังแปล (ดู qa_panel.py) ====================
    # สร้างจริงหลัง speech (SpeechController) ถูกสร้างแล้ว (ดูท้ายฟังก์ชัน หลังบล็อกเสียงอ่าน)

    # ---------- actions
    def current_direction(text):
        d = settings["direction"]
        if d == "th2en":
            return "th", "en"
        if d == "en2th":
            return "en", "th"
        s = detect_lang(text)
        return s, ("en" if s == "th" else "th")

    def start_translate(variant=False, text=None):
        if worker["busy"]:
            return
        if text is None:
            text = src.get("1.0", "end").strip()
        if not text:
            set_status("กรุณาใส่ข้อความก่อน"); return
        if not st["model"]:
            set_status("ยังไม่ได้เชื่อมต่อโมเดล - กด ⚙ ผู้ให้บริการ เพื่อดาวน์โหลดโมเดล หรือกด F5 แล้วลองใหม่"); return
        s, d = current_direction(text)
        level = level_var.get()
        hits = glossary_for(text, s, level, glossary)
        msgs = build_messages(text, s, d, level, hits, variant)
        src_lbl.set(f"ข้อความต้นทาง ({LANGS[s]})"); dst_lbl.set(f"คำแปล ({LANGS[d]})")
        dst.delete("1.0", "end")
        speech.stop_speech()
        qa_panel.clear()               # ข้อความใหม่ -> ล้างบทสนทนาถาม-ตอบเดิม
        if autospeak_var.get():
            speech.stream_speak_begin(d)      # อ่านประโยคแรกทันทีที่แปลเสร็จ ไม่ต้องรอทั้งหมด
        last_src["text"] = text        # จำข้อความที่กำลังแปล ถ้าต้นทางเปลี่ยนไปจากนี้จะล้างกล่องแปล/คำตอบ
        worker["stop"].clear(); worker["busy"] = True
        translate_btn.state(["disabled"]); stop_btn.state(["!disabled"])
        set_status(f"กำลังแปล {LANGS[s]} → {LANGS[d]} · {LEVELS[level]['label']}" + (f" · glossary {len(hits)} คำ" if hits else "") + " ...")
        temp = LEVELS[level]["temp"] + (0.35 if variant else 0)

        def job():
            t0 = time.time(); buf = []; stats = {}
            try:
                gen = chat_stream(st["model"], msgs, temp, worker["stop"])
                while True:
                    try:
                        piece = next(gen)
                    except StopIteration as e:
                        stats = e.value or {}; break
                    buf.append(piece); q.put(("piece", piece))
                q.put(("done", "".join(buf), stats, time.time() - t0, text, level))
            except Exception as e:
                log.exception("แปลผิดพลาด (model=%s, level=%s)", st["model"], level)
                q.put(("error", str(e)))
        worker["thread"] = threading.Thread(target=job, daemon=True); worker["thread"].start()

    def finish(result, stats, elapsed, text, level):
        result = clean_output(result)
        if dst.get("1.0", "end-1c") != result:   # เขียนใหม่เฉพาะเมื่อต่างจริง ไม่งั้นไฮไลท์ท่อนที่กำลังอ่านจะหาย
            dst.delete("1.0", "end"); dst.insert("1.0", result)
        st["last_result"] = result
        if result and not worker["stop"].is_set():
            history.append({"ts": time.strftime("%Y-%m-%d %H:%M"), "level": level, "src": text, "dst": result})
            save_history()
            history_panel.notify_new_entry()
        ev, ed = stats.get("eval_count") or 0, stats.get("eval_duration") or 0
        speed = f" · {ev/(ed/1e9):.1f} tok/s" if ed else ""
        set_status(("หยุดแล้ว" if worker["stop"].is_set() else "แปลเสร็จ") + f" · {elapsed:.1f} วินาที{speed} · {st['model']}")
        if st.get("demo_t0"):
            print(f"[demo] {time.time() - st['demo_t0']:5.1f}s  แปลเสร็จ ({elapsed:.1f}s{speed})", file=sys.stderr, flush=True)
        qa_demo = os.environ.get("TRANSLATOR_QA_DEMO")
        if qa_demo and not st.get("qa_demo_done"):   # สำหรับทดสอบ: ถามคำถามนี้ทันทีหลังแปลเสร็จ
            st["qa_demo_done"] = True
            root.after(500, lambda: qa_panel.ask(qa_demo))
        if worker["stop"].is_set():
            speech.stop_speech()
        else:
            speech.stream_speak_end(result)

    # ---------- ไฮไลท์ท่อนที่กำลังอ่านในกล่องคำแปล: ค้นข้อความของท่อนต่อจากท่อนก่อนหน้า (ไม่ใช้ตำแหน่งตายตัว
    # เพราะข้อความในกล่องอาจถูกเขียนใหม่ตอนแปลจบ) ถ้าไม่เจอทั้งท่อนให้ลองด้วย 20 ตัวอักษรแรก
    speak_hl = {"pos": "1.0"}

    def on_speaking(snippet):
        dst.tag_remove("speaking", "1.0", "end")
        if not snippet:
            speak_hl["pos"] = "1.0"; return
        for probe in (snippet, snippet[:20]):
            start = dst.search(probe, speak_hl["pos"], stopindex="end") or dst.search(probe, "1.0", stopindex="end")
            if start:
                end = f"{start}+{len(snippet)}c"
                dst.tag_add("speaking", start, end)
                speak_hl["pos"] = end
                if not worker["busy"]:
                    dst.see(start)
                return

    # ---------- เสียงอ่าน: แบ่งท่อน สร้างขนาน เล่นทันทีที่ท่อนแรกเสร็จ (ดู speech_controller.py)
    speech = SpeechController(q, set_status, tts_voice_var, tts_rate_var, clone_ids, st, on_speaking=on_speaking)

    qa_panel = QAPanel(root, btns, bottom_box, settings, save_settings, set_status,
                       text_font, small_font, worker, st, src, dst, q, speech.speak_text, speech.stop_speech)

    # ---------- ไอคอนลอยเมื่อเลือกข้อความ: พื้นโปร่งใส เด้งขึ้นลง เปลี่ยนสีวน (ดู float_icon.py)
    float_icon = FloatIcon(root, BASE, fam, q, worker, float_var)

    def pump():
        try:
            while True:
                item = q.get_nowait()
                kind = item[0]
                if kind == "piece":
                    dst.insert("end", item[1]); dst.see("end")
                    if item[1]:
                        speech.stream_speak_piece(item[1])
                elif kind == "done":
                    worker["busy"] = False; translate_btn.state(["!disabled"])
                    finish(*item[1:])
                elif kind == "error":
                    worker["busy"] = False; translate_btn.state(["!disabled"])
                    speech.stop_speech(); set_status("ผิดพลาด: " + item[1][:200])
                elif kind == "models":
                    model_conn.on_models(item[1])
                elif kind == "hotkey":
                    clip_hotkey.hotkey_captured()
                elif kind == "select":
                    float_icon.show(item[1], item[2])
                elif kind == "hide_float":
                    float_icon.maybe_hide()
                elif kind == "tts_event":
                    speech.on_tts_event(item[1], item[2])
                elif kind == "qa_piece":
                    qa_panel.on_piece(item[1])
                elif kind == "qa_done":
                    qa_panel.on_done(item[1], item[2], item[3])
                elif kind == "qa_error":
                    qa_panel.on_error(item[1])
                elif kind == "stt_recording":
                    qa_panel.on_stt_recording(item[1])
                elif kind == "stt_done":
                    qa_panel.on_stt_done(item[1])
                elif kind == "stt_error":
                    qa_panel.on_stt_error(item[1])
        except queue.Empty:
            pass
        root.after(60, pump)

    def swap():
        a = src.get("1.0", "end").strip(); b = dst.get("1.0", "end").strip()
        src.delete("1.0", "end"); dst.delete("1.0", "end")
        src.insert("1.0", b); dst.insert("1.0", a)

    # ---------- เฝ้าคลิปบอร์ด + คีย์ลัดทั่วเครื่อง (ดู clipboard_hotkey.py)
    clip_hotkey = ClipboardHotkey(root, st, src, dst, set_status, start_translate, worker,
                                  settings, clip_var, hotkey_var, topmost_var, q)

    def on_speak_demo_ready(models):
        """สำหรับทดสอบ: TRANSLATOR_SPEAK_DEMO=<ข้อความ> -> แปล + อ่านอัตโนมัติด้วยเสียงที่ระบุ"""
        demo_text = os.environ.get("TRANSLATOR_SPEAK_DEMO")
        if demo_text and not st.get("demo_started"):
            st["demo_started"] = True
            voice_pick = os.environ.get("TRANSLATOR_SPEAK_VOICE")

            def demo():
                if voice_pick and voice_pick in voice_names:
                    tts_voice_var.set(voice_pick); autospeak_var.set(True)   # ระบุเสียง = ทดสอบอ่านอัตโนมัติด้วย
                src.delete("1.0", "end"); src.insert("1.0", demo_text)
                st["demo_t0"] = time.time(); print("[demo] เริ่มแปล", file=sys.stderr, flush=True)
                start_translate()
            root.after(4000, demo)

    # ---------- เชื่อมต่อ/สลับเส้นทางโมเดล (ดู model_connection.py)
    model_conn = ModelConnection(root, settings, save_settings, st, worker, q, model_cb, model_var,
                                 set_status, on_ready=on_speak_demo_ready)
    connect = model_conn.connect

    # ---------- ⚙ ผู้ให้บริการ: ตั้งค่า API ออนไลน์สำรอง (ดู provider_dialog.py)
    def show_provider_dialog():
        open_provider_dialog(root, fam, small_font, settings, save_settings, connect)

    # ---------- คีย์ลัดแก้ไขข้อความทุกภาษาแป้นพิมพ์ + เมนูคลิกขวา (ดู edit_bindings.py)
    setup_edit_bindings(root)

    # ---------- bindings
    root.bind("<Control-Return>", lambda e: (start_translate(), "break"))
    src.bind("<Control-Return>", lambda e: (start_translate(), "break"))

    last_src = {"text": None}

    def on_src_modified(_=None):
        """ข้อความต้นทางเปลี่ยน (พิมพ์ วาง ไอคอนลอย คีย์ลัด) -> ล้างกล่องคำแปลและกล่องคำตอบของโมเดลทุกครั้ง"""
        if not src.edit_modified():
            return
        src.edit_modified(False)
        if worker["busy"]:
            return
        cur = src.get("1.0", "end").strip()
        if last_src["text"] is not None and cur != last_src["text"]:
            last_src["text"] = None
            dst.delete("1.0", "end"); qa_panel.clear()
            speech.stop_speech()
    src.bind("<<Modified>>", on_src_modified)
    root.bind("<Escape>", lambda e: worker["stop"].set())
    root.bind("<F5>", lambda e: connect())
    src.bind("<Control-a>", lambda e: (src.tag_add("sel", "1.0", "end"), "break"))
    dst.bind("<Control-a>", lambda e: (dst.tag_add("sel", "1.0", "end"), "break"))
    root.protocol("WM_DELETE_WINDOW", lambda: (worker["stop"].set(), speech.stop_speech(), save_settings(), root.destroy()))

    apply_topmost()
    connect()
    threading.Thread(target=win_event_thread, daemon=True,
                     args=(clip_hotkey.on_hotkey, lambda x, y: q.put(("select", x, y)), lambda: q.put(("hide_float",)),
                           float_icon.is_own_window, clip_hotkey.hotkey_status)).start()
    root.after(60, pump)
    root.after(1000, clip_hotkey.clip_poll)
    src.focus_set()
    root.after(300, lambda: pane.sashpos(0, root.winfo_width() // 2 - 10))  # แบ่งสองช่องเท่ากัน
    if settings.get("qaOpen"):
        root.after(400, lambda: qa_panel.toggle(True))
    if os.environ.get("TRANSLATOR_PROVIDER_DEMO"):   # สำหรับทดสอบ: เปิดหน้าต่างตั้งค่าผู้ให้บริการ
        root.after(2500, show_provider_dialog)
    if os.environ.get("TRANSLATOR_FLOAT_DEMO"):  # สำหรับทดสอบ: โชว์ไอคอนลอยกลางจอซ้ำทุก 4 วินาที
        print("float frames:", len(float_icon.frames), file=sys.stderr)

        def demo():
            float_icon.show(root.winfo_screenwidth() // 2, root.winfo_screenheight() // 2); root.after(4000, demo)
        root.after(1500, demo)
    if minimized:
        root.iconify()
    root.mainloop()


# ---------------------------------------------------------------- main
if __name__ == "__main__":
    setup_logging()
    ap = argparse.ArgumentParser(description="Local Translator (Ollama)")
    ap.add_argument("--cli", action="store_true", help="แปลใน console แทนหน้าต่าง")
    ap.add_argument("--level", choices=LEVEL_ORDER, default="general")
    ap.add_argument("--src", choices=["th", "en"])
    ap.add_argument("--to", choices=["th", "en"])
    ap.add_argument("--model")
    ap.add_argument("--minimized", action="store_true", help="เปิดแบบย่อหน้าต่าง (สำหรับ Startup)")
    ap.add_argument("--tts", metavar="TEXT", help="ทดสอบเสียงอ่าน: สังเคราะห์และเล่นข้อความนี้")
    ap.add_argument("--stt-selftest", action="store_true",
                    help="ทดสอบถอดเสียง: สังเคราะห์เสียงด้วย SAPI แล้วถอดกลับด้วย whisper (เช็กว่า build นี้ใช้งานได้)")
    ap.add_argument("--ask", metavar="QUESTION", help="(ใช้กับ --cli) ถามคำถามเกี่ยวกับข้อความหลังแปล")
    ap.add_argument("text", nargs="?")
    a = ap.parse_args()
    if a.cli:
        sys.exit(run_cli(a))
    if a.stt_selftest:
        import numpy as np
        from scipy.io import wavfile
        from scipy.signal import resample_poly
        from voice_input import SAMPLE_RATE, _get_model
        text = "ทดสอบระบบถอดเสียงภาษาไทย วันนี้อากาศเป็นอย่างไรบ้าง"
        wav = os.path.join(BASE, "_stt_selftest.wav")
        print("synthesizing with SAPI ..."); sapi_synthesize(text, "Pattara", "+0%", wav)
        rate, data = wavfile.read(wav)
        if data.ndim > 1:
            data = data.mean(axis=1)
        data = (data.astype(np.float32) / np.iinfo(data.dtype).max) if data.dtype.kind == "i" else data.astype(np.float32)
        if rate != SAMPLE_RATE:
            data = resample_poly(data, SAMPLE_RATE, rate).astype(np.float32)
        print("loading faster-whisper model (first run downloads ~500MB) ...")
        model = _get_model()
        segments, info = model.transcribe(data, language=None, vad_filter=True)
        out_text = "".join(s.text for s in segments).strip()
        print("ORIGINAL :", text)
        print("WHISPER  :", out_text)
        print("LANG     :", info.language, f"(p={info.language_probability:.2f})")
        try:
            os.remove(wav)
        except Exception:
            pass
        sys.exit(0)
    if a.tts:
        lang = detect_lang(a.tts)
        v = "th-TH-PremwadeeNeural" if lang == "th" else "en-US-JennyNeural"
        t = apply_replacements(a.tts, load_replacements()) if lang == "th" else a.tts
        p = tts_synthesize(t, v); print("audio:", p, os.path.getsize(p), "bytes")
        pl = Player(); pl.play(p)
        while pl.is_playing():
            time.sleep(0.2)
        pl.stop(); sys.exit(0)
    run_gui(minimized=a.minimized)
