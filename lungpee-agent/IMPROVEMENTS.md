# ลุงพี Agent — บันทึกการปรับปรุงและแนวทางพัฒนาต่อ

> อัปเดต: 2026-10-15 | Branch: master

---

## สิ่งที่ทำเสร็จแล้ว (Phase 4)

### Goal 1 — ความปลอดภัย: ปิดกั้น Delete/Remove/Erase (3 ชั้น)

| ชั้น | ไฟล์ | กลไก |
|------|------|------|
| 1 | `agent.py` | `_DESTRUCTIVE_RE` pre-screen ก่อนส่งโมเดล → ตอบทันทีไม่เสีย inference |
| 2 | `safety.py` | `HARD_BLOCKED_TOOLS` + `_DESTRUCTIVE_SHELL_RE` → ปฏิเสธแม้โมเดลพยายาม call |
| 3 | `agent.py` | `SYSTEM_PROMPT` มีคำสั่งห้ามเรียก `delete_file` โดยตรง |

**ผลลัพธ์**: คำสั่ง "ลบไฟล์", "delete", "remove-item", "erase" ถูกปฏิเสธทันที ไม่มี dialog ไม่มี inference round-trip

---

### Goal 2 — ความเร็ว

| การเปลี่ยนแปลง | ไฟล์ | ผลที่คาดหวัง |
|---------------|------|-------------|
| TTS first-chunk threshold 60→15 ตัวอักษร | `agent.py` | เริ่มพูดเร็วขึ้น ~300ms |
| edge-tts max_retries 5→2 | `tts_engine.py` | ลด worst-case wait จาก 4s → <1s |
| Two-phase warm-up (text + tool-calling path) | `ollama_client.py` | first-tool latency ลดจาก ~800ms → ~300ms |

---

### Goal 3 — ความเข้าใจคำสั่ง

| การเปลี่ยนแปลง | ไฟล์ | ผลที่คาดหวัง |
|---------------|------|-------------|
| `normalize_command()`: แก้ STT errors + ตัด prefix | `agent.py` | ลด "ลงพี่/ลงคี่/หลุงพี" misfire, แก้ชื่อโปรแกรมเพี้ยน |
| Tool hint injection (hint ไม่บันทึกใน history) | `agent.py` | โมเดล 4B เลือก tool แม่น ~40-60% ดีขึ้น |
| Richer tool descriptions + Thai trigger phrases | `tool_registry.py` | `launch_app`, `find_file`, `run_shell` ชัดขึ้น |
| เพิ่ม vocabulary hints | `voice_vocab.txt` | Whisper แม่นขึ้นสำหรับ "รันคำสั่ง", "ค้นหาไฟล์" ฯลฯ |

---

### Goal 4 — คุณภาพระยะยาว

| การเปลี่ยนแปลง | ไฟล์ | รายละเอียด |
|---------------|------|-----------|
| Persistent settings | `settings.py` (ใหม่) | บันทึก voice/rate/model/notes ไว้ที่ `%APPDATA%\lungpee-agent\settings.json` |
| "จำไว้ว่า..." trigger | `agent.py` | บันทึก notes instant, inject เข้า system prompt ทุก turn |
| Default voice เป็น SAPI offline | `settings.py` | "ปัตตรา" เป็น default (เร็ว ~0.2s แทน edge-tts ที่ช้า 5-10s) |
| Duplicate tool-call detection | `agent.py` | ป้องกัน infinite loop เมื่อโมเดลเรียก tool ซ้ำ args เดิม |
| FALLBACK_MODELS เพิ่ม 8B path | `ollama_client.py` | รองรับ upgrade เป็น typhoon2.5-qwen3-8b |

---

## สถาปัตยกรรมปัจจุบัน (หลัง Phase 4)

```
User input (voice/text)
    │
    ├─ "จำไว้ว่า..." → บันทึก notes → speak ทันที
    │
    ├─ Destructive pre-screen (_DESTRUCTIVE_RE) → ปฏิเสธทันที
    │
    ├─ normalize_command() → แก้ STT + ตัด prefix
    │
    ├─ _get_tool_hint() → เพิ่ม hint ใน user message (ไม่บันทึก history)
    │
    └─ Ollama LLM (stream) → tool-calling loop (max 8 รอบ)
            │
            ├─ safety.check() → HARD_BLOCKED_TOOLS / destructive shell → ปฏิเสธ
            │
            ├─ duplicate tool-call detector → ป้องกัน infinite loop
            │
            └─ execute_tool() → result → next LLM turn
```

---

## ไฟล์ที่แก้ไข

| ไฟล์ | สิ่งที่เปลี่ยน |
|------|--------------|
| [`agent.py`](agent.py) | +`import re`, +`import settings`, เพิ่ม constants/functions ทุก Goal, แก้ `handle_command`, `stream_speak_piece`, `_stream_speak` |
| [`safety.py`](safety.py) | +`import re`, `HARD_BLOCKED_TOOLS`, `_DESTRUCTIVE_SHELL_RE`, แก้ `check()` |
| [`tts_engine.py`](tts_engine.py) | `max_retries` 5→2 |
| [`tool_registry.py`](tool_registry.py) | richer descriptions สำหรับ `launch_app`, `find_file`, `run_shell`, `delete_file` |
| [`voice_vocab.txt`](voice_vocab.txt) | เพิ่ม 14 คำ/วลีใหม่ |
| [`ollama_client.py`](ollama_client.py) | two-phase `warm_up()`, เพิ่ม `scb10x/typhoon2.5-qwen3-8b` ใน FALLBACK_MODELS |
| [`settings.py`](settings.py) | **ไฟล์ใหม่** — persistent settings module |

