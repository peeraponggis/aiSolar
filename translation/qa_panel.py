#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
qa_panel.py - แผง "ถามโมเดลเกี่ยวกับข้อความนี้" (ปุ่มคำถามสำเร็จรูป + ถามอิสระ)

แยกออกจาก run_gui() เพราะฟีเจอร์นี้ถูกออกแบบมาให้เป็นบล็อกแยกตั้งแต่แรก (ดูคอมเมนต์เดิม
"บล็อกแยก ไม่แตะการแปล") จุดเชื่อมกับส่วนอื่นของโปรแกรมมีไม่กี่จุด: สร้างปุ่มเปิด/ปิดใน
แถบปุ่มหลัก, สร้างแผงของตัวเองใต้กล่องข้อความ, ให้ reset()/clear() ให้ workflow การแปล
เรียกตอนเริ่มแปลข้อความใหม่ และ on_piece()/on_done()/on_error() ให้ pump() (ตัวอ่านคิวงาน
หลักใน run_gui) เรียกเมื่อมีผลลัพธ์จากเธรด worker ของแผงนี้เอง
"""
import logging
import os
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk

from engine import DEFAULT_QUESTIONS, build_qa_messages, chat_stream, clean_output, detect_lang
from flow_layout import Flow

log = logging.getLogger(__name__)


class QAPanel:
    def __init__(self, root, btns, bottom_box, settings, save_settings, set_status,
                 text_font, small_font, worker, st, src, dst, q, speak_text, stop_speech):
        self.root = root
        self.settings = settings
        self.save_settings = save_settings
        self.set_status = set_status
        self.worker = worker
        self.st = st
        self.src = src
        self.dst = dst
        self.q = q
        self.speak_text = speak_text
        self.stop_speech = stop_speech
        self.small_font = small_font

        self.state = {"busy": False, "stop": threading.Event(), "history": [], "open": False,
                      "edit": False, "question": ""}
        self.pill_widgets = []

        self.btn = ttk.Button(btns, text="❓ ถามโมเดล ▾", style="Big.TButton", command=self.toggle)
        btns.add(self.btn, padx=(12, 0))

        self.frame = ttk.LabelFrame(bottom_box, text=" ถามโมเดลเกี่ยวกับข้อความนี้ ", padding=(10, 4))
        self.pills = Flow(self.frame); self.pills.pack(fill="x")
        row = Flow(self.frame); row.pack(fill="x", pady=(4, 2))
        self.inp = ttk.Entry(row, width=48); row.add(self.inp, padx=(0, 8))
        self.ask_btn = ttk.Button(row, text="ถาม", command=lambda: self.ask(self.inp.get())); row.add(self.ask_btn)
        row.add(ttk.Button(row, text="+ บันทึกเป็นปุ่ม", command=lambda: self.add_question(self.inp.get())))
        self.edit_btn = ttk.Button(row, text="แก้ไขปุ่ม", command=self.toggle_edit); row.add(self.edit_btn)
        bar = Flow(self.frame); bar.pack(fill="x", pady=(4, 0), side="bottom")   # แถวปุ่มอยู่ล่างสุดเสมอ ไม่ถูกช่องคำตอบดันหลุด
        self.out = tk.Text(self.frame, wrap="word", font=text_font, padx=8, pady=6, relief="solid",
                            borderwidth=1, height=4, width=20, background="#F4F6FB")
        self.out.pack(fill="both", expand=True)
        bar.add(ttk.Button(bar, text="หยุด", command=self._stop))  # หยุดทั้งคำตอบและเสียงอ่าน ใช้ได้ตลอด
        bar.add(ttk.Button(bar, text="🔊 อ่านคำตอบ", command=lambda: self.speak_text(self.out.get("1.0", "end"))))
        bar.add(ttk.Button(bar, text="คัดลอกคำตอบ", command=self._copy))
        bar.add(ttk.Button(bar, text="ล้างบทสนทนา", command=lambda: (self.reset(), self.out.delete("1.0", "end"))))
        self.speak_var = tk.BooleanVar(value=settings["qaAutoSpeak"])
        bar.add(ttk.Checkbutton(bar, text="อ่านคำตอบอัตโนมัติ", variable=self.speak_var,
                                command=lambda: (settings.update(qaAutoSpeak=self.speak_var.get()), save_settings())))
        self.size_btn = ttk.Button(bar, text="ขยายช่องคำตอบ ▴", command=self.toggle_size); bar.add(self.size_btn, padx=(12, 6))
        self.hint = ttk.Label(bar, text="", font=small_font, foreground="#777"); bar.add(self.hint)
        self.inp.bind("<Return>", lambda e: (self.ask(self.inp.get()), "break"))

    # ---------- UI helpers
    def _stop(self):
        self.state["stop"].set(); self.stop_speech(); self.set_status("หยุดแล้ว")

    def _copy(self):
        self.root.clipboard_clear(); self.root.clipboard_append(self.out.get("1.0", "end").strip())
        self.set_status("คัดลอกคำตอบแล้ว")

    def toggle_size(self):
        big = self.out.cget("height") <= 4
        self.out.configure(height=12 if big else 4)
        self.size_btn.config(text="ย่อช่องคำตอบ ▾" if big else "ขยายช่องคำตอบ ▴")

    def render_pills(self):
        self.pills.clear(); self.pill_widgets.clear()
        for i, qtext in enumerate(self.settings["questions"]):
            if self.state["edit"]:
                b = ttk.Button(self.pills, text="× " + qtext, command=lambda i=i: self.delete_question(i))
            else:
                b = ttk.Button(self.pills, text=qtext, command=lambda t=qtext: self.ask(t))
            self.pills.add(b); self.pill_widgets.append(b)
        if self.state["edit"]:
            b = ttk.Button(self.pills, text="คืนค่าเริ่มต้น",
                           command=lambda: (self.settings.update(questions=list(DEFAULT_QUESTIONS)),
                                            self.save_settings(), self.render_pills()))
            self.pills.add(b); self.pill_widgets.append(b)
        if not self.settings["questions"] and not self.state["edit"]:
            self.pills.add(ttk.Label(self.pills, text="ยังไม่มีปุ่มคำถาม พิมพ์คำถามแล้วกด '+ บันทึกเป็นปุ่ม'",
                                     font=self.small_font, foreground="#777"))
        self.hint.config(text="โหมดแก้ไข: คลิกปุ่มเพื่อลบ" if self.state["edit"] else "คลิกปุ่มคำถามเพื่อถามทันที · ถามต่อเนื่องได้")

    def add_question(self, text):
        text = (text or "").strip()
        if not text:
            self.set_status("พิมพ์คำถามในช่องก่อน แล้วกด '+ บันทึกเป็นปุ่ม'"); return
        if text in self.settings["questions"]:
            self.set_status("มีปุ่มคำถามนี้อยู่แล้ว"); return
        self.settings["questions"].append(text); self.save_settings(); self.render_pills()
        self.set_status(f"เพิ่มปุ่มคำถาม: {text}")

    def delete_question(self, i):
        if 0 <= i < len(self.settings["questions"]):
            removed = self.settings["questions"].pop(i); self.save_settings(); self.render_pills()
            self.set_status(f"ลบปุ่มคำถาม: {removed}")

    def toggle_edit(self):
        self.state["edit"] = not self.state["edit"]
        self.edit_btn.config(text="เสร็จ" if self.state["edit"] else "แก้ไขปุ่ม")
        self.render_pills()

    def toggle(self, force=None):
        want = (not self.state["open"]) if force is None else force
        self.state["open"] = want
        if want:
            self.frame.pack(fill="x", padx=10, pady=(0, 4))   # ใต้แถวปุ่มในกล่องล่าง (จองที่ก่อนช่องข้อความ)
            self.btn.config(text="❓ ถามโมเดล ▴")
            self.render_pills()
            sh = self.root.winfo_screenheight()
            if self.root.winfo_height() < 900 and sh >= 1000:
                self.root.geometry(f"{max(self.root.winfo_width(), 1000)}x{min(980, sh - 80)}")
            self.inp.focus_set()
        else:
            self.frame.pack_forget(); self.btn.config(text="❓ ถามโมเดล ▾")
        self.settings["qaOpen"] = want; self.save_settings()

    def set_busy(self, busy):
        self.state["busy"] = busy
        self.ask_btn.state(["disabled"] if busy else ["!disabled"])
        for b in self.pill_widgets:
            try:
                b.state(["disabled"] if busy else ["!disabled"])
            except Exception:
                pass

    def reset(self):
        self.state["history"].clear()

    def clear(self):
        """ใช้ตอนข้อความต้นทางเปลี่ยน (เริ่มแปลใหม่) - ล้างทั้งกล่องคำตอบและบทสนทนาเดิม"""
        self.out.delete("1.0", "end"); self.reset()

    def ask(self, question):
        question = (question or "").strip()
        if not question:
            self.set_status("พิมพ์คำถาม หรือคลิกปุ่มคำถาม"); return
        if self.state["busy"]:
            self.set_status("กำลังตอบคำถามก่อนหน้าอยู่ กด 'หยุด' ก่อนถ้าต้องการถามใหม่"); return
        if self.worker["busy"]:
            self.set_status("รอให้แปลเสร็จก่อน แล้วค่อยถาม"); return
        if not self.st["model"]:
            self.set_status("ยังไม่ได้เชื่อมต่อโมเดล"); return
        src_text = self.src.get("1.0", "end").strip()
        translation = self.dst.get("1.0", "end").strip()
        if not src_text and not translation:
            self.set_status("กรุณาใส่ข้อความหรือแปลก่อน"); return
        s_lang = detect_lang(src_text) if src_text else ("en" if detect_lang(translation) == "th" else "th")
        d_lang = "en" if s_lang == "th" else "th"
        msgs = build_qa_messages(src_text, s_lang, translation, d_lang, self.state["history"], question)
        if not self.state["open"]:
            self.toggle(True)
        self.state["question"] = question
        self.out.delete("1.0", "end")
        self.state["stop"].clear(); self.set_busy(True); self.stop_speech()
        self.set_status(f"กำลังถาม: {question[:60]} ...")

        model, stop_event, q = self.st["model"], self.state["stop"], self.q

        def job():
            t0 = time.time(); buf = []; stats = {}
            try:
                gen = chat_stream(model, msgs, 0.4, stop_event)
                while True:
                    try:
                        piece = next(gen)
                    except StopIteration as e:
                        stats = e.value or {}; break
                    buf.append(piece); q.put(("qa_piece", piece))
                q.put(("qa_done", "".join(buf), stats, time.time() - t0))
            except Exception as e:
                log.exception("ถามโมเดลผิดพลาด (model=%s)", model)
                q.put(("qa_error", str(e)))
        threading.Thread(target=job, daemon=True).start()

    # ---------- เรียกจาก pump() ใน run_gui เมื่อมีข้อความจากเธรด worker ของแผงนี้
    def on_piece(self, text):
        self.out.insert("end", text); self.out.see("end")

    def on_done(self, answer, stats, elapsed):
        self.set_busy(False)
        answer = clean_output(answer)
        self.out.delete("1.0", "end"); self.out.insert("1.0", answer)
        stopped = self.state["stop"].is_set()
        if answer and not stopped:
            self.state["history"].append((self.state["question"], answer))
        ev, ed = stats.get("eval_count") or 0, stats.get("eval_duration") or 0
        speed = f" · {ev/(ed/1e9):.1f} tok/s" if ed else ""
        self.set_status(("หยุดตอบแล้ว" if stopped else "ตอบเสร็จ") +
                        f" · {elapsed:.1f} วินาที{speed} · ถามต่อได้ ({len(self.state['history'])} คำถาม)")
        if os.environ.get("TRANSLATOR_QA_DEMO"):
            print(f"[qa-demo] ตอบเสร็จ {elapsed:.1f}s{speed}\n{answer}", file=sys.stderr, flush=True)
        if answer and not stopped and self.speak_var.get():
            self.speak_text(answer)

    def on_error(self, msg):
        self.set_busy(False)
        self.set_status("ถามไม่สำเร็จ: " + msg[:200])
