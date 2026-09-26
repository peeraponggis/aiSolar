# -*- coding: utf-8 -*-
"""
lek_dang_scraper.py — กวาด "เลขดัง/เลขเด็ด" จากหลายเว็บ แล้วสรุปว่าเลขไหนถูกพูดถึงมากสุด

หลักการ:
  - อ่านรายการ URL จากไฟล์ lek_dang_sources.txt (บรรทัดละ 1 URL, # = คอมเมนต์)
  - เปิดแต่ละเว็บด้วย Playwright ดึงข้อความ
  - สกัดเลข 2-3 หลัก ที่อยู่ใกล้คำว่า เลขเด็ด/เลขดัง/วิ่ง/บน/ล่าง/สองตัว/สามตัว/เลขเด่น
  - นับว่าแต่ละเลขถูกพูดถึงใน "กี่เว็บ" (source count = ยิ่งหลายเว็บ = ยิ่งดัง)
  - สรุป + บันทึก CSV

⚠️ หมายเหตุสำคัญ (เชิงวิชาการ):
  "เลขดัง" คือความเชื่อ/กระแส ไม่มีผลต่อการออกจริงของหวย (จับฉลากสุ่มอิสระ)
  เครื่องมือนี้บอกแค่ "คนพูดถึงเลขอะไรบ่อย" ไม่ใช่ "เลขอะไรจะออก"

วิธีใช้:
  1. ใส่ URL เว็บเลขเด็ดที่เชื่อถือลงใน lek_dang_sources.txt
  2. ดับเบิลคลิก scrape_lek_dang.bat  (หรือ python lek_dang_scraper.py)
  3. กดปุ่ม "กวาดเลขดัง" → ดูสรุป + ไฟล์ CSV

ต้องการ: playwright (pip install playwright ; playwright install chromium)
"""
import sys, os, re, csv, asyncio, tempfile, threading
from pathlib import Path
from datetime import datetime
from collections import Counter, defaultdict
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

_HERE = Path(__file__).parent
SOURCES_FILE = _HERE / "lek_dang_sources.txt"
TEMP_PROFILE = os.path.join(tempfile.gettempdir(), "lek_dang_profile")
DEFAULT_OUT = str(_HERE.parent)

# คำที่บ่งชี้ว่ามีเลขเด็ดอยู่ใกล้ ๆ
KEYWORDS = [
    # เลขเด็ด/แนวทางทั่วไป
    'เลขเด็ด', 'เลขดัง', 'เลขเด่น', 'เลขวิ่ง', 'วิ่ง', 'สองตัว', 'สามตัว',
    'เลขบน', 'เลขล่าง', 'ตัวบน', 'ตัวล่าง', 'เลขนำ', 'เจาะ', 'ชุด', 'งวดนี้',
    'ล็อค', 'เด็ด', 'ดัง', 'เลขเข้า', 'ให้โชค', 'เลขมงคล',
    # ความฝัน
    'ฝัน', 'เลขจากฝัน', 'ทำนายฝัน', 'ฝันเห็น', 'ฝันว่า',
    # ทะเบียนรถ
    'ทะเบียน', 'ทะเบียนรถ', 'ป้ายทะเบียน', 'เลขทะเบียน', 'รถ',
    # ข่าวสาร/เหตุการณ์
    'ข่าว', 'เลขจากข่าว', 'เหตุการณ์', 'เลขข่าวดัง',
    # พระเกจิ/สายมู
    'พระ', 'เกจิ', 'หลวงพ่อ', 'หลวงปู่', 'หลวงตา', 'เจ้าอาวาส', 'วัด',
    'เลขธูป', 'เลขนาค', 'ต้นไม้', 'งูเงี้ยว', 'ใบ้หวย', 'ปลัดขิก',
    'เซียมซี', 'ตัวเลขมงคล', 'เลขวันเกิด', 'พญานาค',
]

# กรองเลขที่มักเป็น "ปี พ.ศ./ค.ศ." หรือวันที่ ออก (ลด noise)
def looks_like_year(tok):
    if len(tok) == 4:
        n = int(tok)
        return 2400 <= n <= 2600 or 1990 <= n <= 2099
    return False

