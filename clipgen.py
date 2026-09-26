# -*- coding: utf-8 -*-
"""
clipgen.py - สร้างคลิปสั้นแบบสไลด์โชว์บรรยาย
แต่ละฉาก = รูป (Pollinations) + เสียงบรรยาย (edge-tts Neural) -> ต่อเป็น mp4 ด้วย ffmpeg

ใช้:
  python clipgen.py spec.json
spec.json:
{
  "scenes": [
    {"image": "solar panels on a factory roof, sunny", "narration": "โรงงานติดตั้งโซลาร์ 176 กิโลวัตต์"},
    {"image": "bar chart of energy savings", "narration": "ประหยัดค่าไฟได้มากในเดือนมกราคม"}
  ],
  "voice": "th-TH-PremwadeeNeural",
  "ffmpeg": "D:\\\\LocalAI\\\\tools\\\\ffmpeg\\\\ffmpeg.exe",
  "out": "D:\\\\LocalAI\\\\clips\\\\clip.mp4"
}
"""
import os, sys, json, asyncio, subprocess, urllib.parse, urllib.request
import edge_tts

# สัดส่วนวิดีโอ: image gen (iw,ih) + วิดีโอสุดท้าย (vw,vh)
FORMATS = {
    "portrait":  {"iw": 768, "ih": 1344, "vw": 1080, "vh": 1920},  # 9:16 TikTok/Reels/Shorts
    "landscape": {"iw": 1344, "ih": 768, "vw": 1920, "vh": 1080},  # 16:9 YouTube
    "square":    {"iw": 768, "ih": 768, "vw": 1080, "vh": 1080},   # 1:1
}

def _run(args):
    p = subprocess.run(args, capture_output=True)
    if p.returncode != 0:
        err = (p.stderr or b"").decode("utf-8", "replace").strip().splitlines()
        raise RuntimeError("ffmpeg: " + (err[-1] if err else "unknown error"))

def _is_image(data):
    return (data[:3] == b"\xff\xd8\xff" or data[:8] == b"\x89PNG\r\n\x1a\n"
            or data[:4] == b"RIFF" or data[:6] in (b"GIF87a", b"GIF89a"))

def gen_image(prompt, out_path, w=768, h=768, tries=5):
    import time
    url = ("https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt or "abstract background")
           + "?width=%d&height=%d&nologo=true&seed=%d" % (w, h, abs(hash(prompt)) % 99999))
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    last = None
    for a in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                data = r.read()
            if data and len(data) > 2000 and _is_image(data):
                with open(out_path, "wb") as f:
                    f.write(data)
                return
            last = "รูปที่ได้ไม่ใช่ไฟล์ภาพ (อาจเป็นหน้า error)"
        except Exception as e:
            last = e
        time.sleep(4 * (a + 1))
    # fallback: พื้นหลังไล่สี (ถ้า Pollinations ล่ม คลิปยังทำต่อได้)
    try:
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (w, h), (50, 55, 90))
        d = ImageDraw.Draw(img)
        for y in range(h):
            t = y / max(1, h - 1)
            d.line([(0, y), (w, y)], fill=(int(60 + t * 50), int(55 + t * 25), int(95 + t * 70)))
        img.save(out_path)
    except Exception:
        raise RuntimeError("สร้างรูปไม่ได้: %s" % last)

async def gen_tts(text, voice, out_path):
    audio = bytearray()
    async for chunk in edge_tts.Communicate(text or " ", voice).stream():
        if chunk["type"] == "audio":
            audio += chunk["data"]
    with open(out_path, "wb") as f:
        f.write(bytes(audio))

def _ff(p):
    # escape path สำหรับ ffmpeg filter (drive colon + backslash)
    return p.replace("\\", "/").replace(":", "\\:")

def _wrap(text, n=24):
    text = (text or "").strip()
    out, line = [], ""
    for ch in text:
        line += ch
        if len(line) >= n and ch in " ,.;!?ๆ)]":
            out.append(line.strip()); line = ""
    if line.strip():
        out.append(line.strip())
    return "\n".join(out) if out else text

