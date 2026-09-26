# 🤖 LocalAI — ระบบ AI ในเครื่อง (ลุงพี) — สรุประบบ

> ชุด AI ทำงานในเครื่อง 100% offline (บางฟีเจอร์ต่อเน็ต) พกพาบน external HDD `D:\`
> อัปเดตล่าสุด: 2026-09-18

---

## 🚀 เริ่มใช้งาน (ง่ายสุด)
**ดับเบิลคลิกไอคอน "ลุงพี AI" บน Desktop** (หรือ `D:\LocalAI\lung_pee.bat`)
→ สตาร์ท Ollama + TTS server → เปิดหน้าแชทที่ **http://127.0.0.1:11435/**

> ⚠️ ต้องเปิดผ่าน `http://127.0.0.1:11435/` (ไม่ใช่ file://) เพื่อให้ ปลั๊กอิน / ไมค์ / อ่านไฟล์ / เสียง Neural ทำงาน — `lung_pee.bat` จัดการให้อัตโนมัติ

---

## 💻 สเปคเครื่อง
| ส่วน | รายละเอียด |
|---|---|
| GPU | NVIDIA RTX A500 Laptop — **VRAM 4GB** (คอขวดหลัก) |
| RAM | 32GB |
| CPU | Intel i7-1360P |
| ดิสก์ | D: = external HDD (พกพาได้) |

---

## 🧠 โมเดลที่ติดตั้ง (6 ตัว) + ผลวัดความเร็วจริง
| โมเดล | ความเร็ว | VRAM | GPU/CPU | ใช้ทำ |
|---|---|---|---|---|
| **scb10x/…typhoon2-3b** | **39.5 tok/s** ⚡ | 2.3GB | 100% GPU | ไทย (เร็วสุด) |
| **qwen2.5-coder:3b** | **36.4 tok/s** ⚡ | 2.1GB | 100% GPU | โค้ด (เร็ว) |
| qwen2.5-coder:7b | 12.5 tok/s 🐢 | 5.0GB | 52/48 hybrid | โค้ดคุณภาพสูง |
| qwen2.5:7b | ~12 tok/s 🐢 | 5.0GB | hybrid | ทั่วไป |
| moondream | (vision) | 1.7GB | GPU | อ่านรูป |
| bge-m3 | (embedding) | 1.2GB | GPU | RAG/ค้นความรู้ |

**คำแนะนำ:**
- ใช้ประจำ (เร็ว) → **Typhoon 3B** (ไทย) / **qwen2.5-coder:3b** (โค้ด) = 100% GPU
- 3B (2.1GB) + bge-m3 (1.2GB) อยู่ VRAM พร้อมกันได้ → แชท+RAG ลื่น
- 7B เฉพาะงานคุณภาพสูงสุด (ยอมช้า)
- ไทยจริงจัง → **openai-fast (ฟรีออนไลน์)** ดีกว่า local ทุกตัว
- โหลดโมเดลครั้งแรกช้า 60–135s เพราะอ่านจาก HDD → ถ้าย้ายไป SSD จะเร็วขึ้นมาก
- ตั้ง **Context = 4096** (แทน 8192) → รัน 100% GPU เร็วขึ้น

---

## 💬 ฟีเจอร์ chat.html
- แชทหลายห้อง, สลับโมเดล, สตรีมมิ่ง+หยุด, tok/s, มืด/สว่าง, Console
- คำทักทาย "สวัสดี ลุงพี" + พยากรณ์อากาศ
- **แนบไฟล์:** รูป (vision) / PDF / Excel / CSV
- **เสียง:** 🎤 พูดเป็นข้อความ · 🔊 อ่านออกเสียง (Pattara ในเครื่อง / **เปรมวดี+นิวัตน์ Neural** ออนไลน์) · หยุดด้วยปุ่ม/Esc
- **ลากคลุมข้อความ** → อ่าน/แปลไทย/คัดลอก/ส่งเข้าแชท
- **🧠 RAG คลังความรู้** (bge-m3) + อ้างอิงทุกคำตอบ + 👍 ให้โมเดลเรียนรู้เอง
- **📰 ข่าว & Social** (ผ่าน browser extension)
- **เลือกโมเดล:** Local / 🆓 ฟรีออนไลน์ (openai-fast) / 💳 เสียเงิน (ใส่ API key)
- **🧩 ปลั๊กอิน** (`ui/plugins/` + LocalAI API) — เช่น `/เวลา`, `/นับ`
- **เมนู "+"** รวมเครื่องมือ (ไฟล์/โฟลเดอร์/คำสั่ง/ตัวเชื่อมต่อ/ปลั๊กอิน)
- **📝 Improvement log**, **▶ พรีวิวโค้ด**
- **📁 เข้าถึงไฟล์ในไดรฟ์** + สำรองแชทอัตโนมัติ

