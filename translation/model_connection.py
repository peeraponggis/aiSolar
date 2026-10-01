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

from engine import BACKEND, ensure_ollama, pick_model, warm_up

log = logging.getLogger(__name__)

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
        return bool(a.get("base") and a.get("key") and a.get("model"))

    def use_backend(self, mode):
        """สลับเส้นทางที่ใช้จริง: 'local' หรือ 'api'"""
        a = self.settings.get("api") or {}
        BACKEND.update(mode=mode, base=a.get("base", ""), key=a.get("key", ""), model=a.get("model", ""))
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
        threading.Thread(target=warm_up, args=(self.st["model"],), daemon=True).start()
        self.set_status(f"กำลังโหลด {self.st['model']} เข้า GPU ...")

    def on_models(self, models):
        """models = รายการโมเดลในเครื่อง (None = ไม่พบ Ollama) -> เลือกเส้นทางตามโหมดใน ⚙ ผู้ให้บริการ"""
        a = self.settings.get("api") or {}
        mode = a.get("mode", "auto")
        local_ok = bool(models)
        api_ok = self.api_configured()
        api_entry = (API_TAG + a.get("model", "")) if api_ok else None
        values = list(models or []) + ([api_entry] if api_entry else [])
        self.st["models"] = list(models or []); self.model_cb["values"] = values
        want_api = (mode == "api" and api_ok) or (mode == "auto" and not local_ok and api_ok)
        if want_api:
            self.use_backend("api"); self.model_var.set(api_entry)
            why = "" if mode == "api" else " (ไม่พบโมเดลในเครื่อง จึงสลับให้อัตโนมัติ)"
            self.set_status(f"พร้อมใช้งาน · โมเดลออนไลน์ {a.get('model')} ผ่าน API{why}")
        elif local_ok:
            self.use_backend("local")
            saved = self.settings.get("model", "")
            chosen = saved if saved in models else pick_model(models)
            self.model_var.set(chosen); self.st["model"] = chosen
            note = "" if chosen.startswith("scb10x/typhoon2.5") else " (แนะนำ typhoon2.5-qwen3-4b สำหรับภาษาไทย)"
            self.set_status(f"พร้อม · โมเดล {chosen}{note} · กำลังอุ่นเครื่องเข้า GPU ...")
            threading.Thread(target=lambda: (warm_up(chosen), self.q.put(("piece", ""))), daemon=True).start()
            self.root.after(1500, lambda: self.set_status(f"พร้อมใช้งาน · {chosen}") if not self.worker["busy"] else None)
        else:
            self.use_backend("local"); self.st["model"] = ""
            self.model_var.set("ไม่พบโมเดล" if models is None else "ยังไม่มีโมเดลในเครื่อง")
            self.set_status(("เชื่อมต่อ Ollama ไม่ได้" if models is None else "Ollama ทำงานแต่ยังไม่มีโมเดล")
                            + " - กด ⚙ ผู้ให้บริการ เพื่อดาวน์โหลดโมเดลในเครื่อง หรือใส่ API key ใช้โมเดลออนไลน์")
            return
        if self.on_ready:
            self.on_ready(models)

    def connect(self):
        self.set_status("กำลังเชื่อมต่อ Ollama (ถ้ายังไม่เปิดจะเปิดให้เอง) ...")
        threading.Thread(target=lambda: self.q.put(("models", ensure_ollama())), daemon=True).start()
