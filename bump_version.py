# -*- coding: utf-8 -*-
"""เลื่อนเวอร์ชัน + วันที่ปรับปรุง + บันทึกการเปลี่ยนแปลง ของโปรแกรมลุงพี — ใช้ทุกครั้งที่แก้ไขโปรแกรม

    python bump_version.py <โปรแกรม> <patch|minor|major> "สรุปสิ่งที่เปลี่ยน"
    python bump_version.py --show

โปรแกรม: translator (Local Translator) · agent (ลุงพี Agent) · gateway (ลุงพี AI Gateway) · chat (หน้าแชทลุงพี AI)
patch = แก้บั๊ก/ปรับเล็กน้อย · minor = เพิ่มความสามารถ · major = เปลี่ยนใหญ่ที่เข้ากันไม่ได้กับของเดิม
"""
import datetime
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TARGETS = {
    "translator": ROOT / "translation" / "app_version.py",
    "agent": ROOT / "lungpee-agent" / "app_version.py",
    "gateway": ROOT / "gateway" / "app_version.py",
    "chat": Path(r"C:\Users\Lenovo\LungPeeAI\_internal\ui\chat.html"),
}


def read(path):
    return path.read_bytes().decode("utf-8")   # อ่าน/เขียนแบบ bytes: chat.html มีอักขระ \0 ที่ต้องคงไว้ตามเดิม


def current(path):
    text = read(path)
    if path.suffix == ".py":
        v = re.search(r'^VERSION = "([\d.]+)"', text, re.M).group(1)
        u = re.search(r'^UPDATED = "([\d-]+)"', text, re.M).group(1)
    else:
        m = re.search(r"const APP_INFO=\{[^}]*version:'([\d.]+)'[^}]*updated:'([\d-]+)'", text)
        v, u = m.group(1), m.group(2)
    return v, u


def next_version(v, level):
    major, minor, patch = (int(x) for x in v.split("."))
    if level == "major":
        return f"{major + 1}.0.0"
    if level == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def bump(target, level, note):
    path = TARGETS[target]
    old, _ = current(path)
    new, today = next_version(old, level), datetime.date.today().isoformat()
    text = read(path)
    if path.suffix == ".py":
        text = re.sub(r'^VERSION = "[\d.]+"', f'VERSION = "{new}"', text, count=1, flags=re.M)
        text = re.sub(r'^UPDATED = "[\d-]+"', f'UPDATED = "{today}"', text, count=1, flags=re.M)
        entry = f"    ({json.dumps(new)}, {json.dumps(today)}, {json.dumps(note, ensure_ascii=False)}),\n"
        text = re.sub(r"(^CHANGELOG = \[[^\n]*\n)", lambda m: m.group(1) + entry, text, count=1, flags=re.M)
    else:
        text = re.sub(r"(const APP_INFO=\{[^}]*version:')[\d.]+'", rf"\g<1>{new}'", text, count=1)
        text = re.sub(r"(const APP_INFO=\{[^}]*updated:')[\d-]+'", rf"\g<1>{today}'", text, count=1)
        safe = note.replace("\\", "\\\\").replace("'", "\\'")
        text = text.replace("const APP_CHANGELOG=[\n", f"const APP_CHANGELOG=[\n  ['{new}','{today}','{safe}'],\n", 1)
    path.write_bytes(text.encode("utf-8"))
    print(f"{target}: {old} -> {new} (ปรับปรุง {today}) · {path}")


def main(argv):
    if len(argv) == 1 and argv[0] == "--show":
        for name, path in TARGETS.items():
            v, u = current(path)
            print(f"{name:<11} v{v:<8} ปรับปรุง {u} · {path}")
        return 0
    if len(argv) != 3 or argv[0] not in TARGETS or argv[1] not in ("patch", "minor", "major"):
        print(__doc__)
        return 2
    bump(*argv)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
