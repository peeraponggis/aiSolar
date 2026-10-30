# ============================================================================
# ProInventive Suite
# Copyright (C) 2024-2569 ProInventive. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL
# Unauthorized use, copying, or distribution is prohibited.
# Author: Peerapong (Lungpee) -- ProInventive -- giskku@gmail.com
# ============================================================================

import os
import sys
import json
import asyncio
import urllib.request
import urllib.parse
from pathlib import Path
import httpx
from dotenv import load_dotenv

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_ENV_PATH, override=True)

# Same model + plain REST call (API key as query param) that scripts.brainstorm
# uses successfully. The google.generativeai SDK's genai.configure(api_key=...)
# was failing every call with 401 ACCESS_TOKEN_TYPE_UNSUPPORTED in this
# environment (that package is deprecated upstream in favor of google.genai),
# so every topic silently fell through to the generic "technology/computer/
# digital" fallback below regardless of what the video was actually about.
_GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/"
    "models/gemini-3.5-flash:generateContent"
)


def _get_pexels_key() -> str:
    load_dotenv(_ENV_PATH, override=True)
    return os.getenv("PEXELS_API_KEY", "")


def _get_keywords_from_topic(topic: str, count: int = 4) -> list[str]:
    api_key = os.getenv("GOOGLE_API_KEY", "")
    if not api_key:
        return _fallback_keywords(topic, count)
    try:
        prompt = (
            f"Given this YouTube video topic: \"{topic}\"\n"
            f"Return exactly {count} English search keywords for finding relevant stock videos/photos.\n"
            "Each keyword should be 1-3 words, suitable for Pexels search.\n"
            "Focus on visual concepts that would look good as video backgrounds.\n"
            "Return ONLY a JSON array of strings, nothing else.\n"
            'Example: ["coding laptop", "server room", "artificial intelligence", "technology circuit"]'
        )
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        resp = httpx.post(
            _GEMINI_URL, headers={"x-goog-api-key": api_key}, json=payload, timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        keywords = json.loads(text)
        if isinstance(keywords, list) and keywords:
            return keywords[:count]
        return _fallback_keywords(topic, count)
    except (httpx.HTTPError, ValueError, KeyError, IndexError) as e:
        detail = f"HTTP {e.response.status_code}" if isinstance(e, httpx.HTTPStatusError) else type(e).__name__
        print(f"Keyword generation error: {detail}")
        return _fallback_keywords(topic, count)


def _fallback_keywords(topic: str, count: int) -> list[str]:
    """Used only if Gemini is unreachable/unconfigured. Reuses the topic
    itself rather than generic filler terms (previously "technology",
    "computer", "digital") that have no connection to the actual video and
    produced visibly irrelevant background footage.
    """
    topic = topic.strip() or "lifestyle"
    return [topic] * count


def _search_pexels_videos(query: str, per_page: int = 1, orientation: str = "portrait") -> list[dict]:
    key = _get_pexels_key()
    if not key:
        return []
    url = "https://api.pexels.com/videos/search?" + urllib.parse.urlencode({
        "query": query,
        "per_page": per_page,
        "orientation": orientation,
        "size": "medium",
    })
    req = urllib.request.Request(url, headers={
        "Authorization": key,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            return data.get("videos", [])
    except Exception as e:
        print(f"Pexels video search error for '{query}': {e}")
        return []


def _search_pexels_photos(query: str, per_page: int = 1, orientation: str = "portrait") -> list[dict]:
    key = _get_pexels_key()
    if not key:
        return []
    url = "https://api.pexels.com/v1/search?" + urllib.parse.urlencode({
        "query": query,
        "per_page": per_page,
        "orientation": orientation,
        "size": "medium",
    })
    req = urllib.request.Request(url, headers={
        "Authorization": key,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            return data.get("photos", [])
    except Exception as e:
        print(f"Pexels photo search error for '{query}': {e}")
        return []


def _pick_best_video_file(video: dict, orientation: str = "portrait") -> str | None:
    """Pick the best quality video file from Pexels response matching orientation."""
    files = video.get("video_files", [])
    best = None
    best_height = 0
    for f in files:
        h = f.get("height", 0)
        w = f.get("width", 0)
        if orientation == "landscape":
            if h > w * 1.5:
                continue
        else:
            if w > h * 1.5:
                continue
        if 720 <= h <= 1920 and h > best_height:
            best = f.get("link")
            best_height = h
    # Fallback: any file with decent resolution
    if not best:
        for f in sorted(files, key=lambda x: x.get("height", 0), reverse=True):
            if f.get("height", 0) >= 480:
                best = f.get("link")
                break
    # Last resort: first file
    if not best and files:
        best = files[0].get("link")
    return best


def _download_file(url: str, output_path: str) -> bool:
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0"
        })
        with urllib.request.urlopen(req, timeout=60) as resp:
            with open(output_path, "wb") as f:
                while True:
                    chunk = resp.read(1024 * 256)
                    if not chunk:
                        break
                    f.write(chunk)
        return os.path.exists(output_path) and os.path.getsize(output_path) > 5000
    except Exception as e:
        print(f"Download error: {e}")
        return False


def photo_download_url(photo: dict, orientation: str = "portrait") -> str:
    """Full-resolution original, resized by Pexels' CDN to video size
    (large2x is only ~1300 px tall and gets visibly upscaled)."""
    src = photo.get("src", {})
    original = src.get("original", "")
    if not original:
        return src.get("large2x") or src.get("large", "")
    size = "h=1920" if orientation == "portrait" else "w=1920"
    return f"{original}?auto=compress&cs=tinysrgb&{size}"


def _shorter_query(query: str) -> str:
    words = query.split()
    return " ".join(words[:2]) if len(words) > 2 else ""


def _search_scene(query: str, orientation: str) -> tuple[list[dict], list[dict]]:
    videos = _search_pexels_videos(query, 8, orientation)
    photos = _search_pexels_photos(query, 8, orientation) if len(videos) < 3 else []
    short = _shorter_query(query)
    if not videos and not photos and short:
        videos = _search_pexels_videos(short, 8, orientation)
        photos = _search_pexels_photos(short, 8, orientation)
    return videos, photos


async def fetch_scene_media(project_id: str, scenes: list[dict], topic: str,
                            orientation: str = "portrait", source: str = "pexels",
                            ai_engine: str = "flux", durations: list[float] | None = None,
                            log=None) -> list[dict]:
    """One media file per scene, chosen from that scene's own visual query.
    source: "pexels" (video, else photo), "ai" (AI image for every scene) or
    "mixed" (Pexels video, else AI image). Never reuses a Pexels item.
    Writes media/scenes.json and returns one record per scene."""
    import shutil
    from scripts.ai_images import generate_images, is_available as ai_available
    from scripts.generate_script import image_prompt

    media_dir = os.path.join("projects", project_id, "media")
    os.makedirs(media_dir, exist_ok=True)
    records = [{"index": i, "text": s["text"], "query": s.get("visual") or topic,
                "file": None, "source": None, "fallback": False}
               for i, s in enumerate(scenes)]
    used: set = set()
    use_pexels = source in ("pexels", "mixed") and bool(_get_pexels_key())

    if use_pexels:
        found = await asyncio.gather(*(asyncio.to_thread(_search_scene, r["query"], orientation)
                                       for r in records))
        downloads = []
        for r, (videos, photos) in zip(records, found):
            need = (durations[r["index"]] if durations and r["index"] < len(durations) else 0) or 0
            fresh = [v for v in videos if v.get("id") not in used]
            long_enough = [v for v in fresh if (v.get("duration") or 0) >= need]
            pick = (long_enough or fresh or [None])[0]
            if pick:
                used.add(pick.get("id"))
                url = _pick_best_video_file(pick, orientation)
                path = os.path.join(media_dir, f"{r['index']:02d}_clip.mp4")
                downloads.append((r, url, path, "pexels-video"))
                continue
            if source == "mixed":
                continue
            photo = next((p for p in photos if p.get("id") not in used), None)
            if photo:
                used.add(photo.get("id"))
                path = os.path.join(media_dir, f"{r['index']:02d}_img.jpg")
                downloads.append((r, photo_download_url(photo, orientation), path, "pexels-photo"))
        oks = await asyncio.gather(*(asyncio.to_thread(_download_file, url, path)
                                     for _, url, path, _ in downloads if url))
        for (r, url, path, kind), ok in zip([d for d in downloads if d[1]], oks):
            if ok:
                r["file"], r["source"] = path, kind

    want_ai = [r for r in records if not r["file"]] if source in ("ai", "mixed") else []
    if want_ai and ai_available():
        if log:
            log(f"สร้างภาพ AI {len(want_ai)} ภาพ ({ai_engine}) — ภาพแรกต้องโหลดโมเดลประมาณ 1 นาที")
        shape = "landscape" if orientation == "landscape" else "portrait"
        paths = await generate_images([image_prompt(r["query"]) for r in want_ai], ai_engine, shape)
        for r, src in zip(want_ai, paths):
            if src and os.path.exists(src):
                dst = os.path.join(media_dir, f"{r['index']:02d}_img{os.path.splitext(src)[1]}")
                shutil.copy2(src, dst)
                r["file"], r["source"] = dst, f"ai-{ai_engine}"
    elif want_ai and log:
        log("ไม่พบ AI-Bridge-Launcher — ใช้สื่อจาก Pexels แทน", "warning")

    missing = [r for r in records if not r["file"]]
    if missing and _get_pexels_key():
        videos = await asyncio.to_thread(_search_pexels_videos, topic, 8 + len(missing), orientation)
        spare = [v for v in videos if v.get("id") not in used]
        jobs = []
        for r, v in zip(missing, spare):
            used.add(v.get("id"))
            jobs.append((r, _pick_best_video_file(v, orientation),
                         os.path.join(media_dir, f"{r['index']:02d}_clip.mp4")))
        oks = await asyncio.gather(*(asyncio.to_thread(_download_file, u, p) for _, u, p in jobs if u))
        for (r, _, path), ok in zip([j for j in jobs if j[1]], oks):
            if ok:
                r["file"], r["source"], r["fallback"] = path, "pexels-topic", True

    with open(os.path.join(media_dir, "scenes.json"), "w", encoding="utf-8") as f:
        json.dump([{**r, "file": os.path.basename(r["file"]) if r["file"] else None} for r in records],
                  f, ensure_ascii=False, indent=2)
    return records


async def fetch_background_media(project_id: str, topic: str, count: int = 4,
                                 orientation: str = "portrait") -> dict:
    """Fetch background videos (photo fallback) from Pexels, all scenes in parallel.

    Returns dict with 'videos' and 'images' lists of local file paths.
    """
    if not _get_pexels_key():
        print("No PEXELS_API_KEY — skipping media fetch")
        return {"videos": [], "images": []}

    media_dir = os.path.join("projects", project_id, "media")
    os.makedirs(media_dir, exist_ok=True)
    keywords = (await asyncio.to_thread(_get_keywords_from_topic, topic, count))[:count]

    async def fetch_one(i: int, kw: str) -> tuple[str, str] | None:
        # When a keyword repeats (e.g. topic fallback), take the next result
        # instead of downloading the same clip again.
        pick = keywords[:i].count(kw)
        results = await asyncio.to_thread(_search_pexels_videos, kw, pick + 1, orientation)
        if len(results) > pick:
            video_url = _pick_best_video_file(results[pick], orientation)
            out_path = os.path.join(media_dir, f"{i:02d}_clip.mp4")
            if video_url and await asyncio.to_thread(_download_file, video_url, out_path):
                return "video", out_path
        photos = await asyncio.to_thread(_search_pexels_photos, kw, pick + 1, orientation)
        if len(photos) > pick:
            out_path = os.path.join(media_dir, f"{i:02d}_img.jpg")
            img_url = photo_download_url(photos[pick], orientation)
            if img_url and await asyncio.to_thread(_download_file, img_url, out_path):
                return "image", out_path
        return None

    found = await asyncio.gather(*(fetch_one(i, kw) for i, kw in enumerate(keywords)))
    return {
        "videos": [p for r in found if r and r[0] == "video" for p in [r[1]]],
        "images": [p for r in found if r and r[0] == "image" for p in [r[1]]],
    }
