# -*- coding: utf-8 -*-
"""
yk_fetch_history.py — ดึงประวัติยี่กี cat888 ย้อนหลังหลายวัน + สร้าง CSV + Screenshot

วิธีใช้:
  ดับเบิลคลิก fetch_yk_history.bat
  หรือ: python yk_fetch_history.py

ต้องการ: playwright (pip install playwright), beautifulsoup4
"""
import sys, os, csv, asyncio, tempfile, threading
from pathlib import Path
from datetime import date, timedelta, datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# ─── Import parser จาก yk_live_server ───────────────────────
_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE))
try:
    from yk_live_server import parse_yeekee_table
except ImportError:
    # fallback parser เผื่อ import ล้มเหลว
    import re
    from bs4 import BeautifulSoup
    def parse_yeekee_table(html_text):
        rows = []
        try:
            soup = BeautifulSoup(html_text, 'html.parser')
            for tbl in soup.find_all('table'):
                for tr in tbl.find_all('tr'):
                    cells = [td.get_text(strip=True) for td in tr.find_all('td')]
                    if len(cells) < 3: continue
                    rnd_str = re.sub(r'[^0-9]', '', cells[0])
                    if not rnd_str: continue
                    top3 = re.sub(r'[^0-9]', '', cells[2])[:3].zfill(3)
                    if top3 == '000': continue
                    bot2 = (re.sub(r'[^0-9]', '', cells[3]) if len(cells) > 3 else '')[:2].zfill(2)
                    t = cells[1]
                    if '-' in t and ' - ' not in t:
                        t = t.replace('-', ' - ')
                    rows.append({'round': int(rnd_str), 'time': t, 'top3': top3, 'bot2': bot2})
        except Exception:
            pass
        return rows

# ─── Config ─────────────────────────────────────────────────
CAT888_HISTORY = "https://www.cat888.co/online/yeekee/history?searching_date="
TEMP_PROFILE   = os.path.join(tempfile.gettempdir(), "yk_fetch_profile")  # แยกจาก live server (yk_brave_profile)
DEFAULT_OUT    = str(_HERE.parent)  # F:\...\Trading\data\