---

## แนวทางพัฒนาต่อ (Phase 5+)

### ความสำคัญสูง

#### 1. Parallel Tier-A tool execution
ปัจจุบัน tools ทำงานแบบ sequential ทีละอย่าง  
แก้ใน `agent.py` `handle_command()`: แยก Tier A (read-only) ไป run พร้อมกันด้วย `ThreadPoolExecutor`
```python
TIER_A_TOOLS = frozenset({"list_dir", "find_file", "read_file", "list_ui_controls"})
# run tier_a ใน parallel, tier_bc sequential
```
**ผลที่คาดหวัง**: `find_file` + `read_file` ในรอบเดียว ลดเวลา 5-15 วินาที

#### 2. Context window ขยายตามโมเดล
`NUM_CTX = 4096` ใน `ollama_client.py` กำหนดตายตัว  
ควรทำ dynamic: ถ้าโมเดลมี VRAM มากพอให้ขยายเป็น 8192 หรือ 16384
```python
NUM_CTX = int(os.environ.get("LUNGPEE_CTX", "4096"))
```

#### 3. Tool result summarization
ผล `find_file` ที่ยาวมาก (20 ไฟล์) ดัน context เต็มเร็ว  
ควรตัด/สรุปก่อนใส่ใน message history

---

### ความสำคัญปานกลาง

#### 4. Wake-word (ถ้าต้องการ)
วิธีที่ง่ายที่สุดบน Windows:
- **Porcupine (Picovoice)** free tier: 1 custom wake word, offline, ~30MB
- หรือ **Silero VAD + Whisper tiny**: ตรวจ voice onset → ถอดเสียง 1.5s แรก

ต้องเพิ่ม always-on mic thread ใน `voice_input.py` คู่กับ push-to-talk เดิม

#### 5. Model upgrade
| VRAM | Model | Tool accuracy |
|------|-------|---------------|
| 4GB | typhoon2.5-qwen3-4b (ปัจจุบัน) | ~70% |
| 6-8GB | **typhoon2.5-qwen3-8b** | ~85% |
| 12GB+ | qwen2.5:14b-instruct | ~95% |

เปลี่ยนด้วย: `set LUNGPEE_MODEL=scb10x/typhoon2.5-qwen3-8b` ก่อนเปิดโปรแกรม

#### 6. Settings UI ในถาดระบบ
ตอนนี้ settings.json เปลี่ยนได้แค่ผ่าน "จำไว้ว่า..." หรือแก้ไฟล์โดยตรง  
เพิ่มใน pystray menu: เลือกเสียง (ปัตตรา/เปรมวดี/นิวัฒน์), อัตราเร็ว, และ clear notes

---

### ความสำคัญต่ำ / ระยะยาว

#### 7. Vision capability
ปัจจุบัน UI automation อาศัย accessibility tree (pywinauto UIA) ซึ่งล้มเหลวกับ apps ที่ expose accessibility ไม่ดี  
ทางเลือก: เพิ่ม screenshot → LLM multimodal (ต้องโมเดล vision เช่น llava หรือ qwen2-vl)

#### 8. Persistent conversation memory (selective)
"จำไว้ว่า..." ตอนนี้รองรับ 1 notes string เดียว  
ขยายเป็น key-value store: "จำชื่อโปรเจกต์ว่า Pi_BoQ", "จำว่าฉันชอบเสียงเร็ว" ฯลฯ

#### 9. Multi-file translation pipeline
ตอนนี้แปลได้ทีละไฟล์เท่านั้น  
เพิ่ม tool `translate_folder`: loop `list_dir` + `translate_file` แบบ batch พร้อม progress report

---

## วิธีทดสอบ

```bash
cd F:\LocalAI\lungpee-agent
python agent.py
```

| Test case | คาดหวัง |
|-----------|---------|
| พูด "ลบไฟล์ test.txt" | ได้ยินคำปฏิเสธทันที ไม่มี dialog ไม่มีเสียง LLM processing |
| พูด "delete this file" | เหมือนข้างบน |
| พูด "remove-item C:\test" | เหมือนข้างบน |
| พูด "จำไว้ว่าโปรเจกต์ชื่อ Pi" | ได้ยิน "จำไว้แล้วครับว่า โปรเจกต์ชื่อ Pi" |
| พูด "เปิดโน้ตแพด" | hint → launch_app, เปิด notepad |
| พูด "หาไฟล์ชื่อ resume" | hint → find_file, ค้นหาทันที |
| ปิด-เปิดโปรแกรม | เสียงกลับเป็น "ปัตตรา" (SAPI offline, เร็ว) |

ดู log ที่ `lungpee-agent.log` หา:
- `"BLOCKED (hard)"` — delete_file ถูกบล็อก
- `"BLOCKED (destructive shell)"` — run_shell ที่มีคำสั่งลบ
- `"pre-screen: destructive intent"` — ถูก pre-screen ก่อนถึงโมเดล
- `"tool hint:"` — hint inject ทำงาน
