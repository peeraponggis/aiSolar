ชุดสร้างไฟล์อุปกรณ์สำหรับนำเข้า ASC Studio (Auto Solar Co-pilot Studio) · เวอร์ชัน 3.4 · 5 พ.ย. 2569
====================================================================================

ไฟล์ในโฟลเดอร์นี้
  PROMPT_PV.txt       + PV_MODULE_STRUCTURE.txt     แผงโซลาร์เซลล์
  PROMPT_INV.txt      + INVERTER_STRUCTURE.txt      อินเวอร์เตอร์ (String/Hybrid/Off-grid/Micro/Central)
  PROMPT_BAT.txt      + BATTERY_ESS_STRUCTURE.txt   แบตเตอรี่ / ESS
  PROMPT_OPT.txt      + OPTIMIZER_STRUCTURE.txt     ออปติไมเซอร์ / RSD
  PROMPT_EV.txt       + EV_CHARGE_STRUCTURE.txt     เครื่องชาร์จรถยนต์ไฟฟ้า
  createdtatsheet.txt                               prompt ฉบับรวมทุกชนิด (เอกสารเดียวมีหลายชนิด แนบแม่แบบทั้ง 5)
  PROMPT_MANUAL.txt                                 คู่มือผู้ใช้ (PDF) → <series>.manual.json
                                                    (เบรกเกอร์/RCD/สาย/ค่าตั้งการไฟฟ้า/มิเตอร์ CT/ขนาน)

วิธีใช้ (datasheet)
  1. เปิด AI ที่อ่าน PDF ได้ (Claude / ChatGPT / Gemini) วางข้อความทั้งหมดของ PROMPT_<ชนิด>.txt
  2. แนบแม่แบบของชนิดนั้น + datasheet PDF
  3. ได้ไฟล์ .txt (หรือ ZIP) → ASC Studio เมนู นำเข้าไฟล์ (เลือกหลายไฟล์พร้อมกันได้)
  4. อ่าน "ต้องกรอกเองในโปรแกรมก่อนใช้งาน" ในคำตอบของ AI แล้วแก้ค่าในคลังอุปกรณ์

ตรวจไฟล์ก่อนนำเข้า (ถ้ามี Node.js):  node _src/check-datasheet.mjs <ไฟล์.txt>

ที่เปลี่ยนจาก 3.1 (ฉบับเดิมเก็บไว้ที่ _old_v3.1)
  - แม่แบบเป็นโครงสร้างล่าสุดที่โปรแกรมอ่าน (INV 3.2 + Derating_Curve_C_kW · BAT 3.2 · EV 3.3)
    ฉบับ 3.1 เดิมขาดฟิลด์ที่โปรแกรมใช้ 70 ค่า (ดู _test_3.4\ผลทดสอบ_และตารางเทียบ.txt)
  - ไม่มีข้อมูล = เว้นว่าง + ; [ไม่มีข้อมูล] (ไม่คงค่าเริ่มต้นของแม่แบบ ซึ่งหลายค่าไม่ใช่ศูนย์)
  - ทุกค่ามีที่มา ; [SRC: หน้า · ตาราง · ข้อความต้นฉบับ]
  - ค่าข้อความที่โปรแกรมอ่านแบบเจาะจงมีรายการให้สะกดตาม (ข้อ 11 ในแต่ละ prompt)
  - แยก prompt ตามชนิดอุปกรณ์

ไฟล์ 3.1/3.2/3.3 เดิมยังนำเข้าได้ตามปกติ

แก้เนื้อหา prompt: แก้ไฟล์ใน _src (common.txt + kind_*.txt) แล้วรัน  node _src/build-prompts.mjs
_test_3.4  = ไฟล์ตัวอย่างที่สร้างด้วย prompt 3.4 จาก datasheet จริง + ผลนำเข้า ASC Studio 0.157.0