## 🎨 สร้างสื่อ (สั่งด้วยภาษาไทย)
- **📊 กราฟ** — "วาดกราฟ…" → Chart.js (offline) · ต่อข้อมูล AMR ได้
- **🖼 รูป** — "สร้างรูป…" → Pollinations (ฟรี/ต่อเน็ต)
- **🎬 คลิป** — "ทำคลิป…" → รูป + เสียง Neural + ffmpeg → mp4
  - เลือกแนว: 📱 9:16 (TikTok/Reels) / 🖥 16:9 / ⬛ 1:1
  - ตัวเลือก 💬 ซับไทย (ฟอนต์ Sarabun) + 🎵 เพลงประกอบ
- **📄 อ่านไฟล์จาก path** — พิมพ์ path ไฟล์/โฟลเดอร์ในแชท → backend อ่านให้ (text/CSV/Excel/HTML-xls เช่น AMR)

---

## 🗂 โครงสร้างไฟล์ (D:\LocalAI\)
```
lung_pee.bat / Start-LocalAI.bat   ตัวเปิดโปรแกรม (ASCII+CRLF)
lung_pee.ico                       ไอคอน AI
ollama\                            Ollama portable (GPU)
models\                            โมเดล 6 ตัว
ui\chat.html                       หน้าเว็บแชท (เสิร์ฟผ่าน http)
ui\lib\                            pdf.js, xlsx, chart.js (offline)
ui\plugins\                        ระบบปลั๊กอิน
tts-server.py                      backend: เสียง Neural + เสิร์ฟ UI + /file + /clip
clipgen.py                         ประกอบคลิป (รูป+เสียง+ffmpeg)
tools\ffmpeg\                      ffmpeg (ตัดต่อวิดีโอ)
tools\fonts\Sarabun-Regular.ttf    ฟอนต์ซับไทย
tools\music\ambient.mp3            เพลงประกอบดีฟอลต์
tools\msty\Msty_x64.exe            ตัวติดตั้ง Msty
clips\ chats\ memory\ knowledge\   ผลลัพธ์/ข้อมูล
```

## 🔌 Backend endpoints (tts-server.py, port 11435)
| endpoint | ทำอะไร |
|---|---|
| `GET /` | เสิร์ฟ chat.html |
| `GET /tts?voice=&text=` | เสียง Neural (เปรมวดี/นิวัตน์) → mp3 |
| `GET /voices` | รายชื่อเสียงไทย |
| `GET /file?path=` | อ่านไฟล์/โฟลเดอร์ในเครื่อง (text/CSV/Excel) |
| `POST /clip` | สร้างคลิป (scenes → mp4) |

---

## 🖥 UI ทางเลือก (ต่อ Ollama เดียวกัน)
1. **chat.html** — พกพา + สร้างสื่อครบ (กราฟ/รูป/คลิป/เสียง)
2. **Msty** (ติดตั้งแล้ว) — UI สำเร็จรูป auto-detect Ollama ที่ localhost:11434 → เห็นโมเดล 6 ตัว ใช้ GPU
   - อย่ากด "SETUP LOCAL AI" (เอนจิน CPU ในตัว Msty ที่เราไม่ใช้)
   - ตั้ง Context Window Size = 4096 (ติ๊ก checkbox ก่อน แล้ว Apply) เพื่อความเร็ว
- ทางเลือกง่ายอื่น: Chatbox, Page Assist (extension), Continue (VS Code)

---

## ⚙️ เคล็ดลับ VRAM 4GB
- `OLLAMA_FLASH_ATTENTION=1`, `OLLAMA_KV_CACHE_TYPE=q8_0`, `OLLAMA_ORIGINS=*` (ตั้งใน .bat แล้ว)
- Context 4096 (ไม่ใช่ 8192) → 100% GPU
- อย่าสลับโมเดลบ่อย (โหลดจาก HDD ช้า)
- ปิดแอปที่กิน GPU (เบราว์เซอร์แท็บเยอะ)

## 🔧 แก้ปัญหาที่เจอบ่อย
| อาการ | แก้ |
|---|---|
| เชื่อมต่อ Ollama ไม่ได้ | เปิด lung_pee.bat ค้างไว้ + เปิดผ่าน http://127.0.0.1:11435/ |
| เสียง Neural ไม่ออก | ต้องต่อเน็ต + tts-server ทำงาน (Python) |
| สร้างคลิปไม่ได้ | ต้องมี Python + ffmpeg + เน็ต (มี fallback พื้นหลังถ้ารูปล่ม) |
| .bat เพี้ยน | ต้องเป็น ASCII + CRLF (แก้แล้ว) |

---

## 🧭 หลักการทำงาน (Git Workflow)
งานเขียนโค้ด/สร้างคลิปสั้น ยึด: **1 Task = 1 Branch = 1 Worktree = 1 PR**
ข้อบังคับ: **ห้ามเขียนโค้ด/โปรแกรมลง C:\** — ไฟล์งานทั้งหมดอยู่บน D:

---
*สร้างโดยทีมงาน + Claude — ระบบพร้อมใช้งานเต็มรูปแบบ 🎯*
