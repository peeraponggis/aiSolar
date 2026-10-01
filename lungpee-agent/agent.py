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
import json
import logging
import os
import queue
import threading

import safety
from app_log import setup_logging
from hotkey import hotkey_thread
from voice_input import VoiceInput
from ollama_client import chat, clean_output, ensure_ollama, pick_model, warm_up
from tool_registry import DISPATCH, TOOLS
from tts_engine import EN_VOICES, TTS_RATES, TTS_VOICES, TtsPipeline, clean_for_tts, detect_lang, split_tts_chunks

log = logging.getLogger(__name__)

BASE = os.path.dirname(os.path.abspath(__file__))
ICON_PATH = os.path.normpath(os.path.join(BASE, "..", "lung_pee.ico"))
MAX_HISTORY_TURNS = 10   # เก็บบทสนทนาล่าสุดไว้กี่คู่ ถาม-ตอบ (กัน context ยาวเกิน NUM_CTX)
MAX_TOOL_TURNS = 5       # กันลูปเรียกเครื่องมือไม่รู้จบถ้าโมเดลสับสน

SYSTEM_PROMPT = (
    "คุณชื่อ \"ลุงพี\" เป็นผู้ช่วย AI ที่ทำงานในเครื่องของผู้ใช้ ตอบเป็นภาษาไทยเป็นหลัก "
    "(ถ้าผู้ใช้ถามเป็นภาษาอังกฤษให้ตอบเป็นภาษาอังกฤษ) พูดจากันเองเป็นมิตรเหมือนญาติผู้ใหญ่ที่สนิทกัน "
    "ตอบกระชับ ไม่ต้องยาวเกินจำเป็น เพราะคำตอบจะถูกอ่านออกเสียงให้ฟัง "
    "ถ้าผู้ใช้ขอให้ทำอะไรบนคอมพิวเตอร์ (เปิดโปรแกรม, รันคำสั่ง, อ่าน/เขียน/ลบไฟล์, แปลไฟล์, กด/คลิก/"
    "พิมพ์อะไรในหน้าต่างโปรแกรมอื่น) ห้ามตอบว่า \"จะทำให้\"/\"เสร็จแล้ว\" เฉยๆ โดยไม่เรียกเครื่องมือจริง "
    "ต้องเรียกเครื่องมือที่มีให้เสมอทีละอย่าง แล้วรอดูผลจากเครื่องมือก่อนค่อยตอบ เช่นถ้าผู้ใช้ขอให้กดปุ่ม "
    "ต้องเรียก list_ui_controls ก่อนเพื่อดูชื่อปุ่มจริง แล้วเรียก click_control ตามชื่อที่เจอจริง ห้ามเดาชื่อเอง /no_think"
)

st = {"model": "", "voice": "เปรมวดี (หญิง)", "rate": "ปกติ", "history": []}
pipeline = TtsPipeline(lambda kind, msg: log.info("tts %s: %s", kind, msg))


def speak(text):
    text = clean_for_tts(text)
    if not text:
        return
    pipeline.stop()
    lang = detect_lang(text)
    base_voice = TTS_VOICES.get(st["voice"], ("th-TH-PremwadeeNeural", "th"))[0]
    voice = base_voice if lang == "th" else EN_VOICES.get(base_voice, "en-US-JennyNeural")
    rate = TTS_RATES.get(st["rate"], "+0%")
    pipeline.begin(voice, rate)
    for c in split_tts_chunks(text):
        pipeline.feed(c)
    pipeline.finish()


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
    log.info("คำถาม/คำสั่ง: %s", text)
    if not st["model"]:
        log.warning("ยังไม่ได้เชื่อมต่อโมเดล - ข้ามคำถามนี้")
        speak("ขอโทษครับ ยังเชื่อมต่อโมเดลไม่ได้"); return
    st["history"].append({"role": "user", "content": text})
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + st["history"][-MAX_HISTORY_TURNS * 2:]

    for _ in range(MAX_TOOL_TURNS):
        try:
            result = chat(st["model"], messages, temperature=0.4, tools=TOOLS)
        except Exception:
            log.exception("เรียกโมเดลผิดพลาด (model=%s)", st["model"])
            speak("ขอโทษครับ เรียกโมเดลไม่สำเร็จ"); return

        tool_calls = result["tool_calls"]
        if not tool_calls:
            answer = clean_output(result["content"]) or "ขอโทษครับ ผมตอบไม่ได้ตอนนี้"
            st["history"].append({"role": "assistant", "content": answer})
            log.info("คำตอบ: %s", answer)
            speak(answer)
            return

        messages.append({"role": "assistant", "content": result["content"], "tool_calls": tool_calls})
        for tc in tool_calls:
            fn_info = tc.get("function", {})
            name = fn_info.get("name", "")
            args = _parse_tool_args(fn_info.get("arguments"))
            tool_result = execute_tool(name, args)
            tool_msg = {"role": "tool", "content": json.dumps(tool_result, ensure_ascii=False)}
            if tc.get("id"):
                tool_msg["tool_call_id"] = tc["id"]
            messages.append(tool_msg)

    log.warning("เกินจำนวนรอบเรียกเครื่องมือสูงสุด (%d) - หยุดและแจ้งผู้ใช้", MAX_TOOL_TURNS)
    speak("ขอโทษครับ งานนี้ซับซ้อนเกินไป ลองแบ่งเป็นขั้นตอนย่อยๆ ดูครับ")


def pump(q):
    while True:
        item = q.get()
        kind = item[0]
        if kind == "stt_recording":
            log.info("สถานะอัดเสียง: %s", "เริ่ม" if item[1] else "หยุด")
        elif kind == "stt_done":
            threading.Thread(target=handle_command, args=(item[1],), daemon=True).start()
        elif kind == "stt_error":
            log.warning("ถอดเสียงไม่สำเร็จ: %s", item[1])


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
    log.info("ลุงพี agent (Phase 3: พูดคุยทั่วไป + เรียกเครื่องมือ + คลิก/พิมพ์ในโปรแกรมอื่น) เริ่มทำงาน")
    q = queue.Queue()
    voice = VoiceInput(q)
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

    def on_quit(icon, item):
        pipeline.stop()
        icon.stop()

    menu = pystray.Menu(
        pystray.MenuItem("พูดคุยกับลุงพี (หรือกด Ctrl+Alt+L)", on_toggle),
        pystray.MenuItem("เชื่อมต่อโมเดลใหม่", on_reconnect),
        pystray.MenuItem("ออกจากโปรแกรม", on_quit),
    )
    icon = pystray.Icon("lungpee-agent", image, "ลุงพี", menu)
    icon.run()


if __name__ == "__main__":
    main()
