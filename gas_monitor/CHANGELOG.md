# GAS Monitor — CHANGELOG โดย ลุงพี

## v2.4.0 — 2026-10-27
- อ่านค่าสดจากหน้าต่าง AcGasSynchro (acgas_reader.py) ทุก 0.5 วินาที — ไม่ยุ่งกับกล่อง ECU เลย
  - จับภาพหน้าต่างด้วย PrintWindow (มีหน้าต่างอื่นทับได้ ห้ามย่อ) แล้วอ่านตัวเลขสีกรมท่าในแผงขวาด้วย template (acgas_digits.json)
  - ได้: แรงดันแก๊ส, MAP, เวลาฉีดน้ำมัน/แก๊ส 6 สูบ, อุณหภูมิแก๊ส/หม้อต้ม, Lambda 1-2, แบตเตอรี่, รอบ, สถานะ แก๊ส/น้ำมัน
  - ทดสอบกับภาพจริง 4 ภาพ: ภาพที่ไม่ได้ใช้สร้าง template ถูก 50/50 ค่า, รวมทั้งหมด 100/100
- ปุ่ม 📡 อ่านสด (แถว 2): เริ่ม/หยุด, ปล่อย COM port ให้ AcGasSynchro เอง, บันทึก CSV ที่ logs/acgas_<เวลา>.csv
- การ์ดพารามิเตอร์แบบ "ช่วงปกติ" (ปกติ / นอกช่วง + คำแนะนำ) แทนเกณฑ์ก๊าซรั่วสำหรับค่าของรถ
- Tuning Map ใช้ค่าสด: จุดเขียว = วิ่งแก๊ส, จุดน้ำเงิน = วิ่งน้ำมัน
- แท็บใหม่ 📉 แรงดันแก๊ส: กราฟแรงดันแก๊ส + รอบ 5 นาที, พื้นเขียว/น้ำเงินตามเชื้อเพลิง, เส้นค่าต่ำสุดในกล่อง (ปรับได้),
  ค่าตั้งต้นตอนเดินเบา / ต่ำสุดตอนวิ่งแก๊ส / % ที่ตก, สรุปผล และรายการเหตุการณ์ แก๊ส ↔ น้ำมัน พร้อมแรงดันและรอบ ณ ตอนนั้น
- แถว 2 จัดใหม่: ▶ AcGasSynchro · 📡 อ่านสด · 📈 Map · 📉 แรงดันแก๊ส · 🔧 วิเคราะห์ · 📚 ศัพท์

## v2.3.1 — 2026-10-27
- แก้รุ่นกล่องเป็น STAG-300-6 ISA2 เฟิร์มแวร์ 10.0 (อ่านจริงจาก AcGasSynchro — เดิมเข้าใจผิดว่าเป็น STAG-4 Plus)
- ปุ่มผังสายไฟเปลี่ยนเป็นของ STAG-300 ISA2, คู่มือชี้ไปโฟลเดอร์ ISA2
- เพิ่มปุ่ม 📋 คำอธิบายสายแต่ละเส้น (STAG-300 leads description)
- ศัพท์ช่าง ECU / Emulator อ้างรุ่น ISA2

## v2.3.0 — 2026-10-27
- ผนวก AcGasSynchro 11.2.1.1 (โปรแกรมทางการ AC STAG ติดตั้งที่ F:\Programs\AcGasSynchro)
  - ปุ่ม ▶ เปิด AcGasSynchro: ปล่อย COM6 ให้อัตโนมัติ, กันเปิดซ้ำ, ถ้ายังไม่ติดตั้งจะเสนอติดตั้งจากไฟล์ที่ดาวน์โหลดไว้
  - ปุ่ม 📖 คู่มือ STAG-4 (PDF ภาษาอังกฤษ) และผังสายไฟ STAG-4 Plus ในแท็บดาวน์โหลด
  - แท็บดาวน์โหลดแสดงสถานะ "ติดตั้งแล้ว" + ขั้นตอนใหม่ (Autosearch หา ECU เอง)
- Auto-Scan ได้ 0 bytes ทุก baud → อธิบายสาเหตุใน terminal และแนะนำให้ใช้ AcGasSynchro

## v2.2.0 — 2026-10-27
- เพิ่มแท็บ 📚 ศัพท์ช่าง ใน AC STAG dialog: 18 คำ อธิบายภาษาชาวบ้าน พร้อมค่าปกติ และช่องค้นหา
- เพิ่มปุ่ม 📚 ศัพท์ช่าง บน toolbar (เปิดตรงแท็บศัพท์)
- แก้แท็บ "วิธีอ่านค่า": แยก Collector pressure (MAP) / Gas pressure / Reducer temperature ชัดเจน + ขั้นตอนทดสอบ 5 นาที
- แก้แท็บ "ตัดสินใจ": ตัดสินหม้อต้มจาก Gas pressure + Reducer temperature (เดิมใช้ MAP ซึ่งไม่ถูก) เรียงลำดับเช็คจากถูกไปแพง
- ลิงก์ดาวน์โหลดคลิกเปิดเบราว์เซอร์ได้, ทุกแท็บเลื่อนด้วยล้อเมาส์ได้
- เพิ่มแท็บ 📈 Tuning Map: กราฟ RPM × Collector Pressure (แกน Y ขวามือ = MAP) แบบหน้าหลัก AcGasSynchro
  - จุด cursor ขยับตามค่าสด + เส้นประชี้ค่าบนแกน Y + ทางที่ผ่านมา (trail)
  - กรอบโซน: เดินเบาปกติ / ถอนคันเร่ง (engine braking) / เหยียบคันเร่งสุด
  - แผง Diagnostics: Collector pressure, Gas pressure, Reducer temp, Gas temp, RPM, Injection time (สีเขียว = อยู่ในช่วงปกติ)
  - ติ๊ก "ตัวอย่างจำลอง" เพื่อดูการขยับของจุด (ระบุชัดว่าไม่ใช่ค่าจริง)
- แก้ toolbar: ป้าย Port/Baud/Protocol เคยอยู่ผิดช่อง (ป้ายตามหลังกล่อง) และกล่องถูกบีบหาย → จัดใหม่เป็น 2 แถว
- ตารางค่า MAP ตามการขับ: แก้ "เบรก" เป็น "ถอนคันเร่งขณะรถวิ่ง (engine braking)"

## v2.1.0 — 2026-10-27
- เพิ่มปุ่ม 📡 AC STAG บน toolbar
- เพิ่ม Protocol "AC STAG" (baud อัตโนมัติ 9600, binary frame capture)
- เพิ่ม dialog 3 แท็บ: ดาวน์โหลด AcGasSynchro / วิธีอ่านค่า MAP / ตัดสินใจ
  - AcGasSynchro-11.2.1.1 รองรับ STAG-4 Plus, STAG-300 ISA2/Premium
  - แหล่งดาวน์โหลด: ccy.pl/en/download-left/category/438-ac-stag และ mystag.pl/download/
  - ตารางค่า MAP pressure ที่ดี/น่ากังวล
  - เกณฑ์ตัดสินใจเปลี่ยนหม้อต้ม
- เพิ่มฟังก์ชัน parse_acstag_stream() และ acstag_annotate_frame() (heuristic decode)

## v2.0.0 — ก่อนหน้า
- GUI เต็มรูปแบบ: parameter cards, color-coded alerts
- Protocol parsers: Auto, JSON, CSV, Key=Value, Modbus RTU, HEX
- Auto-Tune + Manual Threshold settings
- Car Gas Diagnostics dialog (8 สาเหตุ+วิธีแก้)
- Export CSV, Desktop Shortcut
