---
name: lungpee
description: กฎการทำงานของลุงพี (Peerapong · ProInventive) สำหรับทุกโปรแกรมที่พัฒนาร่วมกับ Claude — ใช้ทุกครั้งที่จะแก้ สร้าง ทดสอบ commit push หรือ deploy โปรแกรมใดก็ตามใต้ LocalAI / enterprise / picode (ASC Studio · Design Auto · ASC Architect · CRM-Pi · Local Translator · HomeGuard ฯลฯ) ทั้งบน laptop (F:) และ home server (C:) รวมถึงเมื่อสร้างหรือแก้ผู้ช่วย AI ในโปรแกรม
---

# กฎการทำงานของลุงพี

ตอบและสรุปเป็น**ภาษาไทย**ทุกครั้ง · เรียกผู้ใช้ว่า "ลุงพี" · ฉบับล่าสุดของ Skill นี้อยู่ที่ `<ไดรฟ์>:\LocalAI\skills\lungpee\SKILL.md` (repo aiSolar)

## 0. ก่อนเริ่ม: รู้ว่าโปรแกรมอยู่ไหน
- อ่าน `<ไดรฟ์>:\LocalAI\PROGRAMS.md` — ทะเบียนทุกโปรแกรม (ชื่อ · เวอร์ชัน · โฟลเดอร์ · repo) แบ่ง 4 หมวดตาม **ใครเห็นได้**
  1. 🔒 งานบริษัท ProInventive (org `proinventive` private) · 2. 🔒 ผลิตภัณฑ์ของลุงพี (private) · 3. 🌐 public · 4. ⛔ ห้ามขึ้น git
