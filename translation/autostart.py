#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
autostart.py - เปิดโปรแกรมอัตโนมัติเมื่อเปิดเครื่อง (สร้าง/ลบทางลัดในโฟลเดอร์ Startup)

แยกออกจาก run_gui() เพราะไม่มีสถานะร่วมกับ GUI ส่วนอื่นเลย ใช้แค่ callback set_status()
รายงานผลกลับ และพารามิเตอร์ (frozen, base, main_script_path) ที่ run_gui() รู้อยู่แล้ว
"""
import logging
import os
import subprocess
import sys

log = logging.getLogger(__name__)


def startup_lnk():
    return os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu",
                        "Programs", "Startup", "Local Translator.lnk")


def autostart_enabled():
    return os.path.exists(startup_lnk())


def set_autostart(enable, frozen, base, main_script_path, set_status):
    lnk = startup_lnk()
    if not enable:
        try:
            os.remove(lnk)
        except Exception:
            pass
        set_status("ยกเลิกเปิดอัตโนมัติแล้ว"); return
    if frozen:
        target, args = sys.executable, "--minimized"
    else:
        # รันจากซอร์สโค้ด (ไม่มี Translate.bat แล้ว): เปิดด้วย pythonw.exe ตรง ๆ ไม่มีหน้าต่างคอนโซล
        pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        target = pyw if os.path.exists(pyw) else sys.executable
        args = f'"{main_script_path}" --minimized'
    ps = (f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{lnk}');$s.TargetPath='{target}';$s.Arguments='{args}';"
          f"$s.WorkingDirectory='{base}';$s.IconLocation='{os.path.join(base, 'translator.ico')},0';$s.WindowStyle=7;"
          f"$s.Description='Local Translator autostart';$s.Save()")
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, timeout=30,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        set_status("ตั้งเปิดอัตโนมัติเมื่อเปิดเครื่องแล้ว (Startup)" if os.path.exists(lnk) else "สร้างทางลัด Startup ไม่สำเร็จ")
    except Exception as e:
        log.warning("สร้างทางลัด Startup ไม่สำเร็จ", exc_info=True)
        set_status("สร้างทางลัด Startup ไม่สำเร็จ: " + str(e))
