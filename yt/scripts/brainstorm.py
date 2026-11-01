# ============================================================================
# ProInventive Suite
# Copyright (C) 2024-2569 ProInventive. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL
# Unauthorized use, copying, or distribution is prohibited.
# Author: Peerapong (Lungpee) -- ProInventive -- giskku@gmail.com
# ============================================================================

import asyncio
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv

_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_ENV_PATH)

_GEMINI_KEY = os.getenv("GOOGLE_API_KEY", "")
_GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/"
    "models/gemini-3.5-flash:generateContent"
)


async def gemini_generate(prompt: str, json_output: bool = False, timeout: float = 60) -> str | None:
    """One Gemini call; None when unavailable (no key, quota, outage) so callers fall back.
    The key goes in a header, not the URL, so it never appears in error messages."""
    if not _GEMINI_KEY:
        return None
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    if json_output:
        payload["generationConfig"] = {"responseMimeType": "application/json"}
    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(_GEMINI_URL, headers={"x-goog-api-key": _GEMINI_KEY}, json=payload)
                resp.raise_for_status()
                return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        except httpx.HTTPStatusError as e:
            code = e.response.status_code
            if code in (429, 500, 503) and attempt == 0:
                await asyncio.sleep(3)
                continue
            print(f"Gemini error: HTTP {code}")
            return None
        except httpx.TimeoutException:
            print(f"Gemini timed out ({timeout:.0f}s)")
            return None
        except (httpx.HTTPError, KeyError, IndexError) as e:
            print(f"Gemini error: {type(e).__name__}")
            return None
    return None


async def generate_brainstorm(topic: str, duration_preset: str = "short") -> str | None:
    if duration_preset == "long":
        style, facts = "เนื้อหาเชิงลึก (3-5 นาที) สำหรับ YouTube", "5-8"
    elif duration_preset == "medium":
        style, facts = "เนื้อหาปานกลาง (2-3 นาที) สำหรับ YouTube", "3-5"
    else:
        style, facts = "YouTube Shorts style (45-60 seconds)", "2-3"

    prompt = f"""Topic for YouTube video: {topic}

Generate in Thai:
1. [HOOKS] 3 engaging opening lines to grab attention
2. [FACTS] {facts} specific facts or statistics
3. [CTA] One compelling call-to-action

Format: Keep it concise, {style}"""
    return await gemini_generate(prompt, timeout=20)
