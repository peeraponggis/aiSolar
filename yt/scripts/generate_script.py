import json
import os
from pathlib import Path
import httpx
from dotenv import load_dotenv
from scripts.brainstorm import generate_brainstorm

_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_ENV_PATH)

OLLAMA_API = os.getenv("OLLAMA_API", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "scb10x/typhoon2.5-qwen3-4b:latest")

DURATION_PRESETS = {
    "short": {
        "label_th": "Shorts 45-60 วินาที",
        "duration_text": "45-60 วินาที",
        "dialogue_lines": "12-18",
        "media_count": 4,
        "char_warn": 400,
        "char_over": 480,
        "timeout": 600,
    },
    "medium": {
        "label_th": "ปานกลาง 2-3 นาที",
        "duration_text": "2-3 นาที (120-180 วินาที)",
        "dialogue_lines": "30-50",
        "media_count": 8,
        "char_warn": 960,
        "char_over": 1440,
        "timeout": 900,
    },
    "long": {
        "label_th": "ยาว 3-5 นาที",
        "duration_text": "3-5 นาที (180-300 วินาที)",
        "dialogue_lines": "50-80",
        "media_count": 12,
        "char_warn": 1440,
        "char_over": 2400,
        "timeout": 1200,
    },
}


async def ollama_generate(prompt: str, model: str | None = None) -> str:
    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(
            f"{OLLAMA_API}/api/generate",
            json={"model": model or OLLAMA_MODEL, "prompt": prompt, "stream": False},
        )
        resp.raise_for_status()
        return resp.json()["response"]


def _get_section_template(duration_preset: str, polite_particle: str) -> str:
    if duration_preset == "long":
        return (
            f'[Hook 5 วินาที] — ประโยคเปิดที่ทำให้คนหยุดเลื่อน\n'
            f'[ปัญหา 30 วินาที] — ปัญหาจริงที่คนเจอ (ยกตัวอย่าง 2-3 ข้อ)\n'
            f'[ภาพรวม 20 วินาที] — แนะนำเครื่องมือหรือวิธีแก้\n'
            f'[วิธีแก้ 1 — 40 วินาที] — อธิบายวิธีแรกอย่างละเอียด\n'
            f'[วิธีแก้ 2 — 40 วินาที] — อธิบายวิธีที่สอง\n'
            f'[วิธีแก้ 3 — 30 วินาที] — อธิบายวิธีที่สาม\n'
            f'[เปรียบเทียบ 20 วินาที] — เปรียบเทียบข้อดี-ข้อเสีย\n'
            f'[ตัวอย่างจริง 25 วินาที] — ยกตัวอย่างการใช้งานจริง\n'
            f'[คำแนะนำ 15 วินาที] — แนะนำสิ่งที่ควรทำ/ไม่ควรทำ\n'
            f'[สรุป 15 วินาที] — สรุปประเด็นทั้งหมด\n'
            f'[CTA 10 วินาที] — บอกให้กดติดตาม/ไลค์/คอมเมนต์ จบด้วยคำว่า "{polite_particle}"'
        )
    if duration_preset == "medium":
        return (
            f'[Hook 5 วินาที] — ประโยคเปิดที่ทำให้คนหยุดเลื่อน\n'
            f'[ปัญหา 20 วินาที] — ปัญหาจริงที่คนเจอ (ยกตัวอย่าง 2 ข้อ)\n'
            f'[วิธีแก้ 1 — 30 วินาที] — อธิบายวิธีแรก\n'
            f'[วิธีแก้ 2 — 30 วินาที] — อธิบายวิธีที่สอง\n'
            f'[ประโยชน์ 20 วินาที] — ทำไมถึงควรใช้ ยกตัวเลขจริง\n'
            f'[ตัวอย่าง 15 วินาที] — ยกตัวอย่างการใช้งานจริง\n'
            f'[สรุป 10 วินาที] — สรุปสั้นๆ\n'
            f'[CTA 10 วินาที] — บอกให้กดติดตาม/ไลค์/คอมเมนต์ จบด้วยคำว่า "{polite_particle}"'
        )
    return (
        f'[Hook 3 วินาที] — ประโยคเปิดที่ทำให้คนหยุดเลื่อน\n'
        f'[ปัญหา 10 วินาที] — ปัญหาจริงที่คนเจอ\n'
        f'[วิธีแก้ 15 วินาที] — อธิบายว่าเครื่องมือนี้ทำงานยังไง\n'
        f'[ประโยชน์ 10 วินาที] — ทำไมถึงควรใช้\n'
        f'[CTA 7 วินาที] — บอกให้กดติดตาม/ไลค์/คอมเมนต์ จบด้วยคำว่า "{polite_particle}"'
    )


