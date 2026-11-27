# แผน: ชุด .bat ช่วยงานปล่อยรุ่น / ติดตั้ง / รัน SQL / ดึงข้อมูลจาก home server

สถานะ: **เสนอให้ลุงพีตรวจก่อนสร้าง (7 พ.ย. 2569)** · โฟลเดอร์ `F:\LocalAI\setup_prg\ASC\`
หลักการ: ทุก bat เป็น**เมนูถามก่อนทำ** (กด 1-9) · ไม่ commit/push/deploy เองโดยไม่ถาม · ไม่ใส่คีย์ลับในไฟล์ · log ลง `logs\<วันที่>.txt`

## โครงไฟล์

```
F:\LocalAI\setup_prg\ASC\
  00-เมนูหลัก.bat            เมนูรวม เลือกโปรแกรม → เรียก bat ย่อย
  01-ASCS-ปล่อยรุ่น.bat      ASC Studio: ตรวจค้าง → build → ชุดติดตั้ง+ชุดอัปเดต → เว็บ → SQL
  02-ASCA-ปล่อยรุ่น.bat      ASC Architect: ชุดติดตั้ง Inno + ชุดอัปเดต + เว็บ
  03-ASC-Cloud-deploy.bat    push repo asc + รอ GitHub Pages + ตรวจเว็บจริง
  04-CRM-Pi-deploy.bat       build_pages → wrangler deploy (laptop เท่านั้น) + รายการ SQL
  05-Translator-build.bat    PyInstaller → zip ชุดติดตั้ง
  06-SQL-ที่ต้องรัน.bat       รวมไฟล์ SQL ที่ต้องรัน เปิด SQL Editor ให้ + คัดลอกเนื้อหาเข้า clipboard
  07-Home-ดึงข้อมูล.bat      SSH/sftp จาก home: out · HomeGuard · laptop-data · ตรวจรุ่นบน home
  08-ติดตั้งเครื่องใหม่.bat   ติดตั้ง ASCS/ASCA/Translator บนเครื่องอื่น (มี/ไม่มี git)
  lib\common.cmd              ฟังก์ชันร่วม: log · ถามยืนยัน · ตรวจ path · เปิดลิงก์
  README.md                   คู่มือ + ขั้นตอนติดตั้งทุกโปรแกรม (ภาษาไทย)
  logs\
