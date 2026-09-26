import httpx
from dotenv import load_dotenv
from pathlib import Path
import os

_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_ENV_PATH)

_GEMINI_KEY = os.getenv("GOOGLE_API_KEY", "")
_GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/"
    "models/gemini-3.5-flash:generateContent"
)


async def generate_brainstorm(topic: str) -> str | None:
    if not _GEMINI_KEY:
        print("No GOOGLE_API_KEY, skipping brainstorm")
        return None
    try:
        return await _brainstorm_call(topic)
    except httpx.TimeoutException:
        print("Brainstorm timed out (20s), skipping")
        return None
    except Exception as e:
        print(f"Brainstorm error: {e}")
        return None


async def _brainstorm_call(topic: str) -> str:
    prompt = f"""Topic for YouTube Shorts: {topic}

Generate in Thai:
1. [HOOKS] 3 engaging opening lines to grab attention
2. [FACTS] 2-3 specific facts or statistics
3. [CTA] One compelling call-to-action

Format: Keep it concise, YouTube Shorts style (45-60 seconds)"""

    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            _GEMINI_URL,
            params={"key": _GEMINI_KEY},
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]
