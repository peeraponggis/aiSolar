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
import urllib.request
import urllib.error
from pathlib import Path
from xml.sax.saxutils import escape

KEY = os.environ.get("AZURE_SPEECH_KEY", "").strip()
REGION = os.environ.get("AZURE_SPEECH_REGION", "").strip()
VOICES = ["lo-LA-KeomanyNeural", "lo-LA-ChanthavongNeural"]
WORDS = ["ສະບາຍດີ", "ຂອບໃຈ", "ແມວ", "ລາວ", "ປະເທດລາວ"]
OUT = Path(__file__).resolve().parent / "tts_test"


def synth(text, voice):
    url = f"https://{REGION}.tts.speech.microsoft.com/cognitiveservices/v1"
    ssml = (
        "<speak version='1.0' xml:lang='lo-LA'>"
        f"<voice xml:lang='lo-LA' name='{voice}'>{escape(text)}</voice></speak>"
    ).encode("utf-8")
    req = urllib.request.Request(url, data=ssml, method="POST", headers={
        "Ocp-Apim-Subscription-Key": KEY,
        "Content-Type": "application/ssml+xml",
        "X-Microsoft-OutputFormat": "audio-16khz-128kbitrate-mono-mp3",
        "User-Agent": "lao-dict-test",
    })
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def main():
    if not KEY or not REGION:
        print("ตั้งค่า AZURE_SPEECH_KEY และ AZURE_SPEECH_REGION ก่อนรัน")
        return 2
    OUT.mkdir(exist_ok=True)
    ok = 0
    for voice in VOICES:
        for word in WORDS:
            name = f"{voice}_{WORDS.index(word)}.mp3"
            try:
                audio = synth(word, voice)
            except urllib.error.HTTPError as e:
                print(f"FAIL {voice} {word}: HTTP {e.code} {e.reason}")
                continue
            except urllib.error.URLError as e:
                print(f"FAIL {voice} {word}: {e.reason}")
                return 1
            (OUT / name).write_bytes(audio)
            ok += 1
            print(f"OK   {voice} {word} -> {name} ({len(audio)} bytes)")
    print(f"สำเร็จ {ok}/{len(VOICES) * len(WORDS)} ไฟล์อยู่ที่ {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
