"""
yk_live_server.py — ดึงผลยี่กี realtime จาก cat888.co
แล้ว serve JSON ที่ http://localhost:5001/live.json

วิธีใช้:
  pip install playwright beautifulsoup4
  python -m playwright install chromium
  python yk_live_server.py

จะเปิดหน้าต่าง Brave ให้ login ครั้งเดียว → หลังจากนั้น auto-refresh ทุก 60 วิ
"""
import json, time, os, sys, traceback, tempfile
from datetime import date, datetime
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import threading

# ─── Config ──────────────────────────────────────────────────────────
PORT = 5001
FETCH_INTERVAL = 60
CAT888_HISTORY = "https://www.cat888.co/online/yeekee/history?searching_date="
TODAY = date.today().strftime("%Y-%m-%d")

BRAVE_PATHS = [
    r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
    r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
    r"C:\Users\Lenovo\AppData\Local\BraveSoftware\Brave-Browser\Application\brave.exe",
]

TEMP_PROFILE = os.path.join(tempfile.gettempdir(), "yk_brave_profile")

# ─── Global state ───────────────────────────────────────────────────
live_data = []
last_updated = None
fetch_error = None
data_lock = threading.Lock()
logged_in = False

# ─── HTTP Server (รันใน background thread) ───────────────────────────
class LiveHandler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass

    def _cors(self):
        return {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        }

    def _respond(self, code, ctype, body):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        for k, v in self._cors().items():
            self.send_header(k, v)
        if isinstance(body, str):
            body = body.encode('utf-8')
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ('/live.json', '/live.json?'):
            with data_lock:
                body = json.dumps(live_data, ensure_ascii=False)
            self._respond(200, "application/json; charset=utf-8", body)

        elif self.path == '/status':
            with data_lock:
                info = {"count": len(live_data), "last_updated": last_updated,
                        "error": fetch_error, "today": TODAY, "logged_in": logged_in}
            self._respond(200, "application/json; charset=utf-8",
                          json.dumps(info, ensure_ascii=False))

        elif self.path == '/':
            self._respond(200, "text/html; charset=utf-8", self._dashboard())
        else:
            self.send_response(404); self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        for k, v in self._cors().items():
            self.send_header(k, v)
        self.end_headers()

    def _dashboard(self):
        with data_lock:
            n = len(live_data)
            lu = last_updated or "—"
            err = fetch_error or ""
            li = logged_in
            rows_html = ''.join(
                f"<tr><td>{r.get('round','')}</td><td>{r.get('time','')}</td>"
                f"<td>{r.get('top3','')}</td><td>{r.get('bot2','')}</td></tr>"
                for r in live_data[-20:]
            )
        status_color = "#4ade80" if li else "#f87171"
        status_text = "✅ Login แล้ว — ดึงข้อมูลอัตโนมัติ" if li else "⏳ รอ login ในหน้าต่าง Brave..."
        return f"""<!doctype html><meta charset=utf-8>
<title>YK Live Server</title>
<meta http-equiv="refresh" content="10">
<style>body{{font-family:Tahoma;background:#0f172a;color:#e2e8f0;padding:20px}}
h1{{color:#60a5fa}} table{{border-collapse:collapse;width:100%;max-width:500px}}
th,td{{border:1px solid #334155;padding:6px 12px;text-align:center}}
th{{background:#1e40af}} .ok{{color:#4ade80}} .err{{color:#f87171}}</style>
<h1>🔴 YK Live Server — localhost:{PORT}</h1>
<p>สถานะ: <b style="color:{status_color}">{status_text}</b></p>
<p>อัปเดต: <b>{lu}</b> · ผล: <b class="ok">{n} รอบ</b>
{f'<br><span class="err">⚠ {err}</span>' if err else ''}</p>
{f'<table><thead><tr><th>รอบ</th><th>เวลา</th><th>3ตัวบน</th><th>2ตัวล่าง</th></tr></thead><tbody>{rows_html}</tbody></table>' if n else ''}
<p style="color:#64748b;font-size:12px">ดึงข้อมูลทุก {FETCH_INTERVAL} วิ
· <a href="/live.json" style="color:#60a5fa">live.json</a>
· <a href="/status" style="color:#60a5fa">status</a></p>"""


def start_http_server():
    server = ThreadingHTTPServer(('localhost', PORT), LiveHandler)
    server.daemon_threads = True   # ปิด connection ค้างเมื่อ shutdown ไม่ block
    server.serve_forever()


# ─── Scraping ────────────────────────────────────────────────────────

def find_brave():
    for p in BRAVE_PATHS:
        if os.path.exists(p):
            return p
    return None

