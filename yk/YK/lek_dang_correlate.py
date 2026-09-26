# -*- coding: utf-8 -*-
"""
lek_dang_correlate.py — ทดสอบว่า "เลขดัง" correlate กับ "ผลออกจริง" ไหม

หลักการ (พิสูจน์เชิงวิชาการ):
  - เลขดังที่กวาดไว้ (lek_dang_log.csv) จับคู่กับผลออกจริง (lek_dang_results.csv) ตามงวด
  - แต่ละงวด: ดูว่าผลจริง (3บน/2บน/2ล่าง) ตรงกับเลขดังที่ทำนายไว้ไหม
  - เทียบ hit rate จริง vs baseline สุ่ม → lift
  - ถ้า lift ≈ 1.0 = เลขดังไม่มีผล (สุ่ม) · ถ้า >1.2 อย่างมีนัย = มี signal (คาดว่าไม่มี)

ไฟล์ที่ใช้:
  lek_dang_log.csv     : งวด,ประเภท,เลข,จำนวนเว็บ,วันที่กวาด   (สร้างโดย scraper)
  lek_dang_results.csv : งวด,3บน,2บน,2ล่าง                      (ผู้ใช้กรอกผลจริง)

วิธีใช้:
  ดับเบิลคลิก correlate_lek_dang.bat  (หรือ python lek_dang_correlate.py)
"""
import csv
from pathlib import Path
from collections import defaultdict
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

_HERE = Path(__file__).parent
DATA = _HERE.parent
LOG = DATA / "lek_dang_log.csv"
RESULTS = DATA / "lek_dang_results.csv"


