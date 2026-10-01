#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app_log.py - ตั้งค่าการบันทึก log ลงไฟล์สำหรับ Local Translator

จุดประสงค์: ถ้าโปรแกรมที่แจกให้ผู้ใช้ (.exe) ทำงานผิดพลาดหรือค้าง จะมีไฟล์ translator.log
ให้ดูย้อนหลังได้ว่าเกิดอะไรขึ้น แทนที่จะไม่มีร่องรอยอะไรเลยเหมือนเดิม (เดิมหลาย except
จับข้อผิดพลาดแล้วปล่อยผ่านเงียบๆ โดยไม่บันทึกอะไร)

ใช้งาน: เรียก setup_logging() ครั้งเดียวตอนโปรแกรมเริ่มทำงาน (ใน translator.py)
จากนั้นทุกโมดูลเรียก logging.getLogger(__name__) แล้ว log ได้ตามปกติ
"""
import logging
import logging.handlers
import os
import sys
import threading

FROZEN = bool(getattr(sys, "frozen", False))
BASE = os.path.dirname(sys.executable) if FROZEN else os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE, "translator.log")

_configured = False


def setup_logging(level=logging.INFO):
    """ตั้งค่า root logger ให้เขียนลงไฟล์ translator.log (หมุนไฟล์เมื่อเกิน 2MB เก็บ 3 ไฟล์เก่า)
    และดักข้อผิดพลาดที่ไม่มีใครจับ (ทั้งเธรดหลักและเธรด worker) ให้บันทึกลง log แทนที่จะหายไปเฉยๆ"""
    global _configured
    if _configured:
        return
    _configured = True

    root = logging.getLogger()
    root.setLevel(level)

    fmt = logging.Formatter("%(asctime)s %(levelname)-7s [%(threadName)s] %(name)s: %(message)s",
                             datefmt="%Y-%m-%d %H:%M:%S")

    try:
        handler = logging.handlers.RotatingFileHandler(
            LOG_FILE, maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8")
        handler.setFormatter(fmt)
        root.addHandler(handler)
    except Exception:
        # เขียนไฟล์ log เองไม่ได้ (เช่นโฟลเดอร์อ่านอย่างเดียว) - อย่าทำให้โปรแกรมเปิดไม่ได้เพราะเหตุนี้
        pass

    logging.getLogger(__name__).info(
        "เริ่มโปรแกรม (frozen=%s, base=%s, python=%s)", FROZEN, BASE, sys.version.split()[0])

    def log_uncaught(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        logging.getLogger(__name__).critical(
            "ข้อผิดพลาดที่ไม่มีใครจับ (เธรดหลัก)", exc_info=(exc_type, exc_value, exc_tb))
    sys.excepthook = log_uncaught

    def log_uncaught_thread(args):
        logging.getLogger(__name__).critical(
            "ข้อผิดพลาดที่ไม่มีใครจับ (เธรด %s)", args.thread.name if args.thread else "?",
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback))
    threading.excepthook = log_uncaught_thread
