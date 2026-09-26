---
name: local-ai-portable-setup
description: ชุด Local AI พกพาบน D:\LocalAI (Ollama + chat UI) และสเปคเครื่อง
metadata:
  type: project
---

ผู้ใช้มีชุด **Local AI แบบพกพา** ที่ `D:\LocalAI\` (D: เป็น external HDD) รันด้วย `Start-LocalAI.bat` — Ollama portable + โมเดลใน `models\` + UI แชทไฟล์เดียว `ui\chat.html` (self-contained, offline).

**สเปคเครื่องต้นทาง (ตรวจสอบ 2026-09-18):**
- GPU: NVIDIA RTX A500 Laptop — **VRAM 4GB** (คอขวดหลัก)
- RAM: 32GB | CPU: i7-1360P

**โมเดลที่ใช้:** `qwen2.5-coder:7b` (โค้ด ตัวหลัก, hybrid GPU+RAM ~7-10 tok/s), `qwen2.5-coder:3b` (เร็ว), `bge-m3` (embedding/RAG งานฐานข้อมูล BoQ).

**งานหลัก:** เขียนโค้ด + งานเอกสาร/ฐานข้อมูล BoQ (โปรเจกต์ Pi_BoQ).

**เคล็ด VRAM 4GB:** flash-attention + KV cache q8_0 + num_ctx 4096 (ลดเป็น 2048 ถ้าเครื่องสเปคต่ำกว่า). VRAM โน้ตบุ๊กอัปเกรดไม่ได้ ทางเดียวที่เพิ่มจริงคือ eGPU ผ่าน Thunderbolt 4.

ยึด workflow [[git-worktree-workflow]] และข้อบังคับ [[no-code-on-c-drive]]