def parse_yeekee_table(html_text):
    results = []
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_text, 'html.parser')
        for tbl in soup.find_all('table'):
            for tr in tbl.find_all('tr'):
                cells = [td.get_text(strip=True) for td in tr.find_all('td')]
                if len(cells) < 3:
                    continue
                rnd = cells[0].replace(',', '').strip()
                if not rnd.isdigit():
                    continue
                time_s = cells[1] if len(cells) > 1 else ''
                top3 = ''.join(c for c in cells[2] if c.isdigit())[:3].zfill(3)
                bot2_src = cells[3] if len(cells) > 3 else cells[-1]
                bot2 = ''.join(c for c in bot2_src if c.isdigit())[:2].zfill(2)
                if len(top3) == 3 and top3 != '000':
                    time_norm = time_s.replace('-', ' - ') if '-' in time_s and ' - ' not in time_s else time_s
                    results.append({'round': int(rnd), 'time': time_norm,
                                    'top3': top3, 'bot2': bot2})
    except ImportError:
        import re
        for m in re.finditer(
            r'<td[^>]*>(\d+)</td>\s*<td[^>]*>([^<]+)</td>\s*<td[^>]*>(\d+)</td>\s*<td[^>]*>(\d+)</td>',
            html_text
        ):
            rnd, t, top3, bot2 = m.groups()
            t3 = top3.zfill(3)
            if t3 == '000':
                continue
            time_norm = t.strip().replace('-', ' - ') if '-' in t and ' - ' not in t else t.strip()
            results.append({'round': int(rnd), 'time': time_norm,
                            'top3': t3, 'bot2': bot2.zfill(2)})
    return results


# ─── Main: Playwright รัน main thread, HTTP server รัน background ────
if __name__ == '__main__':
    from playwright.sync_api import sync_playwright

    brave_exe = find_brave()
    if not brave_exe:
        print("❌ ไม่พบ Brave Browser"); sys.exit(1)

    os.makedirs(TEMP_PROFILE, exist_ok=True)

    print("=" * 60)
    print(f"  YK Live Server — port {PORT}")
    print(f"  วันที่: {TODAY} | ทุก {FETCH_INTERVAL} วิ")
    print(f"  Brave: {brave_exe}")
    print(f"  Profile: {TEMP_PROFILE}")
    print("=" * 60)

    # เริ่ม HTTP server ใน background thread
    http_thread = threading.Thread(target=start_http_server, daemon=True)
    http_thread.start()
    print(f"\n🚀 HTTP server → http://localhost:{PORT}/")

    # เปิด Brave ด้วย Playwright ใน main thread
    print(f"🌐 เปิด Brave (visible) — login ครั้งแรกครั้งเดียว...")
    print("   👉 Login ที่หน้าต่าง Brave ที่เปิดขึ้นมา\n")

    try:
        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(
                TEMP_PROFILE,
                executable_path=brave_exe,
                headless=False,
                args=['--no-sandbox', '--disable-gpu',
                      '--window-size=900,650', '--window-position=50,50'],
                viewport={'width': 880, 'height': 600},
            )
            page = ctx.pages[0] if ctx.pages else ctx.new_page()

            url = CAT888_HISTORY + TODAY
            err_streak = 0

            while True:
                ts = datetime.now().strftime('%H:%M:%S')
                try:
                    # ── ตรวจว่า browser/page ยังมีชีวิต ถ้าตายให้สร้างใหม่ ──
                    if page.is_closed():
                        print(f"[{ts}] ♻ page ถูกปิด — สร้างใหม่")
                        page = ctx.new_page()

                    print(f"[{ts}] กำลังดึงข้อมูล...")
                    # domcontentloaded เร็วกว่า networkidle มาก (cat888 มี polling ตลอด network ไม่เคย idle)
                    page.goto(url, wait_until='domcontentloaded', timeout=20000)
                    try:
                        page.wait_for_selector('table', timeout=8000)
                    except Exception:
                        pass  # ไม่เจอตารางใน 8 วิ ก็ parse เท่าที่มี

                    title = page.title()
                    html = page.content()

                    if 'login' in title.lower():
                        logged_in = False
                        with data_lock:
                            fetch_error = "ยังไม่ได้ login — กรุณา login ที่หน้าต่าง Brave"
                        print(f"[{ts}] ⏳ รอ login... (login ที่หน้าต่าง Brave แล้ว refresh)")
                    else:
                        results = parse_yeekee_table(html)

                        if results:
                            logged_in = True
                            err_streak = 0
                            with data_lock:
                                live_data = sorted(results, key=lambda x: x['round'])
                                last_updated = datetime.now().strftime('%H:%M:%S')
                                fetch_error = None
                            print(f"[{ts}] ✅ ดึงสำเร็จ: {len(results)} รอบ")
                        else:
                            with data_lock:
                                fetch_error = "login แล้ว แต่ parse ไม่เจอตาราง"
                            debug_path = os.path.join(tempfile.gettempdir(), "yk_debug_page.html")
                            with open(debug_path, 'w', encoding='utf-8') as f:
                                f.write(html)
                            print(f"[{ts}] ⚠ parse ไม่พบข้อมูล → saved {debug_path}")

                except Exception as e:
                    err_streak += 1
                    with data_lock:
                        fetch_error = str(e).splitlines()[0][:200]
                    print(f"[{ts}] ⚠ error #{err_streak}: {str(e).splitlines()[0][:120]}")
                    # error ติดกัน 3 ครั้ง → รีเซ็ต page ใหม่ (กัน page ค้างถาวร)
                    if err_streak >= 3:
                        try:
                            if not page.is_closed():
                                page.close()
                            page = ctx.new_page()
                            print(f"[{ts}] ♻ รีเซ็ต page ใหม่ หลัง error {err_streak} ครั้งติด")
                            err_streak = 0
                        except Exception as e2:
                            print(f"[{ts}] ❌ สร้าง page ใหม่ไม่ได้: {e2}")

                time.sleep(FETCH_INTERVAL)

    except KeyboardInterrupt:
        print("\n⏹ หยุดแล้ว")
    except Exception as e:
        print(f"\n❌ {e}")
        traceback.print_exc()
