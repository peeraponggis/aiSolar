#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ollama_client.py - เชื่อมต่อโมเดลในเครื่องผ่าน Ollama สำหรับลุงพี agent

พอร์ตฟังก์ชันกลุ่ม Ollama มาจาก F:/LocalAI/translation/engine.py ของ Local Translator
(ollama_get/list_models/find_ollama_exe/ensure_ollama/pick_model/stream_chat/warm_up/
clean_output) ตัดส่วนที่เฉพาะกับการแปลภาษาออก (glossary, LEVELS, build_messages, API ออนไลน์
สำรอง) เพราะ agent ตัวนี้คุยทั่วไปและเรียกเครื่องมือ (tool-calling) แทน

เพิ่มเติมจาก engine.py เดิม: stream_chat() รับพารามิเตอร์ tools เสริม ส่งต่อให้ Ollama
/api/chat ตรงๆ (Ollama >= 0.6.7 รองรับ native tool-calling - ตรวจสอบแล้วว่าโมเดล
scb10x/typhoon2.5-qwen3-4b ที่ใช้อยู่มี "capabilities": ["completion", "tools"]) และอ่าน
message.tool_calls จาก response กลับมาเป็นส่วนหนึ่งของ stats
"""
import json
import logging
import os
import re
import time
import urllib.error
import urllib.request

log = logging.getLogger(__name__)

OLLAMA_URL = "http://" + os.environ.get("OLLAMA_HOST", "127.0.0.1:11434").replace("http://", "")
DEFAULT_MODEL = os.environ.get("LUNGPEE_MODEL", "scb10x/typhoon2.5-qwen3-4b:latest")
FALLBACK_MODELS = ["scb10x/typhoon2.5-qwen3-4b", "qwen2.5:7b-instruct", "qwen2.5:7b",
                   "scb10x/llama3.2-typhoon2-3b-instruct", "llama3.1:8b", "hermes3:3b"]
NUM_CTX = 4096          # เท่ากับ Local Translator - รัน 100% GPU บน VRAM 4GB
KEEP_ALIVE = "30m"
THINK_RE = re.compile(r"<think>.*?</think>\s*", re.S)


def ollama_get(path, timeout=5):
    with urllib.request.urlopen(OLLAMA_URL + path, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def list_models():
    try:
        return [m["name"] for m in ollama_get("/api/tags").get("models", [])]
    except Exception as e:
        log.debug("เชื่อมต่อ Ollama ที่ %s ไม่ได้: %s", OLLAMA_URL, e)
        return None


def find_ollama_exe():
    """หา ollama.exe: PATH, โฟลเดอร์ติดตั้งมาตรฐาน, หรือชุดพกพาข้าง LocalAI"""
    import shutil
    base = os.path.dirname(os.path.abspath(__file__))
    cands = [shutil.which("ollama"),
             os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Ollama", "ollama.exe"),
             os.path.join(os.environ.get("ProgramFiles", ""), "Ollama", "ollama.exe"),
             os.path.join(base, "..", "ollama", "ollama.exe")]
    for c in cands:
        if c and os.path.exists(c):
            return os.path.normpath(c)
    return None


def ensure_ollama(wait_s=25):
    """ถ้าเชื่อมต่อ Ollama ไม่ได้ ให้ลองเปิด 'ollama serve' เอง (ซ่อนหน้าต่าง) แล้วรอจนพร้อม คืน list โมเดลหรือ None"""
    models = list_models()
    if models is not None:
        return models
    exe = find_ollama_exe()
    if not exe:
        return None
    import subprocess
    env = dict(os.environ)
    env.setdefault("OLLAMA_ORIGINS", "*"); env.setdefault("OLLAMA_KEEP_ALIVE", KEEP_ALIVE)
    env.setdefault("OLLAMA_FLASH_ATTENTION", "1"); env.setdefault("OLLAMA_KV_CACHE_TYPE", "q8_0")
    portable_models = os.path.join(os.path.dirname(exe), "..", "models")
    if os.path.isdir(portable_models) and "OLLAMA_MODELS" not in env:
        env["OLLAMA_MODELS"] = os.path.normpath(portable_models)
    try:
        subprocess.Popen([exe, "serve"], env=env, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        log.warning("เปิด Ollama (%s) ไม่สำเร็จ", exe, exc_info=True)
        return None
    for _ in range(wait_s * 2):
        time.sleep(0.5)
        models = list_models()
        if models is not None:
            log.info("เปิด Ollama (%s) สำเร็จ พบ %d โมเดล", exe, len(models))
            return models
    log.warning("เปิด Ollama (%s) แล้วแต่รอ %ds ไม่เชื่อมต่อสำเร็จ", exe, wait_s)
    return None


def pick_model(available):
    if DEFAULT_MODEL in available:
        return DEFAULT_MODEL
    for cand in [DEFAULT_MODEL] + FALLBACK_MODELS:
        for name in available:
            if name.split(":")[0] == cand.split(":")[0]:
                return name
    return available[0] if available else DEFAULT_MODEL


def chat(model, messages, temperature=0.4, tools=None, stop_event=None):
    """เรียก Ollama /api/chat แบบไม่สตรีม (stream:false) - ใช้ตอน agent loop ที่ต้องอ่าน
    message.tool_calls ทั้งก้อนก่อนตัดสินใจขั้นต่อไป (ต่างจาก stream_chat ที่ไว้อ่านทีละส่วน
    เพื่อแสดงผล/พูดระหว่างสร้าง) คืน dict ทั้งข้อความ (message.content) และ tool_calls ถ้ามี"""
    body = {
        "model": model, "messages": messages, "stream": False, "think": False,
        "keep_alive": KEEP_ALIVE,
        "options": {"num_ctx": NUM_CTX, "temperature": temperature, "top_p": 0.9, "repeat_penalty": 1.05},
    }
    if tools:
        body["tools"] = tools
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(OLLAMA_URL + "/api/chat", data=data, headers={"Content-Type": "application/json"})
    try:
        resp = urllib.request.urlopen(req, timeout=600)
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8", "replace")
        if "think" in msg:  # โมเดลไม่รับพารามิเตอร์ think -> ส่งใหม่โดยไม่ใส่
            body.pop("think", None)
            req = urllib.request.Request(OLLAMA_URL + "/api/chat", data=json.dumps(body).encode("utf-8"),
                                         headers={"Content-Type": "application/json"})
            resp = urllib.request.urlopen(req, timeout=600)
        else:
            raise RuntimeError(f"Ollama HTTP {e.code}: {msg[:300]}")
    with resp:
        d = json.loads(resp.read().decode("utf-8"))
    if "error" in d:
        raise RuntimeError(d["error"])
    msg = d.get("message", {})
    return {
        "content": msg.get("content", ""),
        "tool_calls": msg.get("tool_calls") or [],
        "stats": {k: d.get(k) for k in ("eval_count", "eval_duration", "load_duration", "total_duration")},
    }


def stream_chat(model, messages, temperature=0.4, tools=None, stop_event=None):
    """generator: yield ข้อความทีละส่วนทันทีที่โมเดลสร้างออกมา (ไม่ต้องรอทั้งก้อนเหมือน chat())
    เพื่อให้เริ่มพูด/แสดงผลได้เร็วที่สุด - ลดความหน่วงที่ผู้ใช้รู้สึกได้ชัดตอนคำตอบยาว คืน
    {"tool_calls": [...], "stats": {...}} ผ่าน StopIteration.value (Ollama ส่ง tool_calls มาใน
    message ก้อนสุดท้ายของสตรีมถ้าโมเดลตัดสินใจเรียกเครื่องมือแทนที่จะตอบเป็นข้อความ)"""
    body = {
        "model": model, "messages": messages, "stream": True, "think": False,
        "keep_alive": KEEP_ALIVE,
        "options": {"num_ctx": NUM_CTX, "temperature": temperature, "top_p": 0.9, "repeat_penalty": 1.05},
    }
    if tools:
        body["tools"] = tools
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(OLLAMA_URL + "/api/chat", data=data, headers={"Content-Type": "application/json"})
    result = {"tool_calls": [], "stats": {}}
    try:
        resp = urllib.request.urlopen(req, timeout=600)
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8", "replace")
        if "think" in msg:
            body.pop("think", None)
            req = urllib.request.Request(OLLAMA_URL + "/api/chat", data=json.dumps(body).encode("utf-8"),
                                         headers={"Content-Type": "application/json"})
            resp = urllib.request.urlopen(req, timeout=600)
        else:
            raise RuntimeError(f"Ollama HTTP {e.code}: {msg[:300]}")
    with resp:
        for line in resp:
            if stop_event is not None and stop_event.is_set():
                break
            if not line.strip():
                continue
            d = json.loads(line.decode("utf-8"))
            if "error" in d:
                raise RuntimeError(d["error"])
            msg_d = d.get("message", {})
            piece = msg_d.get("content", "")
            if piece:
                yield piece
            if msg_d.get("tool_calls"):
                result["tool_calls"] = msg_d["tool_calls"]
            if d.get("done"):
                result["stats"] = {k: d.get(k) for k in ("eval_count", "eval_duration", "load_duration", "total_duration")}
    return result


def clean_output(text):
    text = THINK_RE.sub("", text)
    return text.strip()


def warm_up(model):
    try:
        list(stream_chat(model, [{"role": "user", "content": "ok /no_think"}], 0))
    except Exception:
        pass
