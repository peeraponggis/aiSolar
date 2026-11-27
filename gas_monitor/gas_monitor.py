# ============================================================================
# ProInventive Suite
# Copyright (C) 2024-2569 ProInventive. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL
# Unauthorized use, copying, or distribution is prohibited.
# Author: Peerapong (Lungpee) -- ProInventive -- giskku@gmail.com
# ============================================================================

#!/usr/bin/env python3
"""
GAS Monitor v2.4.0  —  ลุงพี
ตรวจสอบและวิเคราะห์ข้อมูลเซนเซอร์ก๊าซ ผ่าน Serial/USB
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import serial
import serial.tools.list_ports
import threading
import json, csv, os, re, sys, time, struct, statistics
from collections import deque
from datetime import datetime
from pathlib import Path

VERSION = "2.4.0"

# ── Palette ──────────────────────────────────────────────────────────────────
C = {
    'bg':     '#0d1117', 'bg2':  '#161b22', 'bg3':  '#21262d',
    'border': '#30363d', 'green':'#3fb950', 'yellow':'#e3b341',
    'orange': '#f0883e', 'red':  '#f85149', 'blue': '#58a6ff',
    'cyan':   '#39d353', 'text': '#e6edf3', 'text2':'#8b949e',
    'accent': '#1f6feb',
}

BAUD_RATES = [1200, 2400, 4800, 9600, 14400, 19200, 38400, 57600, 115200]

STATUS_TH = {
    'OK':       ('✅ ปกติ',         C['green'],  'ค่าอยู่ในเกณฑ์ปลอดภัย'),
    'WARNING':  ('⚠  เฝ้าระวัง',  C['yellow'], 'ระบายอากาศ / ตรวจแหล่งก๊าซ'),
    'DANGER':   ('🔶 อันตราย',      C['orange'], 'ปิดแหล่งก๊าซ แจ้งเตือนคนในพื้นที่'),
    'CRITICAL': ('🚨 วิกฤต!',       C['red'],    'อพยพทันที! โทร 191 หรือ 199'),
    'UNKNOWN':  ('❓ ไม่มีข้อมูล',  C['text2'],  'รอรับข้อมูลจากเซนเซอร์'),
}

CAR_GAS_PROBLEMS = [
    ("แรงดันก๊าซต่ำ (< 0.3 bar)",
     "เติมก๊าซ หรือตรวจท่อ/ข้อต่อรั่ว"),
    ("เครื่องยังไม่ถึงอุณหภูมิทำงาน",
     "รอให้เข็มวัดน้ำไปอยู่กลาง (> 60°C) ก่อนสลับแก๊ส"),
    ("Solenoid valve ค้างปิด",
     "ฟังเสียง 'คลิก' ตอนสตาร์ — ถ้าไม่มีเสียงให้เช็คไฟ 12V ที่ solenoid"),
    ("ฟิวส์วงจรแก๊สขาด",
     "ตรวจฟิวส์กล่องแก๊ส 10A–15A และฟิวส์หลักในรถ"),
    ("Sensitivity / Delay ตั้งค่าไม่ถูก",
     "ปรับ trimmer pot บนกล่องควบคุม (หมุนทีละน้อย ทดสอบทุกครั้ง)"),
    ("สาย Ground หลุดหรือขาด",
     "ตรวจสายดินกล่องแก๊ส, solenoid และ ECU emulator"),
    ("ECU ไม่รองรับ cold-start บนแก๊ส",
     "กดปุ่มสลับ Manual ก่อนสตาร์ หรือติดตั้ง cold-start emulator"),
    ("MAP/Vacuum sensor ให้ค่าผิดพลาด",
     "ตรวจสายยาง vacuum ไม่รั่ว และ MAP sensor ไม่เสีย"),
]

# ── Parameter model ──────────────────────────────────────────────────────────

class Param:
    def __init__(self, name, unit='', warn=20.0, danger=50.0, crit=80.0, normal=None):
        self.name    = name
        self.unit    = unit
        self.label   = name           # Thai label (user editable)
        self.value   = None
        self.warn    = warn
        self.danger  = danger
        self.crit    = crit
        self.normal  = normal         # (lo, hi): car values judged by range, not leak thresholds
        self.hint    = ''
        self.history = []
        self.updated = None

    def push(self, v):
        try:    v = float(v)
        except: v = str(v)
        self.value   = v
        self.updated = datetime.now()
        self.history.append(v)
        if len(self.history) > 300:
            self.history.pop(0)

    def status(self):
        if self.value is None: return 'UNKNOWN'
        try:
            v = float(self.value)
            if self.normal:
                lo, hi = self.normal
                return 'OK' if lo <= v <= hi else 'WARNING'
            if v >= self.crit:   return 'CRITICAL'
            if v >= self.danger: return 'DANGER'
            if v >= self.warn:   return 'WARNING'
            return 'OK'
        except: return 'UNKNOWN'

    def numeric_history(self):
        try:    return [float(x) for x in self.history]
        except: return []

    def suggest_thresholds(self):
        """Statistical auto-tune: returns (warn, danger, crit) or None"""
        h = self.numeric_history()
        if len(h) < 10:
            return None
        mu  = statistics.mean(h)
        sd  = statistics.stdev(h) if len(h) > 1 else 0
        hi  = max(h)
        # baseline = max observed + buffer
        warn   = round(max(mu + max(sd, mu * 0.15), hi * 0.60), 1)
        danger = round(max(mu + max(2*sd, mu * 0.30), hi * 0.80), 1)
        crit   = round(max(mu + max(3*sd, mu * 0.50), hi * 1.00), 1)
        return warn, danger, crit

# ── Protocol parsers ─────────────────────────────────────────────────────────

def parse_auto(line, params):
    return (parse_json(line, params)
            or parse_csv_line(line, params)
            or parse_kv(line, params))

def parse_json(line, params):
    try:
        d = json.loads(line.strip())
        if isinstance(d, dict):
            for k, v in d.items():
                if k not in params: params[k] = Param(k)
                params[k].push(v)
            return True
    except: pass
    return False

def parse_csv_line(line, params):
    parts = [p.strip() for p in line.strip().split(',')]
    if len(parts) < 2: return False
    try:
        if len(parts) % 2 == 0:
            float(parts[1])
            for i in range(0, len(parts), 2):
                k = parts[i] or f'CH{i//2+1}'
                if k not in params: params[k] = Param(k)
                params[k].push(parts[i+1])
            return True
    except: pass
    try:
        vals = [float(p) for p in parts]
        for i, v in enumerate(vals):
            k = f'CH{i+1}'
            if k not in params: params[k] = Param(k)
            params[k].push(v)
        return True
    except: return False

def parse_kv(line, params):
    hits = re.findall(r'([A-Za-z_]\w*)[\s:=]+([+-]?[\d.]+)', line)
    if not hits: return False
    for name, val in hits:
        if name not in params: params[name] = Param(name)
        params[name].push(val)
    return True

def parse_modbus_response(raw: bytes, params: dict):
    """Modbus RTU read holding registers response"""
    if len(raw) < 5 or raw[1] != 0x03: return False
    n_bytes = raw[2]
    if len(raw) < 3 + n_bytes: return False
    n_regs = n_bytes // 2
    for i in range(n_regs):
        val = struct.unpack('>H', raw[3+i*2:5+i*2])[0]
        k = f'REG{i}'
        if k not in params: params[k] = Param(k)
        params[k].push(val)
    return True

# ── AC STAG Protocol ──────────────────────────────────────────────────────────
ACSTAG_BAUD = 9600

# Official AC STAG software, installed on F: (installer kept for reinstall)
ACGAS_DIR       = Path(r'F:\Programs\AcGasSynchro')
ACGAS_EXE       = ACGAS_DIR / 'ACGasSynchro.exe'
# Car's controller (read by AcGasSynchro 2026-10-27): STAG-300-6 ISA2, firmware 10.0
ECU_MODEL       = 'STAG-300-6 ISA2'
ACGAS_MANUAL    = ACGAS_DIR / 'Docs' / 'STAG-300 ISA2' / 'ver.2.8.9 ENG-STAG-200,STAG-4plus,eco,STAG-300 ISA2,PREMIUM manual.pdf'
ACGAS_WIRING    = ACGAS_DIR / 'Docs' / 'STAG-300 ISA2' / 'ENG_STAG-300 ISA2_Wiring diagram[2013.04.09].pdf'
ACGAS_LEADS     = ACGAS_DIR / 'Docs' / 'STAG-300 ISA2' / 'ENG-STAG-300 plus, STAG-300 ISA2,STAG-300 premium leads description.pdf'
ACGAS_INSTALLER = Path(r'F:\LocalAI\downloads\acgassynchro\SetupAcGasSynchro-11.2.1.1.exe')
ACGAS_URL       = 'https://ftp.stag.pl/apps/AcGasSynchro/SetupAcGasSynchro-11.2.1.1.exe'

# Live read from the AcGasSynchro window (acgas_reader.py)
LIVE_INTERVAL = 0.5                      # seconds between reads
LIVE_HISTORY  = 600                      # samples kept for the graph (5 min)
LIVE_LOG_DIR  = Path(__file__).parent / 'logs'
# key: (ชื่อไทย, หน่วย, ต่ำสุดปกติ, สูงสุดปกติ, คำแนะนำเมื่อนอกช่วง)
LIVE_PARAMS = {
    'GAS_kPa':  ('แรงดันแก๊ส (เหนือ MAP)', 'kPa', 80, 130, 'ต่ำ → เช็คไส้กรองแก๊ส'),
    'MAP_kPa':  ('แรงดันท่อไอดี (MAP)',    'kPa', 15, 100, 'ค้าง 0/100 = เซนเซอร์หรือท่อยางสุญญากาศ'),
    'RED_TEMP': ('อุณหภูมิหม้อต้ม',        '°C',  35,  95, 'ต่ำ = น้ำร้อนเข้าหม้อต้มไม่ดี'),
    'GAS_TEMP': ('อุณหภูมิไอแก๊ส',         '°C',  10,  75, ''),
    'RPM':      ('รอบเครื่อง',             'rpm', 500, 6000, 'รอบสูงเกิน = กล่องตัดไปน้ำมันป้องกันเครื่อง'),
    'INJ_ms':   ('เวลาฉีดแก๊ส (เฉลี่ย)',    'ms',  0,   20, ''),
    'PET_ms':   ('เวลาฉีดน้ำมัน (เฉลี่ย)',  'ms',  0,   20, ''),
    'LAMBDA1':  ('Lambda 1',               'V',   0.0, 1.0, ''),
    'LAMBDA2':  ('Lambda 2',               'V',   0.0, 1.0, ''),
    'BATT_V':   ('แบตเตอรี่',              'V',   12.5, 14.8, 'ต่ำ = เช็คไดชาร์จ/แบตเตอรี่'),
}
FUEL_TH = {'gas': 'แก๊ส', 'petrol': 'น้ำมัน'}

# Default thresholds for AC STAG parameters
ACSTAG_PARAM_DEF = {
    'MAP_kPa':  ('แรงดัน MAP',        'kPa',  60,  100, 150),
    'TEMP_C':   ('อุณหภูมิเครื่องยนต์', '°C',   85,  105, 115),
    'RPM':      ('รอบเครื่องยนต์',      'rpm', 1500, 4000, 6500),
    'INJ_ms':   ('เวลาหัวฉีดแก๊ส',     'ms',   8.0, 14.0,  20.0),
    'GAS_STAT': ('โหมดเชื้อเพลิง',     '',     0.5,  1.5,   2.5),
    'GAS_kPa':  ('แรงดันแก๊ส',         'kPa',  150,  200,  250),
    'RED_TEMP': ('อุณหภูมิหม้อต้ม',     '°C',   95,  105,  115),
    'GAS_TEMP': ('อุณหภูมิไอแก๊ส',      '°C',   70,   90,  100),
}

# Diagnostics panel: (param key, ชื่อในโปรแกรม AcGasSynchro, ชื่อไทย, หน่วย, ต่ำสุดปกติ, สูงสุดปกติ)
# ช่วงปกติ = ตอนเครื่องร้อน เดินเบา ไม่เหยียบคันเร่ง
ACSTAG_DIAG_FIELDS = [
    ('MAP_kPa',  'Collector pressure',   'แรงดันท่อไอดี (MAP)',  'kPa', 25,   40),
    ('GAS_kPa',  'Gas pressure',         'แรงดันแก๊ส เหนือ MAP', 'kPa', 80,  130),
    ('RED_TEMP', 'Reducer temperature',  'อุณหภูมิหม้อต้ม',      '°C',  35,   90),
    ('GAS_TEMP', 'Gas temperature',      'อุณหภูมิไอแก๊ส',       '°C',  15,   60),
    ('RPM',      'RPM',                  'รอบเครื่อง',           'rpm', 600, 1000),
    ('INJ_ms',   'Injection time (gas)', 'เวลาฉีดแก๊ส',          'ms',  2.5,  7.0),
]

# โซนบนกราฟ Tuning Map: (rpm0, rpm1, kpa0, kpa1, สีพื้น, สีขอบ, ป้าย)
TUNING_MAP_ZONES = [
    (600, 1000, 25, 40,  '#10301c', '#3fb950', 'เดินเบา\nปกติ'),
    (1500, 5000, 12, 22, '#33280e', '#e3b341', 'ถอนคันเร่งขณะรถวิ่ง (engine braking)'),
    (2000, 6000, 88, 102, '#3a1616', '#f85149', 'เหยียบคันเร่งสุด'),
]
TUNING_MAP_RPM_MAX = 6000
TUNING_MAP_KPA_MAX = 110

def demo_engine_state(t: float) -> dict:
    """Simulated drive cycle for the Tuning Map demo (20 s loop)."""
    import math
    p = t % 20
    if p < 5:    rpm, kpa = 820 + 30*math.sin(t*3), 31 + 2*math.sin(t*2)
    elif p < 9:  f = (p-5)/4;  rpm, kpa = 820 + f*2700, 31 + f*30
    elif p < 11: f = (p-9)/2;  rpm, kpa = 3520 + f*1200, 61 + f*35
    elif p < 15: f = (p-11)/4; rpm, kpa = 4720 - f*2400, 17 + 2*math.sin(t*4)
    else:        f = (p-15)/5; rpm, kpa = 2320 - f*1500, 17 + f*14
    return {'RPM': round(rpm), 'MAP_kPa': round(kpa, 1),
            'GAS_kPa': round(105 + 5*math.sin(t)), 'RED_TEMP': 58.0,
            'GAS_TEMP': 34.0, 'INJ_ms': round(2.2 + kpa/18, 1)}

# (ศัพท์, ชื่อเต็ม/ภาษาอังกฤษ, คำอธิบายภาษาชาวบ้าน, ค่าที่ควรเห็น/ตัวอย่าง)
ACSTAG_GLOSSARY = [
    ('MAP sensor  =  Collector Pressure',
     'เซนเซอร์วัดความดันในท่อไอดี (Manifold Absolute Pressure)',
     'ท่อไอดี = ท่อที่อากาศวิ่งเข้าไปในเครื่องยนต์ เซนเซอร์ตัวนี้วัดว่าในท่อนั้นมีแรงดูดมากแค่ไหน\n'
     'เปรียบง่ายๆ = วัดว่าเครื่องยนต์ "หายใจหนัก" แค่ไหน\n'
     '• ไม่เหยียบคันเร่ง → ลิ้นปิดเกือบหมด เครื่องดูดอากาศในท่อจนแรงดันต่ำ\n'
     '• เหยียบคันเร่งสุด → ลิ้นเปิดกว้าง อากาศไหลเข้าเต็มที่ แรงดันเกือบเท่าอากาศข้างนอก\n'
     'กล่อง STAG ใช้ค่านี้คำนวณว่าต้องฉีดแก๊สมากน้อยแค่ไหน\n'
     'ในโปรแกรม AcGasSynchro เรียกว่า "Collector pressure" — ตัวเดียวกัน',
     'เดินเบา 25–40 kPa  ·  คันเร่งสุด 90–100 kPa  ·  ถ้าค้าง 0 หรือ 100 ตลอด = เซนเซอร์/ท่อยางมีปัญหา'),

    ('Reducer pressure  /  Gas pressure',
     'แรงดันแก๊สหลังหม้อต้ม',
     'คนละตัวกับ MAP! ตัวนี้วัดแรงดันแก๊สที่ออกจากหม้อต้มไปยังหัวฉีด\n'
     'กล่อง STAG จะยอมสลับเป็นแก๊สก็ต่อเมื่อแรงดันนี้สูงพอ ถ้าต่ำเกิน → ค้างอยู่ที่น้ำมัน\n'
     'ในโปรแกรมมักแสดงเป็นค่า "เหนือ MAP" คือ แรงดันแก๊ส − แรงดันท่อไอดี',
     'ปกติ ~100 kPa (1 bar) เหนือ MAP  ·  ต่ำกว่า ~60 kPa = สงสัยหม้อต้ม/กรองแก๊สตัน'),

    ('kPa  และ  bar',
     'หน่วยวัดแรงดัน (กิโลปาสคาล)',
     'ใช้บอกว่ามีแรงกดมากแค่ไหน\n'
     '• 100 kPa = 1 bar = ประมาณแรงดันอากาศรอบตัวเรา\n'
     '• ค่าต่ำกว่า 100 kPa ในท่อไอดี = มีแรงดูด (สุญญากาศบางส่วน)\n'
     'เทียบลมยางรถเก๋ง ~220 kPa (32 psi) เพื่อให้นึกภาพออก',
     '1 bar = 100 kPa  ·  1 psi ≈ 6.9 kPa'),

    ('หม้อต้ม  (Reducer / Vaporizer)',
     'ตัวแปลงแก๊สเหลวเป็นไอ — ในรถคันนี้คือ AME Black',
     'แก๊ส LPG ในถังเป็น "ของเหลว" แรงดันสูง เครื่องยนต์ใช้ของเหลวไม่ได้\n'
     'หม้อต้มทำ 2 อย่าง: (1) ลดแรงดันลง (2) อุ่นให้กลายเป็นไอ\n'
     'มันใช้ "น้ำหล่อเย็นร้อนจากเครื่องยนต์" ไหลผ่านเพื่อให้ความร้อน\n'
     'ถ้าหม้อต้มเก่า/เมมเบรน(แผ่นยาง)แข็ง หรือน้ำร้อนไหลไม่ผ่าน → ไอแก๊สไม่พอ → ไม่สลับ',
     'อายุราว 8–12 ปี  ·  ตัวในรถนี้ใช้มา ~10 ปี'),

    ('อุณหภูมิหม้อต้ม  (Reducer temperature)',
     'ความร้อนของหม้อต้ม วัดด้วยเซนเซอร์ที่ติดบนหม้อต้ม',
     'กล่อง STAG จะ "ไม่ยอม" สลับไปแก๊สจนกว่าหม้อต้มจะร้อนถึงค่าที่ตั้งไว้\n'
     'นี่คือเหตุผลที่ตอนสตาร์ทรถใหม่ๆ ต้องวิ่งน้ำมันก่อนสักพัก\n'
     'ถ้าอุณหภูมิไม่ขึ้นเลย = ท่อน้ำเข้าหม้อต้มตัน / มีลมในระบบ / เซนเซอร์เสีย',
     'ปกติสลับเมื่อ ~30–40 °C  ·  เครื่องร้อนเต็มที่ 60–80 °C'),

    ('Switch temperature  /  Switching conditions',
     'เงื่อนไขการสลับน้ำมัน → แก๊ส (ตั้งได้ในโปรแกรม)',
     'ค่าที่ช่างตั้งไว้ในกล่อง เช่น "หม้อต้มต้องร้อน ≥ 35°C และรอบเครื่อง ≥ 1,500"\n'
     'กล่องจะสลับเองอัตโนมัติก็ต่อเมื่อครบทุกเงื่อนไข\n'
     'ถ้าเงื่อนไขตั้งสูงเกิน หรือเซนเซอร์อ่านค่าผิด → ไม่สลับ (อาการรถคันนี้)',
     'ดูในแท็บ Settings / Switching ของ AcGasSynchro'),

    ('Solenoid valve  (วาล์วแม่เหล็กไฟฟ้า)',
     'วาล์วเปิด-ปิดทางแก๊สด้วยไฟฟ้า มี 2 ตัว: ที่ถัง และ ที่หม้อต้ม',
     'เมื่อกล่องสั่ง "เปิดแก๊ส" จะจ่ายไฟ 12V → ขดลวดดูดลูกสูบ → ได้ยินเสียง "คลิก"\n'
     'ลุงพีได้ยินเสียงคลิกแล้ว = วาล์วรับคำสั่ง แต่ไม่ได้แปลว่าแก๊สไหลพอ\n'
     '(กรองในวาล์วตันก็ยังคลิกได้ แต่แก๊สผ่านน้อย)',
     'มีเสียงคลิก = ไฟฟ้าโอเค'),

    ('ECU / กล่องควบคุมแก๊ส  (AC STAG-300-6 ISA2)',
     'Electronic Control Unit = คอมพิวเตอร์เล็กๆ ของระบบแก๊ส',
     'รับค่าจากเซนเซอร์ทั้งหมด → ตัดสินใจว่าเมื่อไหร่สลับแก๊ส และฉีดแก๊สนานแค่ไหน\n'
     'รถมี ECU 2 ตัว: ตัวของรถ (สั่งน้ำมัน) และตัว STAG (แปลคำสั่งเป็นแก๊ส)\n'
     'ต้องเปิดสวิตช์กุญแจ ON ก่อน กล่องถึงจะมีไฟและคุยกับคอมพิวเตอร์ได้',
     'ไฟ LED ที่ปุ่ม B/G ติด = กล่องมีไฟ'),

    ('หัวฉีดแก๊ส  (Gas injector — HANA)',
     'วาล์วเล็กๆ ที่ฉีดไอแก๊สเข้าท่อไอดีของแต่ละสูบ',
     'เปิด-ปิดเร็วมาก หลายสิบครั้งต่อวินาที\n'
     'ระยะเวลาที่เปิดแต่ละครั้ง = "Injection time" หน่วยเป็น ms (มิลลิวินาที = 1/1000 วินาที)\n'
     'เปิดนาน = แก๊สเข้ามาก',
     'เดินเบา ~3–6 ms  ·  เร่งแรง ~10–20 ms'),

    ('Injection time  (Petrol / Gas)',
     'เวลาเปิดหัวฉีดน้ำมัน เทียบกับ หัวฉีดแก๊ส',
     'กล่อง STAG "แอบฟัง" คำสั่งที่ ECU รถส่งไปหัวฉีดน้ำมัน แล้วแปลงเป็นเวลาฉีดแก๊ส\n'
     'ในโปรแกรมจะเห็นสองค่าคู่กัน — ค่าแก๊สมักยาวกว่าน้ำมันนิดหน่อย',
     'แก๊ส ≈ น้ำมัน × 1.1–1.4'),

    ('RPM  (Revolutions Per Minute)',
     'รอบเครื่องยนต์ต่อนาที — ตัวเดียวกับเข็มวัดรอบหน้าปัด',
     'เข็มชี้เลข 1 = 1,000 รอบ/นาที\n'
     'บางรถตั้งไว้ให้สลับแก๊สตอน "ปล่อยคันเร่งจากรอบสูง" เท่านั้น',
     'เดินเบา 700–900 rpm'),

    ('Idle  (เดินเบา)',
     'เครื่องติดอยู่ แต่ไม่เหยียบคันเร่ง',
     'สภาพที่ใช้ทดสอบค่าต่างๆ ได้ง่ายที่สุด เพราะค่านิ่ง',
     'จอดรถ เกียร์ P/N ติดเครื่องไว้เฉยๆ'),

    ('Cold start  (สตาร์ทตอนเครื่องเย็น)',
     'ช่วงแรกหลังสตาร์ท ที่เครื่องยนต์และหม้อต้มยังเย็น',
     'ระบบแก๊สหัวฉีดทุกยี่ห้อออกแบบให้สตาร์ทด้วยน้ำมันก่อนเสมอ\n'
     'แล้วสลับไปแก๊สเองเมื่อหม้อต้มร้อน — ถ้าไม่สลับเอง = มีเงื่อนไขข้อใดข้อหนึ่งไม่ผ่าน',
     'ปกติสลับเองภายใน 30 วินาที – 2 นาที'),

    ('Vacuum hose  (ท่อยางสุญญากาศ)',
     'ท่อยางเล็กที่ต่อจากท่อไอดีไปยังเซนเซอร์ MAP และหม้อต้ม',
     'ถ้าท่อนี้แตก หลุด หรือรั่ว → เซนเซอร์อ่านค่าผิด และหม้อต้มปรับแรงดันผิด\n'
     'ตรวจง่าย: ลูบดูว่าแข็งกรอบ มีรอยแตกไหม',
     'ท่อยางอายุ 10 ปี ควรเปลี่ยนทั้งชุด (ราคาถูก)'),

    ('Gas filter  (ไส้กรองแก๊ส)',
     'กรองสิ่งสกปรก/น้ำมันเหนียวในแก๊สก่อนเข้าหัวฉีด',
     'ถ้าตัน → แก๊สไหลไม่พอ → แรงดันตก → สลับไม่ได้ หรือสลับแล้วสะดุด\n'
     'ควรเปลี่ยนทุก 10,000–20,000 กม. — ถูกและควรเช็คก่อนเปลี่ยนหม้อต้ม',
     'ราคา ~150–400 บาท'),

    ('Emulator',
     'อุปกรณ์หลอกสัญญาณให้ ECU รถ',
     'เมื่อวิ่งแก๊ส หัวฉีดน้ำมันถูกตัด ECU รถอาจคิดว่าหัวฉีดเสียแล้วโชว์ไฟเครื่อง\n'
     'Emulator ส่งสัญญาณปลอมให้ ECU รถคิดว่ายังทำงานปกติ\n'
     'STAG-300 ISA2 มีวงจรนี้ในตัวอยู่แล้ว',
     '—'),

    ('Error / Fault code',
     'รหัสความผิดพลาดที่กล่องบันทึกไว้',
     'เมื่อมีอะไรผิดปกติ กล่องจะจำไว้ แม้ปิดเครื่องไปแล้ว\n'
     'ใน AcGasSynchro ดูที่แท็บ Errors / Diagnostics — ถ่ายรูปส่งช่างได้เลย\n'
     'เช่น "Too low gas pressure" = แรงดันแก๊สต่ำ, "Reducer temp too low" = หม้อต้มไม่ร้อน',
     'อ่านก่อนลบเสมอ'),

    ('LPG',
     'Liquefied Petroleum Gas = แก๊สหุงต้ม / แก๊สรถยนต์',
     'ส่วนผสมโพรเพน+บิวเทน เก็บเป็นของเหลวในถังแรงดัน ~5–10 bar\n'
     'ต่างจาก NGV/CNG ที่เป็นแก๊สอัดแรงดันสูงมาก (200 bar)',
     'ถังรถนี้: Energy Reform 73 ลิตร'),
]

def _acstag_init_param(name, params):
    if name not in params and name in ACSTAG_PARAM_DEF:
        lbl, unit, w, d, c = ACSTAG_PARAM_DEF[name]
        p = Param(name, unit, w, d, c)
        p.label = lbl
        params[name] = p

def parse_acstag_stream(raw: bytes, params: dict) -> list[tuple[int, bytes]]:
    """
    Scan raw bytes for AC STAG frame candidates.
    Returns list of (offset, frame_bytes) for each candidate found.
    AC STAG uses proprietary binary protocol — this does heuristic detection.
    """
    frames = []
    i = 0
    while i < len(raw) - 1:
        # Pattern 1: STX (0x02) ... ETX (0x03)
        if raw[i] == 0x02:
            etx = raw.find(0x03, i + 3)
            if 0 < etx - i < 128:
                frames.append((i, raw[i:etx+1]))
                i = etx + 1
                continue
        # Pattern 2: fixed 64-byte block starting with high byte
        if raw[i] >= 0x80 and i + 64 <= len(raw):
            frames.append((i, raw[i:i+64]))
            i += 64
            continue
        i += 1
    return frames

def acstag_annotate_frame(frame: bytes, params: dict) -> str:
    """
    Attempt heuristic parameter extraction from an AC STAG frame.
    Returns annotation string. Updates params if plausible values found.
    """
    if len(frame) < 6:
        return ''
    notes = []
    data = frame[1:-1] if (frame[0] == 0x02 and frame[-1] == 0x03) else frame
    try:
        # Scan for RPM-like uint16 big-endian (400–7000)
        for off in range(0, min(len(data)-1, 16), 2):
            v = struct.unpack('>H', data[off:off+2])[0]
            if 400 <= v <= 7000:
                _acstag_init_param('RPM', params)
                params['RPM'].push(v)
                notes.append(f'RPM≈{v}@+{off}')
                break
        # Scan for MAP kPa as uint16 (20–200)
        for off in range(0, min(len(data)-1, 16), 2):
            v = struct.unpack('>H', data[off:off+2])[0]
            if 20 <= v <= 200:
                _acstag_init_param('MAP_kPa', params)
                params['MAP_kPa'].push(v)
                notes.append(f'MAP≈{v}kPa@+{off}')
                break
        # Scan for temperature byte (value-40 in range 0–140)
        for off in range(2, min(len(data), 16)):
            temp = data[off] - 40
            if 0 <= temp <= 130:
                _acstag_init_param('TEMP_C', params)
                params['TEMP_C'].push(temp)
                notes.append(f'T≈{temp}°C@+{off}')
                break
    except Exception:
        pass
    return ', '.join(notes) if notes else f'{len(data)}B raw'

# ── App ───────────────────────────────────────────────────────────────────────

class GasMonitorApp:

    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f'⚗ GAS Monitor v{VERSION}  —  ลุงพี')
        self.root.geometry('1180x760')
        self.root.configure(bg=C['bg'])
        self.root.minsize(820, 560)

        self.ser: serial.Serial | None = None
        self.running   = False
        self.params:   dict[str, Param] = {}
        self._cards:   dict[str, dict]  = {}
        self._ph_shown = True
        self._hex_mode = False
        self._acstag_buf    = b''
        self._acstag_frames = 0

        # live values read from the AcGasSynchro window
        self._live_on     = False
        self._live_hist   = deque(maxlen=LIVE_HISTORY)   # (time, gas_bar, rpm, fuel, map_bar)
        self._live_events = []                           # (time, from, to, gas_bar, rpm)
        self._live_fuel   = None
        self._live_err    = None
        self._live_file   = None
        self._live_writer = None
        self._live_rows   = 0
        self._live_path   = None
        self._min_bar     = tk.DoubleVar(value=0.60)

        self.port_var   = tk.StringVar()
        self.baud_var   = tk.StringVar(value='9600')
        self.proto_var  = tk.StringVar(value='Auto')
        self.scan_var   = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value='ไม่ได้เชื่อมต่อ')
        self.send_var   = tk.StringVar()

        self._apply_style()
        self._set_icon()
        self.proto_var.trace('w', self._on_proto_change)
        self._build_ui()
        self._refresh_ports()

    # ── Style / Icon ─────────────────────────────────────────────────────────

    def _apply_style(self):
        s = ttk.Style(); s.theme_use('clam')
        for w in ('TCombobox', 'TEntry'):
            s.configure(w, fieldbackground=C['bg3'], background=C['bg3'],
                        foreground=C['text'], selectbackground=C['accent'],
                        bordercolor=C['border'])
        s.configure('TScrollbar', background=C['bg3'], troughcolor=C['bg2'],
                    bordercolor=C['bg2'], arrowcolor=C['text2'])

    def _set_icon(self):
        ico = Path(__file__).parent / 'gas_icon.ico'
        if not ico.exists(): self._make_icon(ico)
        try: self.root.iconbitmap(str(ico))
        except: pass

    def _make_icon(self, path):
        try:
            from PIL import Image, ImageDraw
            img = Image.new('RGBA', (64,64), (0,0,0,0))
            d   = ImageDraw.Draw(img)
            d.ellipse([1,1,63,63], fill='#161b22', outline='#3fb950', width=3)
            for xy, col in [([18,30,46,58],'#f85149'),([22,20,42,42],'#f0883e'),
                            ([25,12,39,30],'#e3b341'),([27, 6,37,20],'#3fb950')]:
                d.ellipse(xy, fill=col)
            img.save(str(path), format='ICO', sizes=[(48,48),(32,32),(16,16)])
        except: pass

    # ── UI layout ────────────────────────────────────────────────────────────

    def _build_ui(self):
        self._build_toolbar()
        paned = tk.PanedWindow(self.root, orient=tk.HORIZONTAL,
                               bg=C['bg'], sashwidth=5, sashrelief=tk.FLAT,
                               handlesize=0)
        paned.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0,6))
        self._build_terminal(paned)
        self._build_params(paned)
        self._build_statusbar()

    # ── Toolbar ──────────────────────────────────────────────────────────────

    def _build_toolbar(self):
        bar = tk.Frame(self.root, bg=C['bg2'], height=56)
        bar.pack(fill=tk.X); bar.pack_propagate(False)

        tk.Label(bar, text='⚗ GAS Monitor', font=('Consolas',14,'bold'),
                 bg=C['bg2'], fg=C['cyan']).pack(side=tk.LEFT, padx=12)

        # ── Connect button
        self._conn_btn = tk.Button(bar, text='⚡ เชื่อมต่อ',
                                   command=self._toggle_connect,
                                   bg='#238636', fg='white', relief=tk.FLAT,
                                   font=('Consolas',10,'bold'),
                                   padx=14, pady=6, cursor='hand2',
                                   activebackground='#2ea043')
        self._conn_btn.pack(side=tk.LEFT, padx=8, pady=8)

        # ── Connection controls, left-to-right right after the Connect button
        def lab(t):
            tk.Label(bar, text=t, bg=C['bg2'], fg=C['text2'],
                     font=('Consolas',9)).pack(side=tk.LEFT, padx=(10,2))
        lab('Port:')
        self._port_cb = ttk.Combobox(bar, textvariable=self.port_var,
                                     width=7, state='readonly')
        self._port_cb.pack(side=tk.LEFT, padx=2)
        tk.Button(bar, text='↻', command=self._refresh_ports,
                  bg=C['bg3'], fg=C['cyan'], relief=tk.FLAT,
                  font=('Consolas',11), padx=4, pady=0,
                  cursor='hand2').pack(side=tk.LEFT)
        lab('Baud:')
        ttk.Combobox(bar, textvariable=self.baud_var,
                     values=[str(b) for b in BAUD_RATES],
                     width=8, state='readonly').pack(side=tk.LEFT, padx=2)
        lab('Protocol:')
        ttk.Combobox(bar, textvariable=self.proto_var,
                     values=['Auto','CSV','JSON','Key=Value','Modbus RTU','AC STAG','HEX'],
                     width=12, state='readonly').pack(side=tk.LEFT, padx=2)
        tk.Checkbutton(bar, text='Auto-Scan Baud', variable=self.scan_var,
                       bg=C['bg2'], fg=C['text2'], selectcolor=C['bg3'],
                       activebackground=C['bg2'], font=('Consolas',9)
                       ).pack(side=tk.LEFT, padx=10)

        # ── Second row: car / AC STAG tools (left) · data tools (right)
        bar2 = tk.Frame(self.root, bg=C['bg3'])
        bar2.pack(fill=tk.X)
        for text, cmd, bg, fg, abg in [
            ('▶ AcGasSynchro', self._launch_acgassynchro,
             '#b45309', '#ffffff', '#d97706'),
            (None, None, None, None, None),          # live toggle goes here
            ('📈 Map', lambda: self._show_acstag_dialog(tab=1),
             '#14532d', '#86efac', '#166534'),
            ('📉 แรงดันแก๊ส', lambda: self._show_acstag_dialog(tab=2),
             '#164e63', '#a5f3fc', '#155e75'),
            ('🔧 วิเคราะห์', self._show_car_diagnostics,
             '#7c2d12', '#fdba74', '#9a3412'),
            ('📚 ศัพท์', lambda: self._show_acstag_dialog(tab=5),
             '#3b1f5c', '#d8b4fe', '#4c2a75'),
        ]:
            if text is None:
                self._live_btn = tk.Button(bar2, text='📡 อ่านสด', command=self._toggle_acgas_live,
                                           bg='#1d4ed8', fg='white', relief=tk.FLAT,
                                           font=('Consolas',9,'bold'), padx=10, pady=4,
                                           cursor='hand2', activebackground='#2563eb')
                self._live_btn.pack(side=tk.LEFT, padx=(8,0), pady=5)
                continue
            tk.Button(bar2, text=text, command=cmd, bg=bg, fg=fg,
                      relief=tk.FLAT, font=('Consolas',9,'bold'),
                      padx=10, pady=4, cursor='hand2', activebackground=abg
                      ).pack(side=tk.LEFT, padx=(8,0), pady=5)

        for text, cmd, fg, bg in [
            ('📌 Shortcut',   self._create_shortcut, C['text'], C['bg2']),
            ('💾 Export CSV', self._export_csv,      C['text'], C['bg2']),
            ('⚙ Threshold',  self._open_settings,   C['text'], C['bg2']),
            ('⚡ Auto-Tune',  self._quick_autotune,  '#86efac', '#14532d'),
        ]:
            tk.Button(bar2, text=text, command=cmd, bg=bg, fg=fg,
                      relief=tk.FLAT, font=('Consolas',9),
                      padx=8, pady=4, cursor='hand2',
                      activebackground=C['border']
                      ).pack(side=tk.RIGHT, padx=(0,6), pady=5)

    # ── Terminal (left panel) ─────────────────────────────────────────────────

    def _build_terminal(self, parent):
        frame = tk.Frame(parent, bg=C['bg'], width=460)
        parent.add(frame, minsize=280)

        # Header
        hdr = tk.Frame(frame, bg=C['bg2']); hdr.pack(fill=tk.X)
        tk.Label(hdr, text='📟 Serial Terminal (ข้อมูลดิบ)',
                 font=('Consolas',10,'bold'),
                 bg=C['bg2'], fg=C['text2'], pady=5).pack(side=tk.LEFT, padx=8)
        tk.Button(hdr, text='HEX', command=self._toggle_hex,
                  bg=C['bg3'], fg=C['blue'], relief=tk.FLAT,
                  font=('Consolas',8), padx=6, pady=2,
                  cursor='hand2').pack(side=tk.RIGHT, padx=3, pady=4)
        tk.Button(hdr, text='Clear', command=self._clear_term,
                  bg=C['bg3'], fg=C['text2'], relief=tk.FLAT,
                  font=('Consolas',8), padx=6, pady=2,
                  cursor='hand2').pack(side=tk.RIGHT, padx=3, pady=4)

        # Terminal
        self._term = tk.Text(frame, bg='#090c0f', fg='#39d353',
                             font=('Consolas',10), relief=tk.FLAT,
                             insertbackground=C['cyan'], wrap=tk.WORD,
                             state=tk.DISABLED)
        sb = ttk.Scrollbar(frame, command=self._term.yview)
        self._term.configure(yscrollcommand=sb.set)
        self._term.pack(side=tk.LEFT, fill=tk.BOTH, expand=True,
                        padx=(6,0), pady=(6,0))
        sb.pack(side=tk.RIGHT, fill=tk.Y, pady=(6,0), padx=(0,4))

        for tag, fg in [('ts',C['text2']),('ok','#39d353'),('warn',C['yellow']),
                        ('err',C['red']),('info',C['blue']),('rx','#a5f3fc')]:
            self._term.tag_config(tag, foreground=fg)

        # Send command bar
        send_bar = tk.Frame(frame, bg=C['bg3']); send_bar.pack(fill=tk.X, pady=(4,6), padx=6)
        tk.Label(send_bar, text='ส่งคำสั่ง:', bg=C['bg3'], fg=C['text2'],
                 font=('Consolas',9)).pack(side=tk.LEFT, padx=6)
        send_entry = ttk.Entry(send_bar, textvariable=self.send_var,
                               font=('Consolas',10), width=30)
        send_entry.pack(side=tk.LEFT, padx=4, pady=4, fill=tk.X, expand=True)
        send_entry.bind('<Return>', lambda e: self._send_cmd())
        tk.Button(send_bar, text='ส่ง ▶', command=self._send_cmd,
                  bg=C['accent'], fg='white', relief=tk.FLAT,
                  font=('Consolas',9,'bold'), padx=10, pady=3,
                  cursor='hand2').pack(side=tk.RIGHT, padx=6)
        tk.Button(send_bar, text='\\r\\n', command=lambda: self.send_var.set(
                  self.send_var.get() + '\\r\\n'),
                  bg=C['bg3'], fg=C['text2'], relief=tk.FLAT,
                  font=('Consolas',8), padx=4, cursor='hand2'
                  ).pack(side=tk.RIGHT)

    # ── Param panel (right) ───────────────────────────────────────────────────

    def _build_params(self, parent):
        frame = tk.Frame(parent, bg=C['bg']); parent.add(frame, minsize=300)

        hdr = tk.Frame(frame, bg=C['bg2']); hdr.pack(fill=tk.X)
        tk.Label(hdr, text='📊 พารามิเตอร์เซนเซอร์',
                 font=('Consolas',10,'bold'),
                 bg=C['bg2'], fg=C['text2'], pady=5).pack(side=tk.LEFT, padx=8)

        canvas = tk.Canvas(frame, bg=C['bg'], highlightthickness=0)
        sb = ttk.Scrollbar(frame, command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6,0), pady=6)
        sb.pack(side=tk.RIGHT, fill=tk.Y, pady=6, padx=(0,4))

        self._pcont  = tk.Frame(canvas, bg=C['bg'])
        self._pcwin  = canvas.create_window((0,0), window=self._pcont, anchor='nw')
        canvas.bind('<Configure>',
            lambda e: canvas.itemconfig(self._pcwin, width=e.width))
        self._pcont.bind('<Configure>',
            lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        self._pcanvas = canvas

        self._placeholder = tk.Label(self._pcont,
            text='⚗\n\nรอรับข้อมูลจากเซนเซอร์...\n\nกด ⚡ เชื่อมต่อ\nแล้วเปิดกล่อง GAS',
            font=('Consolas',12), bg=C['bg'], fg=C['text2'], justify=tk.CENTER)
        self._placeholder.pack(expand=True, pady=60)

    # ── Status bar ───────────────────────────────────────────────────────────

    def _build_statusbar(self):
        bar = tk.Frame(self.root, bg=C['bg3'], height=24)
        bar.pack(fill=tk.X, side=tk.BOTTOM); bar.pack_propagate(False)
        self._dot = tk.Label(bar, text='●', fg=C['text2'],
                             bg=C['bg3'], font=('Consolas',10))
        self._dot.pack(side=tk.LEFT, padx=6)
        tk.Label(bar, textvariable=self.status_var, bg=C['bg3'],
                 fg=C['text2'], font=('Consolas',9)).pack(side=tk.LEFT)
        tk.Label(bar, text=f'v{VERSION}  |  ลุงพี  |  Prolific PL2303 COM6',
                 bg=C['bg3'], fg=C['text2'],
                 font=('Consolas',8)).pack(side=tk.RIGHT, padx=8)

    # ── Parameter cards ──────────────────────────────────────────────────────

    def _refresh_cards(self):
        if self._ph_shown and self.params:
            self._placeholder.pack_forget()
            self._ph_shown = False
        for name, p in self.params.items():
            if name not in self._cards: self._make_card(name, p)
            self._sync_card(name, p)

    def _make_card(self, name, p: Param):
        card = tk.Frame(self._pcont, bg=C['bg2'], padx=12, pady=8,
                        highlightthickness=1, highlightbackground=C['border'])
        card.pack(fill=tk.X, padx=8, pady=5)

        r1 = tk.Frame(card, bg=C['bg2']); r1.pack(fill=tk.X)
        title = p.label if p.label != name else name.upper()
        tk.Label(r1, text=title, font=('Consolas',11,'bold'),
                 bg=C['bg2'], fg=C['text']).pack(side=tk.LEFT)
        if title != name.upper():
            tk.Label(r1, text=f'  {name}', font=('Consolas',8),
                     bg=C['bg2'], fg=C['text2']).pack(side=tk.LEFT)
        badge = tk.Label(r1, text='UNKNOWN', font=('Consolas',8,'bold'),
                         bg=C['text2'], fg=C['bg'], padx=6, pady=1)
        badge.pack(side=tk.RIGHT)

        val_lbl = tk.Label(card, text='---', font=('Consolas',30,'bold'),
                           bg=C['bg2'], fg=C['text'])
        val_lbl.pack(anchor='w')

        pf = tk.Frame(card, bg=C['border'], height=7); pf.pack(fill=tk.X, pady=(2,6))
        pb = tk.Frame(pf, bg=C['green'], height=7)
        pb.place(x=0, y=0, relheight=1, relwidth=0.0)

        adv = tk.Label(card, text='', font=('Consolas',9),
                       bg=C['bg2'], fg=C['text2'], anchor='w')
        adv.pack(fill=tk.X)

        thresh = tk.Label(card, font=('Consolas',8),
                          bg=C['bg2'], fg=C['text2'], anchor='w')
        thresh.pack(fill=tk.X, pady=(4,0))

        self._cards[name] = dict(card=card, badge=badge, val=val_lbl,
                                 pf=pf, pb=pb, adv=adv, thresh=thresh)

    def _sync_card(self, name, p: Param):
        w = self._cards[name]
        st = p.status()
        if p.normal:
            lo, hi = p.normal
            ok = st == 'OK'
            color = C['green'] if ok else (C['yellow'] if st == 'WARNING' else C['text2'])
            try:    vtext = f'{float(p.value):g} {p.unit}'.strip()
            except (TypeError, ValueError): vtext = '---'
            w['val'].config(text=vtext, fg=color)
            w['badge'].config(text='ปกติ' if ok else 'นอกช่วง', bg=color, fg='#0d1117')
            w['adv'].config(text='✅ อยู่ในช่วงปกติ' if ok else f'⚠ นอกช่วงปกติ  {p.hint}'.rstrip(),
                            fg=color)
            w['card'].config(highlightbackground=color)
            w['thresh'].config(text=f'ช่วงปกติ {lo:g} – {hi:g} {p.unit}')
            try:
                w['pb'].place(relwidth=min(max(float(p.value) / (hi * 1.25), 0.0), 1.0))
                w['pb'].config(bg=color)
            except (TypeError, ValueError, ZeroDivisionError):
                pass
            return
        lbl, color, advice = STATUS_TH[st]
        try:    vtext = f'{float(p.value):.2f} {p.unit}'.strip()
        except: vtext = str(p.value or '---')
        w['val'].config(text=vtext, fg=color)
        w['badge'].config(text=st, bg=color, fg='#0d1117')
        w['adv'].config(text=f'{lbl}  —  {advice}', fg=color)
        w['card'].config(highlightbackground=color)
        w['thresh'].config(
            text=f'เฝ้าระวัง ≥ {p.warn}  อันตราย ≥ {p.danger}  วิกฤต ≥ {p.crit}  {p.unit}')
        try:
            pct = min(max(float(p.value)/p.crit, 0.0), 1.0)
            w['pf'].update_idletasks()
            w['pb'].place(relwidth=pct)
            w['pb'].config(bg=color)
        except: pass

    # ── Serial ───────────────────────────────────────────────────────────────

    def _refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self._port_cb['values'] = ports
        if 'COM6' in ports: self.port_var.set('COM6')
        elif ports:         self.port_var.set(ports[0])

    def _toggle_connect(self):
        if self.running: self._disconnect()
        elif self.scan_var.get(): self._scan_then_connect()
        else: self._open_port(self.port_var.get(), int(self.baud_var.get()))

    def _scan_then_connect(self):
        port = self.port_var.get()
        if not port:
            messagebox.showwarning('', 'กรุณาเลือก Port ก่อน'); return
        self._conn_btn.config(state=tk.DISABLED, text='⏳ กำลัง scan...')
        self._log('⏳ Auto-scanning baud rates...', 'info')
        def scan():
            best, best_n = 9600, 0
            for baud in BAUD_RATES:
                try:
                    s = serial.Serial(port, baud, timeout=0.5)
                    time.sleep(0.7); n = s.in_waiting; s.close()
                    self.root.after(0, lambda b=baud, nn=n:
                        self._log(f'  {b:>7} baud → {nn} bytes', 'info'))
                    if n > best_n: best_n, best = n, baud
                except: pass
            self.baud_var.set(str(best))
            if best_n == 0:
                self.root.after(0, self._explain_no_data)
            self.root.after(0, lambda: [
                self._log(f'✅ เลือก {best} baud ({best_n} bytes)', 'ok'),
                self._conn_btn.config(state=tk.NORMAL, text='⚡ เชื่อมต่อ'),
                self._open_port(port, best)])
        threading.Thread(target=scan, daemon=True).start()

    def _open_port(self, port, baud):
        if not port:
            messagebox.showwarning('', 'กรุณาเลือก Port ก่อน'); return
        try:
            self.ser = serial.Serial(port, baud, timeout=1)
            self.running = True
            self._conn_btn.config(text='⏹ หยุด', bg='#b91c1c',
                                  activebackground='#991b1b', state=tk.NORMAL)
            self._set_status(f'● เชื่อมต่อ {port} @ {baud}', C['green'])
            self._log(f'✅ เชื่อมต่อ {port} @ {baud} baud', 'ok')
            threading.Thread(target=self._read_loop, daemon=True).start()
        except serial.SerialException as e:
            messagebox.showerror('Serial Error', str(e))

    def _disconnect(self):
        self.running = False
        try:
            if self.ser and self.ser.is_open: self.ser.close()
        except: pass
        self._conn_btn.config(text='⚡ เชื่อมต่อ', bg='#238636',
                              activebackground='#2ea043', state=tk.NORMAL)
        self._set_status('ไม่ได้เชื่อมต่อ', C['text2'])
        self._log('🔌 ตัดการเชื่อมต่อ', 'warn')

    def _read_loop(self):
        buf = b''
        while self.running:
            try:
                waiting = self.ser.in_waiting
                if waiting:
                    chunk = self.ser.read(waiting)
                    buf += chunk
                    if self.proto_var.get() == 'Modbus RTU':
                        if len(buf) >= 5:
                            self.root.after(0, lambda b=buf:
                                self._process_bytes(b))
                            buf = b''
                    elif self.proto_var.get() == 'AC STAG':
                        self._acstag_buf += chunk
                        frames = parse_acstag_stream(self._acstag_buf, self.params)
                        if frames:
                            for off, frame in frames:
                                self._acstag_frames += 1
                                fc   = self._acstag_frames
                                hexs = ' '.join(f'{b:02X}' for b in frame)
                                ann  = acstag_annotate_frame(frame, self.params)
                                self.root.after(0, lambda h=hexs, n=fc, a=ann:
                                    self._log(f'[STAG#{n} {len(h)//3+1}B] {h}  → {a}', 'rx'))
                            self.root.after(0, self._refresh_cards)
                            # Keep only unprocessed tail
                            if frames:
                                last_off, last_frame = frames[-1]
                                self._acstag_buf = self._acstag_buf[last_off + len(last_frame):]
                        elif len(self._acstag_buf) >= 64:
                            hexs = ' '.join(f'{b:02X}' for b in self._acstag_buf[:64])
                            self.root.after(0, lambda h=hexs:
                                self._log(f'[RAW 64B] {h}', 'rx'))
                            self._acstag_buf = self._acstag_buf[64:]
                        buf = b''
                    elif self.proto_var.get() == 'HEX':
                        hex_str = ' '.join(f'{b:02X}' for b in chunk)
                        self.root.after(0, lambda h=hex_str:
                            self._log(f'[HEX] {h}', 'rx'))
                        buf = b''
                    else:
                        try: text = buf.decode('utf-8', errors='replace')
                        except: text = buf.decode('latin-1', errors='replace')
                        buf = b''
                        while '\n' in text:
                            line, text = text.split('\n', 1)
                            line = line.strip()
                            if line:
                                self.root.after(0, lambda l=line:
                                    self._process_line(l))
                        if text: buf = text.encode()
                else:
                    time.sleep(0.04)
            except Exception as e:
                if self.running:
                    self.root.after(0, lambda err=str(e):
                        self._log(f'❌ Serial error: {err}', 'err'))
                    self.root.after(0, self._disconnect)
                break

    def _process_line(self, line: str):
        ts = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        self._log(f'[{ts}]  {line}', 'ok')
        if self._hex_mode:
            return
        proto = self.proto_var.get()
        if   proto == 'JSON':      ok = parse_json(line, self.params)
        elif proto == 'CSV':       ok = parse_csv_line(line, self.params)
        elif proto == 'Key=Value': ok = parse_kv(line, self.params)
        else:                      ok = parse_auto(line, self.params)
        if ok: self._refresh_cards()

    def _process_bytes(self, raw: bytes):
        hex_str = ' '.join(f'{b:02X}' for b in raw)
        self._log(f'[Modbus RX] {hex_str}', 'rx')
        if parse_modbus_response(raw, self.params):
            self._refresh_cards()

    def _send_cmd(self):
        if not (self.ser and self.ser.is_open):
            self._log('❌ ยังไม่ได้เชื่อมต่อ', 'err'); return
        text = self.send_var.get()
        if not text: return
        data = text.replace('\\r\\n', '\r\n').replace('\\n', '\n').replace('\\r', '\r')
        self.ser.write(data.encode('utf-8', errors='replace'))
        self._log(f'[TX] {repr(data)}', 'info')
        self.send_var.set('')

    def _toggle_hex(self):
        self._hex_mode = not self._hex_mode
        mode = 'HEX MODE' if self._hex_mode else 'TEXT MODE'
        self._log(f'--- {mode} ---', 'info')

    # ── Auto-Tune ────────────────────────────────────────────────────────────

    def _quick_autotune(self):
        """One-click: apply statistical suggestions to all params"""
        if not self.params:
            messagebox.showinfo('Auto-Tune', 'ยังไม่มีข้อมูล — รอรับข้อมูลจากเซนเซอร์ก่อน')
            return
        applied = []
        for name, p in self.params.items():
            s = p.suggest_thresholds()
            if s:
                p.warn, p.danger, p.crit = s
                applied.append(f'{name}: warn={p.warn}  danger={p.danger}  crit={p.crit}')
        if applied:
            self._refresh_cards()
            msg = 'ปรับ Threshold อัตโนมัติแล้ว:\n\n' + '\n'.join(applied)
            self._log('⚡ Auto-Tune applied', 'info')
            messagebox.showinfo('✅ Auto-Tune', msg)
        else:
            messagebox.showinfo('Auto-Tune', 'ต้องมีข้อมูลอย่างน้อย 10 ค่าต่อ channel\nรอสักครู่แล้วลองใหม่')

    # ── Settings (Threshold + Auto-Tune tabs) ────────────────────────────────

    def _open_settings(self):
        win = tk.Toplevel(self.root)
        win.title('⚙ ตั้งค่า Threshold')
        win.geometry('530x580')
        win.configure(bg=C['bg'])
        win.transient(self.root); win.grab_set()

        nb = ttk.Notebook(win)
        nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        tab1 = tk.Frame(nb, bg=C['bg']); nb.add(tab1, text='  📐 ตั้งค่าเอง  ')
        tab2 = tk.Frame(nb, bg=C['bg']); nb.add(tab2, text='  ⚡ Auto-Tune  ')

        # ── Tab 1: Manual ──────────────────────────────────────
        tk.Label(tab1, text='ปรับค่า Threshold และ Unit ต่อพารามิเตอร์',
                 font=('Consolas',10,'bold'), bg=C['bg'], fg=C['text']
                 ).pack(pady=10, padx=10)

        if not self.params:
            tk.Label(tab1, text='ยังไม่มีพารามิเตอร์\nกรุณาเชื่อมต่อและรับข้อมูลก่อน',
                     bg=C['bg'], fg=C['text2'], font=('Consolas',10),
                     justify=tk.CENTER).pack(pady=30)
        else:
            scroll = tk.Frame(tab1, bg=C['bg']); scroll.pack(fill=tk.BOTH, expand=True, padx=10)
            vars_map = {}
            for name, p in self.params.items():
                frm = tk.LabelFrame(scroll, text=f'  {name}  ',
                                    bg=C['bg2'], fg=C['text'], font=('Consolas',9),
                                    padx=10, pady=6, relief=tk.FLAT,
                                    highlightbackground=C['border'], highlightthickness=1)
                frm.pack(fill=tk.X, pady=5)
                vars_map[name] = {}

                # Unit + Thai label
                r0 = tk.Frame(frm, bg=C['bg2']); r0.pack(fill=tk.X, pady=2)
                for lbl_text, key, w_val in [('Unit:', 'unit', p.unit),
                                              ('ชื่อไทย:', 'label', p.label)]:
                    tk.Label(r0, text=lbl_text, width=9, anchor='w',
                             bg=C['bg2'], fg=C['text2'], font=('Consolas',9)
                             ).pack(side=tk.LEFT)
                    var = tk.StringVar(value=w_val)
                    ttk.Entry(r0, textvariable=var, width=12,
                              font=('Consolas',9)).pack(side=tk.LEFT, padx=(0,12))
                    vars_map[name][key] = var

                # Sliders
                for lbl_s, attr, color in [
                    ('⚠  เฝ้าระวัง', 'warn',   C['yellow']),
                    ('🔶 อันตราย',    'danger', C['orange']),
                    ('🚨 วิกฤต',      'crit',   C['red']),
                ]:
                    r = tk.Frame(frm, bg=C['bg2']); r.pack(fill=tk.X, pady=1)
                    tk.Label(r, text=lbl_s, width=15, anchor='w',
                             bg=C['bg2'], fg=color, font=('Consolas',9)
                             ).pack(side=tk.LEFT)
                    var = tk.DoubleVar(value=getattr(p, attr))
                    tk.Scale(r, from_=0, to=100, resolution=0.5,
                             orient=tk.HORIZONTAL, variable=var,
                             bg=C['bg2'], fg=color, troughcolor=C['bg3'],
                             highlightthickness=0, font=('Consolas',8),
                             length=220).pack(side=tk.LEFT, padx=4)
                    tk.Label(r, textvariable=var, width=6,
                             bg=C['bg2'], fg=color,
                             font=('Consolas',9)).pack(side=tk.LEFT)
                    vars_map[name][attr] = var

            def apply_manual():
                for name, attrs in vars_map.items():
                    p = self.params[name]
                    p.unit   = attrs['unit'].get()
                    p.label  = attrs['label'].get()
                    p.warn   = attrs['warn'].get()
                    p.danger = attrs['danger'].get()
                    p.crit   = attrs['crit'].get()
                self._refresh_cards()
                win.destroy()

            tk.Button(tab1, text='✅  บันทึก', command=apply_manual,
                      bg='#238636', fg='white', relief=tk.FLAT,
                      font=('Consolas',11,'bold'), padx=24, pady=6,
                      cursor='hand2').pack(pady=10)

        # ── Tab 2: Auto-Tune ───────────────────────────────────
        tk.Label(tab2, text='⚡ Auto-Tune — คำนวณ Threshold จากข้อมูลจริง',
                 font=('Consolas',10,'bold'), bg=C['bg'], fg=C['text']
                 ).pack(pady=10, padx=10)
        tk.Label(tab2,
                 text='วิธีคำนวณ:\n'
                      '• เฝ้าระวัง  = ค่าเฉลี่ย + 1.5σ (อย่างน้อย 10 ค่า)\n'
                      '• อันตราย   = ค่าเฉลี่ย + 3σ\n'
                      '• วิกฤต      = ค่าเฉลี่ย + 5σ\n\n'
                      'ใช้เมื่อเซนเซอร์ทำงานปกติ (baseline)\n'
                      'แล้วจะได้ threshold ที่เหมาะกับสภาพแวดล้อมจริง',
                 bg=C['bg'], fg=C['text2'], font=('Consolas',9),
                 justify=tk.LEFT).pack(padx=20, anchor='w')

        result_text = tk.Text(tab2, bg=C['bg2'], fg=C['cyan'],
                              font=('Consolas',9), height=10, relief=tk.FLAT,
                              state=tk.DISABLED)
        result_text.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)

        def preview_autotune():
            result_text.config(state=tk.NORMAL); result_text.delete('1.0', tk.END)
            for name, p in self.params.items():
                h = p.numeric_history()
                if len(h) < 10:
                    result_text.insert(tk.END,
                        f'{name}: ข้อมูลไม่พอ ({len(h)}/10 ค่า)\n')
                    continue
                s = p.suggest_thresholds()
                if s:
                    mu = statistics.mean(h)
                    result_text.insert(tk.END,
                        f'{name}:\n'
                        f'  ค่าเฉลี่ย = {mu:.2f}  (n={len(h)})\n'
                        f'  เฝ้าระวัง → {s[0]}  อันตราย → {s[1]}  วิกฤต → {s[2]}\n\n')
            if not result_text.get('1.0', tk.END).strip():
                result_text.insert(tk.END, 'ยังไม่มีข้อมูลพอ...')
            result_text.config(state=tk.DISABLED)

        def apply_autotune():
            self._quick_autotune()
            win.destroy()

        btn_frame = tk.Frame(tab2, bg=C['bg']); btn_frame.pack(pady=6)
        tk.Button(btn_frame, text='🔍 Preview', command=preview_autotune,
                  bg=C['bg3'], fg=C['text'], relief=tk.FLAT,
                  font=('Consolas',10), padx=16, pady=6,
                  cursor='hand2').pack(side=tk.LEFT, padx=6)
        tk.Button(btn_frame, text='✅ Apply', command=apply_autotune,
                  bg='#14532d', fg='#86efac', relief=tk.FLAT,
                  font=('Consolas',10,'bold'), padx=16, pady=6,
                  cursor='hand2').pack(side=tk.LEFT, padx=6)

    # ── Car Gas Diagnostics ───────────────────────────────────────────────────

    def _show_car_diagnostics(self):
        win = tk.Toplevel(self.root)
        win.title('🔧 วิเคราะห์ปัญหารถแก๊ส')
        win.geometry('620x640')
        win.configure(bg=C['bg'])
        win.transient(self.root)

        tk.Label(win,
                 text='🔧 ปัญหา: รถไม่ตัดน้ำมันมาแก๊สอัตโนมัติ',
                 font=('Consolas',12,'bold'), bg=C['bg'], fg=C['orange']
                 ).pack(pady=(16,4), padx=16)
        tk.Label(win,
                 text='อาการ: ต้องกดปุ่มแก๊สเองแล้ว start รถ\n'
                      'สาเหตุที่พบบ่อย และวิธีแก้ไข:',
                 font=('Consolas',10), bg=C['bg'], fg=C['text2']
                 ).pack(padx=20, anchor='w')

        frame = tk.Frame(win, bg=C['bg'])
        frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)

        check_vars = []
        for i, (cause, fix) in enumerate(CAR_GAS_PROBLEMS):
            card = tk.Frame(frame, bg=C['bg2'], padx=12, pady=8,
                            highlightthickness=1, highlightbackground=C['border'])
            card.pack(fill=tk.X, pady=4)
            r1 = tk.Frame(card, bg=C['bg2']); r1.pack(fill=tk.X)
            var = tk.BooleanVar()
            check_vars.append(var)
            tk.Checkbutton(r1, variable=var, bg=C['bg2'],
                           selectcolor=C['bg3'],
                           activebackground=C['bg2']).pack(side=tk.LEFT)
            tk.Label(r1, text=f'{i+1}. {cause}',
                     font=('Consolas',10,'bold'), bg=C['bg2'],
                     fg=C['yellow'], anchor='w'
                     ).pack(side=tk.LEFT, padx=4)
            tk.Label(card,
                     text=f'   → {fix}',
                     font=('Consolas',9), bg=C['bg2'],
                     fg=C['text2'], anchor='w', wraplength=560, justify=tk.LEFT
                     ).pack(fill=tk.X, padx=4, pady=(2,0))

        # Summary tip
        tip = tk.Label(win,
            text='💡 วิธีแก้เบื้องต้น:\n'
                 '   1. ถอด-ต่อ connector กล่องแก๊สใหม่\n'
                 '   2. ตรวจสาย vacuum ไม่รั่ว\n'
                 '   3. ปรับ Sensitivity Pot หมุนซ้าย 2–3 ครั้ง\n'
                 '   4. ถ้ายังไม่หาย → ลองสลับ Switch เป็น Manual แล้ว start\n'
                 '      แล้วค่อยสลับกลับ Auto (bypass cold-start lock)',
            font=('Consolas',9), bg='#1a0a00', fg='#fdba74',
            justify=tk.LEFT, padx=12, pady=8)
        tip.pack(fill=tk.X, padx=12, pady=4)

        tk.Button(win, text='ปิด', command=win.destroy,
                  bg=C['bg3'], fg=C['text'], relief=tk.FLAT,
                  font=('Consolas',10), padx=20, pady=6,
                  cursor='hand2').pack(pady=8)

    # ── AC STAG ──────────────────────────────────────────────────────────────

    def _explain_no_data(self):
        self._log('ℹ ทุก baud ได้ 0 bytes = กล่องไม่ได้ส่งข้อมูลออกมาเอง', 'warn')
        self._log('   • กล่อง STAG ตอบเฉพาะเมื่อ AcGasSynchro "ถาม" (รูปแบบคำถามเป็นความลับบริษัท)', 'warn')
        self._log('   • และต้องเปิดกุญแจ ON กล่องจึงมีไฟ', 'warn')
        self._log('   → กดปุ่ม ▶ AcGasSynchro (แถวที่ 2) เพื่ออ่านค่าจริง', 'warn')

    def _open_doc(self, path):
        if not Path(path).exists():
            messagebox.showwarning('ไม่พบไฟล์',
                f'ไม่พบ:\n{path}\n\nติดตั้ง AcGasSynchro ก่อน (ปุ่ม ▶ AcGasSynchro)')
            return
        os.startfile(str(path))
        self._log(f'📖 เปิด {Path(path).name}', 'info')

    def _acgas_running(self):
        import subprocess
        r = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq ACGasSynchro.exe', '/NH'],
                           capture_output=True, text=True,
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        return 'ACGasSynchro.exe' in r.stdout

    def _launch_acgassynchro(self):
        import subprocess
        if not ACGAS_EXE.exists():
            if ACGAS_INSTALLER.exists() and messagebox.askyesno('AcGasSynchro',
                    'ยังไม่ได้ติดตั้ง AcGasSynchro\n\nมีตัวติดตั้งอยู่แล้วที่\n'
                    f'{ACGAS_INSTALLER}\n\nติดตั้งลง {ACGAS_DIR} เลยไหม?'):
                subprocess.Popen([str(ACGAS_INSTALLER), '/SP-', '/SILENT', '/NORESTART',
                                  f'/DIR={ACGAS_DIR}'])
                self._log('⏳ กำลังติดตั้ง AcGasSynchro — เสร็จแล้วกดปุ่มอีกครั้ง', 'info')
            else:
                self._show_acstag_dialog(tab=0)
            return

        if self._acgas_running():
            messagebox.showinfo('AcGasSynchro', 'AcGasSynchro เปิดอยู่แล้ว — ดูที่แถบงาน (taskbar)')
            return

        if self.running:
            self._disconnect()
            self._log('🔓 ปล่อย COM6 ให้ AcGasSynchro ใช้ (COM port เปิดได้ทีละโปรแกรม)', 'info')

        subprocess.Popen([str(ACGAS_EXE)], cwd=str(ACGAS_DIR))
        self._log('▶ เปิด AcGasSynchro แล้ว', 'ok')
        self._log('   1. เปิดกุญแจ ON (หรือติดเครื่อง)', 'info')
        self._log('   2. โปรแกรมจะ "Autosearch" หา ECU เองทีละ COM — รอให้ถึง COM6', 'info')
        self._log('   3. เจอแล้ว ดูค่าที่แท็บ "ออโต้จูน"/"Map": Collector pressure, Reducer temp', 'info')
        self._log('   4. แท็บ "ข้อผิดพลาด" = รหัส Error — ถ่ายรูปเก็บก่อนลบ', 'info')
        self._set_status('AcGasSynchro กำลังใช้ COM6', C['yellow'])

    # ── Live read from the AcGasSynchro window ───────────────────────────────

    def _toggle_acgas_live(self):
        if self._live_on:
            self._stop_acgas_live()
            return
        if not ACGAS_EXE.exists():
            self._launch_acgassynchro()
            return
        if not self._acgas_running():
            self._launch_acgassynchro()
        elif self.running:
            self._disconnect()
            self._log('🔓 ปล่อย COM port ให้ AcGasSynchro', 'info')

        LIVE_LOG_DIR.mkdir(exist_ok=True)
        self._live_path = LIVE_LOG_DIR / f'acgas_{datetime.now():%Y%m%d_%H%M%S}.csv'
        self._live_file = open(self._live_path, 'w', newline='', encoding='utf-8-sig')
        self._live_writer = csv.writer(self._live_file)
        self._live_writer.writerow(
            ['เวลา', 'เชื้อเพลิง', 'แรงดันแก๊ส_bar', 'MAP_bar', 'รอบ_rpm', 'หม้อต้ม_C', 'แก๊ส_C',
             'Lambda1_V', 'Lambda2_V', 'แบต_V']
            + [f'P{i}_ms' for i in range(1, 7)] + [f'L{i}_ms' for i in range(1, 7)])
        self._live_rows = 0
        self._live_hist.clear()
        self._live_events.clear()
        self._live_fuel = None
        self._live_err = None
        self._live_on = True
        self._live_btn.config(text='⏹ หยุดอ่านสด', bg='#b91c1c', activebackground='#991b1b')
        self._log('📡 เริ่มอ่านค่าสดจากหน้าต่าง AcGasSynchro ทุก 0.5 วินาที', 'ok')
        self._log('   • เปิด AcGasSynchro ค้างไว้ และเชื่อมต่อกล่องแล้ว (มีหน้าต่างอื่นทับได้ แต่ห้ามย่อ)', 'info')
        self._log(f'   • บันทึก CSV → {self._live_path}', 'info')
        threading.Thread(target=self._acgas_live_loop, daemon=True).start()

    def _stop_acgas_live(self):
        self._live_on = False
        if self._live_file:
            self._live_file.close()
            self._live_file = self._live_writer = None
        self._live_btn.config(text='📡 อ่านสด', bg='#1d4ed8', activebackground='#2563eb')
        self._set_status('หยุดอ่านสดแล้ว', C['text2'])
        self._log(f'⏹ หยุดอ่านสด — บันทึก {self._live_rows} แถว, '
                  f'สลับแก๊ส/น้ำมัน {len(self._live_events)} ครั้ง → {self._live_path}', 'info')

    def _acgas_live_loop(self):
        import acgas_reader as AR
        while self._live_on:
            t0 = time.time()
            data, err = None, None
            try:
                params, raw = AR.read_live()
                if not self._live_plausible(raw):
                    err = 'อ่านตัวเลขไม่ชัด (ข้ามค่านี้)'
                else:
                    data = (params, raw)
            except AR.Minimized:
                err = 'หน้าต่าง AcGasSynchro ถูกย่ออยู่ — เปิดขึ้นมา (มีหน้าต่างอื่นทับได้)'
            except AR.NotFound as e:
                err = ('ไม่พบโปรแกรม AcGasSynchro — กด ▶ AcGasSynchro' if 'running' in str(e)
                       else 'AcGasSynchro ยังไม่เชื่อมต่อกล่อง (ไม่เห็นแถบ แกส/น้ำมัน)')
            except Exception as e:
                err = f'อ่านไม่ได้: {e}'
            self.root.after(0, self._apply_live, data, err)
            time.sleep(max(0.05, LIVE_INTERVAL - (time.time() - t0)))

    @staticmethod
    def _live_plausible(raw):
        rpm, gas, mp = raw.get('RPM'), raw.get('GAS_bar'), raw.get('MAP_bar')
        return (rpm is not None and 0 <= rpm <= 9000 and gas is not None and 0 <= gas <= 5
                and mp is not None and 0 <= mp <= 3)

    def _apply_live(self, data, err):
        if not self._live_on:
            return
        if err:
            if err != self._live_err:
                self._log(f'⚠ {err}', 'warn')
                self._live_err = err
            self._set_status(f'📡 {err}', C['yellow'])
            return
        if self._live_err:
            self._log('✅ อ่านค่าจาก AcGasSynchro ได้แล้ว', 'ok')
            self._live_err = None

        params, raw = data
        for key, v in params.items():
            if key not in LIVE_PARAMS:
                continue
            p = self.params.get(key)
            if p is None or not p.normal:
                lbl, unit, lo, hi, hint = LIVE_PARAMS[key]
                p = Param(key, unit, normal=(lo, hi))
                p.label, p.hint = lbl, hint
                if key in self._cards:
                    self._cards.pop(key)['card'].destroy()
                self.params[key] = p
            p.push(v)

        now, fuel = datetime.now(), raw['fuel']
        gas, rpm = raw.get('GAS_bar'), raw.get('RPM')
        self._live_hist.append((now, gas, rpm, fuel, raw.get('MAP_bar')))
        if self._live_fuel and fuel != self._live_fuel:
            self._live_events.append((now, self._live_fuel, fuel, gas, rpm))
            self._log(f'🔄 {now:%H:%M:%S}  {FUEL_TH[self._live_fuel]} → {FUEL_TH[fuel]}   '
                      f'แรงดันแก๊ส {gas:.2f} bar   รอบ {rpm:.0f}',
                      'warn' if fuel == 'petrol' else 'ok')
        self._live_fuel = fuel

        if self._live_writer:
            self._live_writer.writerow(
                [now.strftime('%H:%M:%S.%f')[:-3], FUEL_TH[fuel], gas, raw.get('MAP_bar'), rpm,
                 raw.get('RED_TEMP'), raw.get('GAS_TEMP'), raw.get('LAMBDA1'), raw.get('LAMBDA2'),
                 raw.get('BATT_V')]
                + [raw.get(f'P{i}') for i in range(1, 7)] + [raw.get(f'L{i}') for i in range(1, 7)])
            self._live_file.flush()
            self._live_rows += 1

        self._refresh_cards()
        self._set_status(f'📡 AcGasSynchro สด · {FUEL_TH[fuel]} · แรงดันแก๊ส {gas:.2f} bar · '
                         f'{rpm:.0f} rpm · บันทึก {self._live_rows} แถว',
                         C['green'] if fuel == 'gas' else C['blue'])

    def _open_live_logs(self):
        LIVE_LOG_DIR.mkdir(exist_ok=True)
        os.startfile(str(LIVE_LOG_DIR))

    def _on_proto_change(self, *_):
        if self.proto_var.get() == 'AC STAG':
            self.baud_var.set(str(ACSTAG_BAUD))
            self._acstag_buf    = b''
            self._acstag_frames = 0
            self._log(f'ℹ AC STAG mode — baud → {ACSTAG_BAUD}  (ต้องติดเครื่องก่อน)', 'info')

    def _show_acstag_dialog(self, tab=0):
        win = tk.Toplevel(self.root)
        win.title('📡 AC STAG — ดาวน์โหลด · Tuning Map · แรงดันแก๊ส · วิธีอ่านค่า · ตัดสินใจ · ศัพท์ช่าง')
        win.geometry('900x820')
        win.configure(bg=C['bg'])
        win.transient(self.root)

        nb = ttk.Notebook(win)
        nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10,0))

        def scroll_tab(title):
            outer = tk.Frame(nb, bg=C['bg']); nb.add(outer, text=title)
            cv = tk.Canvas(outer, bg=C['bg'], highlightthickness=0)
            sb = ttk.Scrollbar(outer, command=cv.yview)
            cv.configure(yscrollcommand=sb.set)
            sb.pack(side=tk.RIGHT, fill=tk.Y)
            cv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            inner = tk.Frame(cv, bg=C['bg'])
            wid = cv.create_window((0,0), window=inner, anchor='nw')
            cv.bind('<Configure>', lambda e: cv.itemconfig(wid, width=e.width))
            inner.bind('<Configure>', lambda e: cv.configure(scrollregion=cv.bbox('all')))
            inner.bind('<Enter>', lambda e: cv.bind_all(
                '<MouseWheel>', lambda ev: cv.yview_scroll(-ev.delta//120, 'units')))
            inner.bind('<Leave>', lambda e: cv.unbind_all('<MouseWheel>'))
            return inner

        def section(parent, title, fg=C['blue']):
            tk.Label(parent, text=title, font=('Consolas',10,'bold'),
                     bg=C['bg'], fg=fg, anchor='w').pack(fill=tk.X, padx=14, pady=(10,2))

        def para(parent, text, fg=C['text2']):
            tk.Label(parent, text=text, font=('Consolas',9),
                     bg=C['bg'], fg=fg, anchor='w', justify=tk.LEFT,
                     wraplength=700).pack(fill=tk.X, padx=22, pady=1)

        def table(parent, rows, widths):
            for i, r in enumerate(rows):
                hdr = i == 0
                f = tk.Frame(parent, bg=C['bg3'] if hdr else C['bg2'], padx=8, pady=3)
                f.pack(fill=tk.X, padx=20, pady=1)
                for col, w in zip(r, widths):
                    tk.Label(f, text=col, width=w, anchor='w',
                             font=('Consolas',9,'bold' if hdr else 'normal'),
                             bg=f['bg'], fg=C['cyan'] if hdr else C['text']
                             ).pack(side=tk.LEFT)

        # ── 1. ดาวน์โหลด ─────────────────────────────
        t1 = scroll_tab('  📥 ดาวน์โหลด  ')
        section(t1, '🖥  ซอฟต์แวร์ที่ต้องการ')
        para(t1, 'AcGasSynchro v11.2.1.1  (โปรแกรมทางการของ AC STAG สำหรับคอมพิวเตอร์ Windows)\n'
                 'รองรับ: STAG-300 Plus / ISA2 / Premium, STAG-4 Eco / STAG-4 Plus\n'
                 f'กล่องในรถ: {ECU_MODEL}  เฟิร์มแวร์ 10.0 (อ่านจาก AcGasSynchro แล้ว)', fg=C['text'])

        section(t1, '🌐  ดาวน์โหลดจาก')
        for url, note in [
            ('https://ccy.pl/en/download-left/category/438-ac-stag',
             '→ ไฟล์: AcGasSynchro-11.2.1.1  (58 MB)  — ต้องสมัครสมาชิกฟรี'),
            ('https://mystag.pl/download/',
             '→ เว็บทางการ ไม่ต้องสมัคร: แท็บ Software → AcGasSynchro → SetupAcGasSynchro-11.2.1.1'),
        ]:
            f = tk.Frame(t1, bg=C['bg2'], padx=10, pady=4,
                         highlightthickness=1, highlightbackground=C['border'])
            f.pack(fill=tk.X, padx=20, pady=3)
            lnk = tk.Label(f, text=url, font=('Consolas',9,'underline'), bg=C['bg2'],
                           fg=C['blue'], anchor='w', cursor='hand2')
            lnk.pack(anchor='w')
            lnk.bind('<Button-1>', lambda e, u=url: __import__('webbrowser').open(u))
            tk.Label(f, text=note, font=('Consolas',8), bg=C['bg2'],
                     fg=C['text2'], anchor='w').pack(anchor='w')

        installed = ACGAS_EXE.exists()
        st = tk.Frame(t1, bg=C['bg2'], padx=10, pady=8, highlightthickness=1,
                      highlightbackground=C['green'] if installed else C['yellow'])
        st.pack(fill=tk.X, padx=20, pady=(8,2))
        tk.Label(st, font=('Consolas',10,'bold'), bg=C['bg2'], anchor='w',
                 fg=C['green'] if installed else C['yellow'],
                 text=(f'✅ ติดตั้งแล้วที่ {ACGAS_DIR}  (ภาษาไทยอัตโนมัติ)' if installed
                       else '⚠ ยังไม่ได้ติดตั้งในเครื่องนี้')).pack(anchor='w')
        bf = tk.Frame(st, bg=C['bg2']); bf.pack(anchor='w', pady=(6,0))
        for text, cmd in [('▶ เปิด AcGasSynchro', self._launch_acgassynchro),
                          ('📖 คู่มือ ISA2', lambda: self._open_doc(ACGAS_MANUAL)),
                          ('🔌 ผังสายไฟ ISA2', lambda: self._open_doc(ACGAS_WIRING)),
                          ('📋 คำอธิบายสายแต่ละเส้น', lambda: self._open_doc(ACGAS_LEADS))]:
            tk.Button(bf, text=text, command=cmd, bg='#b45309' if '▶' in text else C['bg3'],
                      fg='white' if '▶' in text else C['text'], relief=tk.FLAT,
                      font=('Consolas',9,'bold'), padx=10, pady=4,
                      cursor='hand2').pack(side=tk.LEFT, padx=(0,6))

        section(t1, '🔌  ขั้นตอนเชื่อมต่อ')
        for s in [
            f'1. ต่อสาย USB ↔ กล่อง {ECU_MODEL} (สาย PL2303 → COM6)',
            '2. เปิดสวิตช์กุญแจ ON หรือติดเครื่อง — ถ้ากุญแจ OFF กล่องไม่มีไฟ คุยไม่ได้',
            '3. กด ▶ เปิด AcGasSynchro — GAS Monitor จะปล่อย COM6 ให้เอง',
            '4. AcGasSynchro "Autosearch" หา ECU ทีละ COM อัตโนมัติ — รอให้ถึง COM6',
            '5. เจอแล้ว ตัวเลขต่างๆ จะเริ่มขยับ  (ถ้าค้นไม่เจอ: เมนู Port → เลือก COM6 เอง)',
        ]:
            para(t1, s)

        # ── Tuning Map ────────────────────────────────
        tm = tk.Frame(nb, bg=C['bg']); nb.add(tm, text='  📈 Tuning Map  ')
        self._build_tuning_map(tm, win)

        pg = tk.Frame(nb, bg=C['bg']); nb.add(pg, text='  📉 แรงดันแก๊ส  ')
        self._build_pressure_graph(pg, win)

        # ── 2. วิธีอ่านค่า ───────────────────────────
        t2 = scroll_tab('  🗺 วิธีอ่านค่า  ')
        section(t2, '📍  ค่าที่ต้องดู มี 3 ตัว (ชื่อในโปรแกรม = ภาษาอังกฤษ)', fg=C['green'])
        table(t2, [
            ('ชื่อในโปรแกรม',          'แปลว่า',                   'บอกอะไร'),
            ('Collector pressure',    'MAP แรงดันท่อไอดี',          'เซนเซอร์/ท่อยางปกติไหม'),
            ('Reducer / Gas pressure','แรงดันแก๊สหลังหม้อต้ม',       'หม้อต้ม/กรองแก๊สดีไหม  ★'),
            ('Reducer temperature',   'ความร้อนหม้อต้ม',            'น้ำร้อนเข้าหม้อต้มไหม  ★'),
        ], [24, 24, 26])
        para(t2, '★ = ตัวสำคัญที่สุดสำหรับอาการ "ไม่สลับเป็นแก๊สเอง"', fg=C['yellow'])

        section(t2, '🖥  อยู่ตรงไหนในหน้าจอ', fg=C['green'])
        para(t2, '• หน้าหลักหลัง Connect: แถบตัวเลขด้านบน/ด้านข้าง แสดงค่า pressure, temperature, RPM สดๆ\n'
                 '• กราฟแผนที่ (map): แกนนอน = รอบเครื่อง, แกนตั้งขวามือ = Collector pressure [kPa]\n'
                 '  จุดที่ขยับบนกราฟ = สภาพเครื่องตอนนี้\n'
                 '• เงื่อนไขการสลับ: แท็บ Settings / Switching (อุณหภูมิ, รอบ ที่ต้องถึงก่อนสลับ)\n'
                 '• รหัสความผิดพลาด: แท็บ Errors / Diagnostics — ถ่ายรูปเก็บก่อนกดลบ', fg=C['text'])

        section(t2, '🔢  ค่าปกติ (ติดเครื่อง เกียร์ว่าง ไม่เหยียบคันเร่ง)', fg=C['green'])
        table(t2, [
            ('ค่า',                    'ปกติ',               'ผิดปกติ'),
            ('Collector pressure',    '25–40 kPa',          'ค้าง 0 หรือ ~100 ตลอด'),
            ('Gas pressure (เหนือ MAP)','~100 kPa (1 bar)',  'ต่ำกว่า ~60 kPa'),
            ('Reducer temperature',   'ขึ้นถึง 35°C+ ใน 1–3 นาที', 'ไม่ขึ้น / ขึ้นช้ามาก'),
            ('RPM',                   '700–900',            '—'),
        ], [24, 24, 26])

        section(t2, '📈  Collector pressure (MAP) เปลี่ยนตามการขับ', fg=C['green'])
        table(t2, [
            ('สภาวะ',                         'ค่าปกติ',     'น่ากังวล'),
            ('เดินเบา (ไม่เหยียบคันเร่ง)',       '25–40 kPa',  '< 20 kPa'),
            ('ถอนคันเร่งขณะรถวิ่ง (engine braking)', '15–20 kPa', '—'),
            ('เหยียบคันเร่งสุด',                 '90–100 kPa', '< 70 kPa'),
        ], [36, 14, 22])
        para(t2, 'หมายเหตุ: "ถอนคันเร่ง" = ปล่อยเท้าจากคันเร่งตอนรถยังวิ่ง ไม่ใช่การเหยียบเบรก\n'
                 'ดูภาพจุดขยับบนกราฟได้ที่แท็บ 📈 Tuning Map (ติ๊ก "ตัวอย่างจำลอง")')

        section(t2, '🧪  ทดสอบ 5 นาที (จดค่าลงกระดาษ)', fg=C['green'])
        para(t2, '1. สตาร์ทเครื่องเย็น → จด Reducer temperature ทุก 30 วินาที\n'
                 '2. พอถึงค่าที่ตั้งใน Switching แล้ว ดูว่ากล่องพยายามสลับไหม (ไฟ/เสียงคลิก)\n'
                 '3. ตอนกดปุ่มแก๊สเอง → ดู Gas pressure ทันที ว่าตกลงมากแค่ไหน\n'
                 '4. เปิดแท็บ Errors ถ่ายรูปรหัสทั้งหมด', fg=C['text'])

        # ── 3. ตัดสินใจ ──────────────────────────────
        t3 = scroll_tab('  🔶 ตัดสินใจ  ')
        section(t3, '🔶  อ่านผลแล้วแปลว่าอะไร', fg=C['orange'])
        for cond, action, color in [
            ('Reducer temperature ไม่ขึ้น / ขึ้นช้ามาก',
             'น้ำร้อนเข้าหม้อต้มไม่ได้ → เช็คท่อน้ำเข้า-ออกหม้อต้ม มีลมค้าง, ท่อพับ, วาล์วน้ำ\n'
             'หรือเซนเซอร์อุณหภูมิเสีย (ถ้าจับหม้อต้มแล้วร้อน แต่โปรแกรมโชว์เย็น)',
             C['orange']),
            ('อุณหภูมิถึงแล้ว แต่ Gas pressure ต่ำ / ตกวูบตอนสลับ',
             'แก๊สไหลไม่พอ → ลำดับเช็คจากถูกไปแพง:\n'
             '  ① ไส้กรองแก๊ส (~150–400 บาท)  ② กรองในโซลินอยด์  ③ หม้อต้ม (1,500–3,000 บาท)\n'
             '  และดูว่าแก๊สในถังเหลือพอ',
             C['red']),
            ('อุณหภูมิถึง + แรงดันปกติ แต่ยังไม่สลับเอง',
             'ปัญหาอยู่ที่ "การตั้งค่า" → เปิด Settings/Switching ดูว่าตั้งอุณหภูมิ/รอบสลับสูงเกินไหม\n'
             'หรือดูรหัส Error — ข้อนี้ช่างแก้ในโปรแกรมได้ ไม่ต้องเปลี่ยนอะไหล่',
             C['yellow']),
            ('Collector pressure ค้าง 0 หรือ ~100 ตลอด',
             'เซนเซอร์ MAP หรือท่อยางสุญญากาศมีปัญหา → เช็คท่อยางแตก/หลุด',
             C['yellow']),
            ('ทุกค่าปกติ ไม่มี Error',
             'ระบบแก๊สน่าจะโอเค → ส่งรหัส/ค่าที่จดให้ช่าง LPG ดูอีกที',
             C['green']),
        ]:
            f = tk.Frame(t3, bg=C['bg2'], padx=12, pady=8,
                         highlightthickness=1, highlightbackground=color)
            f.pack(fill=tk.X, padx=16, pady=5)
            tk.Label(f, text=cond, font=('Consolas',10,'bold'),
                     bg=C['bg2'], fg=color, anchor='w').pack(anchor='w')
            tk.Label(f, text=action, font=('Consolas',9), bg=C['bg2'], fg=C['text'],
                     anchor='w', wraplength=680, justify=tk.LEFT).pack(anchor='w', pady=(2,0))

        section(t3, '📡  ใช้ GAS Monitor โหมด AC STAG (ทดลอง)', fg=C['cyan'])
        para(t3, '1. Protocol → "AC STAG" (baud ตั้ง 9600 ให้เอง)  2. ⚡ เชื่อมต่อ  3. เปิดกุญแจ ON\n'
                 '4. ถ้าเห็น [STAG#…] ใน terminal = กล่องส่งข้อมูลมา\n'
                 'โปรโตคอลของ STAG เป็นความลับบริษัท ค่าที่ GAS Monitor แสดงจึงเป็น "การเดา"\n'
                 'ใช้ AcGasSynchro เป็นตัวตัดสินเสมอ')

        # ── 4. ศัพท์ช่าง ─────────────────────────────
        t4 = scroll_tab('  📚 ศัพท์ช่าง  ')
        top = tk.Frame(t4, bg=C['bg']); top.pack(fill=tk.X, padx=14, pady=(10,4))
        tk.Label(top, text='🔍 ค้นหา:', bg=C['bg'], fg=C['text2'],
                 font=('Consolas',9)).pack(side=tk.LEFT)
        q = tk.StringVar()
        ttk.Entry(top, textvariable=q, width=30,
                  font=('Consolas',10)).pack(side=tk.LEFT, padx=6)
        tk.Label(top, text=f'{len(ACSTAG_GLOSSARY)} คำ — ภาษาชาวบ้าน ไม่ต้องเป็นช่าง',
                 bg=C['bg'], fg=C['text2'], font=('Consolas',8)).pack(side=tk.LEFT, padx=8)

        cards = []
        for term, full, body, ex in ACSTAG_GLOSSARY:
            card = tk.Frame(t4, bg=C['bg2'], padx=12, pady=8,
                            highlightthickness=1, highlightbackground=C['border'])
            tk.Label(card, text=term, font=('Consolas',11,'bold'),
                     bg=C['bg2'], fg=C['blue'], anchor='w').pack(anchor='w')
            tk.Label(card, text=full, font=('Consolas',9,'italic'),
                     bg=C['bg2'], fg=C['cyan'], anchor='w',
                     wraplength=680, justify=tk.LEFT).pack(anchor='w')
            tk.Label(card, text=body, font=('Consolas',9), bg=C['bg2'], fg=C['text'],
                     anchor='w', wraplength=680, justify=tk.LEFT).pack(anchor='w', pady=(4,0))
            if ex and ex != '—':
                tk.Label(card, text=f'📏 {ex}', font=('Consolas',9,'bold'),
                         bg=C['bg2'], fg=C['yellow'], anchor='w',
                         wraplength=680, justify=tk.LEFT).pack(anchor='w', pady=(4,0))
            card.pack(fill=tk.X, padx=14, pady=4)
            cards.append((card, f'{term} {full} {body} {ex}'.lower()))

        def filt(*_):
            s = q.get().strip().lower()
            for card, text in cards:
                card.pack_forget()
            for card, text in cards:
                if not s or s in text:
                    card.pack(fill=tk.X, padx=14, pady=4)
        q.trace_add('write', filt)

        nb.select(tab)
        tk.Button(win, text='ปิด', command=win.destroy,
                  bg=C['bg3'], fg=C['text'], relief=tk.FLAT,
                  font=('Consolas',10), padx=20, pady=6,
                  cursor='hand2').pack(pady=8)

    # ── Tuning Map (กราฟ RPM × Collector Pressure + Diagnostics) ─────────────

    def _build_tuning_map(self, parent, win):
        W, H = 520, 380
        L, R, T, B = 16, 70, 16, 46
        pw, ph = W - L - R, H - T - B

        def X(rpm): return L + min(max(rpm, 0), TUNING_MAP_RPM_MAX) / TUNING_MAP_RPM_MAX * pw
        def Y(kpa): return T + (1 - min(max(kpa, 0), TUNING_MAP_KPA_MAX) / TUNING_MAP_KPA_MAX) * ph

        top = tk.Frame(parent, bg=C['bg']); top.pack(fill=tk.X, padx=10, pady=(8,2))
        tk.Label(top, text='📈 Main Tuning Map — แบบเดียวกับหน้าหลัก AcGasSynchro',
                 font=('Consolas',10,'bold'), bg=C['bg'], fg=C['green']).pack(side=tk.LEFT)
        demo_var = tk.BooleanVar(value=False)
        tk.Checkbutton(top, text='▶ ตัวอย่างจำลอง (ไม่ใช่ค่าจริง)', variable=demo_var,
                       bg=C['bg'], fg=C['yellow'], selectcolor=C['bg3'],
                       activebackground=C['bg'], font=('Consolas',9)).pack(side=tk.RIGHT)

        body = tk.Frame(parent, bg=C['bg']); body.pack(fill=tk.BOTH, expand=True, padx=10)
        cv = tk.Canvas(body, width=W, height=H, bg='#090c0f', highlightthickness=1,
                       highlightbackground=C['border'])
        cv.pack(side=tk.LEFT, anchor='n')

        # static: grid, zones, axes
        for rpm in range(0, TUNING_MAP_RPM_MAX + 1, 500):
            cv.create_line(X(rpm), T, X(rpm), T + ph,
                           fill='#1f262e' if rpm % 1000 else '#2b333c')
            if rpm % 1000 == 0:
                cv.create_text(X(rpm), T + ph + 12, text=str(rpm),
                               fill=C['text2'], font=('Consolas',8))
        for kpa in range(0, TUNING_MAP_KPA_MAX + 1, 10):
            cv.create_line(L, Y(kpa), L + pw, Y(kpa),
                           fill='#2b333c' if kpa % 20 == 0 else '#1f262e')
            cv.create_text(L + pw + 6, Y(kpa), text=str(kpa), anchor='w',
                           fill=C['text2'], font=('Consolas',8))
        for r0, r1, k0, k1, fill, edge, lbl in TUNING_MAP_ZONES:
            cv.create_rectangle(X(r0), Y(k1), X(r1), Y(k0), fill=fill, outline=edge, dash=(3,2))
            cv.create_text((X(r0)+X(r1))/2, (Y(k0)+Y(k1))/2, text=lbl, fill=edge,
                           font=('Consolas',8), justify=tk.CENTER)
        cv.create_line(L + pw, T, L + pw, T + ph, fill=C['cyan'], width=2)
        cv.create_line(L, T + ph, L + pw, T + ph, fill=C['text2'])
        cv.create_text(W - 12, T + ph/2, text='Collector Pressure [kPa]  =  MAP',
                       angle=90, fill=C['cyan'], font=('Consolas',9,'bold'))
        cv.create_text(L + pw/2, H - 10, text='RPM  (รอบเครื่องยนต์ต่อนาที)',
                       fill=C['text2'], font=('Consolas',9))
        cv.create_text(L + 6, T + 6, text='อากาศข้างนอก ≈ 100 kPa ↑', anchor='nw',
                       fill=C['text2'], font=('Consolas',7))
        cv.create_text(L + 6, T + ph - 6, text='แรงดูดมาก (สุญญากาศ) ↓', anchor='sw',
                       fill=C['text2'], font=('Consolas',7))

        # Diagnostics panel
        side = tk.Frame(body, bg=C['bg2'], padx=8, pady=6,
                        highlightthickness=1, highlightbackground=C['border'])
        side.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8,0))
        tk.Label(side, text='🩺 Diagnostics', font=('Consolas',10,'bold'),
                 bg=C['bg2'], fg=C['text']).pack(anchor='w')
        tk.Label(side, text='ช่วงปกติ = เครื่องร้อน เดินเบา', font=('Consolas',7),
                 bg=C['bg2'], fg=C['text2']).pack(anchor='w', pady=(0,4))
        diag = {}
        for key, en, th, unit, lo, hi in ACSTAG_DIAG_FIELDS:
            f = tk.Frame(side, bg=C['bg2']); f.pack(fill=tk.X, pady=2)
            tk.Label(f, text=en, font=('Consolas',9,'bold'), bg=C['bg2'],
                     fg=C['cyan'] if key == 'MAP_kPa' else C['text'], anchor='w').pack(anchor='w')
            r = tk.Frame(f, bg=C['bg2']); r.pack(fill=tk.X)
            v = tk.Label(r, text='---', font=('Consolas',13,'bold'), width=8,
                         bg=C['bg2'], fg=C['text2'], anchor='w')
            v.pack(side=tk.LEFT)
            tk.Label(r, text=f'{th}\nปกติ {lo:g}–{hi:g} {unit}', font=('Consolas',7),
                     bg=C['bg2'], fg=C['text2'], anchor='w', justify=tk.LEFT).pack(side=tk.LEFT)
            diag[key] = (v, unit, lo, hi)

        src = tk.Label(parent, text='', font=('Consolas',9,'bold'), bg=C['bg'], anchor='w')
        src.pack(fill=tk.X, padx=12, pady=(4,0))
        tk.Label(parent, font=('Consolas',8), bg=C['bg'], fg=C['text2'], anchor='w',
                 justify=tk.LEFT, wraplength=720,
                 text='วิธีอ่าน:  ● จุดสีฟ้า = สภาพเครื่องตอนนี้ ขยับตามเครื่องจริง  ·  เส้นประไปทางขวา → '
                      'อ่านค่าบนแกน Y ขวามือ = Collector Pressure  ·  เส้นประลงล่าง → RPM\n'
                      'จุดจางๆ = ทางที่เพิ่งผ่านมา  ·  เดินเบาจุดควรอยู่ในกรอบเขียว  ·  '
                      'ถ้าจุดค้างที่ 0 หรือ ~100 ตลอด = เซนเซอร์/ท่อยางสุญญากาศมีปัญหา'
                 ).pack(fill=tk.X, padx=12, pady=(0,6))

        trail = []
        t0 = time.time()

        def current():
            if demo_var.get():
                return demo_engine_state(time.time() - t0), 'demo'
            vals = {}
            for key, *_ in ACSTAG_DIAG_FIELDS:
                p = self.params.get(key)
                if p is not None and p.value is not None:
                    try: vals[key] = float(p.value)
                    except (TypeError, ValueError): pass
            if vals and self._live_on:
                return vals, 'acgas'
            return vals, ('live' if vals else 'none')

        def tick():
            if not win.winfo_exists():
                return
            vals, mode = current()
            if mode == 'demo':
                src.config(text='🟡 ตัวอย่างจำลอง — ดูว่าจุดขยับยังไง (ไม่ใช่ค่าจากรถ)', fg=C['yellow'])
            elif mode == 'acgas':
                fuel = FUEL_TH.get(self._live_fuel, '?')
                src.config(text=f'🟢 ข้อมูลสดจาก AcGasSynchro · ตอนนี้วิ่ง {fuel}  '
                                f'(จุดเขียว = แก๊ส · จุดน้ำเงิน = น้ำมัน)', fg=C['green'])
            elif mode == 'live':
                src.config(text=f'🟢 ข้อมูลสดจาก {self.port_var.get()} (โหมด AC STAG — ค่าเดา ใช้ AcGasSynchro ยืนยัน)',
                           fg=C['green'])
            else:
                src.config(text='⚪ ยังไม่มีข้อมูล — กด 📡 อ่านสด (แถวที่ 2) ขณะ AcGasSynchro เชื่อมต่อกล่องอยู่  '
                                '(หรือติ๊ก "ตัวอย่างจำลอง" เพื่อดูวิธีอ่าน)', fg=C['text2'])

            for key, (lbl, unit, lo, hi) in diag.items():
                if key in vals:
                    v = vals[key]
                    ok = lo <= v <= hi
                    lbl.config(text=f'{v:g} {unit}', fg=C['green'] if ok else C['yellow'])
                else:
                    lbl.config(text='---', fg=C['text2'])

            cv.delete('dyn')
            rpm, kpa = vals.get('RPM'), vals.get('MAP_kPa')
            if rpm is not None and kpa is not None:
                fuel = self._live_fuel if mode == 'acgas' else None
                dot = {'gas': C['green'], 'petrol': '#3b82f6'}.get(fuel, C['cyan'])
                trail.append((rpm, kpa, {'gas': '#1f5130', 'petrol': '#1e3a8a'}.get(fuel, '#1e4a6e')))
                del trail[:-40]
                n = len(trail)
                for i, (r_, k_, col) in enumerate(trail[:-1]):
                    s = 1 + 3 * i / n
                    cv.create_oval(X(r_)-s, Y(k_)-s, X(r_)+s, Y(k_)+s,
                                   fill=col, outline='', tags='dyn')
                x, y = X(rpm), Y(kpa)
                cv.create_line(x, y, L + pw, y, fill=C['cyan'], dash=(4,3), tags='dyn')
                cv.create_line(x, y, x, T + ph, fill=C['text2'], dash=(4,3), tags='dyn')
                cv.create_oval(x-7, y-7, x+7, y+7, outline=dot, width=2, tags='dyn')
                cv.create_oval(x-3, y-3, x+3, y+3, fill=dot, outline='', tags='dyn')
                cv.create_rectangle(L + pw + 2, y - 9, W - 24, y + 9,
                                    fill=C['cyan'], outline='', tags='dyn')
                cv.create_text(L + pw + 5, y, text=f'{kpa:.0f}', anchor='w',
                               fill='#0d1117', font=('Consolas',9,'bold'), tags='dyn')
                cv.create_text(x, T + ph + 24, text=f'{rpm:.0f} rpm',
                               fill=C['cyan'], font=('Consolas',8,'bold'), tags='dyn')
            elif rpm is None and kpa is None:
                cv.create_text(L + pw/2, T + ph/2, text='รอข้อมูล RPM + Collector pressure',
                               fill=C['text2'], font=('Consolas',10), tags='dyn')
            win.after(250, tick)

        tick()

    # ── Gas pressure graph (live from AcGasSynchro) ──────────────────────────

    def _pressure_verdict(self):
        """(text, colour) judging the gas pressure history."""
        hist = list(self._live_hist)
        if len(hist) < 10:
            return ('ทดสอบ: เดินเบา 30 วินาที → เร่งค้าง ~2,500–3,000 rpm ประมาณ 30 วินาที (ห้ามเกิน 3,000 ตอนจอด)',
                    C['text2'])
        idle = [g for _, g, r, f, _ in hist if g is not None and r is not None and r < 1000]
        load = [g for _, g, r, f, _ in hist if g is not None and r is not None and r >= 2000 and f == 'gas']
        cut = [e for e in self._live_events if e[2] == 'petrol']
        min_bar = self._min_bar.get()
        if not idle:
            return ('ยังไม่มีค่าตอนเดินเบา (รอบ < 1,000) — ปล่อยเดินเบาสักครู่เพื่อเก็บค่าตั้งต้น', C['text2'])
        base = statistics.median(idle)
        if not load:
            msg = f'ค่าตั้งต้นตอนเดินเบา {base:.2f} bar — ลองเร่งค้าง ~2,500–3,000 rpm ขณะวิ่งแก๊ส'
            if cut:
                msg += f'  ·  มีการตัดไปน้ำมัน {len(cut)} ครั้ง'
            return msg, C['text2']
        low = min(load)
        drop = (base - low) / base * 100 if base else 0
        low_cut = [e for e in cut if e[3] is not None and e[3] <= min_bar + 0.05]
        tail = (f'  ·  ตัดไปน้ำมัน {len(cut)} ครั้ง ({len(low_cut)} ครั้งตอนแรงดันใกล้ค่าต่ำสุด)'
                if cut else '')
        if drop >= 25:
            return (f'🔴 แรงดันตก {drop:.0f}% ตอนใช้แก๊สมาก ({base:.2f} → {low:.2f} bar) '
                    f'→ แก๊สไหลไม่ทัน: เช็คไส้กรองแก๊สก่อน แล้วค่อยโซลินอยด์/วาล์วถัง/หม้อต้ม{tail}', C['red'])
        if drop >= 10:
            return (f'🟡 แรงดันตก {drop:.0f}% ({base:.2f} → {low:.2f} bar) — เริ่มตก เฝ้าดูต่อ{tail}', C['yellow'])
        return f'🟢 แรงดันนิ่งดี ตก {drop:.0f}% ({base:.2f} → {low:.2f} bar){tail}', C['green']

    def _build_pressure_graph(self, parent, win):
        W, H = 820, 330
        L, R, T, B = 46, 56, 14, 30
        pw, ph = W - L - R, H - T - B
        BAR_MAX, RPM_MAX = 1.4, 7000

        top = tk.Frame(parent, bg=C['bg']); top.pack(fill=tk.X, padx=10, pady=(8,2))
        tk.Label(top, text='📉 แรงดันแก๊สตามเวลา (5 นาทีล่าสุด)', font=('Consolas',10,'bold'),
                 bg=C['bg'], fg=C['cyan']).pack(side=tk.LEFT)
        btn = tk.Button(top, command=self._toggle_acgas_live, relief=tk.FLAT,
                        font=('Consolas',9,'bold'), padx=10, pady=3, cursor='hand2', fg='white')
        btn.pack(side=tk.RIGHT, padx=(6,0))
        tk.Button(top, text='📂 ไฟล์บันทึก CSV', command=self._open_live_logs, relief=tk.FLAT,
                  bg=C['bg3'], fg=C['text'], font=('Consolas',9), padx=8, pady=3,
                  cursor='hand2').pack(side=tk.RIGHT, padx=(6,0))
        tk.Spinbox(top, from_=0.30, to=1.20, increment=0.05, textvariable=self._min_bar,
                   width=5, format='%.2f', font=('Consolas',9), bg=C['bg3'], fg=C['text'],
                   buttonbackground=C['bg3'], relief=tk.FLAT).pack(side=tk.RIGHT)
        tk.Label(top, text='ค่าต่ำสุดในกล่อง (bar):', bg=C['bg'], fg=C['text2'],
                 font=('Consolas',9)).pack(side=tk.RIGHT, padx=(10,4))

        cv = tk.Canvas(parent, width=W, height=H, bg='#090c0f', highlightthickness=1,
                       highlightbackground=C['border'])
        cv.pack(padx=10, pady=4, anchor='w')

        def Y(bar): return T + (1 - min(max(bar, 0), BAR_MAX) / BAR_MAX) * ph
        def YR(rpm): return T + (1 - min(max(rpm, 0), RPM_MAX) / RPM_MAX) * ph

        for i in range(0, 8):
            bar = i * 0.2
            cv.create_line(L, Y(bar), L + pw, Y(bar), fill='#1f262e')
            cv.create_text(L - 6, Y(bar), text=f'{bar:.1f}', anchor='e', fill=C['cyan'], font=('Consolas',8))
        for rpm in range(0, RPM_MAX + 1, 1000):
            cv.create_text(L + pw + 6, YR(rpm), text=f'{rpm // 1000}k', anchor='w',
                           fill='#f87171', font=('Consolas',8))
        cv.create_text(12, T + ph / 2, text='แรงดันแก๊ส [bar]', angle=90, fill=C['cyan'], font=('Consolas',9,'bold'))
        cv.create_text(W - 10, T + ph / 2, text='รอบ [rpm]', angle=90, fill='#f87171', font=('Consolas',9))
        cv.create_text(L + pw / 2, H - 10, text='เวลา →  (พื้นเขียว = วิ่งแก๊ส · พื้นน้ำเงิน = วิ่งน้ำมัน)',
                       fill=C['text2'], font=('Consolas',8))

        stats = tk.Frame(parent, bg=C['bg']); stats.pack(fill=tk.X, padx=12)
        cells = {}
        for key, title in [('now', 'ตอนนี้'), ('base', 'เดินเบา (ตั้งต้น)'), ('low', 'ต่ำสุดตอนวิ่งแก๊ส'),
                           ('cuts', 'ตัดไปน้ำมัน'), ('rows', 'บันทึกแล้ว')]:
            f = tk.Frame(stats, bg=C['bg2'], padx=10, pady=4); f.pack(side=tk.LEFT, padx=(0,6))
            tk.Label(f, text=title, bg=C['bg2'], fg=C['text2'], font=('Consolas',8)).pack(anchor='w')
            cells[key] = tk.Label(f, text='---', bg=C['bg2'], fg=C['text'], font=('Consolas',12,'bold'))
            cells[key].pack(anchor='w')
        verdict = tk.Label(parent, text='', font=('Consolas',9,'bold'), bg=C['bg'], anchor='w',
                           justify=tk.LEFT, wraplength=800)
        verdict.pack(fill=tk.X, padx=12, pady=(6,2))
        tk.Label(parent, text='เหตุการณ์สลับเชื้อเพลิง (ล่าสุดอยู่บน):', bg=C['bg'], fg=C['text2'],
                 font=('Consolas',8)).pack(anchor='w', padx=12)
        events = tk.Listbox(parent, height=5, bg=C['bg2'], fg=C['text'], font=('Consolas',9),
                            relief=tk.FLAT, highlightthickness=0)
        events.pack(fill=tk.X, padx=12, pady=(0,8))

        def tick():
            if not win.winfo_exists():
                return
            on = self._live_on
            btn.config(text='⏹ หยุดอ่านสด' if on else '📡 เริ่มอ่านสด',
                       bg='#b91c1c' if on else '#1d4ed8')
            cv.delete('dyn')
            hist = list(self._live_hist)
            n = len(hist)
            if n >= 2:
                dx = pw / (LIVE_HISTORY - 1)
                x0 = L + pw - (n - 1) * dx
                for i, (_, _, _, fuel, _) in enumerate(hist[:-1]):
                    cv.create_rectangle(x0 + i * dx, T, x0 + (i + 1) * dx + 1, T + ph, outline='',
                                        fill='#0f2a17' if fuel == 'gas' else '#10213f', tags='dyn')
                cv.tag_lower('dyn')
                rp = [c for i, h in enumerate(hist) if h[2] is not None for c in (x0 + i * dx, YR(h[2]))]
                gp = [c for i, h in enumerate(hist) if h[1] is not None for c in (x0 + i * dx, Y(h[1]))]
                if len(rp) >= 4:
                    cv.create_line(*rp, fill='#ef4444', width=1, tags=('dyn', 'data'))
                if len(gp) >= 4:
                    cv.create_line(*gp, fill=C['cyan'], width=3, tags=('dyn', 'data'))
            try:
                mb = float(self._min_bar.get())
                cv.create_line(L, Y(mb), L + pw, Y(mb), fill=C['red'], dash=(6,3), tags='dyn')
                cv.create_text(L + 4, Y(mb) - 8, text=f'ค่าต่ำสุดในกล่อง {mb:.2f} bar (ใส่ค่าจริงจากหน้า ตั้งค่า ECU)',
                               anchor='w', fill=C['red'], font=('Consolas',8), tags='dyn')
            except (tk.TclError, ValueError):
                pass
            cv.tag_raise('data')
            if not hist:
                cv.create_text(L + pw / 2, T + ph / 2, tags='dyn', fill=C['text2'], font=('Consolas',10),
                               text='กด 📡 เริ่มอ่านสด (AcGasSynchro ต้องเปิดและเชื่อมต่อกล่องอยู่)')

            gases = [h[1] for h in hist if h[1] is not None]
            idle = [h[1] for h in hist if h[1] is not None and h[2] is not None and h[2] < 1000]
            load = [h[1] for h in hist if h[1] is not None and h[3] == 'gas' and (h[2] or 0) >= 2000]
            cells['now'].config(text=f'{gases[-1]:.2f} bar' if gases else '---',
                                fg=C['green'] if self._live_fuel == 'gas' else '#60a5fa')
            cells['base'].config(text=f'{statistics.median(idle):.2f} bar' if idle else '---')
            cells['low'].config(text=f'{min(load):.2f} bar' if load else '---')
            cuts = sum(1 for e in self._live_events if e[2] == 'petrol')
            cells['cuts'].config(text=f'{cuts} ครั้ง', fg=C['red'] if cuts else C['text'])
            cells['rows'].config(text=f'{self._live_rows} แถว')
            text, colour = self._pressure_verdict()
            verdict.config(text=text, fg=colour)

            events.delete(0, tk.END)
            for t, a, b, g, r in reversed(self._live_events[-20:]):
                events.insert(tk.END, f'{t:%H:%M:%S}   {FUEL_TH[a]} → {FUEL_TH[b]}   '
                                      f'แรงดันแก๊ส {g:.2f} bar   รอบ {r:.0f}')
            win.after(500, tick)

        tick()

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _log(self, text, tag='ok'):
        self._term.config(state=tk.NORMAL)
        self._term.insert(tk.END, text + '\n', tag)
        self._term.see(tk.END)
        lines = int(self._term.index('end-1c').split('.')[0])
        if lines > 4000:
            self._term.delete('1.0', f'{lines-4000}.0')
        self._term.config(state=tk.DISABLED)

    def _clear_term(self):
        self._term.config(state=tk.NORMAL)
        self._term.delete('1.0', tk.END)
        self._term.config(state=tk.DISABLED)

    def _set_status(self, text, color=None):
        self.status_var.set(text)
        if color: self._dot.config(fg=color)

    def _export_csv(self):
        if not self.params:
            messagebox.showinfo('Export', 'ยังไม่มีข้อมูล'); return
        path = filedialog.asksaveasfilename(
            defaultextension='.csv',
            filetypes=[('CSV files', '*.csv')],
            initialfile=f'gas_{datetime.now():%Y%m%d_%H%M%S}.csv',
            initialdir='F:/LocalAI/gas_monitor')
        if not path: return
        with open(path, 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.writer(f)
            w.writerow(['เวลา', 'พารามิเตอร์', 'ชื่อไทย', 'ค่า', 'หน่วย',
                        'สถานะ', 'เฝ้าระวัง', 'อันตราย', 'วิกฤต'])
            ts = datetime.now().isoformat()
            for name, p in self.params.items():
                w.writerow([ts, name, p.label, p.value, p.unit,
                            p.status(), p.warn, p.danger, p.crit])
        self._log(f'💾 Export → {path}', 'info')
        messagebox.showinfo('Export', f'บันทึก CSV แล้ว:\n{path}')

    def _create_shortcut(self):
        try:
            profile  = Path(os.environ.get('USERPROFILE', Path.home()))
            od_desk  = profile / 'OneDrive' / 'Desktop'
            desktop  = od_desk if od_desk.exists() else profile / 'Desktop'
            script   = Path(__file__).resolve()
            ico      = script.parent / 'gas_icon.ico'
            link     = desktop / 'GAS Monitor.lnk'
            import subprocess, sys
            ps = (
                f'$ws=New-Object -ComObject WScript.Shell;'
                f'$l=$ws.CreateShortcut("{link}");'
                f'$l.TargetPath="{sys.executable}";'
                f'$l.Arguments=\'\\"{script}\\"\';'
                f'$l.WorkingDirectory="{script.parent}";'
                f'$l.IconLocation="{ico},0";'
                f'$l.Description="GAS Monitor v{VERSION} - ลุงพี";'
                f'$l.Save()'
            )
            subprocess.run(['powershell', '-Command', ps], capture_output=True)
            if link.exists():
                messagebox.showinfo('✅ Shortcut',
                    f'อัปเดต Desktop Shortcut แล้ว!\n{link}')
                self._log(f'📌 Shortcut → {link}', 'info')
            else:
                messagebox.showwarning('Shortcut',
                    f'ลองตรวจสอบด้วยตนเอง:\n{link}')
        except Exception as e:
            messagebox.showerror('Error', str(e))

    def run(self):
        self.root.mainloop()


if __name__ == '__main__':
    GasMonitorApp().run()