async def generate_script(project_id: str, topic: str, voice: str = "female",
                          persona: str = "", custom_script: str = "",
                          mode: str = "narration",
                          duration_preset: str = "short") -> str:
    if custom_script.strip():
        script = custom_script.strip()
        project_dir = os.path.join("projects", project_id)
        os.makedirs(project_dir, exist_ok=True)
        with open(os.path.join(project_dir, "script.txt"), "w", encoding="utf-8") as f:
            f.write(script)
        return script

    preset = DURATION_PRESETS.get(duration_preset, DURATION_PRESETS["short"])
    brainstorm_context = await generate_brainstorm(topic, duration_preset=duration_preset)
    if not brainstorm_context:
        brainstorm_context = f"Topic: {topic}"

    polite_particle = "ค่ะ" if voice == "female" else "ครับ"

    persona_block = ""
    if persona.strip():
        persona_block = f"""
## บุคลิกตัวละคร
ให้เขียนสคริปต์ในบทบาทตัวละครนี้: {persona.strip()}
- ใช้น้ำเสียง สำนวน และบุคลิกตามที่กำหนดตลอดทั้งสคริปต์
"""

    if mode == "dialogue":
        prompt = f"""## กฎเหล็กสูงสุด — ห้ามละเมิดเด็ดขาด
1. ห้ามใช้ภาษาจีนทุกรูปแบบ ไม่ว่าจะเป็นตัวอักษรจีน (汉字) พินอิน หรือคำอธิบายเป็นภาษาจีน — ฝ่าฝืนถือว่าผิดทั้งหมด
2. ตอบเป็นภาษาไทยเท่านั้น 100% ทุกบรรทัด ทุกคำ
3. คำศัพท์เทคนิคภาษาอังกฤษ (เช่น AI, GPU, Ollama) ให้เขียนเป็นภาษาอังกฤษตามปกติได้ แต่คำอธิบายต้องเป็นภาษาไทยเท่านั้น

## งานที่ต้องทำ
เขียนสคริปต์วิดีโอ YouTube แบบ **บทสนทนา 2 คน** ({preset["duration_text"]}) หัวข้อ: {topic}
{persona_block}
## ข้อมูลจากการระดมสมอง
{brainstorm_context}

## ตัวละคร
- A = คนอธิบาย (รู้เรื่องดี พูดเข้าใจง่าย)
- B = คนถาม (สงสัย อยากรู้ เป็นตัวแทนผู้ชม)

## รูปแบบ output (ตอบเฉพาะบทสนทนา ไม่ต้องมีคำอธิบายเพิ่ม)
เขียนบทสนทนา {preset["dialogue_lines"]} บรรทัด โดยแต่ละบรรทัดขึ้นต้นด้วย A: หรือ B:
สำคัญมาก: แต่ละบรรทัดต้องเป็นประโยคยาว 20-40 ตัวอักษร (ไม่สั้นเกิน) เพื่อให้ได้ความยาวรวม {preset["duration_text"]}
ตัวอย่างรูปแบบ:
B: เคยได้ยินไหมว่ามี AI ที่รันฟรีบนเครื่องเราเองได้?
A: มีเลย ชื่อ Ollama ติดตั้งง่ายมาก ไม่ต้องใช้อินเทอร์เน็ตเลย
B: แล้วมันทำอะไรได้บ้างล่ะ เร็วไหม?
A: ได้ 39 โทเค็นต่อวินาที สร้างข้อความ สรุปเอกสาร เขียนโค้ดได้หมด

## สไตล์การเขียน
- ภาษาไทยง่ายๆ เหมือนเพื่อนคุยกัน
- B ถามประโยคเต็มๆ ไม่สั้นจนเกินไป
- A ตอบอธิบายละเอียด มีตัวเลขหรือตัวอย่างจริง
- เริ่มด้วย B ถามสิ่งที่ทำให้คนสนใจ (Hook)
- จบด้วย A บอกให้กดติดตาม
- ห้ามใช้ภาษาจีนเด็ดขาด ตอบภาษาไทยเท่านั้น"""
    else:
        prompt = f"""## กฎเหล็กสูงสุด — ห้ามละเมิดเด็ดขาด
1. ห้ามใช้ภาษาจีนทุกรูปแบบ ไม่ว่าจะเป็นตัวอักษรจีน (汉字) พินอิน หรือคำอธิบายเป็นภาษาจีน — ฝ่าฝืนถือว่าผิดทั้งหมด
2. ตอบเป็นภาษาไทยเท่านั้น 100% ทุกบรรทัด ทุกคำ
3. คำศัพท์เทคนิคภาษาอังกฤษ (เช่น AI, GPU, Ollama) ให้เขียนเป็นภาษาอังกฤษตามปกติได้ แต่คำอธิบายต้องเป็นภาษาไทยเท่านั้น

## งานที่ต้องทำ
เขียนสคริปต์วิดีโอ YouTube ({preset["duration_text"]}) หัวข้อ: {topic}
{persona_block}
## ข้อมูลจากการระดมสมอง
{brainstorm_context}

## รูปแบบ output (ตอบเฉพาะส่วนนี้ ไม่ต้องมีคำอธิบายเพิ่ม)
{_get_section_template(duration_preset, polite_particle)}

## สไตล์การเขียน
- ใช้ภาษาไทยที่เข้าใจง่าย เหมือนพูดกับเพื่อน
- ห้ามเขียนแบบวิชาการ
- เจาะจง ไม่กว้างเกินไป ยกตัวเลขหรือตัวอย่างจริง
- ประโยคสุดท้ายของสคริปต์ต้องจบด้วย "{polite_particle}" เสมอ
- ย้ำอีกครั้ง: ห้ามใช้ภาษาจีนเด็ดขาด ตอบภาษาไทยเท่านั้น"""

    script = await ollama_generate(prompt)

    if mode != "dialogue":
        wrong_particle = "ครับ" if voice == "female" else "ค่ะ"
        script = script.replace(wrong_particle, polite_particle)

        script = script.rstrip()
        if not script.endswith(polite_particle):
            last_char = script[-1] if script else ""
            if last_char in ("!", "。", "！", ".", "?", "？"):
                script = script[:-1]
            script = script.rstrip() + polite_particle

    project_dir = os.path.join("projects", project_id)
    os.makedirs(project_dir, exist_ok=True)
    with open(os.path.join(project_dir, "script.txt"), "w", encoding="utf-8") as f:
        f.write(script)

    return script