def load_log(path):
    """งวด -> {'3ตัว': set, '2ตัว': set}"""
    d = defaultdict(lambda: {'3ตัว': set(), '2ตัว': set()})
    if not path.exists():
        return d
    with open(path, encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            g = (row.get('งวด') or '').strip()
            typ = (row.get('ประเภท') or '').strip()
            num = (row.get('เลข') or '').strip()
            if g and typ in ('3ตัว', '2ตัว') and num:
                d[g][typ].add(num)
    return d


def load_results(path):
    """งวด -> {'3บน','2บน','2ล่าง'}"""
    d = {}
    if not path.exists():
        return d
    with open(path, encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            g = (row.get('งวด') or '').strip()
            if g:
                d[g] = {
                    '3บน': (row.get('3บน') or '').strip().zfill(3),
                    '2บน': (row.get('2บน') or '').strip().zfill(2),
                    '2ล่าง': (row.get('2ล่าง') or '').strip().zfill(2),
                }
    return d


def analyze(log, results):
    """คืนสรุปผล correlation"""
    matched = [g for g in log if g in results]
    lines = []
    if not matched:
        return "❌ ไม่มีงวดที่จับคู่ได้ (log กับ results ต้องมี 'งวด' ตรงกัน)\n" \
               f"   log มี {len(log)} งวด · results มี {len(results)} งวด"

    # นับ hit ต่อประเภท
    stats = {  # ประเภทแทง: [hit, total, sum_baseline]
        '2ล่าง (จากเลขดัง 2ตัว)': [0, 0, 0.0],
        '2บน (จากเลขดัง 2ตัว)':  [0, 0, 0.0],
        '3บน (จากเลขดัง 3ตัว)':  [0, 0, 0.0],
    }
    for g in matched:
        pred2 = log[g]['2ตัว']
        pred3 = log[g]['3ตัว']
        res = results[g]
        # 2ล่าง: ผลจริง 2ล่าง อยู่ในเลขดัง 2ตัวไหม
        if pred2:
            s = stats['2ล่าง (จากเลขดัง 2ตัว)']
            s[1] += 1; s[2] += len(pred2) / 100.0   # baseline = แทง K เลขจาก 100
            if res['2ล่าง'] in pred2: s[0] += 1
            s2 = stats['2บน (จากเลขดัง 2ตัว)']
            s2[1] += 1; s2[2] += len(pred2) / 100.0
            if res['2บน'] in pred2: s2[0] += 1
        if pred3:
            s = stats['3บน (จากเลขดัง 3ตัว)']
            s[1] += 1; s[2] += len(pred3) / 1000.0
            if res['3บน'] in pred3: s[0] += 1

    lines.append(f"═══ ผลทดสอบ Correlation ({len(matched)} งวดที่จับคู่ได้) ═══\n")
    lines.append(f"{'ประเภท':32s} {'ถูก/งวด':>10s} {'จริง%':>7s} {'สุ่ม%':>7s} {'lift':>6s}  สรุป")
    for name, (hit, tot, base) in stats.items():
        if tot == 0:
            continue
        act = hit / tot
        exp = base / tot
        lift = act / exp if exp > 0 else 0
        verdict = ('✅ มี signal!' if lift >= 1.3 else
                   ('~ ก้ำกึ่ง' if lift >= 1.15 else '❌ ไม่ต่างจากสุ่ม (noise)'))
        lines.append(f"{name:32s} {hit:>4d}/{tot:<5d} {act*100:6.2f}% {exp*100:6.2f}% {lift:5.2f}x  {verdict}")

    lines.append("\n📌 แปลผล:")
    lines.append("   lift ≈ 1.0 = เลขดังไม่ช่วย (ถูกเท่าสุ่มเดา) · lift > 1.3 = เลขดังมี signal จริง")
    lines.append("   ⚠️ ต้องมีหลายงวด (เช่น ≥20) ผลถึงเชื่อถือได้ — งวดน้อย = ยังสรุปไม่ได้")
    if len(matched) < 20:
        lines.append(f"\n   🔸 ตอนนี้มีแค่ {len(matched)} งวด — เก็บข้อมูลเพิ่มก่อนสรุป")
    return '\n'.join(lines)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ทดสอบ Correlation เลขดัง vs ผลจริง")
        self.configure(bg='#0f172a'); self.geometry("680x520")
        self.log_path = LOG; self.res_path = RESULTS
        self._build()

    def _build(self):
        tk.Label(self, text="🔬 ทดสอบ: เลขดัง correlate กับผลออกจริงไหม?", bg='#0f172a',
                 fg='#a78bfa', font=('Tahoma', 15, 'bold')).pack(pady=(14, 2))
        tk.Label(self, text="จับคู่ 'เลขดังที่กวาดไว้' กับ 'ผลออกจริง' ตามงวด → คำนวณ lift",
                 bg='#0f172a', fg='#94a3b8', font=('Tahoma', 10)).pack(pady=(0, 10))

        for label, attr, hint in [
            ("ไฟล์เลขดัง (log):", 'log_path', "lek_dang_log.csv (สร้างโดย scraper)"),
            ("ไฟล์ผลจริง:", 'res_path', "lek_dang_results.csv (งวด,3บน,2บน,2ล่าง)")]:
            fr = tk.Frame(self, bg='#0f172a'); fr.pack(fill='x', padx=14, pady=3)
            tk.Label(fr, text=label, bg='#0f172a', fg='#cbd5e1', font=('Tahoma', 10),
                     width=16, anchor='w').pack(side='left')
            var = tk.StringVar(value=str(getattr(self, attr)))
            setattr(self, attr + '_var', var)
            tk.Entry(fr, textvariable=var, bg='#1e293b', fg='#e2e8f0', relief='flat', bd=0,
                     font=('Tahoma', 9), insertbackground='white', highlightthickness=1,
                     highlightbackground='#334155').pack(side='left', fill='x', expand=True, padx=6)
            tk.Button(fr, text="📁", command=lambda a=attr: self._pick(a), bg='#334155',
                      fg='#e2e8f0', relief='flat', bd=0, cursor='hand2').pack(side='left')

        tk.Button(self, text="🔬 ทดสอบ Correlation", command=self._run, bg='#7c3aed',
                  fg='white', relief='flat', bd=0, font=('Tahoma', 12, 'bold'),
                  padx=16, pady=8, cursor='hand2').pack(pady=10)

        res = tk.Frame(self, bg='#0f172a'); res.pack(fill='both', expand=True, padx=14, pady=6)
        self.out = tk.Text(res, bg='#000', fg='#e2e8f0', font=('Consolas', 10), relief='flat',
                           bd=0, wrap='word', highlightthickness=1, highlightbackground='#334155')
        sb = tk.Scrollbar(res, command=self.out.yview); self.out.configure(yscrollcommand=sb.set)
        self.out.pack(side='left', fill='both', expand=True); sb.pack(side='right', fill='y')

    def _pick(self, attr):
        f = filedialog.askopenfilename(filetypes=[('CSV', '*.csv')])
        if f: getattr(self, attr + '_var').set(f)

    def _run(self):
        log = load_log(Path(self.log_path_var.get()))
        results = load_results(Path(self.res_path_var.get()))
        self.out.delete('1.0', 'end')
        self.out.insert('end', analyze(log, results))


if __name__ == '__main__':
    App().mainloop()
