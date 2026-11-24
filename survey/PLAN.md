# Survey (Pee_survey.html) — แผนงานที่พักไว้

บันทึก 24 พ.ย. 2569 · ลุงพีสั่ง "ทำเฉพาะไอคอนแท็บ งานนอกนั้นบันทึกแผนไว้ก่อน"

## สถานะตอนนี้
- เว็บจริง: https://peeraponggis.github.io/aisolar2/Pee_survey.html = เวอร์ชัน 4.14.1 (ขึ้นเว็บ 24 พ.ย. 2569 commit 6b16275 · repo peeraponggis/aisolar2 ไฟล์อยู่ root)
- ต้นฉบับ: `F:\LocalAI\survey\Pee_survey.html` (= `Pee_survey_preview.html`) · สำรอง `Pee_survey_4.2.0_backup.html`, `Pee_survey_4.3.0_backup.html`, `Pee_survey_4.4.0_backup.html`, `Pee_survey_4.5.0_backup.html`, `Pee_survey_4.6.0_backup.html`, `Pee_survey_4.7.0_backup.html`, `Pee_survey_4.8.0_backup.html`, `Pee_survey_4.9.0_backup.html`, `Pee_survey_4.10.0_backup.html`, `Pee_survey_4.11.0_backup.html`
- 4.4.0 มี: ปุ่มเสาไฟฟ้า 12 ม. / เสา+หม้อแปลง / ตู้ MDB (properties.kind = pole | pole_tx | mdb, ต้นไม้ = tree) · แก้บัควาดต้นไม้ค้าง · ระยะด้าน/ตัวเลขขนาดแสดงเฉพาะวัตถุที่เลือก
- 4.6.0: คลิกเลือกวัตถุแล้วลากย้ายได้ทันทีทุกชนิด (Polygon เติมจางตอนเลือก · เส้นหนาขึ้น · ด้าน < 40 px ไม่แสดงป้ายระยะ) · ป้ายล็อกย้ายตาม · Undo ได้
- 4.7.0: หมุนตามองศาที่กรอก (หมุนเพิ่ม + = ตามเข็ม · ตั้งแนวแกนยาวจากทิศเหนือ) · Undo 1 ครั้งต่อการแก้ 1 ครั้ง
- 4.12.0: PDF ภาพแผนที่สี (PNG แทน JPEG) ลดขนาด 50% · รูปวัตถุเพิ่ม 50% (34→51mm) · crop วัตถุ PNG คงสี
- 4.12.1: Map full-width when printing PDF (@media print)
- 4.13.0 (c4b65f4): แก้ป้ายกำกับกระโดดตอนซูม — avoidLabelCollisions ใช้ CSS pixel offset แทน lat/lng conversion
- 4.13.1 (c59b38c): แก้ป้ายเลื่อนเมื่อติ๊กออก checkbox — ข้าม hidden layers ใน avoidLabelCollisions + เรียก avoidLabelCollisions หลัง applyCategoryFilter/refreshAllLabels
- 4.14.0 (f468576): แก้ป้ายเลื่อนผิดตำแหน่งเมื่อ pan แผนที่ — เพิ่ม moveend listener ให้คำนวณหลบชนใหม่ทุกครั้ง
- 4.14.1 (6b16275): แก้ป้ายเลื่อนตอน pan จริง — ใช้ setLatLng แทน CSS margin (เริ่มจาก defaultLatLng ทุกครั้ง ไม่สะสม drift)
- 4.11.0: รายงาน PDF แสดงหน้ารายละเอียดเฉพาะวัตถุที่มีรูปภาพ (วัตถุไม่มีรูปไม่แสดง)
- 4.10.0: ผู้สำรวจ + วันที่สำรวจ (วันที่ไทย) · ตัวกรองประเภทวัตถุ 7 ช่อง (Polygon/Line/Marker/เสาไฟฟ้า/เสา+หม้อแปลง/ตู้ MDB/ต้นไม้) · ตารางสรุป+PDF กรองตามประเภทที่เลือก
- 4.9.0: เลือกข้อมูลบนป้ายกำกับ 6 ช่อง (ชื่อ/พื้นที่/ขนาด/ความสูง/พิกัด/ชนิดอุปกรณ์) · PDF ตามที่เลือก · ภาพรวมพื้นที่เต็มหน้า A4 · รูปวัตถุลด 50%
- 4.8.0: คัดลอก/วาง/ทำซ้ำ (Ctrl+C/V/D ผ่าน event copy/paste + สำรองด้วย e.code · ปุ่มบนแถบ) · ปุ่มลัดตัวเดียวใช้ e.code (แป้นไทยได้) · ยังไม่ได้ลองแป้นไทยจริง/ข้ามแท็บจริง
- 4.3.0 มี:
  - แนบรูปประกอบวัตถุ (แท็บ 📷 รูปภาพ, ย่ออัตโนมัติ ≤1600px JPEG) · รูปย่อในตารางสรุป
  - ปุ่ม 📑 รายงาน PDF พร้อมรูป (ภาพรวมพื้นที่ + ตาราง + 1 หน้าต่อวัตถุ)
  - JSON เก็บ/นำเข้ารูปได้ (`photoStore`)
  - ไอคอนแท็บเบราว์เซอร์ Survey + ชื่อแท็บ "Survey · Advanced GIS Civil & Orthophoto Workspace"
