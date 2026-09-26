# Brave CDP (Chrome DevTools Protocol) — คู่มือเชื่อมต่อและใช้งาน

> บันทึกจากโปรเจกต์ `aipass-auto-router` (2026-09-14)  
> ใช้ได้กับ **ทุกเว็บที่เปิดใน Brave** — ไม่จำกัดเฉพาะ aipass.net

---

## 1. CDP คืออะไร

Chrome DevTools Protocol (CDP) คือ API ที่ Chromium-based browsers (Brave, Chrome, Edge) เปิดให้ภายนอกควบคุมเบราว์เซอร์ได้แบบ programmatic ผ่าน **WebSocket** — อ่าน DOM, คลิก, พิมพ์, ถ่าย screenshot, monitor network, รัน JavaScript, navigate ได้ทั้งหมด

---

## 2. เปิด Brave ให้รับการเชื่อมต่อ

### วิธีที่ 1 — รันจาก shortcut / bat (แนะนำ)

```bat
@echo off
start "" "C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe" ^
  --remote-debugging-port=9222 ^
  --user-data-dir="%TEMP%\brave-cdp-profile"
```

> `--user-data-dir` แยก profile ออกจาก Brave ปกติ → ไม่กระทบ session เดิม  
> ถ้าต้องการใช้ **profile ปกติ** (login เดิม, cookie เดิม) ให้ลบ `--user-data-dir` ออก

### วิธีที่ 2 — ใช้ไฟล์ในโปรเจกต์

```
C:\Users\Lenovo\OneDrive\Desktop\Start_Brave_Debug.bat
```

### ตรวจสอบว่าเปิดสำเร็จ

```powershell
Invoke-WebRequest -Uri "http://127.0.0.1:9222/json/version" -UseBasicParsing
```

หรือเปิด `http://127.0.0.1:9222/json` ใน browser — จะเห็น JSON รายชื่อ tab ที่เปิดอยู่

---

## 3. Endpoint หลัก

| Endpoint | วิธีเรียก | ข้อมูลที่ได้ |
|---|---|---|
| `GET /json/version` | HTTP | ข้อมูล browser (version, webSocketDebuggerUrl) |
| `GET /json` หรือ `/json/list` | HTTP | รายชื่อ tab ทั้งหมด (id, url, title, webSocketDebuggerUrl) |
| `GET /json/new?{url}` | HTTP | เปิด tab ใหม่ |
| `DELETE /json/close/{id}` | HTTP | ปิด tab |
| `ws://127.0.0.1:9222/devtools/page/{id}` | WebSocket | ควบคุม tab นั้น |

---

## 4. เชื่อมต่อด้วย Python (asyncio + websockets)

### ติดตั้ง library

```bash
pip install websockets
```

### โครงสร้าง CDP session พื้นฐาน

```python
import asyncio, json, urllib.request
import websockets

async def cdp_session(tab_url: str):
    async with websockets.connect(tab_url) as ws:
        cmd_id = 0

        async def send(method, params=None):
            nonlocal cmd_id
            cmd_id += 1
            await ws.send(json.dumps({"id": cmd_id, "method": method,
                                      "params": params or {}}))
            # รับผลลัพธ์ที่ตรงกับ id นี้
            while True:
                msg = json.loads(await ws.recv())
                if msg.get("id") == cmd_id:
                    return msg.get("result", {})

        # เปิดใช้งาน domain ที่ต้องการ
        await send("Runtime.enable")
        await send("Page.enable")

        # รัน JavaScript ในหน้า
        result = await send("Runtime.evaluate", {
            "expression": "document.title",
            "returnByValue": True
        })
        print("Title:", result["result"]["value"])

# หา tab ที่ต้องการ
tabs = json.loads(urllib.request.urlopen("http://127.0.0.1:9222/json").read())
target = next(t for t in tabs if "ชื่อเว็บ" in t["url"])
asyncio.run(cdp_session(target["webSocketDebuggerUrl"]))
```

---

## 5. คำสั่ง CDP ที่ใช้บ่อย

### 5.1 Navigate ไปยัง URL

```python
await send("Page.navigate", {"url": "https://example.com"})
await send("Page.loadEventFired")   # รอจนโหลดเสร็จ
```

### 5.2 อ่าน DOM / ข้อความในหน้า

