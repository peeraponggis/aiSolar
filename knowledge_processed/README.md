# ความรู้ (Knowledge Base) - สรุปสำหรับ AI Model Training

## Overview
- **แหล่งข้อมูล**: D:\LocalAI\knowledge\
- **วันที่ประมวล**: 2026-09-19
- **หมวดหมู่**: PEA, MEA, EIT, ตัวอย่าง

## สถิติรวม
| หมวดหมู่ | ประเภท | จำนวน | หน้า/รายการ |
|----------|--------|-------|-------------|
| PEA | PDF | 11 | 98+11+4+2+35+11+34+5+1+4+11 = 216 หน้า |
| PEA | CSV | 1 | 887 แถว, 11 คอลัมน์ |
| MEA | PDF | 14 | ~276 หน้า (ประมาณ) |
| EIT | PDF | 1 | 378 หน้า |
| EIT | JPG | 148 | หน้าเอกสารสแกน |
| ตัวอย่าง | TXT | 1 | 1 บรรทัด |
| **รวม** | | **175** | **~970+ หน้า/ข้อมูล** |

## ประเภทข้อมูลสำคัญ
### 1. อัตราค่าไฟฟ้า (Electricity Tariff)
- อัตราปกติสำหรับบ้านเรือน: 8.19 บาท/หน่วย (เริ่มต้น)
- อัตรา TOU: มีประกาศ (เป็นภาพสแกน)
- อัตรา PEA MAY 2023: มีเอกสาร 11 หน้า

### 2. ค่า Ft ส่วนต่าง
- Sep-Dec 2569: 16.23 สตางค์/หน่วย
- ค่า Ft จริง: 94.82 สตางค์/หน่วย
- กฟผ. รับภาระ: 16,127.17 ล้านบาท

### 3. FiT/ViT
- ปี 2569: มีเอกสาร (เป็นภาพสแกน)

### 4. ระบบ Codes (PEA)
- Connection Code: 98 หน้า (2016-2017)
- Operation Code: 35 หน้า (2016)
- Service Code: 34 หน้า (2016)
- รวม: ~167 หน้า

### 5. ทะเบียนอินเวอร์เตอร์
- PEA: 887 รุ่น (PEA_inverter_registry.csv)
- MEA/PEA: ครั้งที่ 5 ปี 2565 (PDF 12 หน้า)
- ยี่ห้อหลัก: SINENG, SMA, solis, ฯลฯ
- รับรอง: 24 ต.ค. 2566 - หมดอายุ 24 ต.ค. 2569

### 6. เอกสาร EIT ปี 2564
- PDF: 378 หน้า
- JPG: 148 หน้า (สแกน)
- 5 บท + ภาคผนวก ก-ฐ
- คาดการณ์: รายงาน/ข้อกำหนด EIT

### 7. PVsyst Knowledge Base (ใหม่)
- **ที่มา**: 41 หัวข้อจาก Facebook + PVsyst Official Documentation + Tutorial PDFs
- **ไฟล์**: `PVsyst_Knowledge_Base.md`
- **Tutorials**: `PVsyst_Tutorials/` (3 PDF, ~16.8 MB, สกัดข้อความแล้ว)
- **สรุป**: `PVsyst_Tutorial_Summaries.md`
- **Topics**: Version 8 features, Loss analysis, Shading, P50/P90, Financial metrics, .PAN file, Design guidelines

## ไฟล์ที่สร้างขึ้น
### Text Files (สกัดจาก PDF)
- PEA_*.txt: 11 ไฟล์ (ข้อความจาก PDF)
- MEA_*.txt: 14 ไฟล์ (ข้อความจาก PDF)
- eit2564_eit2564.txt: 1 ไฟล์
- PEA_inverter_registry_summary.txt: 1 ไฟล์ (CSV summary)
- PVPMC_2025_PVsyst_Updates.txt: 1 ไฟล์ (PVsyst presentation)

### PVsyst Tutorials (Text extracted from official PDFs)
- pvsyst_tutorial_grid.txt: 123 KB (Grid Connected, ~300 pages)
- pvsyst_tutorial_components.txt: 14 KB (PAN/OND database, 13 pages)
- pvsyst_tutorial_v81.txt: 239 KB (v8.1 comprehensive, ~300 pages)

### Image Index
- eit_image_index.json: 148 รายการ
- eit2564_image_index.json: 0 รายการ (PDF)

### Summary Files
- PEA_สรุป.md: สรุป PEA
- MEA_สรุป.md: สรุป MEA
- EIT_สรุป.md: สรุป EIT
- PVsyst_Knowledge_Base.md: สรุป PVsyst 41 topics
- PVsyst_Tutorial_Summaries.md: สรุป PVsyst tutorials
- knowledge_dataset.txt: Dataset รวมทุกหมวด

### Data Files
- all_pdf_extracted.json: metadata PDF ทั้งหมด
- csv_summaries.json: metadata CSV

## คำแนะนำสำหรับ AI Model
1. **อ่าน PEA_สรุป.md, MEA_สรุป.md, EIT_สรุป.md** ก่อน - เป็นสรุปข้อมูลสำคัญ
2. **อ่าน PVsyst_Knowledge_Base.md** - สำหรับ PVsyst design/simulation knowledge (41 topics)
3. **อ่าน individual .txt files** สำหรับรายละเอียดเฉพาะเรื่อง
4. **อ่าน PVsyst_Tutorial_Summaries.md** - สำหรับ tutorial content
5. **อ่าน PEA_inverter_registry.csv** สำหรับข้อมูลอินเวอร์เตอร์ (887 รุ่น)
6. **หมายเหตุ**: ไฟล์บางส่วนเป็น PDF ภาพสแกน (FiTv_2569, TOU, Solar ประกาศ) - ต้อง OCR
7. **ไฟล์ซ้ำ**: file_8ystbb33.pdf ≈ file_8ystbb33 (1).pdf

## หมวดหมู่คำถามที่ AI สามารถตอบได้
- อัตราค่าไฟฟ้า (Tariff rates)
- ค่า Ft ส่วนต่าง (Ft surcharge)
- FiT/ViT อัตรา
- รหัส PEA (Connection/Operation/Service)
- ทะเบียนอินเวอร์เตอร์
- เอกสาร EIT/MEA/PEA
- ข้อกำหนด Solar ภาคประชาชน
- การร้องขอแก้ไขระบบจำหน่าย
- PVsyst simulation (losses, shading, orientations)
- PVsyst financial analysis (LCOE, ROI, NPV, IRR, PBP)
- PVsyst P50/P90 evaluation
- PVsyst .PAN/.OND file creation
- PVsyst tutorial content (grid, components, v8.1)
