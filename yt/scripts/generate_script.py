# ============================================================================
# ProInventive Suite
# Copyright (C) 2024-2569 ProInventive. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL
# Unauthorized use, copying, or distribution is prohibited.
# Author: Peerapong (Lungpee) -- ProInventive -- giskku@gmail.com
# ============================================================================

import os
import re
from pathlib import Path
from typing import Callable
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
        "min_s": 30,
        "max_s": 80,
    },
    "medium": {
        "label_th": "ปานกลาง 2-3 นาที",
        "duration_text": "2-3 นาที (120-180 วินาที)",
        "dialogue_lines": "30-50",
        "media_count": 8,
        "char_warn": 960,
        "char_over": 1440,
        "min_s": 90,
        "max_s": 225,
    },
    "long": {
        "label_th": "ยาว 3-5 นาที",
        "duration_text": "3-5 นาที (180-300 วินาที)",
        "dialogue_lines": "50-80",
        "media_count": 12,
        "char_warn": 1440,
        "char_over": 2400,
        "min_s": 135,
        "max_s": 375,
    },
}


async def ollama_generate(prompt: str, model: str | None = None, json_output: bool = False) -> str:
    # keep_alive=0 unloads the model right away so the 4 GB GPU is free for
    # the voice-clone step that follows.
    body = {"model": model or OLLAMA_MODEL, "prompt": prompt, "stream": False, "keep_alive": 0}
    if json_output:
        body["format"] = "json"
    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(f"{OLLAMA_API}/api/generate", json=body)
        resp.raise_for_status()
        return resp.json()["response"]


def _spoken_length(script: str) -> int:
    text = re.sub(r"\[.*?\]", "", script)
    text = re.sub(r"^[AB]\s*[:：]", "", text, flags=re.M)
    return len(re.sub(r"\s+", "", text))


async def _shorten_if_too_long(script: str, preset: dict, mode: str,
                               log: Callable | None) -> str:
    length = _spoken_length(script)
    if length <= preset["char_over"]:
        return script
    if log:
        log(f"สคริปต์ยาว {length} ตัวอักษร (เกิน {preset['char_over']}) — กำลังย่อให้พอดีเวลา", "warning")
    keep_format = ("คงรูปแบบ A:/B: ทุกบรรทัด" if mode == "dialogue"
                   else "คงหัวข้อในวงเล็บ [ ] ทุกส่วนไว้เหมือนเดิม")
    prompt = (
        f"ย่อสคริปต์ด้านล่างให้เหลือเนื้อหาพูดไม่เกิน {preset['char_warn']} ตัวอักษร "
        f"(สำหรับวิดีโอ {preset['duration_text']}) โดยเก็บประเด็นสำคัญ ตัวเลข และ CTA ตอนจบไว้ "
        f"{keep_format} ตอบเฉพาะสคริปต์ภาษาไทยที่ย่อแล้วเท่านั้น\n\n{script}"
    )
    shorter = (await ollama_generate(prompt)).strip()
    if shorter and _spoken_length(shorter) < length:
        return shorter
    return script


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
                          duration_preset: str = "short",
                          log: Callable | None = None) -> str:
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
        if log:
            log("Gemini ไม่ตอบ — ให้ Ollama เขียนสคริปต์จากหัวข้ออย่างเดียว", "warning")

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
    script = await _shorten_if_too_long(script, preset, mode, log)

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


# ── Scene scripts (auto modes) ──
# The script comes back as scenes: what is said + an English stock-footage
# query for what is shown, plus post text. One scene = one media item.

_CJK = re.compile(r"[\u3400-\u9fff]")
_IMAGE_STYLE = "photorealistic, natural light, high detail, vertical composition, no text, no watermark"


def _parse_json(raw: str | None) -> dict | None:
    import json
    if not raw:
        return None
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
    try:
        data = json.loads(raw)
    except ValueError:
        m = re.search(r"\{.*\}", raw, re.S)
        try:
            data = json.loads(m.group(0)) if m else None
        except ValueError:
            data = None
    return data if isinstance(data, dict) else None


async def _llm_json(prompt: str, log: Callable | None) -> dict | None:
    """Gemini first (better Thai), local Ollama as fallback."""
    from scripts.brainstorm import gemini_generate
    data = _parse_json(await gemini_generate(prompt, json_output=True, timeout=90))
    if data is None:
        if log:
            log("Gemini ไม่ตอบ — ใช้ Ollama เขียนแทน", "warning")
        try:
            data = _parse_json(await ollama_generate(prompt, json_output=True))
        except httpx.HTTPError:
            data = None
    return data


