#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tool_registry.py - รายชื่อเครื่องมือ (tools) ที่ส่งให้โมเดลผ่าน Ollama /api/chat's "tools"
parameter + ตาราง dispatch เรียกฟังก์ชันจริงเมื่อโมเดลเลือกเรียกเครื่องมือนั้น

ตั้งใจให้จำนวนเครื่องมือน้อยและ schema ชัดเจน (ทีละคำสั่งต่อรอบ) ตามงานวิจัยที่สำรวจไว้ก่อน
เริ่ม Phase 2: โมเดลขนาดเล็ก (4B) แม่นยำน้อยลงถ้าต้องเลือกจากเครื่องมือเยอะ/คลุมเครือพร้อมกัน
"""
from tools import apps, files, shell, ui_automation
from tools import translate as translate_tool

TOOLS = [
    {"type": "function", "function": {
        "name": "launch_app",
        "description": "เปิดโปรแกรมที่ติดตั้งในเครื่อง เช่น notepad, calculator, chrome, explorer",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string", "description": "ชื่อโปรแกรมที่จะเปิด เช่น notepad, calculator, chrome"},
        }, "required": ["name"]},
    }},
    {"type": "function", "function": {
        "name": "run_shell",
        "description": "รันคำสั่ง PowerShell หนึ่งคำสั่ง แล้วคืนผลลัพธ์ (stdout/stderr) - ใช้เมื่อผู้ใช้ขอให้ทำ"
                       "สิ่งที่ต้องใช้สคริปต์/คำสั่งระบบ ต้องขออนุญาตผู้ใช้ก่อนรันเสมอ",
        "parameters": {"type": "object", "properties": {
            "command": {"type": "string", "description": "คำสั่ง PowerShell ที่จะรัน"},
        }, "required": ["command"]},
    }},
    {"type": "function", "function": {
        "name": "list_dir",
        "description": "แสดงรายชื่อไฟล์/โฟลเดอร์ย่อยในโฟลเดอร์ที่ระบุ",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "path ของโฟลเดอร์ที่จะดู"},
        }, "required": ["path"]},
    }},
    {"type": "function", "function": {
        "name": "find_file",
        "description": "ค้นหาไฟล์หรือโฟลเดอร์ด้วยชื่อ (หรือบางส่วนของชื่อ) แบบค้นลึกทุกโฟลเดอร์ย่อยในครั้งเดียว "
                       "ใช้เครื่องมือนี้ทันทีเมื่อผู้ใช้ขอให้หาไฟล์/โฟลเดอร์ ห้ามถามกลับก่อนลองค้นด้วยเครื่องมือนี้",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string", "description": "ชื่อไฟล์/โฟลเดอร์ที่จะค้นหา (หรือบางส่วนของชื่อ)"},
            "root": {"type": "string", "description": "โฟลเดอร์ที่จะเริ่มค้น (ไม่ระบุก็ได้ จะค้นจากโฟลเดอร์ผู้ใช้โดยอัตโนมัติ)"},
        }, "required": ["name"]},
    }},
    {"type": "function", "function": {
        "name": "read_file",
        "description": "อ่านเนื้อหาไฟล์ข้อความ (ตัดถ้ายาวเกิน 8000 ตัวอักษร)",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "path ของไฟล์ที่จะอ่าน"},
        }, "required": ["path"]},
    }},
    {"type": "function", "function": {
        "name": "write_file",
        "description": "สร้างไฟล์ข้อความใหม่หรือเขียนทับไฟล์เดิมด้วยเนื้อหาที่ระบุ "
                       "ถ้าไฟล์มีอยู่แล้วจะขออนุญาตผู้ใช้ก่อนเขียนทับเสมอ",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "path ของไฟล์ที่จะเขียน"},
            "content": {"type": "string", "description": "เนื้อหาที่จะเขียนลงไฟล์"},
        }, "required": ["path", "content"]},
    }},
    {"type": "function", "function": {
        "name": "delete_file",
        "description": "ลบไฟล์ (ต้องขออนุญาตผู้ใช้ก่อนเสมอ เพราะย้อนกลับไม่ได้)",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "path ของไฟล์ที่จะลบ"},
        }, "required": ["path"]},
    }},
    {"type": "function", "function": {
        "name": "list_ui_controls",
        "description": "ดูรายชื่อปุ่ม/ช่องกรอก/ตัวควบคุมทั้งหมดในหน้าต่างโปรแกรมที่กำลังโฟกัสอยู่ตอนนี้ "
                       "เรียกก่อนเสมอเมื่อจะคลิกปุ่มหรือพิมพ์ลงช่องเฉพาะเจาะจงในโปรแกรมอื่น เพื่อดูชื่อจริงก่อนเลือก",
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "click_control",
        "description": "คลิกปุ่มหรือตัวควบคุมที่ชื่อตรงกับที่ระบุ ในหน้าต่างโปรแกรมที่กำลังโฟกัสอยู่ "
                       "(ดูชื่อที่มีจริงจาก list_ui_controls ก่อนเรียกเครื่องมือนี้เสมอ)",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string", "description": "ชื่อปุ่ม/ตัวควบคุมที่จะคลิก (หรือบางส่วนของชื่อ)"},
        }, "required": ["name"]},
    }},
    {"type": "function", "function": {
        "name": "type_text",
        "description": "พิมพ์ข้อความลงช่องกรอกที่ระบุชื่อ ในหน้าต่างโปรแกรมที่กำลังโฟกัสอยู่ ถ้าไม่ระบุชื่อช่อง "
                       "จะพิมพ์ลงตำแหน่งที่กำลังโฟกัสอยู่ตอนนั้นแทน (ดูชื่อช่องที่มีจริงจาก list_ui_controls ก่อน)",
        "parameters": {"type": "object", "properties": {
            "text": {"type": "string", "description": "ข้อความที่จะพิมพ์"},
            "control_name": {"type": "string", "description": "ชื่อช่องกรอกที่จะพิมพ์ลงไป (ไม่ระบุก็ได้)"},
        }, "required": ["text"]},
    }},
    {"type": "function", "function": {
        "name": "translate_file",
        "description": "แปลไฟล์ข้อความเป็นภาษาไทยหรืออังกฤษ แล้วบันทึกเป็นไฟล์ใหม่ (ไม่ทับไฟล์ต้นฉบับ "
                       "เว้นแต่ระบุ output_path เป็นไฟล์เดิมเอง) ใช้แปลทีละไฟล์ - ถ้าต้องการแปลทั้งโฟลเดอร์ "
                       "ให้เรียก list_dir ดูรายชื่อไฟล์ก่อนแล้วค่อยเรียก translate_file ทีละไฟล์",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "path ของไฟล์ต้นฉบับที่จะแปล"},
            "to": {"type": "string", "enum": ["th", "en"], "description": "แปลเป็นภาษาไทย (th) หรืออังกฤษ (en)"},
            "output_path": {"type": "string", "description": "path ของไฟล์ผลลัพธ์ (ไม่ระบุก็ได้ จะตั้งชื่อให้อัตโนมัติ)"},
        }, "required": ["path", "to"]},
    }},
]


def _launch_app(args, ctx):
    return apps.launch_app(args.get("name", ""))


def _run_shell(args, ctx):
    return shell.run_shell(args.get("command", ""))


def _list_dir(args, ctx):
    return files.list_dir(args.get("path", "."))


def _find_file(args, ctx):
    return files.find_file(args.get("name", ""), args.get("root"))


def _read_file(args, ctx):
    return files.read_file(args.get("path", ""))


def _write_file(args, ctx):
    return files.write_file(args.get("path", ""), args.get("content", ""))


def _delete_file(args, ctx):
    return files.delete_file(args.get("path", ""))


def _translate_file(args, ctx):
    return translate_tool.translate_file(args.get("path", ""), args.get("to", "th"),
                                         args.get("output_path"), model=ctx.get("model"))


def _list_ui_controls(args, ctx):
    return ui_automation.list_ui_controls()


def _click_control(args, ctx):
    return ui_automation.click_control(args.get("name", ""))


def _type_text(args, ctx):
    return ui_automation.type_text(args.get("text", ""), args.get("control_name"))


DISPATCH = {
    "launch_app": _launch_app,
    "run_shell": _run_shell,
    "list_dir": _list_dir,
    "find_file": _find_file,
    "read_file": _read_file,
    "write_file": _write_file,
    "delete_file": _delete_file,
    "translate_file": _translate_file,
    "list_ui_controls": _list_ui_controls,
    "click_control": _click_control,
    "type_text": _type_text,
}
