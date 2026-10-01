#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
speech_controller.py - ตัวควบคุมเสียงอ่านระดับ GUI: เลือกเสียง/คำแทนภาษาอังกฤษตามภาษา,
อ่านทั้งข้อความ (ปุ่ม 🔊), และอ่านแบบสตรีมทีละประโยคระหว่างแปล (ตอนเปิด "อ่านอัตโนมัติ")

แยกออกจาก run_gui() เพราะเป็นชั้นประสานงาน (orchestration) ระหว่างเครื่องมือเสียงอ่านดิบใน
tts_engine.py (TtsPipeline, split/pop sentences, replacements) กับตัวแปร GUI (ช่องเลือกเสียง/
ความเร็ว, คิวงานหลัก) จุดเชื่อมกับส่วนอื่น: speak_text()/stop_speech() ที่ปุ่ม 🔊 และ QAPanel ใช้,
stream_speak_begin()/piece()/end() ที่ workflow การแปลหลักเรียกตอนเปิด "อ่านอัตโนมัติ", และ
on_tts_event() ที่ pump() เรียกเมื่อมีเหตุการณ์จากเธรดเล่นเสียง
"""
import logging
import os
import threading
import time

from engine import clean_output, detect_lang
from tts_engine import (
    EN_VOICES, TTS_RATES, TTS_TMP, TTS_VOICES, TtsPipeline,
    apply_replacements, clean_for_tts, load_replacements, pop_sentences, split_tts_chunks,
)

log = logging.getLogger(__name__)


class SpeechController:
    def __init__(self, q, set_status, tts_voice_var, tts_rate_var, clone_ids, st=None):
        self.q = q
        self.set_status = set_status
        self.tts_voice_var = tts_voice_var
        self.tts_rate_var = tts_rate_var
        self.clone_ids = clone_ids
        self.st = st or {}
        self.replacements = load_replacements()
        self.pipeline = TtsPipeline(lambda kind, msg: q.put(("tts_event", kind, msg)))
        self.speak = {"on": False, "buf": "", "lang": "th", "clone": False}
        threading.Thread(target=self._cleanup_tmp, daemon=True).start()

    def _cleanup_tmp(self):
        """ลบไฟล์เสียงชั่วคราวที่เก่ากว่า 1 วัน"""
        try:
            cutoff = time.time() - 86400
            for f in os.listdir(TTS_TMP):
                p = os.path.join(TTS_TMP, f)
                if os.path.isfile(p) and os.path.getmtime(p) < cutoff:
                    os.remove(p)
        except Exception:
            pass

    def speech_config(self, lang):
        """เลือกเสียงตามภาษาของข้อความ (edge-tts ไม่ส่งเสียงถ้าเสียงกับภาษาไม่ตรงกัน) คืน (voice, rate, clone_id, ชื่อที่แสดง)"""
        name = self.tts_voice_var.get()
        clone_id = self.clone_ids.get(name)
        base_voice = TTS_VOICES.get(name, ("th-TH-PremwadeeNeural", "th"))[0] if not clone_id else "th-TH-NiwatNeural"
        voice = base_voice if lang == "th" else EN_VOICES.get(base_voice, "en-US-JennyNeural")
        return voice, TTS_RATES.get(self.tts_rate_var.get(), "+0%"), (clone_id if lang == "th" else None), name

    def feed_sentence(self, text, lang):
        text = clean_for_tts(text)
        if not text:
            return
        if lang == "th":
            text = apply_replacements(text, self.replacements)
        self.pipeline.feed(text)

    def speak_text(self, text):
        """ปุ่ม 🔊: อ่านทั้งข้อความ แบ่งเป็นประโยค เริ่มเล่นทันทีที่ประโยคแรกเสร็จ"""
        text = clean_for_tts(text or "")
        if not text:
            return
        self.stop_speech()
        lang = detect_lang(text)
        voice, rate, clone_id, name = self.speech_config(lang)
        self.pipeline.begin(voice, rate, clone_id)
        # เสียงโคลนใช้เวลาต่อครั้งนานมาก จึงส่งทั้งก้อนเดียว ส่วนเสียงปกติแบ่งประโยคเพื่อให้เริ่มได้เร็ว
        chunks = [text] if clone_id else split_tts_chunks(text)
        self.set_status(f"กำลังสร้างเสียง ({name}{' · โคลน' if clone_id else ''}) {len(chunks)} ท่อน ...")
        for c in chunks:
            self.feed_sentence(c, lang)
        self.pipeline.finish()

    def stream_speak_begin(self, lang):
        """เริ่มอ่านตั้งแต่ประโยคแรกที่แปลเสร็จ (เรียกตอนเริ่มแปล เมื่อเปิด 'อ่านอัตโนมัติ')"""
        voice, rate, clone_id, name = self.speech_config(lang)
        self.pipeline.begin(voice, rate, clone_id)
        self.speak.update(on=True, buf="", lang=lang, clone=bool(clone_id))

    def stream_speak_piece(self, piece):
        if not self.speak["on"]:
            return
        self.speak["buf"] += piece
        if self.speak["clone"]:
            return                                   # โคลน: รอจบแล้วอ่านทีเดียว
        sents, self.speak["buf"] = pop_sentences(self.speak["buf"])
        for s in sents:
            self.feed_sentence(s, self.speak["lang"])

    def stream_speak_end(self, full_text):
        if not self.speak["on"]:
            return
        self.speak["on"] = False
        if self.speak["clone"]:
            self.feed_sentence(clean_output(full_text), self.speak["lang"])
        else:
            sents, _ = pop_sentences(self.speak["buf"], final=True)
            for s in sents:
                self.feed_sentence(s, self.speak["lang"])
        self.speak["buf"] = ""
        self.pipeline.finish()

    def stop_speech(self):
        self.speak["on"] = False; self.speak["buf"] = ""
        self.pipeline.stop()

    def on_tts_event(self, kind, msg):
        """เรียกจาก pump() เมื่อมีคิวงาน 'tts_event' จากเธรดเล่นเสียง"""
        if self.st.get("demo_t0"):
            import sys
            print(f"[demo] {time.time() - self.st['demo_t0']:5.1f}s  {kind}: {msg}", file=sys.stderr, flush=True)
        if kind in ("status", "done"):
            self.set_status(msg)
        elif kind == "error":
            self.set_status("เสียงอ่านไม่สำเร็จ: " + msg[:140])