```

## รายละเอียดแต่ละ bat

### 01 ASCS ปล่อยรุ่น (เมนูย่อย)
1. ตรวจก่อน: `git status` ทั้ง asc_auto + asc · โค้ดค้าง · รุ่นใน VERSION.json
2. build: `npm run kb:build` → `typecheck` → `test` → `build` (หยุดถ้าไม่ผ่าน)
3. ชุดติดตั้ง + ชุดอัปเดต: `installer\build-setup.ps1` → แสดง path exe + ascs-release
4. เว็บ: `build-cloud.mjs --to asc\docs\studio` + ใส่หัวลิขสิทธิ์ + `kb:sql`
5. สแกนคีย์ลับใน repo asc (sk- · AIza · ghp_ · service_role · กุญแจ password.txt)
6. **ถามยืนยัน** → commit+push asc_auto · commit+push asc · `gh run watch` · curl ตรวจ latest.json/เวอร์ชัน
7. SQL: แสดงรายการ + เปิด SQL Editor (ต่อข้อ 06)
8. อัปเดต PROGRAMS.md + push aiSolar
- ไม่ทำ: bump เวอร์ชัน (ให้ Claude ทำตามกฎ) · ไม่แตะ `out\usermanual\_pdfs.json` · `sync-home-gui.ps1`

### 02 ASCA ปล่อยรุ่น
1. ตรวจ git + VERSION.json
2. `scripts\build_installer.py` (Inno Setup · รหัสจาก `apps\ASCA-release\password.txt`) → `ASCA-Setup-<v>.exe` + `asca-release`
3. `scripts\build_cloud.py --to asc\docs\architec`
4. ถามยืนยัน → push pee_architec (private) + ต่อข้อ 03

### 03 ASC Cloud deploy
- สแกนคีย์ลับ → ถามยืนยัน → commit+push → `gh run watch` → ตรวจ URL (studio · architec · ascs-release · asca-release) → เตือนถ้า `sw.js` SHELL เปลี่ยนแต่ไม่ bump VERSION

### 04 CRM-Pi deploy
- `node pi_crm_erp/scripts/build_pages.mjs` → ตรวจคีย์ใน dist_pages → ถามยืนยัน → `npx wrangler pages deploy dist_pages --project-name pi-system --branch production` → เปิด pi-system.pages.dev
- รายการ SQL: `pi_system_full_install.sql` → `20261031_asc_studio.sql` → `20261031_admin_users.sql` (+ ไฟล์ YYYYMMDD ใหม่กว่า install ล่าสุด)

### 05 Local Translator build
- `pyinstaller LocalTranslator.spec` → zip `dist\LocalTranslator` เป็น `LocalTranslator-setup-<v>.zip` (ตอนนี้ zip เก่ากว่ารุ่นจริง) · ไม่มีระบบอัปเดต = ติดตั้งทับ

### 06 SQL ที่ต้องรัน (ใช้บ่อยสุด)
เมนูเลือก project → แสดง**ลำดับ** + path เต็ม → กดเลข = คัดลอกเนื้อหาไฟล์เข้า clipboard + เปิด SQL Editor ในเบราว์เซอร์ → ลุงพีวาง + Run
- ASC Cloud (`rcaslesvgilknupqmwrp`): ครั้งแรก schema → kb → ascs-studio → ascs-release → ai-install … · **ทุกรุ่น**: `kb-data.sql` · `ascs-release-key.sql` (ถ้าเปลี่ยนกุญแจ) · `standards-data.sql` (ถ้าตารางเปลี่ยน)
- CRM-Pi (`zloxphgxhttrtgqlafsz`): ตามข้อ 04
- บันทึกว่าไฟล์ไหนรันแล้วเมื่อไหร่ (`logs\sql-done.txt` เทียบ hash ไฟล์) → ครั้งต่อไปขึ้นเฉพาะที่ยังไม่ได้รัน/เปลี่ยน

### 07 Home server
- ใช้ `Host home` ใน ssh config ที่มีอยู่ · ตรวจ `ssh home echo ok` ก่อน
- เมนู: ① ดูรุ่นโปรแกรมบน home (VERSION.json ของ ASCS/ASCA/picode) ② ดึง `design-auto\out` (เรียก `sync-home.ps1 -Direction Pull`) ③ ดึง HomeGuard live copy ④ ส่ง laptop-data ⑤ สั่ง home `pull-home.ps1` (git pull + build) ⑥ เปิด Remote Control
- ไม่ดึง `server\data` · AMR · cctv (ข้อมูลลูกค้า) นอกจากเลือกเอง

### 08 ติดตั้งเครื่องใหม่
- ASCS: มี git → `git clone` + `install.bat` · ไม่มี → เปิด `ASC-Studio-Setup-<v>.exe` ล่าสุดจาก `out\setup`
- ASCA: `ASCA-Setup-<v>.exe` (รหัสจาก password.txt — แสดงแค่ path ไม่พิมพ์รหัส)
- Translator: `Install-LocalTranslator.bat`
- ตรวจก่อน: Python 3.12 · Node · git · Ollama · Tailscale · แล้วสรุปว่าขาดอะไร

## README.md จะมี
ขั้นตอนติดตั้งทีละโปรแกรม (ASC Cloud · ASCS · ASCA · CRM-Pi · Local Translator) · พอร์ต · ที่เก็บกุญแจ · ลำดับ SQL · วิธีอัปเดต · วิธีดึงจาก home · ปัญหาที่เจอบ่อย

## ต้องให้ลุงพีตัดสินใจ
1. ชื่อไฟล์ภาษาไทยหรืออังกฤษ (ไทยอ่านง่าย แต่บาง shell เพี้ยน → เสนอ **อังกฤษ + หน้าเมนูเป็นไทย**)
2. bat ควร commit/push ให้เองหลังถามยืนยัน หรือแค่เตรียมแล้วให้ Claude/ลุงพีสั่ง push
3. bat ปล่อยรุ่นควร bump เวอร์ชันเองหรือไม่ (เสนอ: ไม่ — Claude bump ตามกฎ "โดย ลุงพี")
4. โฟลเดอร์ setup_prg ขึ้น git aiSolar ไหม (ไม่มีคีย์ในไฟล์ จึงขึ้นได้)
