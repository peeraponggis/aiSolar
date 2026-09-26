import os
import sys
import json
import asyncio
import urllib.request
import urllib.parse
from pathlib import Path
from dotenv import load_dotenv

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_ENV_PATH, override=True)


def _get_pexels_key() -> str:
    load_dotenv(_ENV_PATH, override=True)
    return os.getenv("PEXELS_API_KEY", "")


def _get_keywords_from_topic(topic: str) -> list[str]:
    try:
        import google.generativeai as genai
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        model = genai.GenerativeModel("gemini-3.6-flash")
        prompt = (
            f"Given this YouTube Shorts topic: \"{topic}\"\n"
            "Return exactly 4 English search keywords for finding relevant stock videos/photos.\n"
            "Each keyword should be 1-3 words, suitable for Pexels search.\n"
            "Focus on visual concepts that would look good as vertical video backgrounds.\n"
            "Return ONLY a JSON array of strings, nothing else.\n"
            'Example: ["coding laptop", "server room", "artificial intelligence", "technology circuit"]'
        )
        response = model.generate_content(prompt)
        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        return json.loads(text)
    except Exception as e:
        print(f"Keyword generation error: {e}")
        words = topic.split()
        return [" ".join(words[:3]), "technology", "computer", "digital"]


def _search_pexels_videos(query: str, per_page: int = 1) -> list[dict]:
    key = _get_pexels_key()
    if not key:
        return []
    url = "https://api.pexels.com/videos/search?" + urllib.parse.urlencode({
        "query": query,
        "per_page": per_page,
        "orientation": "portrait",
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


def _search_pexels_photos(query: str, per_page: int = 1) -> list[dict]:
    key = _get_pexels_key()
    if not key:
        return []
    url = "https://api.pexels.com/v1/search?" + urllib.parse.urlencode({
        "query": query,
        "per_page": per_page,
        "orientation": "portrait",
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


def _pick_best_video_file(video: dict) -> str | None:
    """Pick the best quality portrait-friendly video file from Pexels response."""
    files = video.get("video_files", [])
    # Prefer HD quality, portrait orientation
    best = None
    best_height = 0
    for f in files:
        h = f.get("height", 0)
        w = f.get("width", 0)
        # Prefer portrait or square, skip ultra-wide
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


async def fetch_background_media(project_id: str, topic: str, count: int = 4) -> dict:
    """Fetch background videos and photos from Pexels.

    Returns dict with 'videos' and 'images' lists of local file paths.
    """
    if not _get_pexels_key():
        print("No PEXELS_API_KEY — skipping media fetch")
        return {"videos": [], "images": []}

    media_dir = os.path.join("projects", project_id, "media")
    os.makedirs(media_dir, exist_ok=True)

    keywords = await asyncio.to_thread(_get_keywords_from_topic, topic)
    print(f"Media keywords: {keywords}")

    videos = []
    images = []

    for i, kw in enumerate(keywords[:count]):
        # Try video first
        results = await asyncio.to_thread(_search_pexels_videos, kw)
        if results:
            video_url = _pick_best_video_file(results[0])
            if video_url:
                out_path = os.path.join(media_dir, f"clip_{i:02d}.mp4")
                ok = await asyncio.to_thread(_download_file, video_url, out_path)
                if ok:
                    videos.append(out_path)
                    print(f"Video downloaded: {kw} -> {out_path}")
                    continue

        # Fallback to photo
        photos = await asyncio.to_thread(_search_pexels_photos, kw)
        if photos:
            photo = photos[0]
            img_url = (photo.get("src", {}).get("large2x")
                       or photo.get("src", {}).get("large", ""))
            if img_url:
                out_path = os.path.join(media_dir, f"bg_{i:02d}.jpg")
                ok = await asyncio.to_thread(_download_file, img_url, out_path)
                if ok:
                    images.append(out_path)
                    print(f"Photo downloaded: {kw} -> {out_path}")

    return {"videos": videos, "images": images}


# Backward-compatible wrapper
async def fetch_background_images(project_id: str, topic: str, count: int = 4) -> list[str]:
    result = await fetch_background_media(project_id, topic, count)
    return result["images"]
