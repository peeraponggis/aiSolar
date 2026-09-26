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


async def ollama_generate(prompt: str, model: str | None = None) -> str:
    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(
            f"{OLLAMA_API}/api/generate",
            json={"model": model or OLLAMA_MODEL, "prompt": prompt, "stream": False},
        )
        resp.raise_for_status()
        return resp.json()["response"]


async def generate_script(project_id: str, topic: str, voice: str = "female",
                          persona: str = "", custom_script: str = "",
                          mode: str = "narration") -> str:
    if custom_script.strip():
        script = custom_script.strip()
        project_dir = os.path.join("projects", project_id)
        os.makedirs(project_dir, exist_ok=True)
        with open(os.path.join(project_dir, "script.txt"), "w", encoding="utf-8") as f:
            f.write(script)
        return script

    brainstorm_context = await generate_brainstorm(topic)
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
เขียนสคริปต์ YouTube Shorts แบบ **บทสนทนา 2 คน** (45-60 วินาที) หัวข้อ: {topic}
{persona_block}
## ข้อมูลจากการระดมสมอง
{brainstorm_context}

## ตัวละคร
- A = คนอธิบาย (รู้เรื่องดี พูดเข้าใจง่าย)
- B = คนถาม (สงสัย อยากรู้ เป็นตัวแทนผู้ชม)

## รูปแบบ output (ตอบเฉพาะบทสนทนา ไม่ต้องมีคำอธิบายเพิ่ม)
เขียนบทสนทนา 12-18 บรรทัด โดยแต่ละบรรทัดขึ้นต้นด้วย A: หรือ B:
สำคัญมาก: แต่ละบรรทัดต้องเป็นประโยคยาว 20-40 ตัวอักษร (ไม่สั้นเกิน) เพื่อให้ได้ความยาวรวม 45-60 วินาที
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
เขียนสคริปต์ YouTube Shorts (45-60 วินาที) หัวข้อ: {topic}
{persona_block}
## ข้อมูลจากการระดมสมอง
{brainstorm_context}

## รูปแบบ output (ตอบเฉพาะส่วนนี้ ไม่ต้องมีคำอธิบายเพิ่ม)
[Hook 3 วินาที] — ประโยคเปิดที่ทำให้คนหยุดเลื่อน
[ปัญหา 10 วินาที] — ปัญหาจริงที่คนเจอ
[วิธีแก้ 15 วินาที] — อธิบายว่าเครื่องมือนี้ทำงานยังไง
[ประโยชน์ 10 วินาที] — ทำไมถึงควรใช้
[CTA 7 วินาที] — บอกให้กดติดตาม/ไลค์/คอมเมนต์ จบด้วยคำว่า "{polite_particle}"

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
