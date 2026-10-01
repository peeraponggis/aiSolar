#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
win_hooks.py - ปุ่มลัดทั่วเครื่อง (global hotkey) และตรวจการลากคลุม/ดับเบิลคลิกข้อความ
ในโปรแกรมอื่นด้วย low-level mouse hook ของ Windows (ctypes ล้วน ไม่พึ่ง library ภายนอก)
แยกออกจาก translator.py เพราะเป็นโค้ดระดับ Windows API ที่ไม่เกี่ยวกับตรรกะการแปล/GUI
"""
import ctypes
import os
import sys
import time

FROZEN = bool(getattr(sys, "frozen", False))          # รันจาก exe ที่สร้างด้วย PyInstaller
BASE = os.path.dirname(sys.executable) if FROZEN else os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- Windows: คีย์ลัด + ตรวจการลากคลุมข้อความ (ctypes ล้วน)
MOD_ALT, MOD_CONTROL, MOD_NOREPEAT = 0x0001, 0x0002, 0x4000
WM_HOTKEY, WH_MOUSE_LL = 0x0312, 14
WM_LBUTTONDOWN, WM_LBUTTONUP, WM_RBUTTONDOWN, WM_MBUTTONDOWN = 0x0201, 0x0202, 0x0204, 0x0207
VK_CONTROL, VK_MENU, VK_C, KEYEVENTF_KEYUP = 0x11, 0x12, 0x43, 0x0002
GA_ROOT, GWL_EXSTYLE, WS_EX_NOACTIVATE, WS_EX_TOOLWINDOW = 2, -20, 0x08000000, 0x00000080


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("pt", POINT), ("mouseData", ctypes.c_uint), ("flags", ctypes.c_uint),
                ("time", ctypes.c_uint), ("dwExtraInfo", ctypes.c_size_t)]


class MSG(ctypes.Structure):
    _fields_ = [("hwnd", ctypes.c_void_p), ("message", ctypes.c_uint), ("wParam", ctypes.c_size_t),
                ("lParam", ctypes.c_ssize_t), ("time", ctypes.c_uint), ("pt", POINT)]


HOOKPROC = ctypes.CFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, ctypes.c_size_t, ctypes.c_ssize_t)
_hook_ref = {}  # กัน GC เก็บ callback


def win_event_thread(on_hotkey, on_select, on_click_elsewhere, is_own_window, status_cb):
    """เธรดเดียวรับทั้ง hotkey และ mouse hook (ทั้งสองต้องอยู่กับ message loop ของเธรดที่ติดตั้ง)
    on_select(x, y) ถูกเรียกเมื่อผู้ใช้ลากเมาส์ (เลือกข้อความ) หรือดับเบิลคลิก ในหน้าต่างที่ไม่ใช่ของเรา"""
    user32 = ctypes.windll.user32
    user32.CallNextHookEx.restype = ctypes.c_ssize_t
    user32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_size_t, ctypes.c_ssize_t]
    user32.SetWindowsHookExW.restype = ctypes.c_void_p
    user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, ctypes.c_void_p, ctypes.c_uint]
    user32.GetForegroundWindow.restype = ctypes.c_void_p
    hot_ok = None  # ลอง Ctrl+Alt+T ก่อน ถ้าโปรแกรมอื่นจองไว้ให้ใช้ Ctrl+Alt+Y แทน
    for key in ("T", "Y"):
        if user32.RegisterHotKey(None, 1, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, ord(key)):
            hot_ok = "Ctrl+Alt+" + key; break
    state = {"down": None, "last_down": (0, 0, 0)}
    dbl_ms = user32.GetDoubleClickTime()

    def proc(nCode, wParam, lParam):
        if nCode >= 0:
            try:
                info = ctypes.cast(lParam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                x, y, t = info.pt.x, info.pt.y, info.time
                if wParam == WM_LBUTTONDOWN:
                    own = is_own_window(user32.GetForegroundWindow(), x, y)
                    if not own:
                        on_click_elsewhere()
                    lx, ly, lt = state["last_down"]
                    state["last_down"] = (x, y, t)
                    state["down"] = None if own else (x, y, t)
                    if not own and t - lt <= dbl_ms and abs(x - lx) < 6 and abs(y - ly) < 6:
                        state["down"] = None
                        on_select(x, y)           # ดับเบิลคลิกเลือกคำ
                elif wParam == WM_LBUTTONUP:
                    d = state["down"]; state["down"] = None
                    if d and (abs(x - d[0]) > 14 or abs(y - d[1]) > 14) and not is_own_window(user32.GetForegroundWindow(), x, y):
                        on_select(x, y)           # ลากคลุม
                elif wParam in (WM_RBUTTONDOWN, WM_MBUTTONDOWN):
                    on_click_elsewhere()
            except Exception:
                pass
        return user32.CallNextHookEx(None, nCode, wParam, lParam)

    cb = HOOKPROC(proc); _hook_ref["cb"] = cb
    hook = user32.SetWindowsHookExW(WH_MOUSE_LL, cb, None, 0)
    status_cb(hot_ok, bool(hook))
    msg = MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        if msg.message == WM_HOTKEY:
            on_hotkey()


def build_float_frames(size, n, key_color):
    """สร้างเฟรมหุ่นยนต์ n สี (วนตามวงล้อสี) บนพื้นสีคีย์ สำหรับไอคอนลอยแบบโปร่งใส คืน list ของ tk.PhotoImage"""
    try:
        import base64
        import colorsys
        import io
        import tkinter as tk
        from PIL import Image
        sys.path.insert(0, BASE)
        from make_icon import draw_robot
        key = tuple(int(key_color[i:i + 2], 16) for i in (1, 3, 5))
        out = []
        for i in range(n):
            r, g, b = colorsys.hsv_to_rgb(i / n, 0.75, 1.0)
            col = (int(r * 255), int(g * 255), int(b * 255), 255)
            im = draw_robot(256, bg=False, accent=col, glow=col).resize((size, size), Image.LANCZOS)
            bgim = Image.new("RGBA", (size, size), key + (255,)); bgim.alpha_composite(im)
            buf = io.BytesIO(); bgim.convert("RGB").save(buf, format="PNG")
            out.append(tk.PhotoImage(data=base64.b64encode(buf.getvalue())))
        return out
    except Exception:
        return []


def make_noactivate(hwnd):
    """ให้หน้าต่างลอยไม่แย่งโฟกัส (ข้อความที่เลือกในโปรแกรมอื่นจะยังถูกเลือกอยู่ตอนคลิกไอคอน)"""
    user32 = ctypes.windll.user32
    user32.GetWindowLongW.restype = ctypes.c_long
    root_hwnd = user32.GetAncestor(hwnd, GA_ROOT)
    for h in {hwnd, root_hwnd}:
        style = user32.GetWindowLongW(h, GWL_EXSTYLE)
        user32.SetWindowLongW(h, GWL_EXSTYLE, style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)
    return root_hwnd


def send_ctrl_c():
    """ปล่อย Alt ที่ผู้ใช้กดค้าง แล้วส่ง Ctrl+C ไปยังหน้าต่างที่โฟกัสอยู่"""
    user32 = ctypes.windll.user32
    user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
    time.sleep(0.05)
    user32.keybd_event(VK_CONTROL, 0, 0, 0)
    user32.keybd_event(VK_C, 0, 0, 0)
    user32.keybd_event(VK_C, 0, KEYEVENTF_KEYUP, 0)
    user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