- อ่าน `CLAUDE.md` ของโปรแกรมนั้นก่อนแก้ (มีกฎเฉพาะ เช่น design-auto ต้อง typecheck → test → build)
- เครื่อง: **laptop = `F:\`** (ห้ามเขียนโค้ดลง C:) · **home server = `C:\LocalAI` + `C:\enterprise`** (ไม่มี F:) · โค้ดห้ามเขียนไดรฟ์ตายตัว ใช้ path สัมพัทธ์
- Python บน home: `py` หรือ `.venv\Scripts\python` (คำสั่ง `python` เป็นตัวลัด Store ใช้ไม่ได้)
- CRM-Pi ต้นฉบับจริง = monorepo `proinventive/picode` โฟลเดอร์ `pi-system/` (ไม่ใช่ repo `proinventive/pi-system` ซึ่งเป็นสำเนาเก่า **เก็บไว้สำรอง** — ห้ามแก้ ห้ามลบ)

## 1. กฎเหล็ก 2 เครื่อง (ทุก repo)
1. **เริ่มงาน → pull ก่อนแตะไฟล์:** `git -C <repo> pull --rebase --autostash`
2. **จบงาน → commit + push ทันที** ในรอบเดียวกัน ไม่รอให้สั่ง (เว้นลุงพีบอก "ไว้ทีหลัง") · ห้ามทิ้ง commit ค้างเครื่องเดียว
3. diverged → `pull --rebase --autostash` · **CONFLICT → หยุดถาม** ห้าม `--force`
4. commit เฉพาะไฟล์ที่ตัวเองแก้ — ไฟล์ค้างจากงานอื่นอย่าแตะ
5. งานทำบน home ส่งกลับ laptop: ใส่หมายเหตุใน commit + สรุป (ทำบน C: · มี path ต้องปรับไหม · ไฟล์นอก git ที่ต้องคัดลอกเอง · laptop ต้องทำอะไรต่อ)

## 2. ทุกครั้งที่แก้โปรแกรม
- **bump เวอร์ชัน + CHANGELOG** "โดย ลุงพี" (คง created เดิม · ใส่ updated) — Design Auto ใช้ `py <ไดรฟ์>:\LocalAI\bump_version.py designauto <patch|minor|major> "สรุปไทย"` · โปรแกรมไม่มีไฟล์เวอร์ชัน = สร้าง `VERSION.json` + `CHANGELOG.md` เริ่ม 1.0.0
- เว็บที่ import โมดูลแบบ `?v=x.y.z` → เปลี่ยนเลขให้ตรงเวอร์ชันใหม่ (กันแคชเบราว์เซอร์)
- **ทดสอบจริงก่อนบอกว่าเสร็จ:** เทสต์ของโปรแกรม + ลองในเบราว์เซอร์/แอปจริง (ลาก พิมพ์ คลิก) · เทสต์ที่พังอยู่ก่อนแล้วให้ย้อนโค้ดพิสูจน์ แล้วรายงานตรง ๆ
- โปรแกรมใหม่ทุกตัว: **ไอคอน .ico ของตัวเอง + shortcut .lnk บน Desktop** (สคริปต์ make-shortcut รันซ้ำได้ทั้ง 2 เครื่อง)
- อัปเดตเวอร์ชันใน `PROGRAMS.md` แล้ว push repo aiSolar ด้วย
- เครื่อง home RAM 8 GB: เปิด Claude ≤ 2 session · ไม่รัน test/build 2 session พร้อมกัน (HomeGuard ให้รอ ไม่ต้องหาทางเลี่ยง) · ปิดเซิร์ฟเวอร์ทดสอบ/แท็บเบราว์เซอร์ทันทีที่ตรวจเสร็จ
- ไดรฟ์ I: และ J: สายมีปัญหา — ห้ามใช้จนลุงพีแจ้ง

## 3. ความปลอดภัยของข้อมูล
- **ก่อน push repo public** (aiSolar · asc · online · ai) ตรวจ API key / รหัสผ่าน / ข้อมูลลูกค้า: `sk-` `AIza` `ghp_` `gsk_` `hf_` `xai-` `sb_secret_` `service_role` JWT `eyJ…`
- ⛔ ห้ามขึ้น git ทุกกรณี: `design-auto\out` · `server\data` · ภาพสแกน วสท. (`eit`) · `AMR_Fetcher\data` (ลูกค้าจริง) · วิดีโอ CCTV · รหัสผ่าน PEA · คีย์ AI (อยู่ใน localStorage เท่านั้น)
- โปรแกรมเล็กหมวด 3.3 ขึ้น repo `ai` ผ่าน `git\ai\tools\sync_from_localai.sh` เท่านั้น (คัดเฉพาะโค้ด + ล้างรหัสผ่าน)
- `pee_architec` (ASCA) เป็น private ห้ามปนกับ aiSolar
- ข้อความที่ส่ง Telegram/WhatsApp/recap: ห้ามมีชื่อลูกค้า · ราคา/ต้นทุน · token
- **ขอลุงพีอนุมัติก่อน:** deploy เว็บที่คนใช้จริง (ASC Cloud `peeraponggis.github.io/asc` · CRM-Pi `pi-system.pages.dev` Cloudflare) · สร้าง repo ใหม่ · ลบไฟล์/repo · ติดตั้งโปรแกรม

## 4. ผู้ช่วย AI ทุกโปรแกรม (แบบ piBot ของ ASC Studio / ASCA / CRM-Pi)
อ่านรายละเอียดเต็มที่ `pee_architec\หลักการผู้ช่วยAI.md` แล้วใช้ ASCA `web\ai\` เป็นต้นแบบ
1. ค่าเริ่มต้น **ไม่ใช้ AI** (ค้นคลังในเครื่อง ไม่ส่งอะไรออก) · หลายผู้ให้บริการ + ลองเจ้าถัดไปเอง · คีย์อยู่ใน localStorage
2. AI ไม่คิดตัวเลขเอง (เอาจากโค้ด) · เปลี่ยนข้อมูลต้องให้คนกดยืนยันการ์ดก่อน · ห้ามบอกว่า "ทำแล้ว"
3. เรื่องโปรแกรม → คลังความรู้ (RAG) ก่อนเสมอ ไม่พบ = บอกว่าไม่มีในคู่มือ · ข้อมูลในงาน → ค่าจริง · เรื่องทั่วไป → ความรู้ AI ได้
4. ป้ายที่มาใต้คำตอบ 📚 คลัง · 🗂️ ข้อมูลในงาน · 🌐 ความรู้ทั่วไป (คิดจากเครื่องมือที่เรียกจริง)
5. ปุ่ม ➡️ "ต่อไปทำอะไร" จากสถานะจริงของหน้า · กล่องแชทรู้ว่าอยู่หน้าไหน
6. **ปุ่มกลมผู้ช่วยต้องลากย้ายได้ตั้งแต่สร้าง:** ขยับ > 5px = ลาก ไม่นับคลิก · คลิก = เปิด/ปิด · จำตำแหน่ง localStorage · ไม่หลุดขอบจอ (resize/zoom) · `touch-action: none`
7. ไอคอน piBot จาก `LocalAI\img\piBot-2-2.jpg` 4 ท่า · เพิ่มคำถาม-ตอบใหม่ลงคลังความรู้ทุกครั้งที่เพิ่มความสามารถ แล้ว build ดัชนีใหม่

## 5. Design Auto / ASC Studio โดยเฉพาะ
- วัตถุที่ผู้ใช้ลาก/พิมพ์ค่า **ต้องอยู่ตรงนั้น** ห้ามเด้งกลับหรือบีบค่าเงียบ ๆ — ผิดกติกาให้เตือน ⚠ แทน (ยกเว้นดูดชิดผนัง)
- วัตถุ 3D ใหม่ทุกชิ้นต้องมีป้ายกำกับ + ขนาดเป็น m
- จุดหยุดรอตรวจ: เขียนสรุป `LocalAI\notify\last-summary.txt` + `scripts\notify-review.ps1 -Next "…"` (ดู CLAUDE.md ของ design-auto)

## 6. GitHub บน home server
- Claude รันใน Session 0 อ่าน Credential Manager ของหน้าจอ RDP ไม่ได้ → ใช้ GCM แบบ `dpapi` (ตั้งใน `~/.claude/settings.json` env แล้ว) · push/pull ได้เอง
- token หมดอายุ → ขอรหัสยืนยันแบบ device flow ให้ลุงพีใส่ที่ github.com/login/device · **ห้ามขอรหัสผ่าน**
- **CRM-Pi deploy จาก laptop เท่านั้น** (ลุงพีสั่ง 1 พ.ย. 2569) — บน home ทำถึง build + ตรวจคีย์ใน `dist_pages` แล้วส่งคำสั่งให้ลุงพีรันบน laptop:
  `cd F:\enterprise\picode\pi-system` → `node pi_crm_erp/scripts/build_pages.mjs` → `npx wrangler pages deploy dist_pages --project-name pi-system --branch production`

## 7. จบงานทุกครั้ง
สรุปภาษาไทย: ทำอะไร · ไฟล์ที่แก้ · เวอร์ชัน + commit · ผลเทสต์จริง · สิ่งที่ยังไม่ได้ทำ/ไม่ได้ตรวจ · สิ่งที่ laptop ต้องทำต่อ

## 8. แก้/เพิ่มกฎใน Skill นี้
- ลุงพีสั่งกฎใหม่ (เช่น "ตั้งเป็นกฎ" "ต่อไปให้…" "บันทึกไว้") → Claude แก้ไฟล์นี้ที่ `<ไดรฟ์>:\LocalAI\skills\lungpee\SKILL.md` (ต้นฉบับใน repo เท่านั้น ห้ามแก้ตัวที่ติดตั้งใน `~/.claude/skills`) + บันทึก memory ด้วย
- ใส่กฎไว้ในหัวข้อที่ตรงเรื่อง เขียนสั้น ระบุ "ลุงพีสั่ง <วันที่>" · กฎเฉพาะโปรแกรมเดียวให้ลง `CLAUDE.md` ของโปรแกรมนั้นแทน แล้วอ้างถึงจากที่นี่ถ้าสำคัญ
- **Skill เรื่องใหม่แยกต่างหาก** ทำเป็นโฟลเดอร์ใหม่ `skills\<ชื่อ>\SKILL.md` แล้ว `install-skills.ps1` จะติดตั้งให้ทุกตัวเองแบบออโต้ (ลุงพีสั่ง 1 พ.ย. 2569) — สคริปต์หาทุกโฟลเดอร์ใต้ `skills\` ที่มี `SKILL.md` เอง ไม่ต้องแก้สคริปต์ · ใส่ frontmatter `name` (ตรงกับชื่อโฟลเดอร์) + `description` บอกว่าใช้เมื่อไร
- เสร็จแล้ว: รัน `skills\install-skills.ps1` · commit + push aiSolar · บอกลุงพีให้เครื่องอีกฝั่ง pull แล้วรัน install-skills.ps1 · session ที่เปิดค้างต้องเปิดใหม่จึงเห็นกฎใหม่