def find_font():
    here = os.path.dirname(os.path.abspath(__file__))
    for c in [os.path.join(here, "tools", "fonts", "Sarabun-Regular.ttf"),
              r"C:\Windows\Fonts\tahoma.ttf", r"C:\Windows\Fonts\Leelawadee.ttf",
              r"C:\Windows\Fonts\arial.ttf"]:
        if os.path.isfile(c):
            return c
    return None

def make_clip(scenes, voice, ffmpeg, workdir, out_path, fmt="portrait",
              subtitle=True, music=None, progress=None):
    F = FORMATS.get(fmt, FORMATS["portrait"])
    vw, vh, iw, ih = F["vw"], F["vh"], F["iw"], F["ih"]
    base_vf = ("scale=%d:%d:force_original_aspect_ratio=decrease,"
               "pad=%d:%d:(ow-iw)/2:(oh-ih)/2,setsar=1" % (vw, vh, vw, vh))
    font = find_font()
    portrait = (fmt == "portrait")
    os.makedirs(workdir, exist_ok=True)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    segs = []
    for i, sc in enumerate(scenes):
        if progress: progress("ฉาก %d/%d: สร้างรูป" % (i + 1, len(scenes)))
        img = os.path.join(workdir, "img%d.png" % i)
        aud = os.path.join(workdir, "aud%d.mp3" % i)
        seg = os.path.join(workdir, "seg%d.mp4" % i)
        gen_image(sc.get("image"), img, iw, ih)
        if progress: progress("ฉาก %d/%d: สร้างเสียง" % (i + 1, len(scenes)))
        asyncio.run(gen_tts(sc.get("narration"), voice, aud))
        vf = base_vf
        narr = (sc.get("narration") or "").strip()
        if subtitle and font and narr:
            subf = os.path.join(workdir, "sub%d.txt" % i)
            with open(subf, "w", encoding="utf-8") as f:
                f.write(_wrap(narr, 22 if portrait else 42))
            fs = 54 if portrait else 40
            ypad = 170 if portrait else 70
            vf += (",drawtext=fontfile='%s':textfile='%s':fontcolor=white:fontsize=%d:"
                   "line_spacing=12:box=1:boxcolor=black@0.55:boxborderw=22:"
                   "x=(w-text_w)/2:y=h-text_h-%d" % (_ff(font), _ff(subf), fs, ypad))
        if progress: progress("ฉาก %d/%d: ประกอบวิดีโอ" % (i + 1, len(scenes)))
        _run([ffmpeg, "-y", "-loop", "1", "-i", img, "-i", aud,
              "-c:v", "libx264", "-tune", "stillimage", "-c:a", "aac", "-b:a", "192k",
              "-pix_fmt", "yuv420p", "-vf", vf, "-shortest", seg])
        segs.append(seg)
    listf = os.path.join(workdir, "list.txt")
    with open(listf, "w", encoding="utf-8") as f:
        for s in segs:
            f.write("file '%s'\n" % os.path.abspath(s).replace("\\", "/"))
    if progress: progress("ต่อคลิป")
    concat = os.path.join(workdir, "concat.mp4")
    _run([ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", listf, "-c", "copy", concat])
    if music and os.path.isfile(music):
        if progress: progress("ผสมเพลงประกอบ")
        _run([ffmpeg, "-y", "-i", concat, "-stream_loop", "-1", "-i", music,
              "-filter_complex",
              "[1:a]volume=0.16[bg];[0:a][bg]amix=inputs=2:duration=first:dropout_transition=0[a]",
              "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
              out_path])
    else:
        import shutil; shutil.copyfile(concat, out_path)
    return out_path

if __name__ == "__main__":
    spec = json.load(open(sys.argv[1], encoding="utf-8"))
    out = make_clip(spec["scenes"], spec.get("voice", "th-TH-PremwadeeNeural"),
                    spec.get("ffmpeg", "ffmpeg"), spec.get("workdir", "clip_work"),
                    spec.get("out", "clip.mp4"), fmt=spec.get("format", "portrait"),
                    subtitle=spec.get("subtitle", True), music=spec.get("music"),
                    progress=lambda m: print("[clip]", m))
    print("OK", out)