- ไฟล์ไอคอน: `survey-icon.svg` (ต้นฉบับ) · `survey-icon.ico` (สำหรับ shortcut) · `survey-icon.png`
- ทดสอบในเบราว์เซอร์: `.claude\launch.json` ของ LocalAI ชื่อ `pee-survey` (พอร์ต 8766)

## ขั้นตอนปล่อยขึ้นเว็บ (ทุกรอบ หลังลุงพี OK ตัวอย่าง)
1. คัดลอก `Pee_survey_preview.html` → `Pee_survey.html`
2. clone aisolar2 ใหม่ใน scratchpad (`F:\LocalAI\project_plan_spa` ตามหลัง origin + มีไฟล์ค้าง อย่าใช้) วางไฟล์ที่ root · diff --cached --stat · commit "โดย ลุงพี" · push
3. รอ GitHub Pages ~1 นาที แล้วเปิด github.io ตรวจเลขเวอร์ชันจริง

## งานที่พักไว้ (ยังไม่เริ่ม)

### 2. เวอร์ชันเดสก์ท็อป
- `Survey.bat` เปิด Edge/Chrome แบบ `--app=` (หน้าต่างแอป ไม่มีแถบที่อยู่) + shortcut .lnk ไอคอน `survey-icon.ico` บน Desktop ทั้ง `Desktop` และ `OneDrive\Desktop` + README วิธีเปิด
- ทางเลือกใหญ่กว่า: ตัวติดตั้งแบบ ASC Studio (`design-auto\installer\`) — ลุงพีต้องสั่งก่อน

### 3. แก้ไขวัตถุได้ทุกด้าน — ✅ ขึ้นเว็บแล้ว 4.5.0
- แท็บ "สีแต่ละด้าน" → พิมพ์ความยาวแต่ละด้านได้ รูปทรงบนแผนที่ขยับตาม
- คลิกป้ายระยะด้านบนแผนที่ → เปิดช่องแก้ด้านนั้น
- ค่าที่พิมพ์ต้องอยู่ตามนั้น ห้ามบีบค่าเงียบ ๆ รูปเพี้ยนให้เตือน ⚠
- (ยังต้องยืนยันกับลุงพีว่าเข้าใจความหมาย "แก้ไขได้ทุกด้าน" ถูก)

### 4. ส่งออก JSON ให้ ASC Studio นำเข้า — ✅ ขึ้นเว็บแล้ว 4.5.0 แบบไม่แก้ ASCS: ไฟล์เดียว `_ASCS.json` = ไฟล์โครงการของ ASCS เอง (schema design-auto/1) · ชื่อ พิกัด อาคาร สิ่งกีดขวาง ต้นไม้ + อุปกรณ์จริง pole/transformer(kVA)/mdb พร้อมชื่อ · ทดสอบ importFiles + derive ของ ASCS 0.211.0 ผ่าน · ยังไม่ได้เปิดดูภาพ 3D ในแอป ASCS จริง · ⚠ ผูกกับโครงสร้างภายใน ASCS (types.ts) ถ้า ASCS เปลี่ยน schema ต้องปรับ buildAscsProject
- หมายเหตุ 4.4.0: วัตถุมี `kind` แล้ว (tree / pole / pole_tx / mdb) → แมปเข้า ASC Studio ได้ง่ายขึ้น (tree→tree, mdb/pole→equipment หรือ obstacle)
- ASC Studio (`F:\LocalAI\aiSolar\design-auto`) ตอนนี้รับ GeoJSON ที่มี `properties.kind` (`building`/`obstacle`/`keepout`/`neighbor`/`tree`) — `src/io/import/index.ts:128,177-202`
  - ข้อจำกัด: ไม่ตั้งชื่อ/พิกัดโครงการ (ใช้ศูนย์กลางโครงการที่เปิดอยู่) · เส้น/สี/ความสูงรายจุดหาย · สิ่งกีดขวางกลายเป็นสี่เหลี่ยม
- แผนที่แนะนำ (ทำ 2 ฝั่ง):
  - Survey: ปุ่ม "ส่งออกให้ ASC Studio" + เลือกบทบาทวัตถุ (อาคาร/หลังคา · สิ่งกีดขวาง · เขตที่ดิน · ต้นไม้)
  - ASC Studio: เพิ่ม branch ใน `importOne` เช่น `format:'asc-survey-map/1'` → ตั้ง `site.projectName/note/lat/lng`, `site.boundary`, อาคาร+ความสูง (แบบ `importSurvey` index.ts:500-522)
  - ASC Studio ต้อง bump → typecheck → test → build → deploy studio/

### 5. รวมเข้า ASC Enterprise + สิทธิ์ (repo peeraponggis/asc = `F:\LocalAI\git\asc`)
- `docs/index.html` ~2793: แถวแรกใน `APP_MENUS` (ก่อน Project Plan) เช่น `{ key:'survey', label:'Survey', icon:'fa-map-location-dot', url:'https://peeraponggis.github.io/aisolar2/Pee_survey.html' }` → ชิปสิทธิ์ในหน้าผู้ดูแลขึ้นเอง
- `docs/asc-cloud.js` ~507: `PRESENCE_APPS` เพิ่ม `{ path:'/aisolar2/pee_survey', app:'SURVEY', base:'Survey' }`
- `docs/asc-pimonitor.js:23` `APP_LABEL` · `docs/pi-monitor.html:93` option SURVEY · `tests/presence.mjs` เพิ่ม assert
- `supabase/presence-apps.sql` เพิ่ม `('SURVEY','Survey')` → ลุงพีรันใน SQL Editor https://supabase.com/dashboard/project/rcaslesvgilknupqmwrp/sql/new (จำเป็น ไม่งั้น ping Pi monitor ล้มเงียบ)
- `Pee_survey.html` `<head>`: ใส่ 4 บรรทัด gate แบบ `project_plan_spa.html` (supabase-js 2.58.0 + `/asc/supabase-config.js` + `/asc/asc-cloud.js` + `maintenanceGuard(true)`)
- ⚠ ช่องโหว่: สิทธิ์รายโปรแกรมตอนนี้แค่ซ่อนเมนู รู้ลิงก์ก็เปิดได้ (Project Plan ก็เป็น) → แนะนำให้หน้า Survey ตรวจ `user_menus` จริง (ผู้ดูแล + @proinventive.co.th ผ่าน)
- deploy ASC Enterprise จริงต้องขออนุมัติลุงพีก่อน · bump asc VERSION.json/CHANGELOG/STATUS
