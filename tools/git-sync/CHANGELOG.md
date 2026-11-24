# Git Sync — CHANGELOG

## 1.0.0 — 2026-11-24 โดย ลุงพี
- เริ่มโปรแกรม: pull / push หลาย repo พร้อมกันในคลิกเดียว (Git-Pull-All.bat · Git-Push-All.bat · เมนู Git-Sync.bat)
- Pull ทุก repo พร้อมกันแบบ `pull --rebase --autostash` · CONFLICT = ยกเลิกกลับสภาพเดิมแล้วแจ้งสีแดง
- Push ถามทีละ repo (Y ไฟล์ที่แก้ · A รวมไฟล์ใหม่ · P push อย่างเดียว · N ข้าม) แสดง `diff --cached --stat` ก่อน commit
- ด่านกันพลาด: ตรวจคีย์/รหัสลับ ชื่อไฟล์ลับ (.env, .key, config.ini ฯลฯ) และไฟล์ใหญ่ > 95 MB → ไม่ commit · ไม่ใช้ --force
- ไอคอน git-sync.ico + shortcut "Git Sync" บน Desktop · log ที่ git-sync.log