def extract_numbers(text):
    """คืน (set ของเลข 2 หลัก, set ของเลข 3 หลัก) ที่อยู่ใกล้ keyword"""
    two, three = set(), set()
    # แบ่งข้อความเป็นช่วง ๆ รอบ keyword (หน้าต่าง ±60 ตัวอักษร)
    lowers = text
    idxs = []
    for kw in KEYWORDS:
        start = 0
        while True:
            i = lowers.find(kw, start)
            if i < 0: break
            idxs.append(i)
            start = i + 1
    if not idxs:
        windows = [text]  # fallback: ทั้งหน้า
    else:
        windows = [text[max(0, i-60): i+60] for i in idxs]
    for w in windows:
        for m in re.findall(r'(?<!\d)(\d{2,3})(?!\d)', w):
            if looks_like_year(m):
                continue
            if len(m) == 2:
                two.add(m)
            elif len(m) == 3:
                three.add(m)
    return two, three


def next_draw_date():
    """งวดหวยรัฐบาลถัดไป (1 หรือ 16 ของเดือน)"""
    from datetime import date
    t = date.today()
    if t.day < 16:
        return t.replace(day=16).isoformat()
    # ไป 1 ของเดือนถัดไป
    y, m = (t.year + 1, 1) if t.month == 12 else (t.year, t.month + 1)
    return date(y, m, 1).isoformat()


def load_sources():
    if not SOURCES_FILE.exists():
        return []
    urls = []
    for line in SOURCES_FILE.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if not line.startswith('http'):
            line = 'https://' + line
        urls.append(line)
    return urls


async def scrape_async(urls, log_fn, progress_fn):
    from playwright.async_api import async_playwright
    two_src = Counter()    # เลข 2 หลัก -> จำนวนเว็บที่พูดถึง
    three_src = Counter()  # เลข 3 หลัก -> จำนวนเว็บที่พูดถึง
    per_site = {}          # url -> (two, three)
    ok_sites = 0

    async with async_playwright() as p:
        try:
            ctx = await p.chromium.launch_persistent_context(
                TEMP_PROFILE, headless=True, args=['--window-size=1200,900'])
        except Exception as e:
            log_fn(f"❌ เปิด browser ไม่ได้: {e}")
            return None
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()

        for i, url in enumerate(urls, 1):
            progress_fn(i, len(urls), url)
            log_fn(f"🌐 [{i}/{len(urls)}] {url[:70]}")
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(1.5)
                text = await page.inner_text('body')
            except Exception as e:
                log_fn(f"   ⚠️ ข้าม: {str(e)[:80]}")
                continue
            two, three = extract_numbers(text)
            if not two and not three:
                log_fn("   — ไม่พบเลขใกล้ keyword")
                continue
            per_site[url] = (sorted(two), sorted(three))
            for n in two:   two_src[n] += 1
            for n in three: three_src[n] += 1
            ok_sites += 1
            log_fn(f"   ✅ พบ 2ตัว {len(two)} · 3ตัว {len(three)}")
            await asyncio.sleep(1)

        await ctx.close()

    return {'two': two_src, 'three': three_src, 'per_site': per_site,
            'ok_sites': ok_sites, 'total_sites': len(urls)}


