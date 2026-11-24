# Git Sync — pull / push ทุก repo พร้อมกัน

โฟลเดอร์: `F:\LocalAI\tools\git-sync\` (laptop) · `C:\LocalAI\tools\git-sync\` (home server)

## วิธีเปิด (หน้าต่าง — แนะนำ)
1. ดับเบิลคลิกไอคอน **Git Sync** (วงกลมส้ม ลูกศรขึ้น-ลง) บน Desktop
   — หรือดับเบิลคลิก `F:\LocalAI\tools\git-sync\Git-Sync-GUI.bat`
2. ติ๊ก repo ที่จะใช้ (คลิกที่ช่อง ☑/☐ · ดับเบิลคลิกแถว = เปิดโฟลเดอร์)
3. เลือก **ดึงจาก GitHub มาเครื่องนี้ (Pull)** หรือ **ส่งจากเครื่องนี้ขึ้น GitHub (Push)**
   - Push: พิมพ์ข้อความ commit · ติ๊ก "รวมไฟล์ใหม่ด้วย" ถ้าจะเอาไฟล์ที่ยังไม่เคยขึ้น git ไปด้วย
4. กด **① ดูแผน** — ดูว่าแต่ละ repo จะดึง/ส่งอะไร (ยังไม่เปลี่ยนแปลงอะไร)
5. กด **② ดำเนินการ** → ยืนยัน — ทุก repo ทำพร้อมกัน ผลขึ้นในตาราง (เขียว = สำเร็จ · แดง = ต้องแก้เอง)

## วิธีเปิด (แบบเมนูในหน้าจอดำ)
- ดับเบิลคลิก `Git-Sync.bat` → เลือก `1` Pull · `2` Push · `3` Status · `4` แก้รายชื่อ repo
- หรือกดทีเดียว: `Git-Pull-All.bat` / `Git-Push-All.bat`

## Push แบบเมนูหน้าจอดำ ทำงานอย่างไร
ไล่ทีละ repo แสดงไฟล์ที่แก้และไฟล์ใหม่ แล้วถาม
- `Y` commit เฉพาะไฟล์ที่ git รู้จักอยู่แล้ว (ปลอดภัยสุด)
- `A` รวมไฟล์ใหม่ทั้งหมดด้วย (ระวัง repo ที่มีไฟล์ใหม่เยอะ เช่น `F:\LocalAI`)
- `P` push commit ที่มีอยู่แล้วอย่างเดียว · `N` ข้าม

ก่อน commit จะแสดงรายการไฟล์ (`diff --cached --stat`) และให้พิมพ์ข้อความ commit (Enter = ข้อความอัตโนมัติ "โดย ลุงพี" · `X` = ยกเลิก)
จากนั้นส่งทุก repo ที่เลือกขึ้น GitHub **พร้อมกัน** (pull --rebase ก่อน แล้ว push)

## ด่านกันพลาด
- เจอคีย์/รหัสลับ (`sk-` `AIza` `ghp_` `gsk_` `hf_` `xai-` JWT ฯลฯ) ชื่อไฟล์ลับ (`.env` `.key` `.pem` `config.ini`) หรือไฟล์ > 95 MB → **หยุด repo นั้น ไม่ commit** (ไฟล์ยังอยู่ครบ)
- CONFLICT ตอน pull → ยกเลิก rebase กลับสภาพเดิม แจ้งสีแดง ให้แก้เอง · **ไม่ใช้ `--force` ทุกกรณี**
- ไม่มีเน็ต → ยกเลิกก่อนแตะอะไร
- ผลทุกครั้งเขียนลง `git-sync.log`

## ไฟล์
| ไฟล์ | หน้าที่ |
|---|---|
| `git_sync_gui.pyw` / `Git-Sync-GUI.bat` | หน้าต่าง Git Sync (ไอคอน Desktop ชี้มาที่นี่) |
| `Git-Sync.bat` | เมนูแบบหน้าจอดำ |
| `Git-Pull-All.bat` / `Git-Push-All.bat` | กดทีเดียว pull / push ทุก repo |
| `git-sync.ps1` | ตัวทำงานจริง (`-Mode Pull|Push|Status`) |
| `repos.txt` | รายชื่อ repo (path ใต้ไดรฟ์ ใช้ได้ทั้ง F: และ C:) |
| `make-shortcut.ps1` | สร้างไอคอน Desktop ใหม่ (รันซ้ำได้) |
| `make-icon.py` / `git-sync.ico` | ไอคอนโปรแกรม |

## ติดตั้งบนเครื่องใหม่ / home server
```powershell
powershell -ExecutionPolicy Bypass -File C:\LocalAI\tools\git-sync\make-shortcut.ps1
```
