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
model_connection.py - เชื่อมต่อ/สลับเส้นทางโมเดล: Ollama ในเครื่อง หรือ API ออนไลน์สำรอง
(ตั้งค่าใน ⚙ ผู้ให้บริการ - provider_dialog.py) แล้วอัปเดตช่องเลือกโมเดลกับสถานะ

แยกออกจาก run_gui() เพราะเป็นกลุ่มลอจิกที่ใช้ settings['api']/BACKEND/st ร่วมกันชัดเจน
จุดเชื่อมกับส่วนอื่น: model_cb (ช่องเลือกโมเดล) ที่ผูก on_model_change ไว้, connect() ที่เรียก
ตอนเริ่มโปรแกรม/กด F5/จาก provider_dialog หลังบันทึก/ดาวน์โหลดโมเดลเสร็จ, และ on_ready callback
ที่ run_gui() ใช้ต่อ (เช่น test hook TRANSLATOR_SPEAK_DEMO) หลัง on_models() จัดการเส้นทางเสร็จ
"""
import logging
import threading

import os
import subprocess

from engine import BACKEND, api_ready, ensure_ollama, find_ollama_exe, list_models, pick_model, resolve_api_key, warm_up

log = logging.getLogger(__name__)

RETRY_MS = 10_000   # เชื่อมต่อ Ollama ไม่ได้: ลองใหม่เบื้องหลังทุก 10 วินาที
API_TAG = "☁ "   # รายการโมเดลออนไลน์ในช่องโมเดลขึ้นต้นด้วยเครื่องหมายนี้


class ModelConnection:
    def __init__(self, root, settings, save_settings, st, worker, q, model_cb, model_var, set_status, on_ready=None):
        self.root = root
        self.settings = settings
        self.save_settings = save_settings
        self.st = st
        self.worker = worker
        self.q = q
        self.model_cb = model_cb
        self.model_var = model_var
        self.set_status = set_status
        self.on_ready = on_ready
        self.model_cb.bind("<<ComboboxSelected>>", self.on_model_change)

    def api_configured(self):
        a = self.settings.get("api") or {}
        return api_ready(a)

    def use_backend(self, mode):
        """สลับเส้นทางที่ใช้จริง: 'local' หรือ 'api'"""
        a = self.settings.get("api") or {}
        BACKEND.update(mode=mode, base=a.get("base", ""), key=resolve_api_key(a), model=a.get("model", ""), fallback_model="")
        self.st["backend"] = mode
        if mode == "api":
            self.st["model"] = a.get("model", "")   # ให้ปุ่มแปล/ถามผ่านการตรวจ "มีโมเดล" (chat_stream ใช้ BACKEND['model'] เอง)

    def on_model_change(self, _=None):
        name = self.model_var.get()
        if name.startswith(API_TAG):
            self.use_backend("api"); self.settings["model"] = name; self.save_settings()
            self.set_status(f"ใช้โมเดลออนไลน์ {BACKEND['model']} ผ่าน API"); return
        self.use_backend("local")
        self.st["model"] = name; self.settings["model"] = name; self.save_settings()
        def load():   # โหลดเสร็จแล้วต้องเปลี่ยนสถานะด้วย — เดิมค้าง "กำลังโหลด ... เข้า GPU" ตลอดแม้โมเดลพร้อมแล้ว
            warm_up(name)
            self.root.after(0, lambda: self.set_status(f"พร้อมใช้งาน · {name}") if not self.worker["busy"] else None)
        threading.Thread(target=load, daemon=True).start()
        self.set_status(f"กำลังโหลด {name} เข้า GPU ...")

    def on_models(self, models):
        """models = รายการโมเดลในเครื่อง (None = ไม่พบ Ollama) -> เลือกเส้นทางตามโหมดใน ⚙ ผู้ให้บริการ"""
        a = self.settings.get("api") or {}
        mode = a.get("mode", "auto")
        local_ok = bool(models)
        api_ok = self.api_configured()
        api_entry = (API_TAG + a.get("model", "")) if api_ok else None
        values = list(models or []) + ([api_entry] if api_entry else [])
        self.st["models"] = list(models or []); self.model_cb["values"] = values
        # อัตโนมัติ = ใช้ API ก่อน (เร็ว/คุณภาพสูงกว่าโมเดล 4B ในเครื่อง) ถ้ายังไม่ได้ตั้ง API ค่อยใช้โมเดลในเครื่อง
        want_api = (mode == "api" and api_ok) or (mode == "auto" and api_ok)
        if want_api:
            self.use_backend("api"); self.model_var.set(api_entry)
            why = ""
            if mode == "auto" and local_ok:   # API ล้มเมื่อไร chat_stream ถอยไปใช้โมเดลในเครื่องตัวนี้เอง
                saved = self.settings.get("model", "")
                BACKEND["fallback_model"] = saved if saved in models else pick_model(models)
                why = f" (อัตโนมัติ · ถ้า API ล้มจะใช้ {BACKEND['fallback_model']} ในเครื่องแทน)"
            elif mode == "auto":
                why = " (อัตโนมัติ · ไม่พบโมเดลในเครื่อง)"
            self.set_status(f"พร้อมใช้งาน · โมเดลออนไลน์ {a.get('model')} ผ่าน API{why}")
        elif local_ok:
            self.use_backend("local")
            saved = self.settings.get("model", "")
            chosen = saved if saved in models else pick_model(models)
            self.model_var.set(chosen); self.st["model"] = chosen
            note = "" if chosen.startswith("scb10x/typhoon2.5") else " (แนะนำ typhoon2.5-qwen3-4b สำหรับภาษาไทย)"
            self.set_status(f"พร้อม · โมเดล {chosen}{note} · กำลังอุ่นเครื่องเข้า GPU ...")
            def _startup_warm(m=chosen):
                warm_up(m)
                self.root.after(0, lambda: self.set_status(f"พร้อมใช้งาน · {m}") if not self.worker["busy"] else None)
                self.q.put(("piece", ""))
            threading.Thread(target=_startup_warm, daemon=True).start()
        else:
            self.use_backend("local"); self.st["model"] = ""
            self.model_var.set("ไม่พบโมเดล" if models is None else "ยังไม่มีโมเดลในเครื่อง")
            self.set_status(("เชื่อมต่อ Ollama ไม่ได้ (จะลองใหม่เองทุก 10 วินาที)" if models is None else "Ollama ทำงานแต่ยังไม่มีโมเดล")
                            + " - กด ⚙ ผู้ให้บริการ เพื่อดาวน์โหลดโมเดลในเครื่อง หรือใส่ API key ใช้โมเดลออนไลน์")
            if models is None:   # เช่น เปิดเครื่องตอน Ollama กำลังอัปเดต/ยังไม่ขึ้น: เดิมต้องกด F5 เอง
                self.root.after(RETRY_MS, self.retry_quietly)
            return
        if self.on_ready:
            self.on_ready(models)

    def connect(self):
        a = self.settings.get("api") or {}
        mode = a.get("mode", "auto")
        if mode in ("auto", "api") and self.api_configured():
            self.q.put(("models", None))
            self.set_status("กำลังเชื่อมต่อ API ออนไลน์ + เปิด Ollama เบื้องหลัง ...")
            def _bg():
                models = ensure_ollama()
                if models:
                    self.q.put(("models", models))
            threading.Thread(target=_bg, daemon=True).start()
        else:
            self.set_status("กำลังเชื่อมต่อ Ollama (ถ้ายังไม่เปิดจะเปิดให้เอง) ...")
            threading.Thread(target=lambda: self.q.put(("models", ensure_ollama())), daemon=True).start()

    def retry_quietly(self):
        """ลองเชื่อมต่อ Ollama ใหม่เบื้องหลัง — ถ้ายังไม่ทำงานจะลองเปิดให้เองด้วย"""
        if self.st.get("model") or BACKEND.get("mode") == "api":
            return

        def check():
            models = list_models()
            if models is None:
                self._try_start_ollama()
                models = list_models()
            if models is not None:
                log.info("เชื่อมต่อ Ollama ได้แล้ว (ลองใหม่อัตโนมัติ) พบ %d โมเดล", len(models))
            self.q.put(("models", models))
        threading.Thread(target=check, daemon=True).start()

    @staticmethod
    def _try_start_ollama():
        """ลองเปิด ollama serve ถ้ายังไม่มี process — ไม่รอนาน แค่จุดเริ่ม"""
        try:
            out = subprocess.check_output(["tasklist", "/FI", "IMAGENAME eq ollama.exe", "/NH"],
                                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                                          timeout=5, text=True)
            if "ollama.exe" in out.lower():
                return
        except Exception:
            pass
        exe = find_ollama_exe()
        if not exe:
            return
        env = dict(os.environ)
        env.setdefault("OLLAMA_ORIGINS", "*")
        env.setdefault("OLLAMA_FLASH_ATTENTION", "1")
        env.setdefault("OLLAMA_KV_CACHE_TYPE", "q8_0")
        try:
            subprocess.Popen([exe, "serve"], env=env,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            log.info("retry: เปิด Ollama (%s) อีกครั้ง", exe)
            import time; time.sleep(5)
        except Exception:
            log.warning("retry: เปิด Ollama ไม่สำเร็จ", exc_info=True)