# ─── Playwright scraper ──────────────────────────────────────
async def fetch_range_async(start_date: date, end_date: date, out_dir: Path,
                             do_screenshot: bool, log_fn, progress_fn):
    from playwright.async_api import async_playwright
    all_rows = []
    total_days = (end_date - start_date).days + 1
    day_num = 0

    async with async_playwright() as p:
        try:
            ctx = await p.chromium.launch_persistent_context(
                TEMP_PROFILE,
                headless=False,
                args=['--window-size=1024,768']
            )
        except Exception as e:
            log_fn(f"❌ เปิด browser ไม่ได้: {e}")
            return None

        page = ctx.pages[0] if ctx.pages else await ctx.new_page()

        # Warmup: เปิดหน้าหลักก่อนให้ browser พร้อม
        log_fn("🔄 เตรียม browser...")
        try:
            await page.goto("https://www.cat888.co/", wait_until="domcontentloaded", timeout=20000)
            await asyncio.sleep(2)
        except Exception:
            pass

        d = start_date
        while d <= end_date:
            day_num += 1
            url = CAT888_HISTORY + d.strftime("%Y-%m-%d")
            log_fn(f"📅 กำลังดึง {d} ...")
            progress_fn(day_num, total_days, d)

            rows = []
            skipped_holiday = False
            for attempt in range(2):  # retry เฉพาะ error เครือข่าย
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    # ตรวจว่าถูก redirect ออกไปหรือเปล่า = วันหยุด/หน้า lock ของเว็บ
                    current_url = page.url
                    if "history" not in current_url:
                        # หน้าว่าง/lock (วันหยุดของเว็บ) → ข้ามทันที ไม่ต้องอ่าน/ดูซ้ำ
                        log_fn(f"⏭️ {d} — วันหยุดของเว็บ (หน้าว่าง/lock) ข้าม")
                        skipped_holiday = True
                        break

                    await page.wait_for_selector("table", timeout=15000)
                    title = (await page.title()).lower()
                    if "login" in title or "เข้าสู่ระบบ" in title:
                        log_fn("❌ ต้อง login ก่อน — เปิดโปรแกรม ก.ย. login แล้ว restart")
                        d = end_date + timedelta(days=1)  # หยุด loop
                        break

                    html = await page.content()
                    rows = parse_yeekee_table(html)
                    # ตารางว่าง (ไม่มีรอบ) = วันหยุด → ข้ามทันที ไม่ retry
                    if not rows:
                        log_fn(f"⏭️ {d} — วันหยุดของเว็บ (ตารางว่าง) ข้าม")
                        skipped_holiday = True
                    break  # สำเร็จ (มีข้อมูล หรือ ตารางว่าง — ทั้งคู่ไม่ต้อง retry)

                except Exception as e:
                    if attempt == 0:
                        log_fn(f"   ⚠️ attempt 1 error: {str(e)[:80]} — ลองใหม่")
                        await asyncio.sleep(3)
                    else:
                        log_fn(f"⚠️ {d} — ข้าม: {str(e)[:100]}")

            if rows:
                for r in rows:
                    r['date'] = d.strftime("%Y-%m-%d")
                all_rows.extend(rows)
                log_fn(f"✅ {d} — {len(rows)} รอบ")
            elif not skipped_holiday and d <= end_date:
                log_fn(f"⚠️ {d} — ไม่พบข้อมูล")

            if do_screenshot and rows:
                try:
                    ss_path = out_dir / f"yk_ss_{d.strftime('%Y%m%d')}.png"
                    await page.screenshot(path=str(ss_path), full_page=True)
                    log_fn(f"   📸 Screenshot → {ss_path.name}")
                except Exception:
                    pass

            d += timedelta(days=1)
            await asyncio.sleep(1.5)  # กันถูกบล็อก

        await ctx.close()

    if not all_rows:
        return None

    fname = f"yk_his_{start_date.strftime('%Y%m%d')}_to_{end_date.strftime('%Y%m%d')}.csv"
    csv_path = out_dir / fname
    with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=['วันที่', 'รอบ', 'เวลา', '3 ตัวบน', '2 ตัวล่าง', 'สถานะ'])
        writer.writeheader()
        for r in all_rows:
            writer.writerow({
                'วันที่': r['date'],
                'รอบ':   r['round'],
                'เวลา':  r['time'],
                '3 ตัวบน': r['top3'],
                '2 ตัวล่าง': r['bot2'],
                'สถานะ': 'result'
            })

    # ลบ screenshot *.png หลังบันทึก CSV เสร็จ (ไม่จำเป็นแล้ว)
    deleted = 0
    for png in out_dir.glob("yk_ss_*.png"):
        try:
            png.unlink()
            deleted += 1
        except Exception:
            pass
    if deleted:
        log_fn(f"🧹 ลบ screenshot {deleted} ไฟล์ (ไม่จำเป็นหลังได้ CSV)")

    return csv_path, len(all_rows)