# ─────────────────────────── GUI ───────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("กวาดเลขดัง — Lek Dang Scraper")
        self.configure(bg='#0f172a')
        self.geometry("640x600")
        self._running = False
        self._build()

    def _build(self):
        tk.Label(self, text="🔢 กวาดเลขดัง (เลขเด็ด) จากเว็บ", bg='#0f172a', fg='#fbbf24',
                 font=('Tahoma', 15, 'bold')).pack(pady=(14, 2))
        tk.Label(self, text="สรุปว่าเลขไหนถูกพูดถึงในหลายเว็บมากสุด (= ดังสุด)",
                 bg='#0f172a', fg='#94a3b8', font=('Tahoma', 10)).pack()
        tk.Label(self, text="⚠️ เลขดัง = กระแส ไม่ใช่การทำนายผลออกจริง (หวยสุ่มอิสระ)",
                 bg='#0f172a', fg='#f87171', font=('Tahoma', 9)).pack(pady=(0, 8))

        # งวดเป้าหมาย (ไว้จับคู่กับผลออกจริงภายหลัง)
        gwd = tk.Frame(self, bg='#0f172a'); gwd.pack(fill='x', padx=14, pady=(4, 0))
        tk.Label(gwd, text="งวดเป้าหมาย (YYYY-MM-DD):", bg='#0f172a', fg='#cbd5e1',
                 font=('Tahoma', 10)).pack(side='left')
        self.var_gwd = tk.StringVar(value=next_draw_date())
        tk.Entry(gwd, textvariable=self.var_gwd, width=14, bg='#1e293b', fg='#e2e8f0',
                 relief='flat', bd=0, font=('Tahoma', 11), insertbackground='white',
                 highlightthickness=1, highlightbackground='#334155').pack(side='left', padx=8)
        tk.Label(gwd, text="(บันทึกลง log เพื่อทดสอบ correlation กับผลจริง)", bg='#0f172a',
                 fg='#64748b', font=('Tahoma', 9)).pack(side='left')

        bar = tk.Frame(self, bg='#0f172a'); bar.pack(fill='x', padx=14, pady=(6,0))
        self.btn = tk.Button(bar, text="🔍 กวาดเลขดัง", command=self._start,
                             bg='#16a34a', fg='white', relief='flat', bd=0,
                             font=('Tahoma', 12, 'bold'), padx=16, pady=8, cursor='hand2')
        self.btn.pack(side='left')
        tk.Button(bar, text="📝 แก้รายการเว็บ", command=self._edit_sources,
                  bg='#334155', fg='#e2e8f0', relief='flat', bd=0,
                  font=('Tahoma', 10), padx=12, pady=8, cursor='hand2').pack(side='left', padx=8)
        self.src_lbl = tk.Label(bar, text="", bg='#0f172a', fg='#94a3b8', font=('Tahoma', 9))
        self.src_lbl.pack(side='left', padx=6)

        self.pbar = ttk.Progressbar(self, mode='determinate', length=600)
        self.pbar.pack(fill='x', padx=14, pady=(8, 4))
        self.prog_lbl = tk.Label(self, text="", bg='#0f172a', fg='#94a3b8', font=('Tahoma', 9))
        self.prog_lbl.pack()

        # ผลสรุป
        res = tk.Frame(self, bg='#0f172a'); res.pack(fill='both', expand=True, padx=14, pady=6)
        self.result = tk.Text(res, bg='#000', fg='#e2e8f0', font=('Consolas', 11),
                              relief='flat', bd=0, wrap='word', height=12,
                              highlightthickness=1, highlightbackground='#334155')
        sb = tk.Scrollbar(res, command=self.result.yview)
        self.result.configure(yscrollcommand=sb.set)
        self.result.pack(side='left', fill='both', expand=True); sb.pack(side='right', fill='y')

        # log
        self.log_text = tk.Text(self, bg='#0f172a', fg='#64748b', font=('Consolas', 9),
                                relief='flat', bd=0, wrap='word', height=6,
                                highlightthickness=1, highlightbackground='#1e293b')
        self.log_text.pack(fill='x', padx=14, pady=(0, 12))
        self._refresh_src()

    def _refresh_src(self):
        urls = load_sources()
        self.src_lbl.config(text=f"({len(urls)} เว็บใน sources)")

    def _edit_sources(self):
        if not SOURCES_FILE.exists():
            SOURCES_FILE.write_text(SOURCES_TEMPLATE, encoding='utf-8')
        os.startfile(str(SOURCES_FILE))
        self.after(1500, self._refresh_src)

    def _log(self, m):
        self.after(0, lambda: (self.log_text.insert('end', m + '\n'), self.log_text.see('end')))

    def _prog(self, c, t, u):
        def up():
            self.pbar['maximum'] = t; self.pbar['value'] = c
            self.prog_lbl.config(text=f"{c}/{t} เว็บ")
        self.after(0, up)

    def _start(self):
        if self._running: return
        urls = load_sources()
        if not urls:
            messagebox.showwarning("ยังไม่มีเว็บ",
                "กรุณากด '📝 แก้รายการเว็บ' แล้วใส่ URL เว็บเลขเด็ดที่ต้องการกวาด (บรรทัดละ 1)")
            self._edit_sources(); return
        self._running = True
        self.btn.config(state='disabled')
        self.result.delete('1.0', 'end'); self.log_text.delete('1.0', 'end')

        def run():
            loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)
            data = loop.run_until_complete(scrape_async(urls, self._log, self._prog))
            loop.close()
            self.after(0, lambda: self._done(data))
        threading.Thread(target=run, daemon=True).start()

    def _done(self, data):
        self._running = False
        self.btn.config(state='normal')
        if not data:
            self.result.insert('end', "❌ กวาดไม่สำเร็จ\n"); return
        two, three = data['two'], data['three']
        lines = []
        lines.append(f"═══ สรุปเลขดัง (จาก {data['ok_sites']}/{data['total_sites']} เว็บ) ═══\n")
        lines.append("🔸 เลข 3 ตัว — เรียงตามจำนวนเว็บที่พูดถึง:")
        for n, c in three.most_common(15):
            lines.append(f"    {n}  ← {c} เว็บ")
        lines.append("\n🔸 เลข 2 ตัว — เรียงตามจำนวนเว็บที่พูดถึง:")
        for n, c in two.most_common(15):
            lines.append(f"    {n}  ← {c} เว็บ")
        self.result.insert('end', '\n'.join(lines))

        # save CSV
        out = Path(DEFAULT_OUT) / f"lek_dang_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        with open(out, 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.writer(f)
            w.writerow(['ประเภท', 'เลข', 'จำนวนเว็บที่พูดถึง'])
            for n, c in three.most_common():
                w.writerow(['3ตัว', n, c])
            for n, c in two.most_common():
                w.writerow(['2ตัว', n, c])
        self._log(f"💾 บันทึก: {out.name}")
        self.result.insert('end', f"\n\n💾 บันทึกไฟล์: {out.name}")

        # append ลง log สะสม (สำหรับทดสอบ correlation ภายหลัง)
        gwd = self.var_gwd.get().strip()
        log_path = Path(DEFAULT_OUT) / "lek_dang_log.csv"
        new_file = not log_path.exists()
        with open(log_path, 'a', newline='', encoding='utf-8-sig') as f:
            w = csv.writer(f)
            if new_file:
                w.writerow(['งวด', 'ประเภท', 'เลข', 'จำนวนเว็บ', 'วันที่กวาด'])
            ts = datetime.now().strftime('%Y-%m-%d %H:%M')
            for n, c in three.most_common():
                w.writerow([gwd, '3ตัว', n, c, ts])
            for n, c in two.most_common():
                w.writerow([gwd, '2ตัว', n, c, ts])
        self._log(f"📚 บันทึก log งวด {gwd} → lek_dang_log.csv (ใช้ทดสอบ correlation)")


SOURCES_TEMPLATE = """# รายการเว็บเลขเด็ด/เลขดัง — ใส่ URL บรรทัดละ 1
# บรรทัดที่ขึ้นต้นด้วย # = คอมเมนต์ (ไม่ถูกกวาด)
# ตัวอย่างรูปแบบ (ใส่เว็บที่คุณเชื่อถือเอง):
# https://www.example-lottery-tips.com/
# https://another-huay-site.com/lek-ded
#
# ⚠️ เลขดังเป็นกระแส/ความเชื่อ ไม่ใช่การทำนายผลออกจริง
"""


if __name__ == '__main__':
    if not SOURCES_FILE.exists():
        SOURCES_FILE.write_text(SOURCES_TEMPLATE, encoding='utf-8')
    App().mainloop()