def _scene_problems(data: dict | None, n: int, preset: dict, mode: str) -> list[str]:
    if not data or not isinstance(data.get("scenes"), list):
        return ["ไม่ได้ตอบเป็น JSON ตามรูปแบบ"]
    scenes = data["scenes"]
    problems = []
    if len(scenes) != n:
        problems.append(f"ต้องมี {n} ฉากพอดี แต่ได้ {len(scenes)} ฉาก")
    for i, s in enumerate(scenes, 1):
        if not isinstance(s, dict) or not str(s.get("text", "")).strip():
            problems.append(f"ฉาก {i} ไม่มีข้อความ")
        elif not str(s.get("visual", "")).strip():
            problems.append(f"ฉาก {i} ไม่มี visual")
        elif mode == "dialogue" and not re.match(r"^\s*[AB]\s*[:：]", str(s["text"])):
            problems.append(f"ฉาก {i} ต้องเป็นบรรทัด A:/B:")
    text = "\n".join(str(s.get("text", "")) for s in scenes if isinstance(s, dict))
    length = _spoken_length(text)
    if length > preset["char_over"]:
        problems.append(f"ยาว {length} ตัวอักษร เกินกำหนด {preset['char_over']} — ตัดให้สั้นลง")
    elif length < preset["char_warn"] * 0.6:
        problems.append(f"สั้นไป ({length} ตัวอักษร) — ควรประมาณ {preset['char_warn']}")
    if _CJK.search(text):
        problems.append("มีอักษรจีน — ต้องเป็นภาษาไทยเท่านั้น")
    if not str(data.get("title", "")).strip():
        problems.append("ไม่มี title")
    return problems


def _scene_prompt(topic: str, n: int, preset: dict, mode: str, particle: str,
                  persona: str, context: str) -> str:
    target = (preset["char_warn"] + preset["char_over"]) // 2
    if mode == "dialogue":
        speech_rule = ("แต่ละฉาก text เป็นบทสนทนาหลายบรรทัด ขึ้นต้นด้วย A: (คนอธิบาย) "
                       "หรือ B: (คนถาม) คั่นบรรทัดด้วย \\n")
    else:
        speech_rule = "แต่ละฉาก text คือคำพูดบรรยาย 1-3 ประโยค"
    persona_rule = f"\n- บุคลิกผู้พูด: {persona.strip()}" if persona.strip() else ""
    return (
        f"เขียนสคริปต์วิดีโอ YouTube ภาษาไทย ({preset['duration_text']}) หัวข้อ: {topic}\n\n"
        f"ข้อมูลประกอบ:\n{context}\n\n"
        "ตอบเป็น JSON object เท่านั้น รูปแบบ:\n"
        '{"title": "ชื่อคลิปภาษาไทย ไม่เกิน 60 ตัวอักษร ชวนคลิก",\n'
        ' "scenes": [{"text": "คำพูดของฉากนี้", "visual": "English stock footage search query"}],\n'
        ' "description": "คำอธิบายคลิปสำหรับโพสต์ 2-3 บรรทัด",\n'
        ' "hashtags": ["#แฮชแทก"]}\n\n'
        "กฎ:\n"
        f"- ต้องมี {n} ฉากพอดี ฉากแรกเป็น Hook ดึงความสนใจ ฉากสุดท้ายเป็น CTA ชวนกดติดตาม ลงท้ายด้วย \"{particle}\"\n"
        f"- {speech_rule}\n"
        f"- ความยาวคำพูดรวมทุกฉากประมาณ {target} ตัวอักษร (ห้ามเกิน {preset['char_over']})\n"
        f"- ภาษาไทยเท่านั้น ห้ามมีอักษรจีน ใช้ภาษาพูดเข้าใจง่าย มีตัวเลขหรือตัวอย่างจริง{persona_rule}\n"
        "- visual: ภาษาอังกฤษ 2-5 คำ บอกสิ่งที่ถ่ายเป็นภาพได้จริงตรงกับเนื้อหาฉากนั้น "
        "(คน สิ่งของ การกระทำ สถานที่) ห้ามเป็นคำนามธรรม แต่ละฉากต้องไม่ซ้ำกัน\n"
        "- hashtags 5-8 อัน"
    )


async def _custom_scene_meta(topic: str, texts: list[str], log: Callable | None) -> dict:
    numbered = "\n".join(f"{i + 1}. {t[:400]}" for i, t in enumerate(texts))
    prompt = (
        f"สำหรับสคริปต์วิดีโอหัวข้อ \"{topic}\" ที่แบ่งเป็นฉากด้านล่าง ตอบ JSON object รูปแบบ "
        '{"visuals": ["English stock footage query, 2-5 concrete visual words, one per scene"], '
        '"title": "ชื่อคลิปภาษาไทย ไม่เกิน 60 ตัวอักษร", "description": "คำอธิบาย 2-3 บรรทัด", '
        '"hashtags": ["#..."]} '
        f"visuals ต้องมี {len(texts)} รายการตามลำดับฉาก\n\n{numbered}"
    )
    return await _llm_json(prompt, log) or {}


