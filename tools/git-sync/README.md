# Git Sync — pull / push ทุก repo พร้อมกัน

โฟลเดอร์: `F:\LocalAI\tools\git-sync\` (laptop) · `C:\LocalAI\tools\git-sync\` (home server)

## วิธีเปิด
1. ดับเบิลคลิกไอคอน **Git Sync** (วงกลมส้ม ลูกศรขึ้น-ลง) บน Desktop
   — หรือดับเบิลคลิก `F:\LocalAI\tools\git-sync\Git-Sync.bat`
2. เลือกเมนู
   - `1` **Pull** — ดึงงานล่าสุดจาก GitHub ทุก repo พร้อมกัน (ทำก่อนเริ่มงาน)
   - `2` **Push** — ส่งงานขึ้น GitHub ทุก repo (ทำตอนจบงาน)
   - `3` **Status** — ดูว่า repo ไหนมีไฟล์ค้าง / รอ push / ตามหลัง
   - `4` แก้รายชื่อ repo (`repos.txt`)
3. ถ้าอยากกดทีเดียวไม่ผ่านเมนู: `Git-Pull-All.bat` หรือ `Git-Push-All.bat`

## Push ทำงานอย่างไร
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
| `Git-Sync.bat` | เมนูหลัก (ไอคอน Desktop ชี้มาที่นี่) |
| `Git-Pull-All.bat` / `Git-Push-All.bat` | กดทีเดียว pull / push ทุก repo |
| `git-sync.ps1` | ตัวทำงานจริง (`-Mode Pull|Push|Status`) |
| `repos.txt` | รายชื่อ repo (path ใต้ไดรฟ์ ใช้ได้ทั้ง F: และ C:) |
| `make-shortcut.ps1` | สร้างไอคอน Desktop ใหม่ (รันซ้ำได้) |
| `make-icon.py` / `git-sync.ico` | ไอคอนโปรแกรม |

## ติดตั้งบนเครื่องใหม่ / home server
```powershell
powershell -ExecutionPolicy Bypass -File C:\LocalAI\tools\git-sync\make-shortcut.ps1
```
