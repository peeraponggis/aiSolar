#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
voice_input.py - พูดคำสั่งแบบกดปุ่ม/คีย์ลัดแล้วพูด (push-to-talk) ถอดเสียงเป็นข้อความด้วย
faster-whisper (ออฟไลน์ ทำงานบน CPU) แล้วส่งต่อให้ agent loop ใน agent.py

พอร์ตมาจาก F:/LocalAI/translation/voice_input.py ของ Local Translator แบบแทบไม่แก้ (ไม่มี
Tkinter หรือโค้ดเฉพาะโปรแกรมแปลผูกอยู่เลยตั้งแต่ต้น - รับแค่ queue.Queue ธรรมดา)

เลือกรันบน CPU ไม่ใช่ GPU เพราะ GPU ของเครื่องถูกโมเดลคุยด้วย (Ollama) ใช้อยู่แล้ว การแย่ง VRAM
กันจะทำให้ทั้งสองช้าลง ส่วนโมเดลขนาด "small" เลือกเพราะแม่นพอสำหรับภาษาไทย/อังกฤษ แต่ยังโหลด/
ถอดเสียงสั้นๆ ได้ในไม่กี่วินาทีบน CPU ทั่วไป ไม่ใช้โหมดฟังตลอดเวลา (wake-word) เพราะกินทรัพยากร
ต่อเนื่องและมีประเด็นความเป็นส่วนตัว จึงใช้โหมดกดปุ่มพูด/กดอีกทีเพื่อหยุด เหมือนเครื่องส่งวิทยุ

โมเดลถูกโหลดครั้งแรกตอนเริ่มอัดเสียงครั้งแรก (lazy, ในเธรดพื้นหลัง ไม่บล็อก UI) เพื่อไม่ให้
ผู้ที่ไม่ใช้ฟีเจอร์นี้ต้องรอโหลดฟรีๆ ตอนเปิดโปรแกรม ครั้งแรกจะดาวน์โหลดจาก Hugging Face
(~500 MB ต้องต่ออินเทอร์เน็ต) แล้วแคชไว้ใช้ครั้งต่อไปโดยไม่ต้องโหลดซ้ำ

คำศัพท์เฉพาะ (ชื่อ "ลุงพี" เอง, ชื่อโปรแกรม ฯลฯ) ที่ Whisper มักฟังผิด ("ลุงพี" เคยถูกถอดเป็น
"ลงคี่"/"ลงพี่" ตอนทดสอบจริง) แก้โดยส่ง initial_prompt ให้โมเดล - เป็นฟีเจอร์มาตรฐานของ Whisper
ที่ช่วย "โน้มเอียง" คำศัพท์/โทนการถอดเสียงไปทางคำที่กำหนดไว้ ไม่ใช่การเทรนโมเดลใหม่หรือเก็บเสียง
ผู้ใช้จริงๆ (เบากว่ามากและไม่ต้องมีขั้นตอนอัดเสียงฝึกโมเดลแยก) รายชื่อคำอยู่ใน voice_vocab.txt
แก้ไฟล์นั้นเพิ่มคำเองได้เลยโดยไม่ต้องแก้โค้ด
"""
import logging
import os
import threading

import numpy as np
import sounddevice as sd

log = logging.getLogger(__name__)

MODEL_SIZE = "small"
SAMPLE_RATE = 16000
MAX_SECONDS = 30          # กันอัดค้างถ้าผู้ใช้ลืมกดหยุด
MIN_SECONDS = 0.3         # สั้นกว่านี้ถือว่าไม่ได้พูดอะไร (กดพลาด/ปล่อยเร็วไป)
VOCAB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "voice_vocab.txt")


def _load_vocab_prompt():
    """อ่านรายการคำศัพท์จาก voice_vocab.txt (บรรทัดละคำ/วลี, # นำหน้า = คอมเมนต์) มาต่อกันเป็น
    ข้อความเดียวให้ Whisper ใช้เป็น initial_prompt คืน None ถ้าไม่มีไฟล์/ไม่มีคำเลย"""
    try:
        with open(VOCAB_FILE, "r", encoding="utf-8") as f:
            words = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]
        return " ".join(words) if words else None
    except Exception:
        return None

_model = None
_model_lock = threading.Lock()


def _get_model():
    global _model
    with _model_lock:
        if _model is None:
            from faster_whisper import WhisperModel
            log.info("กำลังโหลดโมเดลถอดเสียง faster-whisper (%s, CPU) ครั้งแรก ...", MODEL_SIZE)
            _model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
            log.info("โหลดโมเดลถอดเสียงเสร็จแล้ว")
    return _model


class VoiceInput:
    """q: queue.Queue ของ agent.py - ส่งผลลัพธ์กลับเป็น ("stt_recording", bool) /
    ("stt_done", text) / ("stt_error", msg) ให้ main loop อ่านแล้วส่งต่อให้ agent ประมวลผล"""

    def __init__(self, q):
        self.q = q
        self.recording = False
        self._frames = []
        self._stream = None
        self._max_timer = None

    def toggle(self):
        self.stop() if self.recording else self.start()

    def start(self):
        if self.recording:
            return
        self._frames = []
        threading.Thread(target=_get_model, daemon=True).start()   # เริ่มโหลดโมเดลล่วงหน้าระหว่างอัด

        def callback(indata, frames, time_info, status):
            if status:
                log.debug("sounddevice status: %s", status)
            self._frames.append(indata.copy())

        try:
            self._stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32", callback=callback)
            self._stream.start()
        except Exception as e:
            log.warning("เปิดไมโครโฟนไม่ได้", exc_info=True)
            self.q.put(("stt_error", f"เปิดไมโครโฟนไม่ได้: {e}"))
            return
        self.recording = True
        self._max_timer = threading.Timer(MAX_SECONDS, self.stop)
        self._max_timer.daemon = True; self._max_timer.start()
        self.q.put(("stt_recording", True))

    def stop(self):
        if not self.recording:
            return
        self.recording = False
        if self._max_timer:
            self._max_timer.cancel(); self._max_timer = None
        self.q.put(("stt_recording", False))
        try:
            self._stream.stop(); self._stream.close()
        except Exception:
            log.debug("ปิดสตรีมไมโครโฟนไม่สำเร็จ", exc_info=True)
        frames, self._frames = self._frames, []
        if not frames:
            self.q.put(("stt_error", "ไม่ได้ยินเสียง ลองพูดอีกครั้ง")); return
        audio = np.concatenate(frames, axis=0).flatten()
        if len(audio) < SAMPLE_RATE * MIN_SECONDS:
            self.q.put(("stt_error", "ไม่ได้ยินเสียง ลองพูดอีกครั้ง")); return

        def job():
            try:
                model = _get_model()
                segments, _info = model.transcribe(audio, language=None, vad_filter=True,
                                                   initial_prompt=_load_vocab_prompt())
                text = "".join(seg.text for seg in segments).strip()
                if text:
                    self.q.put(("stt_done", text))
                else:
                    self.q.put(("stt_error", "ถอดเสียงไม่ได้ยินข้อความ ลองพูดอีกครั้ง"))
            except Exception as e:
                log.exception("ถอดเสียงผิดพลาด")
                self.q.put(("stt_error", str(e)))
        threading.Thread(target=job, daemon=True).start()
