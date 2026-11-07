# ชุด .bat — ปล่อยรุ่น · ติดตั้ง · SQL · home server (ASC Studio / ASC Architect / ASC Cloud / CRM-Pi / Local Translator)

สร้าง 7 พ.ย. 2569 · โดย ลุงพี · โฟลเดอร์ `F:\LocalAI\setup_prg\ASC` (ขึ้น git aiSolar · ไม่มีคีย์ในไฟล์)
เปิดจากไอคอน Desktop **"ASC ปล่อยรุ่น"** หรือดับเบิลคลิก `ASC-Menu.bat`

| ไฟล์ | ทำอะไร |
|---|---|
| `ASC-Menu.bat` | เมนูหลัก: แสดงรุ่นทุกโปรแกรม (laptop · git · home) + จำนวน SQL ค้าง แล้วเลือก 1–8 |
| `01-ascs-release.bat` | ASC Studio: build → ชุดติดตั้ง+ชุดอัปเดต → เว็บ → สแกนคีย์ → push → ตรวจเว็บจริง → PROGRAMS.md |
| `02-asca-release.bat` | ASC Architect: ชุดติดตั้ง Inno + ชุดอัปเดต → เว็บ → push |
| `03-cloud-deploy.bat` | ASC Cloud: push `docs/` → รอ GitHub Pages → ตรวจ URL |
| `04-crm-deploy.bat` | CRM-Pi: build_pages → ตรวจคีย์ → wrangler deploy **production** (laptop เท่านั้น) |
| `05-translator-build.bat` | Local Translator: PyInstaller → zip ชุดติดตั้ง → ส่ง home |
| `06-sql-todo.bat` | SQL ที่ต้องรันใน Supabase: **แสดงลิงก์ SQL Editor ทุกครั้ง** · คัดลอกไฟล์เข้า clipboard · เปิดลิงก์ · จำว่ารันแล้ว |
| `07-home.bat` | home server ผ่าน `ssh home`: ดูรุ่น · อัปเดต ASCS บน home · ดึง/ส่ง `out` · HomeGuard · laptop-data · Remote Control |
| `08-new-pc.bat` | ติดตั้งบนเครื่องใหม่: ตรวจเครื่องมือ · เปิดชุดติดตั้งล่าสุด · winget ที่ขาด · ไอคอน Desktop |
| `lib\config.ps1` | **path และค่าตั้งทั้งหมด** — ย้ายโฟลเดอร์/เปลี่ยน project/เพิ่มไฟล์ SQL แก้ที่นี่ที่เดียว |
| `lib\*.ps1` | ตัวทำงานจริง (bat เป็นแค่ตัวเรียก) · `logs\<วันที่>.txt` ทุกคำสั่ง · `logs\sql-done.json` SQL ที่รันแล้ว |
| `installers\` | วางชุดติดตั้งที่จะพกไปเครื่องใหม่ (08 หาในนี้ด้วย) |

## กฎที่ bat ทุกตัวถือ
- **ถามก่อน** commit/push/deploy ทุกครั้ง (ค่าเริ่ม = ไม่) · เว็บที่คนใช้จริงเตือนซ้ำ
- **ไม่ bump เวอร์ชัน** — Claude bump ตามกฎ "โดย ลุงพี" ก่อนเรียก bat
- **ขั้นไหนไม่ผ่าน = หยุดทันที** แสดง 20 บรรทัดท้ายของ error · git CONFLICT = หยุด ไม่ `--force`
- **สแกนคีย์ลับ** ก่อน push repo public (sk- · AIza · ghp_ · service_role · JWT · กุญแจชุดติดตั้ง)
- ไม่ commit `out\` · `server\data` · `scripts\sync-home-gui.ps1` · `out\usermanual\_pdfs.json`
- ไม่พิมพ์กุญแจ/รหัสผ่านบนจอหรือใน log (แสดงแค่ path ไฟล์)
- SQL ทุกไฟล์ที่ให้ลุงพีรัน มี **ลิงก์ SQL Editor + path เต็ม + ลำดับ** เสมอ
- bat **ไม่ต้องแก้ตามเมื่อแก้โค้ดโปรแกรม** (อ่าน VERSION.json/เรียกสคริปต์ของโปรแกรมตอนรัน) · ต้องแก้เฉพาะเมื่อย้ายโฟลเดอร์ เปลี่ยนชื่อสคริปต์ หรือเพิ่มขั้นตอนใหม่ → เมนูหลักตรวจและเตือนถ้าสคริปต์ที่เรียกหายไป

## 1. ภาพรวมโปรแกรม

| โปรแกรม | โฟลเดอร์ (laptop) | repo | เห็นได้ | พอร์ต/ที่อยู่ |
|---|---|---|---|---|
| ASC Studio (ASCS · Design Auto) | `LocalAI\aiSolar\design-auto` | peeraponggis/asc_auto (private) | ลูกค้าผ่านชุดติดตั้ง · เว็บ | 11437 · gateway 11435 · Ollama 11434 |
| ASC Architect (ASCA) | `LocalAI\pee_architec` | peeraponggis/pee_architec (private) | ชุดติดตั้ง Inno (มีรหัส) | 11440 |
| ASC Cloud | `LocalAI\git\asc` → `docs/` | peeraponggis/asc (public · GitHub Pages) | https://peeraponggis.github.io/asc | Supabase `rcaslesvgilknupqmwrp` |
| CRM-Pi | `enterprise\picode\pi-system` | proinventive/picode (private) | https://pi-system.pages.dev (Cloudflare) | Supabase `zloxphgxhttrtgqlafsz` |
| Local Translator | `LocalAI\translation` | aiSolar (public · โค้ดเท่านั้น) | zip + Ollama | 11434 |

home server: `C:\LocalAI` · `C:\enterprise` (ไม่มี F:) · `ssh home` (Tailscale 100.118.18.110) · Python ใช้ `py` · RAM 8 GB ห้าม build ซ้อน

## 2. ติดตั้งครั้งแรก

**ASC Cloud (Supabase)** — เปิด https://supabase.com/dashboard/project/rcaslesvgilknupqmwrp/sql/new วางทีละไฟล์จาก `F:\LocalAI\git\asc\supabase\` ตามลำดับ (ใน 06 กด F แล้วพิมพ์ `asc-1` … เพื่อคัดลอก+เปิดลิงก์ให้):
1. `schema.sql` 2. `kb.sql` 3. `ascs-studio.sql` 4. `ascs-release.sql` 5. `ai-install.sql` 6. `allow-domains.sql` 7. `devices.sql` 8. `menu-access.sql` 9. `presence.sql` 10. `pi-monitor-telegram.sql` 11. `presence-ingest.sql` 12. `presence-device.sql` 13. `presence-apps.sql` 14. `device-menus.sql`
แล้วรันข้อมูล: `out\cloud\kb-data.sql` · `out\cloud\standards-data.sql` · `out\cloud\ascs-release-key.sql` (🔒) — ทั้งสามอยู่ใน 06
เว็บ: GitHub Pages เผยแพร่ `docs/` ของ branch main อัตโนมัติเมื่อ push (03)

**ASC Studio บนเครื่องอื่น**
- ไม่มี git (ลูกค้า/ทีม): เปิด `out\setup\ASC-Studio-Setup-<รุ่น>.exe` → ติดตั้งที่ `<ไดรฟ์>\LocalAI\aiSolar\ASC Studio` · ใส่ `update.key` ให้ → ต่อไปอัปเดตเองจากแถบ "มีรุ่นใหม่" (ตรวจตอนเปิด + ทุก 6 ชม.) หรือ `ASC Studio Update.bat`
- มี git (laptop/home): `git clone` + `install.bat` (สร้าง .venv · pip · playwright · npm build · ไอคอน)
- ต้องมี Python 3.12+ (ชุดติดตั้งเสนอ winget ให้ถ้าไม่มี) · ไม่ต้องมี Node
- เครื่องที่ติดตั้งจากชุดรุ่นก่อน 0.162.0 ไม่มี `update.key` → ติดตั้งชุดใหม่ทับครั้งเดียว

**ASC Architect**: `ASCA-Setup-<รุ่น>.exe` จาก `F:\LocalAI\apps\ASCA-release\<รุ่น>\` (รหัสในไฟล์ `F:\LocalAI\apps\ASCA-release\password.txt`) → ติดตั้งที่ `%LOCALAPPDATA%\Programs\ASC Architect` พร้อม Python ในตัว · อัปเดตเองจาก `asca-release\latest.json` (ถามก่อน · ย้อนกลับเองถ้าเปิดไม่ขึ้นใน 60 วิ) · แบบ git: `pee_architec.bat` สร้าง .venv เอง

**CRM-Pi**: Supabase CRM https://supabase.com/dashboard/project/zloxphgxhttrtgqlafsz/sql/new รัน `pi_crm_erp\supabase\pi_system_full_install.sql` → `20261031_asc_studio.sql` → `20261031_admin_users.sql` (รันซ้ำทุกครั้งหลัง full_install) · เว็บ deploy ด้วย 04 · Pi_BoQ ใช้ `pi_boq_app\supabase\migrations\` + `deploy\*.sql` seeds 1–5

**Local Translator**: แตก `LocalTranslator-setup-<รุ่น>.zip` → `Install-LocalTranslator.bat` (หา/เปิด Ollama · ดึงโมเดล typhoon 2.5 GB · ไอคอน) · ไม่มีระบบอัปเดต = ติดตั้งทับ

## 3. ปล่อยรุ่นใหม่ (ลำดับ)
1. Claude: ตรวจโค้ดค้างทุกงาน → แสดงตัวอย่างให้ลุงพีอนุมัติ → bump เวอร์ชัน + CHANGELOG + KB
2. `01` (ASCS) หรือ `02` (ASCA) เลือก [1] ทำครบ — หยุดถามก่อน push
3. `06` รัน SQL ที่ขึ้น ● ค้าง (kb-data ทุกรุ่น · key เมื่อกุญแจเปลี่ยน · standards เมื่อตารางเปลี่ยน)
4. `07` [1] อัปเดต home server ให้ตามรุ่น
5. เครื่องลูกค้าอัปเดตเองผ่านแถบรุ่นใหม่

## 4. กุญแจ/รหัส (ห้ามขึ้น git · สำรองไว้นอกเครื่อง)
| ไฟล์ | ใช้กับ | หายแล้ว |
|---|---|---|
| `F:\LocalAI\apps\ASCS-release\password.txt` | เข้ารหัสชุดอัปเดต/ชุดติดตั้ง ASCS · ตาราง `app_release_keys` | เครื่องที่ติดตั้งแล้วอัปเดตไม่ได้ ต้องติดตั้งชุดใหม่ทับทุกเครื่อง |
| `F:\LocalAI\apps\ASCA-release\password.txt` | รหัสเปิดชุดติดตั้ง ASCA | ชุดติดตั้งเก่าเปิดไม่ได้ ต้องสร้างใหม่ |
| `F:\LocalAI\notify\notify.json` | Telegram/WhatsApp แจ้งเตือน | ตั้งใหม่ด้วย `scripts\notify-setup.ps1` |
| `~\.ssh\id_ed25519` | ssh home | ลงทะเบียนคีย์ใหม่ที่ `C:\ProgramData\ssh\administrators_authorized_keys` บน home |

## 5. ปัญหาที่เจอบ่อย
- **ssh home ไม่ตอบ**: Tailscale ทั้งสองเครื่องเปิดอยู่ไหม · ลอง `ssh home-lan` ในบ้าน
- **gh run watch ค้าง/ไม่ login**: `gh auth login` · ดูที่ https://github.com/peeraponggis/asc/actions
- **เว็บจริงยังรุ่นเก่า**: แคช Service Worker — reload 2 ครั้ง หรือถ้า `docs/sw.js` SHELL เปลี่ยนต้อง bump VERSION ใน sw.js
- **wrangler ขึ้น Preview ไม่ใช่ production**: ลืม `--branch production` (04 ใส่ให้เสมอ)
- **Inno Setup ไม่พบ**: ต้องอยู่ที่ `F:\LocalAI\apps\InnoSetup6\ISCC.exe`
- **csc.exe ไม่พบ** (ชุดติดตั้ง ASCS): ต้องมี .NET Framework 4 (มีใน Windows 10/11)
- **พอร์ต 11437 ชน**: มี ASCS ตัวเก่าเปิดอยู่ · `ASC Studio Update.bat` ปิดให้เอง
- **SQL รันซ้ำได้ไหม**: ไฟล์ใน 06 ทุกไฟล์รันซ้ำได้ (upsert/if not exists) ยกเว้น `cleanup-allowlist.sql` ที่ลบแล้วย้อนไม่ได้
- **PROGRAMS.md กับ VERSION.json ไม่ตรง** (CRM-Pi 1.2.2 vs 1.0.0): 04 เตือน — แก้ให้ตรงก่อนปล่อย
