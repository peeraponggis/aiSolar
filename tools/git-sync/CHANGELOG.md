# Git Sync — CHANGELOG

## 1.1.0 — 2026-11-24 โดย ลุงพี
- เพิ่มหน้าต่าง `git_sync_gui.pyw` (หน้าตาแบบโปรแกรมคัดลอกไฟล์ ↔ home): ตาราง repo ติ๊กเลือก · Pull/Push · ① ดูแผน (ไม่แตะอะไร) → ② ดำเนินการ + ยืนยัน · ตารางผลเป็นสี + แถบความคืบหน้า
- ทุก repo ทำพร้อมกัน · ด่านกันพลาดเหมือนเดิม (คีย์/ไฟล์ลับ/ไฟล์ใหญ่ = ไม่ commit · CONFLICT = ย้อนกลับ · ไม่ใช้ --force)
- ปุ่มเพิ่ม repo / ลบออกจากรายการ แก้ `repos.txt` ให้เอง · จำ repo ที่ไม่ติ๊กไว้ใน `git-sync-gui.json`
- ไอคอน Desktop "Git Sync" เปิดหน้าต่างนี้แทนเมนู · เมนู `Git-Sync.bat` ยังใช้ได้เหมือนเดิม

## 1.0.0 — 2026-11-24 โดย ลุงพี
- เริ่มโปรแกรม: pull / push หลาย repo พร้อมกันในคลิกเดียว (Git-Pull-All.bat · Git-Push-All.bat · เมนู Git-Sync.bat)
- Pull ทุก repo พร้อมกันแบบ `pull --rebase --autostash` · CONFLICT = ยกเลิกกลับสภาพเดิมแล้วแจ้งสีแดง
- Push ถามทีละ repo (Y ไฟล์ที่แก้ · A รวมไฟล์ใหม่ · P push อย่างเดียว · N ข้าม) แสดง `diff --cached --stat` ก่อน commit
- ด่านกันพลาด: ตรวจคีย์/รหัสลับ ชื่อไฟล์ลับ (.env, .key, config.ini ฯลฯ) และไฟล์ใหญ่ > 95 MB → ไม่ commit · ไม่ใช้ --force
- ไอคอน git-sync.ico + shortcut "Git Sync" บน Desktop · log ที่ git-sync.log
