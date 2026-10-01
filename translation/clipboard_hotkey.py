#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
clipboard_hotkey.py - เฝ้าคลิปบอร์ด (แปลอัตโนมัติเมื่อมีการคัดลอกข้อความใหม่) และตอบสนอง
คีย์ลัดทั่วเครื่อง/ไอคอนลอย (จำลอง Ctrl+C แล้วอ่านคลิปบอร์ดมาแปล)

แยกออกจาก run_gui() เพราะเป็นกลุ่มฟังก์ชันที่ใช้คลิปบอร์ดร่วมกันชัดเจน จุดเชื่อมกับส่วนอื่น
ของโปรแกรม: start_translate/worker/settings ที่ส่งเข้ามาตอนสร้าง, ปุ่ม "วาง+แปล"/"คัดลอก"
ที่เรียก paste_and_translate()/copy_result(), on_hotkey/hotkey_status ที่ win_event_thread
เรียกจากเธรดคีย์ลัด, และ hotkey_captured() ที่ pump() เรียกเมื่อมีคิวงาน "hotkey" เข้ามา
"""
import time

from engine import HOTKEY_LABEL
from win_hooks import send_ctrl_c


class ClipboardHotkey:
    def __init__(self, root, st, src, dst, set_status, start_translate, worker,
                 settings, clip_var, hotkey_var, topmost_var, q):
        self.root = root
        self.st = st
        self.src = src
        self.dst = dst
        self.set_status = set_status
        self.start_translate = start_translate
        self.worker = worker
        self.settings = settings
        self.clip_var = clip_var
        self.hotkey_var = hotkey_var
        self.topmost_var = topmost_var
        self.q = q

    def copy_result(self):
        r = self.dst.get("1.0", "end").strip()
        if r:
            self.root.clipboard_clear(); self.root.clipboard_append(r); self.st["last_clip"] = r
            self.set_status("คัดลอกคำแปลแล้ว")

    def read_clipboard(self):
        try:
            return self.root.clipboard_get()
        except Exception:
            return ""

    def paste_and_translate(self):
        t = self.read_clipboard().strip()
        if t:
            self.src.delete("1.0", "end"); self.src.insert("1.0", t); self.start_translate()

    def bring_to_front(self):
        self.root.deiconify(); self.root.lift(); self.root.attributes("-topmost", True)
        self.root.after(300, lambda: self.root.attributes("-topmost", self.topmost_var.get()))
        self.root.focus_force()

    def hotkey_captured(self):
        """เรียกจาก pump() เมื่อมีคิวงาน 'hotkey' (ผู้ใช้กดคีย์ลัด/คลิกไอคอนลอย)"""
        t = self.read_clipboard().strip()
        if t and t != self.st["last_result"]:
            self.src.delete("1.0", "end"); self.src.insert("1.0", t)
            self.bring_to_front(); self.start_translate()
        else:
            self.bring_to_front()
            self.set_status("ไม่พบข้อความที่เลือก - ลากคลุมข้อความก่อนแล้วกด " + HOTKEY_LABEL)

    def on_hotkey(self):
        """เรียกจากเธรด win_event_thread (ไม่ใช่เธรดหลัก) ตอนกดคีย์ลัดทั่วเครื่อง"""
        send_ctrl_c(); time.sleep(0.25); self.q.put(("hotkey",))

    def hotkey_status(self, hot_ok, hook_ok):
        """เรียกจากเธรด win_event_thread ครั้งเดียวตอนเริ่ม เพื่อรายงานว่าลงทะเบียนคีย์ลัด/mouse hook สำเร็จหรือไม่"""
        self.st["hotkey_ok"] = hot_ok
        parts = ["ลากคลุมข้อความในโปรแกรมใดก็ได้ แล้วคลิกไอคอนหุ่นยนต์ที่ลอยขึ้นมา" if hook_ok else "ตรวจการลากคลุมไม่ได้"]
        parts.append(f"หรือกด {hot_ok}" if hot_ok else "คีย์ลัด Ctrl+Alt+T/Y ถูกโปรแกรมอื่นใช้อยู่")
        self.hotkey_var.set(" · ".join(parts))

    def clip_poll(self):
        if self.clip_var.get() and not self.worker["busy"]:
            t = self.read_clipboard()
            if t and t.strip() and t != self.st["last_clip"] and t.strip() != self.st["last_result"]:
                self.st["last_clip"] = t
                self.src.delete("1.0", "end"); self.src.insert("1.0", t.strip()); self.start_translate()
            elif self.st["last_clip"] is None:
                self.st["last_clip"] = t
        self.root.after(700, self.clip_poll)
