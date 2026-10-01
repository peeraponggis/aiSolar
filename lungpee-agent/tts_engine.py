#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tts_engine.py - เสียงพูดของลุงพี: edge-tts (เปรมวดี/นิวัฒน์) + เสียงในเครื่อง (SAPI/Pattara) สำรอง,
และ pipeline เล่นเสียงแบบสตรีมทีละท่อน

พอร์ตมาจาก F:/LocalAI/translation/tts_engine.py ของ Local Translator โดยตัดส่วนโคลนเสียง
(OpenVoice) และตารางคำอ่านภาษาอังกฤษ->ไทย (replacements.json) ที่ผูกกับโปรเจกต์ yt ออก
เพื่อให้ lungpee-agent ไม่ต้องพึ่งไฟล์ข้ามโปรเจกต์เลย ใช้ edge-tts + SAPI ตรงๆ
"""
import ctypes
import logging
import os
import queue
import re
import sys
import threading
import time

log = logging.getLogger(__name__)

FROZEN = bool(getattr(sys, "frozen", False))          # รันจาก exe ที่สร้างด้วย PyInstaller
BASE = os.path.dirname(sys.executable) if FROZEN else os.path.dirname(os.path.abspath(__file__))
TTS_TMP = os.path.join(os.environ.get("TEMP", BASE), "lungpee-agent-tts")
TTS_VOICES = {  # ชื่อที่แสดง -> (ชื่อเสียง edge-tts หรือ sapi:ชื่อเสียง Windows, ภาษา)
    "เปรมวดี (หญิง)": ("th-TH-PremwadeeNeural", "th"),
    "นิวัฒน์ (ชาย)": ("th-TH-NiwatNeural", "th"),
    "ปัตตรา (ในเครื่อง เร็ว ออฟไลน์)": ("sapi:Pattara", "th"),
}
EN_VOICES = {"th-TH-PremwadeeNeural": "en-US-JennyNeural", "th-TH-NiwatNeural": "en-US-GuyNeural", "sapi:Pattara": "sapi:Zira"}
TTS_RATES = {"ช้า": "-20%", "ปกติ": "+0%", "เร็ว": "+20%", "เร็วมาก": "+40%"}
THAI_RE = re.compile(r"[฀-๿]")


def detect_lang(text):
    """ตรวจภาษาจากสัดส่วนอักษรไทย (พอร์ตจาก engine.py ของ Local Translator) ใช้เลือกเสียงอ่านที่เข้ากับภาษา"""
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return "th"
    thai = sum(1 for c in letters if THAI_RE.match(c))
    return "th" if thai / len(letters) > 0.3 else "en"


def clean_for_tts(text):
    lines = []
    for line in text.strip().split("\n"):
        line = re.sub(r"\[.*?\]", "", line.strip())
        line = re.sub(r"^[—\-–•*]+\s*", "", line).strip()
        line = re.sub(r"\*{1,2}(.*?)\*{1,2}", r"\1", line)
        if line:
            lines.append(line)
    return "\n".join(lines)


def sapi_synthesize(text, voice_name, rate, out_wav):
    """เสียงในเครื่องของ Windows (OneCore เช่น Microsoft Pattara) ผ่าน WinRT ใน PowerShell: ออฟไลน์ เร็วมาก (~0.2 วินาที)
    แต่ธรรมชาติน้อยกว่าเสียง Neural ของ edge-tts"""
    import base64
    import subprocess
    speed = 1.0 + int(rate.replace("%", "").replace("+", "")) / 100.0   # +20% -> 1.2
    b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
    ps = (
        "Add-Type -AssemblyName System.Runtime.WindowsRuntime;"
        "[Windows.Media.SpeechSynthesis.SpeechSynthesizer, Windows.Media, ContentType=WindowsRuntime] | Out-Null;"
        "$s=New-Object Windows.Media.SpeechSynthesis.SpeechSynthesizer;"
        f"$v=[Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices | ? {{ $_.DisplayName -like '*{voice_name}*' }} | select -First 1;"
        "if($v){$s.Voice=$v};"
        f"try{{$s.Options.SpeakingRate={speed:.2f}}}catch{{}};"
        f"$op=$s.SynthesizeTextToStreamAsync([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{b64}')));"
        "$m=([System.WindowsRuntimeSystemExtensions].GetMethods() | ? { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0];"
        "$t=$m.MakeGenericMethod([Windows.Media.SpeechSynthesis.SpeechSynthesisStream]).Invoke($null,@($op));$t.Wait();"
        "$n=[System.IO.WindowsRuntimeStreamExtensions]::AsStreamForRead($t.Result.GetInputStreamAt(0));"
        f"$f=[System.IO.File]::Create('{out_wav}');$n.CopyTo($f);$f.Close()"
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, timeout=120,
                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if not (os.path.exists(out_wav) and os.path.getsize(out_wav) > 100):
        raise RuntimeError(f"เสียง {voice_name} ในเครื่องไม่ทำงาน")
    return out_wav


def tts_synthesize(text, voice, rate="+0%", pitch="+0Hz", max_retries=5):
    """สังเคราะห์เสียงเป็นไฟล์ mp3 คืน path; วนลองซ้ำเพราะ edge-tts ล้มเหลวชั่วคราวบ่อย"""
    import asyncio
    import edge_tts
    os.makedirs(TTS_TMP, exist_ok=True)
    import uuid
    stamp = f"{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"   # ไม่ซ้ำแม้สร้างหลายท่อนพร้อมกัน
    out = os.path.join(TTS_TMP, f"tts_{stamp}.mp3")

    if voice.startswith("sapi:"):
        return sapi_synthesize(text, voice[5:], rate, out[:-4] + ".wav")

    async def run():
        last = None
        for attempt in range(max_retries):
            try:
                await edge_tts.Communicate(text, voice, rate=rate, pitch=pitch).save(out)
                if os.path.exists(out) and os.path.getsize(out) > 100:
                    return
            except Exception as e:
                last = e
                log.debug("edge-tts ลองครั้งที่ %d ไม่สำเร็จ (%s): %s", attempt + 1, voice, e)
            await asyncio.sleep(0.4 * (attempt + 1))   # ข้อผิดพลาดชั่วคราวของ edge-tts มักผ่านเมื่อลองซ้ำทันที ไม่ต้องรอนาน
        raise last or RuntimeError("edge-tts ไม่ส่งเสียงกลับมา")
    try:
        asyncio.run(run())
    except Exception:
        # บริการ edge-tts ล่มชั่วคราว -> ใช้เสียงในเครื่องของ Windows แทน เพื่อให้ยังได้ยินเสียง (ปัตตรา/Zira)
        fallback = "Pattara" if voice.startswith("th") else "Zira"
        log.warning("edge-tts (%s) ล้มเหลวหลังลอง %d ครั้ง - ใช้เสียงในเครื่อง %s แทน",
                    voice, max_retries, fallback, exc_info=True)
        return sapi_synthesize(text, fallback, rate, out[:-4] + ".wav")
    return out


def split_tts_chunks(text, max_len=140):
    """แบ่งข้อความเป็นท่อนสั้นๆ ตามบรรทัดและประโยค เพื่อเริ่มเล่นท่อนแรกได้เร็วระหว่างสร้างท่อนถัดไป"""
    chunks = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        parts = re.split(r"(?<=[.!?。])\s+", line)
        for p in parts:
            while len(p) > max_len:
                cut = p.rfind(" ", 0, max_len)
                if cut < max_len // 2:
                    cut = max_len
                chunks.append(p[:cut].strip()); p = p[cut:].strip()
            if p:
                chunks.append(p)
    return chunks


def pop_sentences(buf, final=False, min_len=60, max_len=140):
    """ดึงประโยคที่จบแล้วออกจากบัฟเฟอร์ข้อความที่กำลังสตรีมเข้ามา คืน (รายการประโยค, ส่วนที่เหลือ)"""
    out = []
    while True:
        m = re.search(r"\n|(?<=[.!?。])\s", buf)
        cut = None
        if m:
            cut = m.start()
        elif len(buf) >= max_len:
            comma = buf.rfind(", ", min_len // 2, max_len)
            sp = buf.rfind(" ", min_len, max_len)
            cut = comma + 1 if comma > 0 else (sp if sp > 0 else max_len)
        elif len(buf) >= min_len and " " in buf[min_len:] and THAI_RE.search(buf):
            cut = buf.index(" ", min_len)
        if cut is None:
            break
        piece, buf = buf[:cut].strip(), buf[cut + 1:] if m and m.group() == "\n" else buf[cut:].lstrip()
        if piece:
            out.append(piece)
        if not buf:
            break
    if final and buf.strip():
        out.append(buf.strip()); buf = ""
    return out, buf


class TtsPipeline:
    """รับข้อความทีละท่อนขณะกำลังตอบ สร้างเสียงแบบขนาน (สูงสุด 3 ท่อน) และเล่นตามลำดับทันทีที่ท่อนแรกเสร็จ
    begin() -> feed() ซ้ำได้ -> finish(); stop() หยุดทุกอย่างและทิ้งท่อนที่รอ
    on_event(kind, msg): 'status' ระหว่างทำงาน, 'done' เมื่อจบ, 'error' เมื่อผิดพลาด"""
    def __init__(self, on_event):
        self.on_event = on_event
        self.stop_event = threading.Event()
        self.thread = None
        self.player = Player()
        self.pool = None
        self.jobs = None
        self.count = 0

    @property
    def running(self):
        return self.thread is not None and self.thread.is_alive()

    def begin(self, voice, rate):
        from concurrent.futures import ThreadPoolExecutor
        self.stop()
        self.stop_event = threading.Event()
        self.voice, self.rate = voice, rate
        self.pool = ThreadPoolExecutor(max_workers=3)
        self.jobs = queue.Queue()
        self.count = 0
        ev, jobs, pool = self.stop_event, self.jobs, self.pool

        def run():
            played = 0
            try:
                while not ev.is_set():
                    fut = jobs.get()
                    if fut is None:
                        break
                    path = fut.result()
                    if ev.is_set():
                        break
                    played += 1
                    self.on_event("status", f"กำลังอ่านท่อนที่ {played} ...")
                    self.player.play(path)
                    while self.player.is_playing() and not ev.is_set():
                        time.sleep(0.1)
                    self.player.stop()
                if not ev.is_set():
                    self.on_event("done", f"อ่านเสียงจบแล้ว ({played} ท่อน)")
            except Exception as e:
                log.exception("TtsPipeline เล่นเสียงผิดพลาด")
                self.player.stop()
                self.on_event("error", str(e))
            finally:
                pool.shutdown(wait=False, cancel_futures=True)
        self.thread = threading.Thread(target=run, daemon=True); self.thread.start()

    def feed(self, text):
        if self.jobs is None or self.stop_event.is_set() or not text.strip():
            return
        self.count += 1
        self.jobs.put(self.pool.submit(tts_synthesize, text, self.voice, self.rate))

    def finish(self):
        if self.jobs is not None:
            self.jobs.put(None)

    def stop(self):
        self.stop_event.set()
        if self.jobs is not None:
            self.jobs.put(None)
        try:
            self.player.stop()
        except Exception:
            pass


class Player:
    """เล่นไฟล์เสียงด้วย MCI ของ Windows (winmm) ไม่ต้องลง library"""
    def __init__(self):
        self.mci = ctypes.windll.winmm.mciSendStringW
        self.alias = None

    def play(self, path):
        self.stop()
        alias = "tts" + str(int(time.time() * 1000) % 100000)
        typ = "waveaudio" if path.lower().endswith(".wav") else "mpegvideo"
        rc = 1
        for _ in range(4):   # ไฟล์อาจยังถูกปิดไม่เสร็จ ลองซ้ำสั้นๆ
            rc = self.mci(f'open "{path}" type {typ} alias {alias}', None, 0, None)
            if rc == 0:
                break
            time.sleep(0.3)
        if rc != 0:
            buf = ctypes.create_unicode_buffer(256)
            ctypes.windll.winmm.mciGetErrorStringW(rc, buf, 256)
            raise RuntimeError(f"เปิดไฟล์เสียงไม่ได้ ({buf.value.strip() or rc}): {os.path.basename(path)}")
        self.alias = alias
        self.mci(f"play {alias}", None, 0, None)

    def is_playing(self):
        if not self.alias:
            return False
        buf = ctypes.create_unicode_buffer(64)
        self.mci(f"status {self.alias} mode", buf, 64, None)
        return buf.value == "playing"

    def stop(self):
        if self.alias:
            self.mci(f"stop {self.alias}", None, 0, None)
            self.mci(f"close {self.alias}", None, 0, None)
            self.alias = None
