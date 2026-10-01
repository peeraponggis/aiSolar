#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
safety.py - ด่านความปลอดภัยก่อนรันเครื่องมือใดๆ ที่โมเดลเรียก (tool-calling)

อิงแนวทางจาก Open Interpreter / Microsoft UFO / งานวิจัย 2025-2026 ที่สำรวจไว้ก่อนเริ่ม Phase 2:
1. ขอ confirm ก่อนรันเสมอสำหรับ Tier C (เสี่ยงสูง - ย้อนกลับไม่ได้/กระทบระบบ)
2. จำกัดโปรแกรม/คำสั่งที่อนุญาตไว้ล่วงหน้า (allowlist) - ป้องกันดีกว่าตรวจจับทีหลัง
3. เขียนทับไฟล์ที่มีอยู่แล้วถือเป็นความเสี่ยงสูงกว่าสร้างไฟล์ใหม่ (ยกระดับ B -> C อัตโนมัติ)

RISK_TIER: "A" รันได้เลย, "B" รันได้แต่บันทึก log ไว้ (ย้อนกลับง่าย), "C" ต้อง confirm ก่อนเสมอ
"""
import ctypes
import logging
import os

log = logging.getLogger(__name__)

RISK_TIER = {
    "launch_app": "A",
    "list_dir": "A",
    "read_file": "A",
    "translate_file": "B",
    "write_file": "B",
    "run_shell": "C",
    "delete_file": "C",
}

# โปรแกรมที่อนุญาตให้ launch_app เปิดได้โดยไม่ต้อง confirm (นอกรายชื่อนี้ = ต้อง confirm แม้ Tier A)
ALLOWED_APPS = {
    "notepad", "โน้ตแพด", "calculator", "calc", "เครื่องคิดเลข",
    "explorer", "file explorer", "ตัวจัดการไฟล์", "paint", "wordpad",
    "chrome", "google chrome", "edge", "msedge", "code", "vscode", "visual studio code",
}

MB_YESNO, MB_ICONWARNING, MB_TOPMOST = 0x4, 0x30, 0x40000
IDYES = 6


def confirm(title, message):
    """แสดงกล่องโต้ตอบ Yes/No ของ Windows (บล็อกเธรดที่เรียกจนกว่าผู้ใช้จะตอบ) คืน True ถ้ากด Yes"""
    try:
        res = ctypes.windll.user32.MessageBoxW(0, message, title, MB_YESNO | MB_ICONWARNING | MB_TOPMOST)
        return res == IDYES
    except Exception:
        log.exception("แสดงกล่อง confirm ไม่สำเร็จ - ปฏิเสธคำสั่งไว้ก่อนเพื่อความปลอดภัย")
        return False


def _describe(tool_name, args):
    if tool_name == "run_shell":
        return f"รันคำสั่ง PowerShell:\n{args.get('command', '')}"
    if tool_name == "delete_file":
        return f"ลบไฟล์:\n{args.get('path', '')}"
    if tool_name == "write_file":
        return f"เขียนทับไฟล์ที่มีอยู่แล้ว:\n{args.get('path', '')}"
    if tool_name == "launch_app":
        return f"เปิดโปรแกรม:\n{args.get('name', '')}"
    return f"{tool_name}({args})"


def check(tool_name, args):
    """ตรวจสิทธิ์ + ขอ confirm ถ้าจำเป็น คืน (allowed: bool, reason: str|None)"""
    tier = RISK_TIER.get(tool_name, "C")   # เครื่องมือที่ไม่รู้จัก = ถือว่าเสี่ยงสูงสุดไว้ก่อน

    if tool_name == "launch_app":
        name = (args.get("name") or "").strip().lower()
        if name not in ALLOWED_APPS:
            ok = confirm("ลุงพีขออนุญาต", _describe(tool_name, args) + "\n\n(ไม่อยู่ในรายชื่อโปรแกรมที่อนุญาตไว้ล่วงหน้า)")
            return (True, None) if ok else (False, "ผู้ใช้ไม่อนุญาตให้เปิดโปรแกรมนี้")
        return True, None

    if tool_name == "write_file":
        path = args.get("path") or ""
        if os.path.exists(path):   # เขียนทับของเดิม = ยกระดับเป็น Tier C
            ok = confirm("ลุงพีขออนุญาต", _describe(tool_name, args))
            return (True, None) if ok else (False, "ผู้ใช้ไม่อนุญาตให้เขียนทับไฟล์นี้")
        return True, None

    if tier == "C":
        ok = confirm("ลุงพีขออนุญาต", _describe(tool_name, args))
        return (True, None) if ok else (False, "ผู้ใช้ไม่อนุญาตให้ทำรายการนี้")

    return True, None