```python
# อ่าน element ด้วย CSS selector
result = await send("Runtime.evaluate", {
    "expression": "document.querySelector('#answer-box')?.innerText",
    "returnByValue": True
})
text = result.get("result", {}).get("value")
```

### 5.3 คลิก element

```python
await send("Runtime.evaluate", {
    "expression": "document.querySelector('button.send').click()"
})
```

### 5.4 พิมพ์ข้อความใน textarea

```python
# วิธีที่ 1: ใช้ JavaScript (เร็ว ใช้ได้เสมอ)
js = """
const el = document.querySelector('textarea');
const nativeInputSetter = Object.getOwnPropertyDescriptor(
    window.HTMLTextAreaElement.prototype, 'value').set;
nativeInputSetter.call(el, 'ข้อความที่ต้องการ');
el.dispatchEvent(new Event('input', { bubbles: true }));
"""
await send("Runtime.evaluate", {"expression": js})

# วิธีที่ 2: ใช้ Input.dispatchKeyEvent (คล้าย keyboard จริง)
await send("Input.dispatchKeyEvent", {"type": "keyDown", "key": "a"})
await send("Input.dispatchKeyEvent", {"type": "keyUp",   "key": "a"})
```

### 5.5 ถ่าย Screenshot

```python
result = await send("Page.captureScreenshot", {"format": "png"})
import base64
png_bytes = base64.b64decode(result["data"])
open("screenshot.png", "wb").write(png_bytes)
```

### 5.6 Monitor Network Request

```python
await send("Network.enable")
# รับ event
while True:
    msg = json.loads(await ws.recv())
    if msg.get("method") == "Network.responseReceived":
        print(msg["params"]["response"]["url"],
              msg["params"]["response"]["status"])
```

### 5.7 รัน JavaScript และรับค่า object ซับซ้อน

```python
result = await send("Runtime.evaluate", {
    "expression": "JSON.stringify(window.__store?.getState())",
    "returnByValue": True,
    "awaitPromise": True
})
data = json.loads(result["result"]["value"])
```

---

## 6. Pattern: รอจนกว่า element จะปรากฏ

```python
import asyncio

async def wait_for_element(ws, send_fn, selector: str, timeout=60):
    """รอจนกว่า querySelector จะคืนค่าที่ไม่ใช่ null"""
    JS = f"document.querySelector({json.dumps(selector)}) !== null"
    t0 = asyncio.get_event_loop().time()
    while asyncio.get_event_loop().time() - t0 < timeout:
        r = await send_fn("Runtime.evaluate", {"expression": JS, "returnByValue": True})
        if r.get("result", {}).get("value"):
            return True
        await asyncio.sleep(0.5)
    raise TimeoutError(f"'{selector}' ไม่ปรากฏภายใน {timeout}s")
```

---

## 7. Pattern: เปิด Tab ใหม่ + รอโหลด

```python
import urllib.request, json

def open_new_tab(url: str) -> dict:
    resp = urllib.request.urlopen(
        f"http://127.0.0.1:9222/json/new?{url}"
    )
    return json.loads(resp.read())   # คืน tab object พร้อม webSocketDebuggerUrl

tab = open_new_tab("https://example.com")
# แล้วเชื่อมต่อ WebSocket ด้วย tab["webSocketDebuggerUrl"]
```

---

## 8. ตัวอย่าง: ดึงข้อมูลจากเว็บที่เปิดอยู่

```python
import asyncio, json, urllib.request
import websockets

TARGET_URL_PATTERN = "example.com"   # เปลี่ยนตามเว็บที่ต้องการ

async def scrape():
    # หา tab ที่เปิดอยู่
    tabs = json.loads(urllib.request.urlopen("http://127.0.0.1:9222/json").read())
    tab = next((t for t in tabs if TARGET_URL_PATTERN in t.get("url", "")), None)
    if not tab:
        print("ไม่พบ tab — เปิดเว็บก่อน"); return

    async with websockets.connect(tab["webSocketDebuggerUrl"]) as ws:
        _id = 0
        async def send(method, params=None):
            nonlocal _id; _id += 1
            await ws.send(json.dumps({"id": _id, "method": method, "params": params or {}}))
            while True:
                msg = json.loads(await ws.recv())
                if msg.get("id") == _id:
                    return msg.get("result", {})

        # ดึงข้อมูลทั้งหน้า
        r = await send("Runtime.evaluate", {
            "expression": "document.body.innerText",
            "returnByValue": True
        })
        print(r["result"]["value"][:500])

asyncio.run(scrape())
```

