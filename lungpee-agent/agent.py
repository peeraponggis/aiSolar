# ============================================================================
# ProInventive Suite
# Copyright (C) 2024-2569 ProInventive. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL
# Unauthorized use, copying, or distribution is prohibited.
# Author: Peerapong (Lungpee) -- ProInventive -- giskku@gmail.com
# ============================================================================

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
agent.py - ลุงพี: ผู้ช่วย AI พูดคุยทั่วไปที่ทำงานเป็นไอคอนในถาดระบบ (system tray)

Phase 3 (ตัวนี้): เพิ่มการคลิก/พิมพ์ลงช่องเฉพาะเจาะจงในโปรแกรมอื่นจริงๆ ผ่าน UI Automation
(list_ui_controls/click_control/type_text ใน tools/ui_automation.py) ต่อยอดจาก Phase 2 ที่มี
เปิดโปรแกรม/รันคำสั่ง PowerShell/อ่านเขียนลบไฟล์/แปลไฟล์ข้อความอยู่แล้ว ดูรายชื่อเครื่องมือ+
schema ทั้งหมดใน tool_registry.py และด่านขออนุญาตก่อนรันคำสั่งเสี่ยงใน safety.py

กดคีย์ลัด Ctrl+Alt+L (หรือ Ctrl+Alt+K ถ้า L ถูกจองไว้) ครั้งแรกเพื่อเริ่มพูด พูดจบกดอีกครั้ง
เพื่อหยุด ลุงพีจะถอดเสียง ส่งเข้าโมเดล Ollama ในเครื่อง แล้วพูดคำตอบกลับ หรือคลิกขวาที่ไอคอน
ในถาดระบบเพื่อเริ่ม/หยุดพูดด้วยเมาส์แทนคีย์ลัดก็ได้
"""
import ctypes
import json
import logging
import os
import queue
import re
import threading
import tkinter as tk

import safety
import settings as _settings
from app_log import setup_logging
from app_version import APP_NAME, AUTHOR, UPDATED, VERSION, about_text, thai_date
from avatar import AvatarWindow
from hotkey import hotkey_thread
from text_input import TextInputPopup
from voice_input import VoiceInput
from ollama_client import clean_output, ensure_ollama, hub_models, pick_model, stream_chat, warm_up
from tool_registry import DISPATCH, TOOLS
from tts_engine import (
    EN_VOICES, TTS_RATES, TTS_VOICES, TtsPipeline,
    clean_for_tts, detect_lang, pop_sentences, split_tts_chunks,
)

log = logging.getLogger(__name__)

BASE = os.path.dirname(os.path.abspath(__file__))
ICON_PATH = os.path.join(BASE, "lungpee-agent.ico")
MAX_HISTORY_TURNS = 10   # เก็บบทสนทนาล่าสุดไว้กี่คู่ ถาม-ตอบ (กัน context ยาวเกิน NUM_CTX)
MAX_TOOL_TURNS = 8       # กันลูปเรียกเครื่องมือไม่รู้จบถ้าโมเดลสับสน (เพิ่มจาก 5 เพราะการค้นหาไฟล์
                         # จริงมักต้องลองหลายโฟลเดอร์กว่าจะเจอ 5 รอบไม่พอ)
MUTEX_NAME = "Local\\LungpeeAgent.single"

# ---------------------------------------------------------------------------
# Goal 1: ป้องกันคำสั่ง destructive (ลบ/delete/remove/erase) ชั้นที่ 1 — pre-screen
# ---------------------------------------------------------------------------
_DESTRUCTIVE_RE = re.compile(
    r"(?:ลบ(?:ออก|ทิ้ง|ไฟล์|โฟลเดอร์|ทั้งหมด)?"
    r"|เอาออก"
    r"|ล้าง(?:ออก|ทิ้ง|ข้อมูล)?"
    r"|ทำลาย(?:ไฟล์)?"
    r"|(?<!\w)delete(?!\w)"
    r"|(?<!\w)remove(?!\w)"
    r"|(?<!\w)erase(?!\w)"
    r"|(?<!\w)del\s"
    r"|(?<!\w)rm\s)",
    re.IGNORECASE,
)
_DESTRUCTIVE_WARN = (
    "ขอโทษครับ ลุงพีไม่ลบไฟล์หรือโฟลเดอร์ให้ได้ "
    "เพื่อความปลอดภัยของข้อมูลคุณ "
    "กรุณาลบด้วยตัวเองผ่าน File Explorer หรือ PowerShell โดยตรงนะครับ"
)

# Goal 4a — trigger สำหรับ "จำไว้ว่า..." บันทึก notes แบบ instant
_REMEMBER_RE = re.compile(r"จำ(?:ไว้)?ว่า\s+(.+)", re.IGNORECASE)

# ---------------------------------------------------------------------------
# Goal 3a: แก้คำที่ Whisper STT ถอดเสียงผิดบ่อย + ตัด prefix ที่เรียกชื่อลุงพี
# ---------------------------------------------------------------------------
_STT_CORRECTIONS = {
    "ลงพี่": "ลุงพี", "ลงคี่": "ลุงพี", "หลุงพี": "ลุงพี", "ลุ้งพี่": "ลุงพี",
    "ไลน": "line", "ไล้น": "line", "ไล้": "line",
    "ฟรีแคด": "freecad", "ฟรีกา": "freecad",
    "โน้ตแพด": "notepad", "โน๊ตแพ็ด": "notepad",
    "เอ็กเซล": "excel", "เอ็กเซ็ล": "excel",
    "เวิร์ด": "word", "เวิด": "word",
    "โพเวอร์เชล": "powershell", "พาวเวอร์เชลล์": "powershell",
    "วิชวล สตูดิโอ": "visual studio code", "วีเอส โค้ด": "vscode",
}
_ADDRESS_RE = re.compile(r"^(?:ลุงพี|คุณลุงพี|พี่ลุงพี)\s*[,:\s]+", re.IGNORECASE)


def normalize_command(text: str) -> str:
    """แก้คำเพี้ยนจาก STT และตัดคำเรียกชื่อนำหน้าออก"""
    for wrong, right in _STT_CORRECTIONS.items():
        text = text.replace(wrong, right)
    return _ADDRESS_RE.sub("", text).strip()


# ---------------------------------------------------------------------------
# Goal 3b: hint โมเดลว่าควรใช้ tool ไหน — ช่วย 4B model เลือก tool ได้แม่นขึ้น
# ---------------------------------------------------------------------------
_TOOL_HINTS = [
    (re.compile(r"(?:หา|ค้น(?:หา)?|find|search)\s*(?:ไฟล์|โฟลเดอร์|file|folder)", re.I),
     "เครื่องมือที่ควรใช้: find_file"),
    (re.compile(r"(?:เปิด|เรียก|launch|open)\s+\S+", re.I),
     "เครื่องมือที่ควรใช้: launch_app"),
    (re.compile(r"(?:อ่าน|read|แสดงเนื้อหา)\s*(?:ไฟล์|file)", re.I),
     "เครื่องมือที่ควรใช้: read_file"),
    (re.compile(r"(?:ดูรายการ|list|ls\b|dir\b)\s*(?:ใน|ที่|in|at)?\s*\S+", re.I),
     "เครื่องมือที่ควรใช้: list_dir"),
    (re.compile(r"(?:เขียน|สร้าง|บันทึก)\s*(?:ไฟล์|file)|write\s+file", re.I),
     "เครื่องมือที่ควรใช้: write_file"),
    (re.compile(r"(?:คลิก|กดปุ่ม|click|press\s+button)", re.I),
     "เครื่องมือที่ควรใช้: list_ui_controls แล้ว click_control"),
    (re.compile(r"(?:พิมพ์ลง|พิมพ์ใส่|type\s+into|type\s+in)", re.I),
     "เครื่องมือที่ควรใช้: list_ui_controls แล้ว type_text"),
    (re.compile(r"(?:แปล|translate)\s*(?:ไฟล์|file)", re.I),
     "เครื่องมือที่ควรใช้: translate_file"),
    (re.compile(r"(?:รัน|รันคำสั่ง|execute|run)\s*(?:คำสั่ง|command|script)?", re.I),
     "เครื่องมือที่ควรใช้: run_shell"),
]


def _get_tool_hint(text: str):
    for pat, hint in _TOOL_HINTS:
        if pat.search(text):
            return hint
    return None


def acquire_single_instance():
    """กันเปิดซ้อนหลายชุด (ไม่งั้นจะได้คีย์ลัด/ไอคอนถาดระบบซ้อนกันหลายตัว คีย์ลัดใช้ได้แค่ตัวแรกที่เปิด
    ทำให้งงว่าทำไมพูดแล้วไม่ตอบ) แพทเทิร์นเดียวกับ Local Translator's acquire_single_instance() แต่
    ตัวนี้ไม่มีหน้าต่างหลักให้ดึงขึ้นมาแทน (เป็นแค่ไอคอนถาดระบบ) จึงแค่แจ้งเตือนแล้วปิดตัวที่เปิดซ้ำ"""
    k32 = ctypes.windll.kernel32
    k32.CreateMutexW.restype = ctypes.c_void_p
    handle = k32.CreateMutexW(None, False, MUTEX_NAME)
    if k32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        return False
    return handle

SYSTEM_PROMPT = (
    "คุณชื่อ \"ลุงพี\" เป็นผู้ช่วย AI ที่ทำงานในเครื่องของผู้ใช้ ตอบเป็นภาษาไทยเป็นหลัก "
    "(ถ้าผู้ใช้ถามเป็นภาษาอังกฤษให้ตอบเป็นภาษาอังกฤษ) พูดจากันเองเป็นมิตรเหมือนญาติผู้ใหญ่ที่สนิทกัน "
    "ตอบกระชับ ไม่ต้องยาวเกินจำเป็น เพราะคำตอบจะถูกอ่านออกเสียงให้ฟัง "
    "ห้ามใช้คำว่า \"แซ่บๆ\" ให้ใช้ \"OK ครับ\" แทน "
    "ถ้าผู้ใช้ขอให้ทำอะไรบนคอมพิวเตอร์ (เปิดโปรแกรม, รันคำสั่ง, อ่าน/เขียนไฟล์, แปลไฟล์, กด/คลิก/"
    "พิมพ์อะไรในหน้าต่างโปรแกรมอื่น) ห้ามตอบว่า \"จะทำให้\"/\"เสร็จแล้ว\" เฉยๆ โดยไม่เรียกเครื่องมือจริง "
    "ต้องเรียกเครื่องมือที่มีให้เสมอทีละอย่าง แล้วรอดูผลจากเครื่องมือก่อนค่อยตอบ เช่นถ้าผู้ใช้ขอให้กดปุ่ม "
    "ต้องเรียก list_ui_controls ก่อนเพื่อดูชื่อปุ่มจริง แล้วเรียก click_control ตามชื่อที่เจอจริง ห้ามเดาชื่อเอง "
    "ถ้าผู้ใช้ขอให้หาไฟล์/โฟลเดอร์ ให้เรียก find_file ทันทีก่อนถามกลับเสมอ ห้ามถามชื่อโฟลเดอร์ก่อน "
    "ห้ามเรียก delete_file โดยเด็ดขาดทุกกรณี ถึงแม้ผู้ใช้จะขอให้ลบไฟล์/โฟลเดอร์ "
    "ด้วยคำว่า ลบ/ลบออก/ลบทิ้ง/เอาออก/ล้าง/remove/delete/erase ก็ตาม "
    "ให้แจ้งผู้ใช้ว่าลุงพีไม่มีสิทธิ์ลบไฟล์ และให้ผู้ใช้ลบเองแทน /no_think"
)

# โหลด settings ที่ persist ข้ามเซสชัน (voice, rate, model, notes) — Goal 4a
st = _settings.load()
st["model"] = ""      # model ตั้งค่าตอน connect_model() เสมอ ไม่ใช้ค่าเก่า
st["history"] = []    # history รีเซ็ตทุกครั้ง (privacy)
avatar = None       # ตั้งค่าจริงใน main() หลังสร้าง Tk root แล้ว (ดู avatar.py)
text_popup = None   # ตั้งค่าจริงใน main() เช่นกัน (ดู text_input.py)


def _ui(fn):
    """เรียก fn() บนเธรดหลักของ Tkinter อย่างปลอดภัย - ถูกเรียกจากเธรดพื้นหลังหลายจุด (pump,
    handle_command, เธรดเล่นเสียงของ TtsPipeline) ซึ่งห้ามแตะวิดเจ็ต Tkinter ตรงๆ"""
    if avatar is not None:
        try:
            avatar.root.after(0, fn)
        except Exception:
            pass


def _on_tts_event(kind, msg):
    log.info("tts %s: %s", kind, msg)
    if kind == "status":
        _ui(lambda: avatar.show("🗣️ กำลังพูด..."))
    elif kind in ("done", "error"):
        _ui(avatar.hide)


pipeline = TtsPipeline(_on_tts_event)


def _voice_for_lang(lang):
    base_voice = TTS_VOICES.get(st["voice"], ("th-TH-PremwadeeNeural", "th"))[0]
    voice = base_voice if lang == "th" else EN_VOICES.get(base_voice, "en-US-JennyNeural")
    return voice, TTS_RATES.get(st["rate"], "+0%")


def speak(text):
    """พูดข้อความสำเร็จรูปทั้งก้อน (ข้อความ error/แจ้งเตือนสั้นๆ) - คำตอบจริงจากโมเดลใช้
    stream_speak_begin/piece/end ด้านล่างแทน เพื่อเริ่มพูดได้ทันทีตั้งแต่ประโยคแรกไม่ต้องรอทั้งก้อน"""
    text = clean_for_tts(text)
    if not text:
        _ui(avatar.hide)
        return
    pipeline.stop()
    _ui(lambda: avatar.show("🗣️ กำลังพูด..."))
    voice, rate = _voice_for_lang(detect_lang(text))
    pipeline.begin(voice, rate)
    for c in split_tts_chunks(text):
        pipeline.feed(c)
    pipeline.finish()


_stream_speak = {"on": False, "buf": "", "started": False, "first_chunk": True}


def stream_speak_begin():
    pipeline.stop()
    _stream_speak.update(on=True, buf="", started=False, first_chunk=True)
    _ui(lambda: avatar.show("🗣️ กำลังพูด..."))


def _stream_feed(sentence):
    sentence = clean_for_tts(sentence)
    if not sentence:
        return
    if not _stream_speak["started"]:
        voice, rate = _voice_for_lang(detect_lang(sentence))
        pipeline.begin(voice, rate)
        _stream_speak["started"] = True
    pipeline.feed(sentence)


def stream_speak_piece(piece):
    if not _stream_speak["on"]:
        return
    _stream_speak["buf"] += piece
    # Goal 2a: ประโยคแรกรอแค่ 15 ตัวอักษร (ลดจาก 60) เพื่อเริ่มพูดได้เร็วขึ้น
    min_len = 15 if _stream_speak["first_chunk"] else 60
    sents, _stream_speak["buf"] = pop_sentences(_stream_speak["buf"], min_len=min_len)
    for s in sents:
        _stream_speak["first_chunk"] = False
        _stream_feed(s)


def stream_speak_end():
    if not _stream_speak["on"]:
        return
    _stream_speak["on"] = False
    sents, _ = pop_sentences(_stream_speak["buf"], final=True)
    for s in sents:
        _stream_feed(s)
    _stream_speak["buf"] = ""
    if _stream_speak["started"]:
        pipeline.finish()
    else:
        _ui(avatar.hide)   # ไม่มีอะไรถูกพูดเลย (เช่นโมเดลเรียก tool ตรงๆ ไม่พูดอะไรนำก่อน)


def execute_tool(name, args):
    fn = DISPATCH.get(name)
    if not fn:
        return {"ok": False, "error": f"ไม่รู้จักเครื่องมือ {name}"}
    allowed, reason = safety.check(name, args)
    if not allowed:
        log.info("ปฏิเสธเครื่องมือ %s args=%s: %s", name, args, reason)
        return {"ok": False, "error": reason}
    log.info("กำลังรันเครื่องมือ %s args=%s", name, args)
    try:
        result = fn(args, {"model": st["model"]})
    except Exception as e:
        log.exception("รันเครื่องมือ %s ผิดพลาด", name)
        result = {"ok": False, "error": str(e)}
    log.info("ผลเครื่องมือ %s: %s", name, result)
    return result


def _parse_tool_args(raw):
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        log.warning("แปลง tool arguments เป็น JSON ไม่ได้: %r", raw)
        return {}


def handle_command(text):
    log.info("คำถาม/คำสั่ง (raw): %s", text)
    if not st["model"] and not st.get("online_model"):   # ตอนเปิดเครื่อง Ollama อาจยังไม่ขึ้น/กำลังอัปเดต: ลองเชื่อมต่อใหม่ก่อน ไม่ต้องกดเมนูเอง
        log.info("ยังไม่ได้เชื่อมต่อโมเดล - ลองเชื่อมต่อใหม่")
        connect_model()
    if not st["model"] and not st.get("online_model"):
        log.warning("ยังไม่ได้เชื่อมต่อโมเดล - ข้ามคำถามนี้")
        speak("ขอโทษครับ ยังเชื่อมต่อโมเดลไม่ได้"); return
    use_model = st.get("online_model") or st["model"]   # โมเดลออนไลน์จากศูนย์ผู้ให้บริการ (ถ้าเลือกไว้ในเมนูถาดระบบ)

    # Goal 4a — "จำไว้ว่า..." บันทึก notes แบบ instant โดยไม่ส่งโมเดล
    m_remember = _REMEMBER_RE.search(text)
    if m_remember:
        st["notes"] = m_remember.group(1).strip()
        _settings.save(st)
        speak(f"จำไว้แล้วครับว่า {st['notes']}")
        return

    # Goal 1 — ชั้น 1: pre-screen destructive intent ก่อนส่งโมเดล (ไม่เสีย inference ฟรี)
    if _DESTRUCTIVE_RE.search(text):
        log.info("pre-screen: destructive intent ตรวจพบใน %r", text[:80])
        _ui(lambda: avatar.show("⚠️ ปฏิเสธ"))
        speak(_DESTRUCTIVE_WARN)
        return

    # Goal 3a — normalize: แก้ STT error + ตัด prefix ชื่อ
    text = normalize_command(text)
    log.info("คำถาม/คำสั่ง (normalized): %s", text)

    # Goal 3b — tool hint: ช่วยโมเดลเลือก tool ถูกต้อง (hint ไม่บันทึกใน history)
    hint = _get_tool_hint(text)
    model_text = f"[{hint}]\n{text}" if hint else text
    if hint:
        log.info("tool hint: %s", hint)

    # Goal 4a — inject notes ที่ผู้ใช้ขอให้จำ ถ้ามี
    notes = st.get("notes", "").strip()
    system_prompt = (
        SYSTEM_PROMPT + f"\nข้อมูลที่ผู้ใช้ขอให้จำ: {notes}" if notes else SYSTEM_PROMPT
    )

    _ui(lambda: avatar.show("🤔 กำลังคิด..."))
    st["history"].append({"role": "user", "content": text})
    messages = [{"role": "system", "content": system_prompt}] + st["history"][-MAX_HISTORY_TURNS * 2:]
    # แทนที่ user message สุดท้ายด้วยเวอร์ชันที่มี hint (ไม่กระทบ history)
    if hint:
        messages[-1] = {"role": "user", "content": model_text}

    # Goal 4b — ติดตาม tool calls ที่เคยเรียกแล้วเพื่อป้องกัน infinite loop
    _seen_calls: set = set()

    for _ in range(MAX_TOOL_TURNS):
        buf = []
        stream_speak_begin()   # เริ่มพูดได้ทันทีตั้งแต่ประโยคแรกของรอบนี้
        try:
            gen = stream_chat(use_model, messages, temperature=0.4, tools=TOOLS)
            result = {"tool_calls": [], "stats": {}}
            while True:
                try:
                    piece = next(gen)
                except StopIteration as e:
                    result = e.value or result
                    break
                buf.append(piece)
                stream_speak_piece(piece)
        except Exception:
            log.exception("เรียกโมเดลผิดพลาด (model=%s)", use_model)
            stream_speak_end()
            speak("ขอโทษครับ เรียกโมเดลไม่สำเร็จ"); return
        stream_speak_end()

        content = clean_output("".join(buf))
        tool_calls = result.get("tool_calls") or []

        if not tool_calls:
            answer = content or "ขอโทษครับ ผมตอบไม่ได้ตอนนี้"
            prev = [m["content"] for m in st["history"] if m["role"] == "assistant"]
            if prev and prev[-1] == answer:
                log.warning("โมเดลตอบซ้ำคำตอบก่อนหน้าเป๊ะ - ล้างประวัติสนทนา")
                st["history"].clear()
            else:
                st["history"].append({"role": "assistant", "content": answer})
            log.info("คำตอบ: %s", answer)
            if not content:
                speak(answer)
            return

        _ui(lambda: avatar.show("🔧 กำลังทำงาน..."))
        messages.append({"role": "assistant", "content": content, "tool_calls": tool_calls})
        for tc in tool_calls:
            fn_info = tc.get("function", {})
            name = fn_info.get("name", "")
            args = _parse_tool_args(fn_info.get("arguments"))

            # Goal 4b — ตรวจ duplicate tool call (same tool + same args = model ติดลูป)
            call_key = (name, json.dumps(args, sort_keys=True, ensure_ascii=False))
            if call_key in _seen_calls:
                log.warning("โมเดลเรียกเครื่องมือซ้ำ %s args=%s — ฉีกลูป", name, args)
                tool_result = {"ok": False, "error": "เครื่องมือนี้ถูกเรียกซ้ำด้วย arguments เดิม กรุณาลองวิธีอื่น"}
            else:
                _seen_calls.add(call_key)
                tool_result = execute_tool(name, args)

            tool_msg = {"role": "tool", "content": json.dumps(tool_result, ensure_ascii=False)}
            if tc.get("id"):
                tool_msg["tool_call_id"] = tc["id"]
            messages.append(tool_msg)

    log.warning("เกินจำนวนรอบเรียกเครื่องมือสูงสุด (%d) - หยุดและแจ้งผู้ใช้", MAX_TOOL_TURNS)
    speak("ขอโทษครับ งานนี้ซับซ้อนเกินไป ลองแบ่งเป็นขั้นตอนย่อยๆ ดูครับ")


def ask_async(text):
    threading.Thread(target=handle_command, args=(text,), daemon=True).start()


def pump(q):
    while True:
        item = q.get()
        kind = item[0]
        if kind == "stt_recording":
            log.info("สถานะอัดเสียง: %s", "เริ่ม" if item[1] else "หยุด")
            if item[1]:
                _ui(lambda: avatar.show("🎙️ กำลังฟัง..."))
            else:
                _ui(lambda: avatar.show("🤔 กำลังถอดเสียง..."))
        elif kind == "stt_done":
            ask_async(item[1])
        elif kind == "stt_error":
            log.warning("ถอดเสียงไม่สำเร็จ: %s", item[1])
            _ui(avatar.hide)
            _ui(lambda: text_popup.show(f"ฟังไม่รู้เรื่องครับ ({item[1]}) ลองพิมพ์คำถามแทนได้เลย"))


def connect_model():
    models = ensure_ollama()
    if models:
        st["model"] = pick_model(models)
        log.info("เชื่อมต่อโมเดลสำเร็จ: %s", st["model"])
        threading.Thread(target=warm_up, args=(st["model"],), daemon=True).start()
    else:
        log.warning("เชื่อมต่อ Ollama ไม่ได้ - ลุงพีจะตอบไม่ได้จนกว่าจะเชื่อมต่อสำเร็จ (ลองกด 'เชื่อมต่อใหม่' ในเมนูถาดระบบ)")


def on_hotkey_status(hot_ok):
    log.info("คีย์ลัดพูดคุย: %s", hot_ok or "ลงทะเบียนไม่สำเร็จ (โปรแกรมอื่นอาจจองคีย์ลัดไว้)")


def main():
    setup_logging()
    if not acquire_single_instance():
        log.warning("ลุงพีเปิดอยู่แล้ว (ดูไอคอนในถาดระบบ) - ปิดตัวที่เปิดซ้ำนี้ลง")
        try:
            ctypes.windll.user32.MessageBoxW(
                0, "ลุงพีกำลังทำงานอยู่แล้วครับ ดูไอคอนในถาดระบบ (มุมขวาล่างจอ) ได้เลย",
                "ลุงพี", 0x40)   # MB_ICONINFORMATION
        except Exception:
            pass
        return
    log.info("%s เริ่มทำงาน", about_text())
    q = queue.Queue()
    voice = VoiceInput(q)

    # Tk root ไม่โชว์หน้าต่างเปล่าๆ ใช้แค่ขับ mainloop ให้ AvatarWindow (หน้าต่างลอยแสดงสถานะ
    # ฟัง/คิด/พูด ดู avatar.py) - ต้องรันบนเธรดหลักเสมอ ส่วน pystray ย้ายไปรันในเธรดแยกแทน
    global avatar, text_popup
    root = tk.Tk()
    root.withdraw()
    avatar = AvatarWindow(root)
    text_popup = TextInputPopup(root, ask_async)
    text_popup.show()   # ขึ้นค้างไว้ตลอดตั้งแต่เปิดโปรแกรม ไม่ต้องรอให้พูดไม่รู้เรื่องก่อนถึงจะเห็น

    threading.Thread(target=pump, args=(q,), daemon=True).start()
    threading.Thread(target=connect_model, daemon=True).start()
    threading.Thread(target=hotkey_thread, args=(voice.toggle, on_hotkey_status), daemon=True).start()

    import pystray
    from PIL import Image
    try:
        image = Image.open(ICON_PATH)
    except Exception:
        log.warning("โหลดไอคอน %s ไม่ได้ - ใช้ไอคอนสำรอง", ICON_PATH, exc_info=True)
        image = Image.new("RGB", (64, 64), "steelblue")

    def on_toggle(icon, item):
        voice.toggle()

    def on_reconnect(icon, item):
        threading.Thread(target=connect_model, daemon=True).start()

    def on_type_instead(icon, item):
        root.after(0, lambda: text_popup.show("พิมพ์คำถามหรือคำสั่งถึงลุงพีได้เลยครับ"))

    def on_quit(icon, item):
        pipeline.stop()
        icon.stop()
        root.after(0, root.quit)

    # โมเดล: ในเครื่อง (ค่าเริ่มต้น) หรือโมเดลออนไลน์จากศูนย์ผู้ให้บริการ (ทะเบียนกลางที่ Multi Tools จัดการ)
    def pick_online(mid):
        def handler(icon, item):
            st["online_model"] = mid
            _settings.save(st)
            log.info("เลือกโมเดล: %s", mid or "ในเครื่อง (Ollama)")
        return handler

    def model_items():
        yield pystray.MenuItem("ในเครื่อง (Ollama)" + (f" · {st['model']}" if st["model"] else ""), pick_online(""),
                               checked=lambda item: not st.get("online_model"), radio=True)
        opts = hub_models()
        if not opts:
            yield pystray.MenuItem("ยังไม่มีโมเดลออนไลน์ (ตั้งค่าใน Multi Tools → ศูนย์ผู้ให้บริการ)", None, enabled=False)
        for mid, label in opts:
            yield pystray.MenuItem(label, pick_online(mid), checked=lambda item, m=mid: st.get("online_model") == m, radio=True)

    menu = pystray.Menu(
        pystray.MenuItem(f"{APP_NAME} v{VERSION} · ปรับปรุง {thai_date(UPDATED)} · โดย {AUTHOR}", None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("พูดคุยกับลุงพี (หรือกด Ctrl+Alt+L)", on_toggle),
        pystray.MenuItem("พิมพ์ถามแทน", on_type_instead),
        pystray.MenuItem("เชื่อมต่อโมเดลใหม่", on_reconnect),
        pystray.MenuItem("โมเดล", pystray.Menu(model_items)),
        pystray.MenuItem("ออกจากโปรแกรม", on_quit),
    )
    icon = pystray.Icon("lungpee-agent", image, f"ลุงพี v{VERSION}", menu)
    threading.Thread(target=icon.run, daemon=True).start()
    root.mainloop()


if __name__ == "__main__":
    main()
