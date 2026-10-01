#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
agent.py - ลุงพี: ผู้ช่วย AI พูดคุยทั่วไปที่ทำงานเป็นไอคอนในถาดระบบ (system tray)

Phase 1 (ตัวนี้): พูดคุยตอบคำถามทั่วไปด้วยเสียงเท่านั้น ไม่มีการคุมคอมพิวเตอร์/เรียกเครื่องมือ
ใดๆ เลย - ดูแผนเต็มในแฟ้มแผนของเซสชัน (Phase 2 จะเพิ่ม tool-calling สำหรับเปิดโปรแกรม/รันคำสั่ง/
แปลไฟล์เป็นชุด, Phase 3 จะเพิ่มการคลิก/พิมพ์ในโปรแกรมอื่นผ่าน UI Automation)

กดคีย์ลัด Ctrl+Alt+L (หรือ Ctrl+Alt+K ถ้า L ถูกจองไว้) ครั้งแรกเพื่อเริ่มพูด พูดจบกดอีกครั้ง
เพื่อหยุด ลุงพีจะถอดเสียง ส่งเข้าโมเดล Ollama ในเครื่อง แล้วพูดคำตอบกลับ หรือคลิกขวาที่ไอคอน
ในถาดระบบเพื่อเริ่ม/หยุดพูดด้วยเมาส์แทนคีย์ลัดก็ได้
"""
import logging
import os
import queue
import threading

from app_log import setup_logging
from hotkey import hotkey_thread
from voice_input import VoiceInput
from ollama_client import chat, clean_output, ensure_ollama, pick_model, warm_up
from tts_engine import EN_VOICES, TTS_RATES, TTS_VOICES, TtsPipeline, clean_for_tts, detect_lang, split_tts_chunks

log = logging.getLogger(__name__)

BASE = os.path.dirname(os.path.abspath(__file__))
ICON_PATH = os.path.normpath(os.path.join(BASE, "..", "lung_pee.ico"))
MAX_HISTORY_TURNS = 10   # เก็บบทสนทนาล่าสุดไว้กี่คู่ ถาม-ตอบ (กัน context ยาวเกิน NUM_CTX)

SYSTEM_PROMPT = (
    "คุณชื่อ \"ลุงพี\" เป็นผู้ช่วย AI ที่ทำงานในเครื่องของผู้ใช้ ตอบเป็นภาษาไทยเป็นหลัก "
    "(ถ้าผู้ใช้ถามเป็นภาษาอังกฤษให้ตอบเป็นภาษาอังกฤษ) พูดจากันเองเป็นมิตรเหมือนญาติผู้ใหญ่ที่สนิทกัน "
    "ตอบกระชับ ไม่ต้องยาวเกินจำเป็น เพราะคำตอบจะถูกอ่านออกเสียงให้ฟัง /no_think"
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


def handle_command(text):
    log.info("คำถาม: %s", text)
    if not st["model"]:
        log.warning("ยังไม่ได้เชื่อมต่อโมเดล - ข้ามคำถามนี้")
        speak("ขอโทษครับ ยังเชื่อมต่อโมเดลไม่ได้"); return
    st["history"].append({"role": "user", "content": text})
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + st["history"][-MAX_HISTORY_TURNS * 2:]
    try:
        result = chat(st["model"], messages, temperature=0.5)
        answer = clean_output(result["content"])
    except Exception:
        log.exception("เรียกโมเดลผิดพลาด (model=%s)", st["model"])
        speak("ขอโทษครับ เรียกโมเดลไม่สำเร็จ"); return
    if not answer:
        answer = "ขอโทษครับ ผมตอบไม่ได้ตอนนี้"
    st["history"].append({"role": "assistant", "content": answer})
    log.info("คำตอบ: %s", answer)
    speak(answer)


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
    log.info("ลุงพี agent (Phase 1: พูดคุยทั่วไปด้วยเสียง) เริ่มทำงาน")
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