async def generate_scene_script(project_id: str, topic: str, voice: str = "female",
                                persona: str = "", custom_script: str = "",
                                mode: str = "narration", duration_preset: str = "short",
                                scene_count: int | None = None,
                                log: Callable | None = None) -> dict:
    """Returns {"scenes": [{"text", "visual"}], "title", "description", "hashtags",
    "problems", "script"}. Scene text is already normalised for speech."""
    import json
    from scripts.script_tools import normalize_for_speech, split_scenes

    preset = DURATION_PRESETS.get(duration_preset, DURATION_PRESETS["short"])
    n = scene_count or preset["media_count"]
    particle = "ค่ะ" if voice == "female" else "ครับ"
    custom = custom_script.strip()

    if custom:
        if mode == "dialogue":
            texts = [p.strip() for p in re.split(r"\n\s*\n", custom) if p.strip()]
        else:
            texts = split_scenes(custom, n)
        meta = await _custom_scene_meta(topic, texts, log)
        visuals = meta.get("visuals") if isinstance(meta.get("visuals"), list) else []
        data = {
            "scenes": [{"text": t, "visual": str(visuals[i]) if i < len(visuals) else topic}
                       for i, t in enumerate(texts)],
            "title": meta.get("title") or topic,
            "description": meta.get("description") or "",
            "hashtags": meta.get("hashtags") or [],
            "problems": [],
        }
        if log:
            log(f"ใช้สคริปต์กำหนดเอง — แบ่งเป็น {len(texts)} ฉาก")
    else:
        context = await generate_brainstorm(topic, duration_preset=duration_preset) or f"Topic: {topic}"
        prompt = _scene_prompt(topic, n, preset, mode, particle, persona, context)
        data = await _llm_json(prompt, log)
        problems = _scene_problems(data, n, preset, mode)
        for round_no in range(2):
            if not problems:
                break
            if log:
                log(f"ตรวจสคริปต์รอบ {round_no + 1}: " + "; ".join(problems[:3]), "warning")
            previous = json.dumps(data, ensure_ascii=False) if data else "(ไม่มี)"
            fix = (f"{prompt}\n\nคำตอบก่อนหน้านี้มีปัญหา: {'; '.join(problems)}\n"
                   f"แก้ให้ถูกต้องครบทุกข้อ แล้วตอบ JSON ทั้งหมดใหม่\nคำตอบก่อนหน้า:\n{previous}")
            fixed = await _llm_json(fix, log)
            fixed_problems = _scene_problems(fixed, n, preset, mode)
            if fixed and len(fixed_problems) <= len(problems):
                data, problems = fixed, fixed_problems
        if not data or not isinstance(data.get("scenes"), list) or not data["scenes"]:
            raise RuntimeError("AI เขียนสคริปต์แบบแบ่งฉากไม่สำเร็จ (Gemini และ Ollama)")
        if problems and log:
            log("สคริปต์ยังไม่ผ่านทุกข้อ: " + "; ".join(problems[:3]), "warning")
        data["problems"] = problems

    dictionary = None
    scenes = []
    for s in data["scenes"]:
        if not isinstance(s, dict) or not str(s.get("text", "")).strip():
            continue
        text = str(s["text"]).strip()
        if mode != "dialogue":
            text = re.sub(r"\s*\n\s*", " ", text)
        scenes.append({"text": normalize_for_speech(text, dictionary),
                       "visual": str(s.get("visual") or topic).strip()})
    if mode != "dialogue" and scenes and not custom:
        last = scenes[-1]["text"].rstrip(" .!?")
        wrong = "ครับ" if particle == "ค่ะ" else "ค่ะ"
        if last.endswith(wrong):
            last = last[: -len(wrong)] + particle
        elif not last.endswith(particle):
            last += particle
        scenes[-1]["text"] = last

    hashtags = data.get("hashtags") if isinstance(data.get("hashtags"), list) else []
    result = {
        "scenes": scenes,
        "title": str(data.get("title") or topic).strip()[:100],
        "description": str(data.get("description") or "").strip(),
        "hashtags": [h if h.startswith("#") else f"#{h}" for h in map(str, hashtags)][:10],
        "problems": data.get("problems", []),
        "script": "\n\n".join(s["text"] for s in scenes),
    }
    project_dir = os.path.join("projects", project_id)
    os.makedirs(project_dir, exist_ok=True)
    with open(os.path.join(project_dir, "script.txt"), "w", encoding="utf-8") as f:
        f.write(result["script"])
    return result


def image_prompt(visual: str) -> str:
    return f"{visual}, {_IMAGE_STYLE}"
