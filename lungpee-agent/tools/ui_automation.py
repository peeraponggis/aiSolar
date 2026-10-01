#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/ui_automation.py - คลิก/พิมพ์ลงช่องเฉพาะเจาะจงในโปรแกรมอื่นจริงๆ ผ่าน UI Automation (UIA)

ใช้แนวทาง "accessibility tree เป็นข้อความ" แทนการเดาพิกัดพิกเซล (ตามที่สำรวจไว้ก่อนเริ่ม
Phase 3: โปรเจกต์จริงที่ทำคล้ายกัน เช่น Microsoft UFO, BillJr99/AutoGUI ใช้วิธีนี้) เพราะโมเดล
ที่ใช้เป็นโมเดลข้อความล้วน ไม่มี vision จะเดาพิกัดพิกเซลไม่ได้เลย - list_ui_controls() อ่าน
โครงสร้างปุ่ม/ช่องของหน้าต่างที่โฟกัสอยู่เป็นข้อความสั้นๆ ให้โมเดลเลือกชื่อ แล้ว click_control()/
type_text() จะหาตัวควบคุมจากชื่อนั้นอีกที (ไม่ใช่จากพิกัด) จึงทนทานต่อหน้าต่างที่ย้าย/ปรับขนาด

list_ui_controls = Tier A (อ่านอย่างเดียว), click_control/type_text = Tier B (เปลี่ยนสถานะ
หน้าต่างอื่นได้ แต่ย้อนกลับง่ายกว่า run_shell/delete_file มาก)
"""
import ctypes
import logging

log = logging.getLogger(__name__)

MAX_CONTROLS = 60   # กัน context ของโมเดลยาวเกิน NUM_CTX ถ้าหน้าต่างมีตัวควบคุมเยอะมาก
NAMED_CONTROL_TYPES = {
    "Button", "Edit", "CheckBox", "RadioButton", "ComboBox", "MenuItem",
    "TabItem", "ListItem", "Hyperlink", "Text",
}


def _get_foreground_window():
    from pywinauto import Desktop
    hwnd = ctypes.windll.user32.GetForegroundWindow()
    if not hwnd:
        return None, "หาหน้าต่างที่โฟกัสอยู่ไม่เจอ"
    try:
        win = Desktop(backend="uia").window(handle=hwnd)
        return win, None
    except Exception as e:
        log.warning("เชื่อมต่อหน้าต่างผ่าน UIA ไม่ได้ (hwnd=%s)", hwnd, exc_info=True)
        return None, f"เชื่อมต่อหน้าต่างที่โฟกัสอยู่ไม่ได้: {e}"


def _find_control(win, name):
    """หาตัวควบคุมที่ชื่อมีคำว่า name อยู่ (ไม่สนตัวพิมพ์เล็ก/ใหญ่) - คืนตัวแรกที่เจอ"""
    needle = (name or "").strip().lower()
    if not needle:
        return None
    try:
        descendants = win.descendants()
    except Exception:
        log.warning("อ่านโครงสร้างหน้าต่างไม่ได้", exc_info=True)
        return None
    for ctrl in descendants:
        try:
            cname = (ctrl.element_info.name or "").strip().lower()
        except Exception:
            continue
        if cname and needle in cname:
            return ctrl
    return None


def _escape_keys(text):
    """ตัวอักษรพิเศษของ pywinauto.type_keys (+^%~(){}) ต้องครอบด้วย {} เองจึงจะพิมพ์ตามตัวอักษรจริง"""
    out = []
    for ch in text:
        out.append("{" + ch + "}" if ch in "+^%~(){}" else ch)
    return "".join(out)


def list_ui_controls():
    win, err = _get_foreground_window()
    if err:
        return {"ok": False, "error": err}
    try:
        title = win.window_text()
    except Exception:
        title = "(ไม่ทราบชื่อหน้าต่าง)"
    try:
        descendants = win.descendants()
    except Exception as e:
        log.warning("อ่านโครงสร้างหน้าต่าง '%s' ไม่ได้", title, exc_info=True)
        return {"ok": False, "error": f"อ่านโครงสร้างหน้าต่างไม่ได้: {e}"}
    controls = []
    for ctrl in descendants:
        if len(controls) >= MAX_CONTROLS:
            break
        try:
            info = ctrl.element_info
            name = (info.name or "").strip()
            ctype = info.control_type
        except Exception:
            continue
        if not name or ctype not in NAMED_CONTROL_TYPES:
            continue
        controls.append({"name": name, "type": ctype})
    return {"ok": True, "window_title": title, "controls": controls,
            "truncated": len(descendants) > MAX_CONTROLS}


def click_control(name):
    win, err = _get_foreground_window()
    if err:
        return {"ok": False, "error": err}
    ctrl = _find_control(win, name)
    if not ctrl:
        return {"ok": False, "error": f"ไม่พบปุ่ม/ช่องชื่อ '{name}' ในหน้าต่างนี้ - ลองเรียก list_ui_controls ดูชื่อที่มีจริงก่อน"}
    try:
        ctrl.invoke()   # เรียกผ่าน UIA InvokePattern ตรงๆ - แม่นกว่า click_input() มาก เพราะไม่ต้องจำลองเมาส์จริง
                        # (ไม่ต้องย้ายเคอร์เซอร์จริง ไม่พลาดแม้หน้าต่างซ้อน/จอเปลี่ยนระหว่างคลิก)
        return {"ok": True, "message": f"คลิก '{name}' แล้ว"}
    except Exception:
        try:
            ctrl.click_input()   # ตัวควบคุมบางชนิดไม่รองรับ InvokePattern - fallback เป็นคลิกเมาส์จำลอง
            return {"ok": True, "message": f"คลิก '{name}' แล้ว"}
        except Exception as e:
            log.warning("คลิก '%s' ไม่สำเร็จ", name, exc_info=True)
            return {"ok": False, "error": f"คลิก '{name}' ไม่สำเร็จ: {e}"}


def type_text(text, control_name=None):
    win, err = _get_foreground_window()
    if err:
        return {"ok": False, "error": err}
    target = None
    if control_name:
        target = _find_control(win, control_name)
        if not target:
            return {"ok": False, "error": f"ไม่พบช่องชื่อ '{control_name}' - ลองเรียก list_ui_controls ดูชื่อที่มีจริงก่อน"}
    try:
        if target is not None:
            try:
                target.set_text(text)   # เร็ว/แม่นกว่าสำหรับช่อง Edit ทั่วไป
            except Exception:
                target.click_input()
                target.type_keys(_escape_keys(text), with_spaces=True, with_tabs=True)
            return {"ok": True, "message": f"พิมพ์ข้อความลงช่อง '{control_name}' แล้ว"}
        from pywinauto.keyboard import send_keys
        send_keys(_escape_keys(text), with_spaces=True)
        return {"ok": True, "message": "พิมพ์ข้อความลงที่ที่กำลังโฟกัสอยู่แล้ว"}
    except Exception as e:
        log.warning("พิมพ์ข้อความไม่สำเร็จ (control=%s)", control_name, exc_info=True)
        return {"ok": False, "error": f"พิมพ์ข้อความไม่สำเร็จ: {e}"}