# ─── GUI ─────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("YK History Fetcher — ดึงประวัติยี่กี cat888")
        self.configure(bg='#0f172a')
        self.resizable(True, True)
        self.minsize(540, 480)
        self._build_ui()
        self._running = False

    # ── Helpers ──────────────────────────────────────────────
    def _lbl(self, parent, text, fg='#e2e8f0', **kw):
        return tk.Label(parent, text=text, bg='#0f172a', fg=fg,
                        font=('Tahoma', 10), **kw)

    def _entry(self, parent, textvariable, width=16):
        return tk.Entry(parent, textvariable=textvariable, width=width,
                        bg='#1e293b', fg='#e2e8f0', insertbackground='white',
                        relief='flat', bd=0, font=('Tahoma', 11),
                        highlightthickness=1, highlightcolor='#3b82f6',
                        highlightbackground='#334155')

    def _btn(self, parent, text, command, color='#3b82f6', fg='white', padx=14, pady=7, **kw):
        b = tk.Button(parent, text=text, command=command,
                      bg=color, fg=fg, activebackground=color,
                      relief='flat', bd=0, font=('Tahoma', 11, 'bold'),
                      padx=padx, pady=pady, cursor='hand2', **kw)
        b.bind('<Enter>', lambda e: b.config(bg=self._darken(color)))
        b.bind('<Leave>', lambda e: b.config(bg=color))
        return b

    @staticmethod
    def _darken(hex_color):
        try:
            r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
            return f'#{max(0,r-25):02x}{max(0,g-25):02x}{max(0,b-25):02x}'
        except Exception:
            return hex_color

    # ── Build UI ─────────────────────────────────────────────
    def _build_ui(self):
        pad = {'padx': 14, 'pady': 6}

        # Title
        tk.Label(self, text="📅 YK History Fetcher", bg='#0f172a', fg='#60a5fa',
                 font=('Tahoma', 15, 'bold')).pack(pady=(14, 2))
        tk.Label(self, text="ดึงประวัติยี่กี cat888.co หลายวันพร้อมกัน → CSV",
                 bg='#0f172a', fg='#94a3b8', font=('Tahoma', 10)).pack(pady=(0, 10))

        # Card frame
        card = tk.Frame(self, bg='#1e293b', bd=0, relief='flat')
        card.pack(fill='x', padx=14, pady=4)

        # Date inputs
        frm_dates = tk.Frame(card, bg='#1e293b')
        frm_dates.pack(fill='x', **pad)
        today = date.today()
        week_ago = today - timedelta(days=6)
        self.var_from = tk.StringVar(value=week_ago.strftime('%Y-%m-%d'))
        self.var_to   = tk.StringVar(value=today.strftime('%Y-%m-%d'))
        self._lbl(frm_dates, "จากวันที่:").grid(row=0, column=0, sticky='w', padx=(0, 8))
        self._entry(frm_dates, self.var_from).grid(row=0, column=1, sticky='w')
        self._lbl(frm_dates, "  ถึง:").grid(row=0, column=2, sticky='w', padx=(12, 8))
        self._entry(frm_dates, self.var_to).grid(row=0, column=3, sticky='w')
        self._lbl(frm_dates, "  (YYYY-MM-DD)", fg='#64748b').grid(row=0, column=4, sticky='w', padx=(8, 0))

        # Output dir
        frm_out = tk.Frame(card, bg='#1e293b')
        frm_out.pack(fill='x', **pad)
        self.var_out = tk.StringVar(value=DEFAULT_OUT)
        self._lbl(frm_out, "บันทึกที่:").grid(row=0, column=0, sticky='w', padx=(0, 8))
        tk.Entry(frm_out, textvariable=self.var_out, width=42,
                 bg='#0f172a', fg='#94a3b8', insertbackground='white',
                 relief='flat', bd=0, font=('Tahoma', 10),
                 highlightthickness=1, highlightcolor='#3b82f6',
                 highlightbackground='#334155').grid(row=0, column=1, sticky='ew')
        self._btn(frm_out, "📁", self._choose_dir, color='#334155', pady=4, padx=8
                  ).grid(row=0, column=2, padx=(6, 0))
        frm_out.columnconfigure(1, weight=1)

        # Screenshot checkbox
        frm_opts = tk.Frame(card, bg='#1e293b')
        frm_opts.pack(fill='x', padx=14, pady=4)
        self.var_ss = tk.BooleanVar(value=True)
        tk.Checkbutton(frm_opts, text="📸 บันทึก Screenshot ต่อวัน (.png)",
                       variable=self.var_ss, bg='#1e293b', fg='#e2e8f0',
                       selectcolor='#0f172a', activebackground='#1e293b',
                       font=('Tahoma', 10)).pack(side='left')

        # Start button
        frm_btn = tk.Frame(self, bg='#0f172a')
        frm_btn.pack(pady=8)
        self.btn_start = self._btn(frm_btn, "🚀  เริ่มดึงข้อมูล", self._on_start, color='#16a34a')
        self.btn_start.pack(side='left', padx=4)
        self.btn_stop = self._btn(frm_btn, "⏹ หยุด", self._on_stop, color='#dc2626')
        self.btn_stop.pack(side='left', padx=4)
        self.btn_stop.config(state='disabled')

        # Progress
        frm_prog = tk.Frame(self, bg='#0f172a')
        frm_prog.pack(fill='x', padx=14, pady=(0, 4))
        self.var_prog_lbl = tk.StringVar(value="")
        tk.Label(frm_prog, textvariable=self.var_prog_lbl, bg='#0f172a',
                 fg='#94a3b8', font=('Tahoma', 10)).pack(side='left')
        self.pbar = ttk.Progressbar(frm_prog, mode='determinate', length=350)
        self.pbar.pack(side='left', padx=(10, 0), fill='x', expand=True)

        # Log text area
        log_frame = tk.Frame(self, bg='#0f172a')
        log_frame.pack(fill='both', expand=True, padx=14, pady=(4, 14))
        self._lbl(log_frame, "Log:").pack(anchor='w')
        txt_frame = tk.Frame(log_frame, bg='#0f172a')
        txt_frame.pack(fill='both', expand=True)
        self.log_text = tk.Text(txt_frame, bg='#000', fg='#94a3b8',
                                font=('Consolas', 10), relief='flat',
                                bd=0, wrap='word', state='disabled',
                                highlightthickness=1, highlightbackground='#334155')
        sb = tk.Scrollbar(txt_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=sb.set)
        self.log_text.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')

        # Result label
        self.var_result = tk.StringVar(value="")
        tk.Label(self, textvariable=self.var_result, bg='#0f172a', fg='#4ade80',
                 font=('Tahoma', 11, 'bold'), wraplength=500).pack(pady=(0, 8))

    # ── Actions ──────────────────────────────────────────────
    def _choose_dir(self):
        d = filedialog.askdirectory(initialdir=self.var_out.get(), title="เลือกโฟลเดอร์บันทึก")
        if d:
            self.var_out.set(d)

    def _log(self, msg: str):
        self.after(0, self._log_ui, msg)

    def _log_ui(self, msg: str):
        self.log_text.config(state='normal')
        ts = datetime.now().strftime('%H:%M:%S')
        self.log_text.insert('end', f"[{ts}] {msg}\n")
        self.log_text.see('end')
        self.log_text.config(state='disabled')

    def _set_progress(self, current: int, total: int, d: date):
        def _upd():
            self.pbar['maximum'] = total
            self.pbar['value'] = current
            self.var_prog_lbl.set(f"{current}/{total} วัน — {d}")
        self.after(0, _upd)

    def _parse_date(self, val: str, label: str) -> date | None:
        val = val.strip()
        for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%Y%m%d'):
            try:
                return datetime.strptime(val, fmt).date()
            except ValueError:
                continue
        messagebox.showerror("วันที่ไม่ถูกต้อง", f"{label}: '{val}'\nรูปแบบที่รับได้: YYYY-MM-DD")
        return None

    def _on_start(self):
        if self._running:
            return
        start = self._parse_date(self.var_from.get(), "จากวันที่")
        end   = self._parse_date(self.var_to.get(), "ถึง")
        if not start or not end:
            return
        if start > end:
            messagebox.showerror("ข้อผิดพลาด", "วันเริ่มต้นต้องไม่มากกว่าวันสิ้นสุด")
            return
        if (end - start).days > 365:
            if not messagebox.askyesno("ยืนยัน", f"ช่วงนี้ยาว {(end-start).days+1} วัน — ใช้เวลานาน\nดำเนินการต่อ?"):
                return

        out_dir = Path(self.var_out.get())
        out_dir.mkdir(parents=True, exist_ok=True)

        self._running = True
        self.btn_start.config(state='disabled')
        self.btn_stop.config(state='normal')
        self.var_result.set("")
        self._log(f"▶ เริ่มดึง {start} ถึง {end} ({(end-start).days+1} วัน)")

        def _run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(
                fetch_range_async(start, end, out_dir,
                                  self.var_ss.get(),
                                  self._log, self._set_progress)
            )
            loop.close()
            self.after(0, self._on_done, result, out_dir)

        threading.Thread(target=_run, daemon=True).start()

    def _on_stop(self):
        self._running = False
        self._log("⏹ ขอหยุด — รอรอบปัจจุบันเสร็จก่อน...")

    def _on_done(self, result, out_dir: Path):
        self._running = False
        self.btn_start.config(state='normal')
        self.btn_stop.config(state='disabled')
        self.pbar['value'] = self.pbar['maximum']
        if result:
            csv_path, total_rows = result
            self._log(f"✅ เสร็จ! {total_rows} แถว → {csv_path.name}")
            self.var_result.set(f"✅ CSV: {csv_path.name}  ({total_rows:,} rows)")
            if messagebox.askyesno("เสร็จแล้ว", f"บันทึก {total_rows:,} แถว\nเปิดโฟลเดอร์?"):
                os.startfile(str(out_dir))
        else:
            self._log("⚠️ ไม่ได้ข้อมูล — ตรวจ login หรือวันที่")
            self.var_result.set("⚠️ ไม่ได้ข้อมูล — ดู Log ด้านบน")


# ─── Entry ───────────────────────────────────────────────────
if __name__ == '__main__':
    app = App()
    app.mainloop()
