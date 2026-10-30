# ============================================================================
# ProInventive Suite
# Copyright (C) 2024-2569 ProInventive. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL
# Unauthorized use, copying, or distribution is prohibited.
# Author: Peerapong (Lungpee) -- ProInventive -- giskku@gmail.com
# ============================================================================

"""
RemoteAIR QR Generator — สร้าง QR code สำหรับส่งให้ผู้ใช้ติดตั้งแอป
โดย ลุงพี

ใช้งาน:
  python generate_qr.py [--url URL] [--out OUTPUT_DIR]

ค่าเริ่มต้น URL จะชี้ไปที่ GitHub Releases ของโปรเจกต์
"""

import argparse
import os
import json
from pathlib import Path

try:
    import qrcode
    from PIL import Image, ImageDraw, ImageFont
    HAS_QR = True
except ImportError:
    HAS_QR = False

DEFAULT_URL = "https://github.com/peeraponggis/cctv/tree/master/remoterAIR"
PLAYSTORE_URL = "https://play.google.com/store/apps/details?id=com.lungpee.remoter_air"
APPSTORE_URL  = "https://apps.apple.com/app/remoter-air/id0000000000"
GITHUB_APK    = "https://github.com/peeraponggis/cctv/releases/latest/download/remoter_air.apk"

def read_version():
    p = Path(__file__).parent / "VERSION.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8")).get("version", "1.0.0")
    return "1.0.0"

def make_qr(url: str, out_path: str, title: str = "RemoteAIR"):
    if not HAS_QR:
        print("❌ ไม่พบ library: pip install qrcode[pil]")
        print(f"   URL ที่จะใช้: {url}")
        return False

    qr = qrcode.QRCode(
        version=2,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

    # เพิ่มหัวข้อใต้ QR
    border = 20
    label_h = 60
    new_w = img.width + border * 2
    new_h = img.height + border * 2 + label_h
    canvas = Image.new("RGB", (new_w, new_h), "white")
    canvas.paste(img, (border, border))

    draw = ImageDraw.Draw(canvas)
    try:
        font_big = ImageFont.truetype("arial.ttf", 22)
        font_sm  = ImageFont.truetype("arial.ttf", 14)
    except Exception:
        font_big = ImageFont.load_default()
        font_sm  = font_big

    text_y = img.height + border + 4
    draw.text((new_w // 2, text_y), title, font=font_big, fill="black", anchor="mt")
    draw.text((new_w // 2, text_y + 28), url[:60] + ("…" if len(url) > 60 else ""), font=font_sm, fill="#555555", anchor="mt")

    canvas.save(out_path)
    print(f"✅ สร้าง QR สำเร็จ → {out_path}")
    print(f"   URL: {url}")
    return True

def main():
    version = read_version()
    parser = argparse.ArgumentParser(description="RemoteAIR QR Generator")
    parser.add_argument("--url", default=GITHUB_APK, help="URL สำหรับ QR code")
    parser.add_argument("--out", default=str(Path(__file__).parent / "qr_output"), help="โฟลเดอร์ output")
    parser.add_argument("--all", action="store_true", help="สร้าง QR ทุกแบบ")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.all:
        targets = [
            (GITHUB_APK,  out_dir / "qr_android_apk.png",    f"RemoteAIR v{version} — Android APK"),
            (PLAYSTORE_URL, out_dir / "qr_playstore.png",    f"RemoteAIR — Google Play"),
            (APPSTORE_URL,  out_dir / "qr_appstore.png",     f"RemoteAIR — App Store"),
            (DEFAULT_URL,   out_dir / "qr_source.png",       f"RemoteAIR — Source Code"),
        ]
    else:
        targets = [(args.url, out_dir / "qr_install.png", f"RemoteAIR v{version}")]

    for url, path, title in targets:
        make_qr(url, str(path), title)

    if not HAS_QR:
        print("\nวิธีติดตั้ง library:")
        print("  pip install qrcode[pil] Pillow")

if __name__ == "__main__":
    main()