---

## 9. ข้อควรระวัง (Gotchas จากประสบการณ์จริง)

| ปัญหา | สาเหตุ | วิธีแก้ |
|---|---|---|
| Bridge อ่านคำตอบเก่ากลับมา | Tab มีบทสนทนาเก่าค้างอยู่ | Navigate ไปที่ URL เริ่มต้น (`/chat`) ก่อนส่ง prompt |
| Safety filter บล็อก | เว็บบางแห่ง filter keyword เช่น `==`, `if :`, `def ` | ใช้ REST API แทน หรือ wrap โค้ดในรูป plain text |
| React input ไม่รับค่า | React ใช้ synthetic event ไม่รับ `.value =` ตรงๆ | ใช้ `nativeInputSetter` + `dispatchEvent('input')` |
| `asyncio.run()` ซ้อนกัน | เรียก `asyncio.run()` ใน event loop ที่รันอยู่แล้ว | ใช้ `await` โดยตรง หรือ `loop.run_until_complete()` |
| Port 9222 ถูกใช้แล้ว | Brave เปิดปกติอยู่ | ปิด Brave ปกติก่อน หรือใช้ port อื่นเช่น `9223` |
| ข้อความยาวถูกตัด | Brave ส่ง chunk WebSocket หลายก้อน | buffer จนได้ `"result"` ที่ตรงกับ command `id` |
| Tab ถูกระงับ (throttled) | Tab อยู่ background นานๆ | ส่ง `Page.bringToFront` ก่อนทำงาน |

---

## 10. ใช้กับ library `pycdp` หรือ `playwright` แทน websockets ดิบ

### playwright (ง่ายกว่า แนะนำสำหรับงานใหม่)

```bash
pip install playwright
playwright install chromium
```

```python
from playwright.async_api import async_playwright
import asyncio

async def main():
    async with async_playwright() as p:
        # เชื่อมต่อ Brave ที่เปิดอยู่ (CDP port 9222)
        browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        page = browser.contexts[0].pages[0]   # tab แรก
        print(await page.title())
        await page.fill("textarea", "ข้อความ")
        await page.click("button[type=submit]")
        await page.screenshot(path="shot.png")

asyncio.run(main())
```

> playwright จัดการ wait, retry, element visibility ให้อัตโนมัติ — ง่ายกว่า CDP ดิบมาก

---

## 11. โครงสร้างไฟล์ในโปรเจกต์ aipass-auto-router (ตัวอย่างจริง)

```
C:\enterprise\aipass-auto-router\
├── scripts\
│   ├── aipass_bridge.py        ← CDP client หลัก (ส่ง prompt ไปยัง aipass.net)
│   ├── kku_bridge.py           ← REST client (ไม่ใช้ CDP)
│   └── task_classifier.py      ← จำแนก task class อัตโนมัติ
├── launchers\
│   └── launcher_app.py         ← Tkinter GUI เชื่อมทั้ง CDP + REST
└── references\
    └── routing.md              ← บันทึก selector จริงใน aipass DOM
```

`aipass_bridge.py` ใช้ `websockets` โดยตรง (ไม่ผ่าน playwright) เพราะต้องการควบคุม timing และ event listening แบบละเอียด

---

## 12. Quick-start สำหรับเว็บใหม่

1. เปิด Brave ด้วย `--remote-debugging-port=9222`
2. เปิดเว็บที่ต้องการใน Brave
3. ดู tab list: `http://127.0.0.1:9222/json`
4. คัดลอก `webSocketDebuggerUrl` ของ tab นั้น
5. ใช้ `websockets.connect(url)` แล้วส่ง CDP command ตามต้องการ
6. **Inspect element ใน Brave DevTools** เพื่อหา CSS selector ที่ถูกต้องก่อนเขียนโค้ด

---

*อ้างอิง: [Chrome DevTools Protocol](https://chromedevtools.github.io/devtools-protocol/) · [websockets (Python)](https://websockets.readthedocs.io/) · [Playwright CDP](https://playwright.dev/python/docs/api/class-browsertype#browser-type-connect-over-cdp)*
