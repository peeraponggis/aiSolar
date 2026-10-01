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
from flow_layout import Flow
from qa_panel import QAPanel
from engine import (
    API_PRESETS, BACKEND, DEFAULT_MODEL, DEFAULT_QUESTIONS, GLOSSARY_FILE, HISTORY_FILE,
    HOTKEY_LABEL, LANGS, LEVEL_ORDER, LEVELS, MAX_HISTORY, SETTINGS_FILE,
    build_messages, chat_stream, clean_output, detect_lang,
    ensure_ollama, find_ollama_exe, glossary_for, list_models, list_models_openai,
    load_glossary, pick_model, pull_model, run_cli, stream_chat_openai, warm_up,
)
from tts_engine import (
    EN_VOICES, TTS_RATES, TTS_TMP, TTS_VOICES, Player, TtsPipeline,
    apply_replacements, clean_for_tts, list_clone_profiles, load_replacements,
    pop_sentences, split_tts_chunks, tts_synthesize,
)
from win_hooks import (
    GA_ROOT, KEYEVENTF_KEYUP, VK_MENU,
    build_float_frames, make_noactivate, send_ctrl_c, win_event_thread,
)

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

    # ---------- เปิดอัตโนมัติเมื่อเปิดเครื่อง (ทางลัดในโฟลเดอร์ Startup)
    def startup_lnk():
        return os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs", "Startup", "Local Translator.lnk")

    def autostart_enabled():
        return os.path.exists(startup_lnk())

    def set_autostart(enable):
        import subprocess
        lnk = startup_lnk()
        if not enable:
            try:
                os.remove(lnk)
            except Exception:
                pass
            set_status("ยกเลิกเปิดอัตโนมัติแล้ว"); return
        if FROZEN:
            target, args = sys.executable, "--minimized"
        else:
            # รันจากซอร์สโค้ด (ไม่มี Translate.bat แล้ว): เปิดด้วย pythonw.exe ตรง ๆ ไม่มีหน้าต่างคอนโซล
            pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
            target = pyw if os.path.exists(pyw) else sys.executable
            args = f'"{os.path.abspath(__file__)}" --minimized'
        ps = (f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{lnk}');$s.TargetPath='{target}';$s.Arguments='{args}';"
              f"$s.WorkingDirectory='{BASE}';$s.IconLocation='{os.path.join(BASE, 'translator.ico')},0';$s.WindowStyle=7;"
              f"$s.Description='Local Translator autostart';$s.Save()")
        try:
            subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, timeout=30,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            set_status("ตั้งเปิดอัตโนมัติเมื่อเปิดเครื่องแล้ว (Startup)" if os.path.exists(lnk) else "สร้างทางลัด Startup ไม่สำเร็จ")
        except Exception as e:
            log.warning("สร้างทางลัด Startup ไม่สำเร็จ", exc_info=True)
            set_status("สร้างทางลัด Startup ไม่สำเร็จ: " + str(e))

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
    hist_btn = ttk.Button(hdr, text="ประวัติ ▾", command=lambda: toggle_history()); hdr.add(hist_btn)
    hdr.add(ttk.Button(hdr, text="glossary", command=lambda: os.startfile(GLOSSARY_FILE) if os.path.exists(GLOSSARY_FILE) else None))
    hdr.add(ttk.Button(hdr, text="⚙ ผู้ให้บริการ", command=lambda: open_provider_dialog()), padx=(12, 6))

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

    API_TAG = "☁ "   # รายการโมเดลออนไลน์ในช่องโมเดลขึ้นต้นด้วยเครื่องหมายนี้

    def api_configured():
        a = settings.get("api") or {}
        return bool(a.get("base") and a.get("key") and a.get("model"))

    def use_backend(mode):
        """สลับเส้นทางที่ใช้จริง: 'local' หรือ 'api'"""
        a = settings.get("api") or {}
        BACKEND.update(mode=mode, base=a.get("base", ""), key=a.get("key", ""), model=a.get("model", ""))
        st["backend"] = mode
        if mode == "api":
            st["model"] = a.get("model", "")   # ให้ปุ่มแปล/ถามผ่านการตรวจ "มีโมเดล" (chat_stream ใช้ BACKEND['model'] เอง)

    def on_model_change(_=None):
        name = model_var.get()
        if name.startswith(API_TAG):
            use_backend("api"); settings["model"] = name; save_settings()
            set_status(f"ใช้โมเดลออนไลน์ {BACKEND['model']} ผ่าน API"); return
        use_backend("local")
        st["model"] = name; settings["model"] = name; save_settings()
        threading.Thread(target=warm_up, args=(st["model"],), daemon=True).start()
        set_status(f"กำลังโหลด {st['model']} เข้า GPU ...")
    model_cb.bind("<<ComboboxSelected>>", on_model_change)

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
    stop_btn = ttk.Button(btns, text="หยุด", command=lambda: (worker["stop"].set(), stop_speech(), set_status("หยุดแล้ว"))); btns.add(stop_btn)  # หยุดทั้งการแปลและเสียงอ่าน ใช้ได้ตลอด
    btns.add(ttk.Button(btns, text="แปลอีกสำนวน", command=lambda: start_translate(variant=True)))
    btns.add(ttk.Button(btns, text="⇄ สลับ", command=lambda: swap()))
    btns.add(ttk.Button(btns, text="วาง+แปล", command=lambda: paste_and_translate()))
    btns.add(ttk.Button(btns, text="คัดลอก", command=lambda: copy_result()))
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

    # ---------- แถวเสียงอ่าน (ฟังก์ชันจากโปรเจกต์ yt)
    tts_row.add(ttk.Button(tts_row, text="🔊 อ่านคำแปล", command=lambda: speak_text(dst.get("1.0", "end"))), padx=(0, 4))
    tts_row.add(ttk.Button(tts_row, text="⏹", width=3, command=lambda: stop_speech()), padx=(0, 8))
    voice_names = list(TTS_VOICES.keys())
    clone_profiles = list_clone_profiles()
    voice_names += [f"โคลน: {p.get('name', p['id'])}" for p in clone_profiles]
    clone_ids = {f"โคลน: {p.get('name', p['id'])}": p["id"] for p in clone_profiles}
    tts_voice_var = tk.StringVar(value=settings["ttsVoice"] if settings["ttsVoice"] in voice_names else voice_names[0])
    vcb = ttk.Combobox(tts_row, textvariable=tts_voice_var, values=voice_names, state="readonly", width=15); tts_row.add(vcb, padx=(0, 4))
    vcb.bind("<<ComboboxSelected>>", lambda e: (settings.update(ttsVoice=tts_voice_var.get()), save_settings()))
    tts_rate_var = tk.StringVar(value=settings["ttsRate"] if settings["ttsRate"] in TTS_RATES else "ปกติ")
    rcb = ttk.Combobox(tts_row, textvariable=tts_rate_var, values=list(TTS_RATES.keys()), state="readonly", width=7); tts_row.add(rcb)
    rcb.bind("<<ComboboxSelected>>", lambda e: (settings.update(ttsRate=tts_rate_var.get()), save_settings()))
    autospeak_var = tk.BooleanVar(value=settings["autospeak"])
    tts_row.add(ttk.Checkbutton(tts_row, text="อ่านอัตโนมัติ", variable=autospeak_var,
                                command=lambda: (settings.update(autospeak=autospeak_var.get()), save_settings())))

    # ---------- history panel (ซ่อนได้)
    hist_frame = ttk.Frame(root, padding=(10, 0, 10, 6))
    hist_list = tk.Listbox(hist_frame, height=6, font=small_font, activestyle="none")
    hist_list.pack(side="left", fill="both", expand=True)
    hsb = ttk.Scrollbar(hist_frame, command=hist_list.yview); hsb.pack(side="right", fill="y")
    hist_list.config(yscrollcommand=hsb.set)
    hist_shown = {"on": False}

    def refresh_history():
        hist_list.delete(0, "end")
        for h in reversed(history[-60:]):
            s = h["src"].replace("\n", " ")[:60]; d = h["dst"].replace("\n", " ")[:60]
            hist_list.insert("end", f"[{LEVELS.get(h.get('level'), LEVELS['general'])['label']}] {s}  →  {d}")

    def toggle_history():
        hist_shown["on"] = not hist_shown["on"]
        if hist_shown["on"]:
            refresh_history(); hist_frame.pack(side="bottom", fill="x", padx=10, pady=(0, 6), before=bottom_box); hist_btn.config(text="ประวัติ ▴")
        else:
            hist_frame.pack_forget(); hist_btn.config(text="ประวัติ ▾")

    def load_history_item(_=None):
        sel = hist_list.curselection()
        if not sel:
            return
        h = list(reversed(history[-60:]))[sel[0]]
        src.delete("1.0", "end"); src.insert("1.0", h["src"])
        dst.delete("1.0", "end"); dst.insert("1.0", h["dst"])
    hist_list.bind("<Double-Button-1>", load_history_item)

    # ==================== Q&A: ถามโมเดลเกี่ยวกับข้อความหลังแปล (ดู qa_panel.py) ====================
    # สร้างจริงหลัง stop_speech()/speak_text() ถูกนิยามแล้ว (ดูท้ายฟังก์ชัน หลังบล็อกเสียงอ่าน)

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
        stop_speech()
        qa_panel.clear()               # ข้อความใหม่ -> ล้างบทสนทนาถาม-ตอบเดิม
        if autospeak_var.get():
            stream_speak_begin(d)      # อ่านประโยคแรกทันทีที่แปลเสร็จ ไม่ต้องรอทั้งหมด
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
        dst.delete("1.0", "end"); dst.insert("1.0", result)
        st["last_result"] = result
        if result and not worker["stop"].is_set():
            history.append({"ts": time.strftime("%Y-%m-%d %H:%M"), "level": level, "src": text, "dst": result})
            save_history()
            if hist_shown["on"]:
                refresh_history()
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
            stop_speech()
        else:
            stream_speak_end(result)

    # ---------- เสียงอ่าน: แบ่งท่อน สร้างขนาน เล่นทันทีที่ท่อนแรกเสร็จ (เสียงเก่าถูกหยุดก่อนเสมอ ไม่ซ้อนกัน)
    replacements = load_replacements()

    def cleanup_tts_tmp():
        """ลบไฟล์เสียงชั่วคราวที่เก่ากว่า 1 วัน"""
        try:
            cutoff = time.time() - 86400
            for f in os.listdir(TTS_TMP):
                p = os.path.join(TTS_TMP, f)
                if os.path.isfile(p) and os.path.getmtime(p) < cutoff:
                    os.remove(p)
        except Exception:
            pass
    threading.Thread(target=cleanup_tts_tmp, daemon=True).start()
    pipeline = TtsPipeline(lambda kind, msg: q.put(("tts_event", kind, msg)))

    speak = {"on": False, "buf": "", "lang": "th"}   # สถานะการอ่านแบบสตรีมระหว่างแปล

    def speech_config(lang):
        """เลือกเสียงตามภาษาของข้อความ (edge-tts ไม่ส่งเสียงถ้าเสียงกับภาษาไม่ตรงกัน) คืน (voice, rate, clone_id, ชื่อที่แสดง)"""
        name = tts_voice_var.get()
        clone_id = clone_ids.get(name)
        base_voice = TTS_VOICES.get(name, ("th-TH-PremwadeeNeural", "th"))[0] if not clone_id else "th-TH-NiwatNeural"
        voice = base_voice if lang == "th" else EN_VOICES.get(base_voice, "en-US-JennyNeural")
        return voice, TTS_RATES.get(tts_rate_var.get(), "+0%"), (clone_id if lang == "th" else None), name

    def feed_sentence(text, lang):
        text = clean_for_tts(text)
        if not text:
            return
        if lang == "th":
            text = apply_replacements(text, replacements)
        pipeline.feed(text)

    def speak_text(text):
        """ปุ่ม 🔊: อ่านทั้งข้อความ แบ่งเป็นประโยค เริ่มเล่นทันทีที่ประโยคแรกเสร็จ"""
        text = clean_for_tts(text or "")
        if not text:
            return
        stop_speech()
        lang = detect_lang(text)
        voice, rate, clone_id, name = speech_config(lang)
        pipeline.begin(voice, rate, clone_id)
        # เสียงโคลนใช้เวลาต่อครั้งนานมาก จึงส่งทั้งก้อนเดียว ส่วนเสียงปกติแบ่งประโยคเพื่อให้เริ่มได้เร็ว
        chunks = [text] if clone_id else split_tts_chunks(text)
        set_status(f"กำลังสร้างเสียง ({name}{' · โคลน' if clone_id else ''}) {len(chunks)} ท่อน ...")
        for c in chunks:
            feed_sentence(c, lang)
        pipeline.finish()

    def stream_speak_begin(lang):
        """เริ่มอ่านตั้งแต่ประโยคแรกที่แปลเสร็จ (เรียกตอนเริ่มแปล เมื่อเปิด 'อ่านอัตโนมัติ')"""
        voice, rate, clone_id, name = speech_config(lang)
        pipeline.begin(voice, rate, clone_id)
        speak.update(on=True, buf="", lang=lang, clone=bool(clone_id))

    def stream_speak_piece(piece):
        if not speak["on"]:
            return
        speak["buf"] += piece
        if speak["clone"]:
            return                                   # โคลน: รอจบแล้วอ่านทีเดียว
        sents, speak["buf"] = pop_sentences(speak["buf"])
        for s in sents:
            feed_sentence(s, speak["lang"])

    def stream_speak_end(full_text):
        if not speak["on"]:
            return
        speak["on"] = False
        if speak["clone"]:
            feed_sentence(clean_output(full_text), speak["lang"])
        else:
            sents, _ = pop_sentences(speak["buf"], final=True)
            for s in sents:
                feed_sentence(s, speak["lang"])
        speak["buf"] = ""
        pipeline.finish()

    def stop_speech():
        speak["on"] = False; speak["buf"] = ""
        pipeline.stop()

    qa_panel = QAPanel(root, btns, bottom_box, settings, save_settings, set_status,
                       text_font, small_font, worker, st, src, dst, q, speak_text, stop_speech)

    def on_tts_event(kind, msg):
        if st.get("demo_t0"):
            print(f"[demo] {time.time() - st['demo_t0']:5.1f}s  {kind}: {msg}", file=sys.stderr, flush=True)
        if kind == "status":
            set_status(msg)
        elif kind == "done":
            set_status(msg)
        elif kind == "error":
            set_status("เสียงอ่านไม่สำเร็จ: " + msg[:140])

    # ---------- ไอคอนลอยเมื่อเลือกข้อความ: พื้นโปร่งใส เด้งขึ้นลง เปลี่ยนสีวน
    FLOAT_KEY = "#010203"          # สีคีย์ที่ Windows ทำให้โปร่งใส
    FLOAT_SIZE, FLOAT_FRAMES = 56, 16
    frames = build_float_frames(FLOAT_SIZE, FLOAT_FRAMES, FLOAT_KEY)
    if not frames:
        try:
            frames = [tk.PhotoImage(file=os.path.join(BASE, "translator.png")).subsample(5)]
        except Exception:
            frames = []
    flt = tk.Toplevel(root); flt.title("translator-float-icon"); flt.overrideredirect(True); flt.attributes("-topmost", True); flt.withdraw()
    flt.configure(background=FLOAT_KEY)
    try:
        flt.attributes("-transparentcolor", FLOAT_KEY)
    except Exception:
        pass
    flt_btn = tk.Label(flt, image=frames[0] if frames else None, text="" if frames else "แปล", background=FLOAT_KEY,
                       foreground="#56E0D8", cursor="hand2", borderwidth=0, padx=0, pady=0, font=(fam, 10, "bold"))
    flt_btn.pack()
    flt_state = {"hwnd": None, "timer": None, "shown_at": 0, "anim": None, "x": 0, "y": 0, "tick": 0}

    def animate_float():
        if flt.state() == "withdrawn":
            flt_state["anim"] = None; return
        t = flt_state["tick"] = flt_state["tick"] + 1
        if frames:
            flt_btn.configure(image=frames[t % len(frames)])          # เปลี่ยนสีวน
        bounce = int(abs(math.sin(t / 5.0)) * 10)                        # เด้งขึ้นลง 10 px
        flt.geometry(f"+{flt_state['x']}+{flt_state['y'] - bounce}")
        flt_state["anim"] = root.after(70, animate_float)

    def float_hwnd():
        if flt_state["hwnd"] is None:
            try:
                flt_state["hwnd"] = make_noactivate(flt.winfo_id())
            except Exception:
                flt_state["hwnd"] = 0
        return flt_state["hwnd"]

    def show_float(x, y):
        if not float_var.get() or worker["busy"]:
            return
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        w = h = FLOAT_SIZE
        px, py = min(x + 14, sw - w - 4), min(y + 18, sh - h - 4)
        flt_state["x"], flt_state["y"] = px, py
        flt.geometry(f"+{px}+{py}"); flt.deiconify(); flt.lift(); flt.attributes("-topmost", True)
        float_hwnd()
        flt_state["shown_at"] = time.time()
        if flt_state["timer"]:
            root.after_cancel(flt_state["timer"])
        flt_state["timer"] = root.after(5000, hide_float)
        if not flt_state["anim"]:
            animate_float()

    def hide_float():
        if flt_state["timer"]:
            root.after_cancel(flt_state["timer"]); flt_state["timer"] = None
        if flt_state["anim"]:
            root.after_cancel(flt_state["anim"]); flt_state["anim"] = None
        flt.withdraw()

    def float_clicked(_=None):
        hide_float()
        threading.Thread(target=lambda: (send_ctrl_c(), time.sleep(0.25), q.put(("hotkey",))), daemon=True).start()
    flt_btn.bind("<Button-1>", float_clicked)

    def is_own_window(fg_hwnd, x, y):
        """คลิกในหน้าต่างโปรแกรมเราหรือบนไอคอนลอย ไม่ต้องแสดงไอคอน"""
        try:
            user32 = ctypes.windll.user32
            ours = user32.GetAncestor(root.winfo_id(), GA_ROOT)
            if fg_hwnd == ours:
                return True
            if flt.state() != "withdrawn":
                fx, fy = flt.winfo_rootx(), flt.winfo_rooty()
                if fx - 2 <= x <= fx + flt.winfo_width() + 2 and fy - 2 <= y <= fy + flt.winfo_height() + 2:
                    return True
        except Exception:
            pass
        return False


    def pump():
        try:
            while True:
                item = q.get_nowait()
                kind = item[0]
                if kind == "piece":
                    dst.insert("end", item[1]); dst.see("end")
                    if item[1]:
                        stream_speak_piece(item[1])
                elif kind == "done":
                    worker["busy"] = False; translate_btn.state(["!disabled"])
                    finish(*item[1:])
                elif kind == "error":
                    worker["busy"] = False; translate_btn.state(["!disabled"])
                    stop_speech(); set_status("ผิดพลาด: " + item[1][:200])
                elif kind == "models":
                    on_models(item[1])
                elif kind == "hotkey":
                    hotkey_captured()
                elif kind == "select":
                    show_float(item[1], item[2])
                elif kind == "hide_float":
                    if flt.state() != "withdrawn" and time.time() - flt_state["shown_at"] > 0.3:
                        hide_float()
                elif kind == "tts_event":
                    on_tts_event(item[1], item[2])
                elif kind == "qa_piece":
                    qa_panel.on_piece(item[1])
                elif kind == "qa_done":
                    qa_panel.on_done(item[1], item[2], item[3])
                elif kind == "qa_error":
                    qa_panel.on_error(item[1])
        except queue.Empty:
            pass
        root.after(60, pump)

    def swap():
        a = src.get("1.0", "end").strip(); b = dst.get("1.0", "end").strip()
        src.delete("1.0", "end"); dst.delete("1.0", "end")
        src.insert("1.0", b); dst.insert("1.0", a)

    def copy_result():
        r = dst.get("1.0", "end").strip()
        if r:
            root.clipboard_clear(); root.clipboard_append(r); st["last_clip"] = r
            set_status("คัดลอกคำแปลแล้ว")

    def read_clipboard():
        try:
            return root.clipboard_get()
        except Exception:
            return ""

    def paste_and_translate():
        t = read_clipboard().strip()
        if t:
            src.delete("1.0", "end"); src.insert("1.0", t); start_translate()

    def bring_to_front():
        root.deiconify(); root.lift(); root.attributes("-topmost", True)
        root.after(300, lambda: root.attributes("-topmost", topmost_var.get())); root.focus_force()

    def hotkey_captured():
        t = read_clipboard().strip()
        if t and t != st["last_result"]:
            src.delete("1.0", "end"); src.insert("1.0", t)
            bring_to_front(); start_translate()
        else:
            bring_to_front(); set_status("ไม่พบข้อความที่เลือก - ลากคลุมข้อความก่อนแล้วกด " + HOTKEY_LABEL)

    def on_hotkey():           # เรียกจากเธรด hotkey
        send_ctrl_c(); time.sleep(0.25); q.put(("hotkey",))

    def hotkey_status(hot_ok, hook_ok):
        st["hotkey_ok"] = hot_ok
        parts = []
        parts.append("ลากคลุมข้อความในโปรแกรมใดก็ได้ แล้วคลิกไอคอนหุ่นยนต์ที่ลอยขึ้นมา" if hook_ok else "ตรวจการลากคลุมไม่ได้")
        parts.append(f"หรือกด {hot_ok}" if hot_ok else "คีย์ลัด Ctrl+Alt+T/Y ถูกโปรแกรมอื่นใช้อยู่")
        hotkey_var.set(" · ".join(parts))

    def clip_poll():
        if clip_var.get() and not worker["busy"]:
            t = read_clipboard()
            if t and t.strip() and t != st["last_clip"] and t.strip() != st["last_result"]:
                st["last_clip"] = t
                src.delete("1.0", "end"); src.insert("1.0", t.strip()); start_translate()
            elif st["last_clip"] is None:
                st["last_clip"] = t
        root.after(700, clip_poll)

    def on_models(models):
        """models = รายการโมเดลในเครื่อง (None = ไม่พบ Ollama) -> เลือกเส้นทางตามโหมดใน ⚙ ผู้ให้บริการ"""
        a = settings.get("api") or {}
        mode = a.get("mode", "auto")
        local_ok = bool(models)
        api_ok = api_configured()
        api_entry = (API_TAG + a.get("model", "")) if api_ok else None
        values = list(models or []) + ([api_entry] if api_entry else [])
        st["models"] = list(models or []); model_cb["values"] = values
        want_api = (mode == "api" and api_ok) or (mode == "auto" and not local_ok and api_ok)
        if want_api:
            use_backend("api"); model_var.set(api_entry)
            why = "" if mode == "api" else " (ไม่พบโมเดลในเครื่อง จึงสลับให้อัตโนมัติ)"
            set_status(f"พร้อมใช้งาน · โมเดลออนไลน์ {a.get('model')} ผ่าน API{why}")
        elif local_ok:
            use_backend("local")
            saved = settings.get("model", "")
            chosen = saved if saved in models else pick_model(models)
            model_var.set(chosen); st["model"] = chosen
            note = "" if chosen.startswith("scb10x/typhoon2.5") else " (แนะนำ typhoon2.5-qwen3-4b สำหรับภาษาไทย)"
            set_status(f"พร้อม · โมเดล {chosen}{note} · กำลังอุ่นเครื่องเข้า GPU ...")
            threading.Thread(target=lambda: (warm_up(chosen), q.put(("piece", ""))), daemon=True).start()
            root.after(1500, lambda: set_status(f"พร้อมใช้งาน · {chosen}") if not worker["busy"] else None)
        else:
            use_backend("local"); st["model"] = ""
            model_var.set("ไม่พบโมเดล" if models is None else "ยังไม่มีโมเดลในเครื่อง")
            set_status(("เชื่อมต่อ Ollama ไม่ได้" if models is None else "Ollama ทำงานแต่ยังไม่มีโมเดล")
                       + " - กด ⚙ ผู้ให้บริการ เพื่อดาวน์โหลดโมเดลในเครื่อง หรือใส่ API key ใช้โมเดลออนไลน์")
            return
        demo_text = os.environ.get("TRANSLATOR_SPEAK_DEMO")
        if demo_text and not st.get("demo_started"):   # สำหรับทดสอบ: แปล + อ่านอัตโนมัติด้วยเสียงที่ระบุ
            st["demo_started"] = True
            voice_pick = os.environ.get("TRANSLATOR_SPEAK_VOICE")

            def demo():
                if voice_pick and voice_pick in voice_names:
                    tts_voice_var.set(voice_pick); autospeak_var.set(True)   # ระบุเสียง = ทดสอบอ่านอัตโนมัติด้วย
                src.delete("1.0", "end"); src.insert("1.0", demo_text)
                st["demo_t0"] = time.time(); print("[demo] เริ่มแปล", file=sys.stderr, flush=True)
                start_translate()
            root.after(4000, demo)

    def connect():
        set_status("กำลังเชื่อมต่อ Ollama (ถ้ายังไม่เปิดจะเปิดให้เอง) ...")
        threading.Thread(target=lambda: q.put(("models", ensure_ollama())), daemon=True).start()

    # ---------- ⚙ ผู้ให้บริการ: ตั้งค่า API ออนไลน์สำรอง (ใช้เมื่อเครื่องไม่มีโมเดลในเครื่อง หรือเลือกใช้เอง)
    def open_provider_dialog():
        import webbrowser
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

    # ---------- คีย์ลัดแก้ไขข้อความที่ใช้ได้ทุกภาษาแป้นพิมพ์ + เมนูคลิกขวา
    # Tk ผูก Ctrl+V/C/X/A กับ "ตัวอักษร" v/c/x/a เมื่อแป้นพิมพ์อยู่ที่ภาษาไทย keysym เป็นอักษรไทย จึงวาง/คัดลอกไม่ได้
    # แก้โดยดูรหัสปุ่มจริง (keycode 86=V 67=C 88=X 65=A) เฉพาะกรณีที่ keysym ไม่ใช่อักษรละติน (ภาษาอังกฤษปล่อยให้ Tk จัดการเอง)
    EDIT_KEYS = {86: "<<Paste>>", 67: "<<Copy>>", 88: "<<Cut>>", 65: "<<SelectAll>>"}

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
            stop_speech()
    src.bind("<<Modified>>", on_src_modified)
    root.bind("<Escape>", lambda e: worker["stop"].set())
    root.bind("<F5>", lambda e: connect())
    src.bind("<Control-a>", lambda e: (src.tag_add("sel", "1.0", "end"), "break"))
    dst.bind("<Control-a>", lambda e: (dst.tag_add("sel", "1.0", "end"), "break"))
    root.protocol("WM_DELETE_WINDOW", lambda: (worker["stop"].set(), stop_speech(), save_settings(), root.destroy()))

    apply_topmost()
    connect()
    threading.Thread(target=win_event_thread, daemon=True,
                     args=(on_hotkey, lambda x, y: q.put(("select", x, y)), lambda: q.put(("hide_float",)),
                           is_own_window, hotkey_status)).start()
    root.after(60, pump)
    root.after(1000, clip_poll)
    src.focus_set()
    root.after(300, lambda: pane.sashpos(0, root.winfo_width() // 2 - 10))  # แบ่งสองช่องเท่ากัน
    if settings.get("qaOpen"):
        root.after(400, lambda: qa_panel.toggle(True))
    if os.environ.get("TRANSLATOR_PROVIDER_DEMO"):   # สำหรับทดสอบ: เปิดหน้าต่างตั้งค่าผู้ให้บริการ
        root.after(2500, open_provider_dialog)
    if os.environ.get("TRANSLATOR_FLOAT_DEMO"):  # สำหรับทดสอบ: โชว์ไอคอนลอยกลางจอซ้ำทุก 4 วินาที
        print("float frames:", len(frames), file=sys.stderr)

        def demo():
            show_float(root.winfo_screenwidth() // 2, root.winfo_screenheight() // 2); root.after(4000, demo)
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
    ap.add_argument("--ask", metavar="QUESTION", help="(ใช้กับ --cli) ถามคำถามเกี่ยวกับข้อความหลังแปล")
    ap.add_argument("text", nargs="?")
    a = ap.parse_args()
    if a.cli:
        sys.exit(run_cli(a))
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
