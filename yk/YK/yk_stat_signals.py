# -*- coding: utf-8 -*-
"""
yk_stat_signals.py — เก็บสถิติสัญญาณ ⑩ + ⑪ สะสมหลายวัน

⑩ เลขเรียง (ขึ้น 012..901 / ลง 987..098) ออก → 3 รอบถัดไปเป็น OK?
⑪ 2ตัวล่าง เด่น {97,78,69} / เย็น {95} ออก → 3 รอบถัดไปเป็น OK?

วิธีใช้:
  python yk_stat_signals.py --bootstrap   # เก็บย้อนหลังจาก CSV ประวัติ (ครั้งแรก)
  python yk_stat_signals.py               # ดึง LIVE วันนี้มา append (กันวันซ้ำ)
  python yk_stat_signals.py --show        # แสดงสถิติสะสมอย่างเดียว

ผลเก็บใน stat_signals_history.json (key = วันที่)
"""
import json, os, sys, csv, urllib.request
from datetime import date
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.dirname(HERE)
HIST = os.path.join(HERE, "stat_signals_history.json")
CSV_HISTORY = os.path.join(DATA_DIR, "cat888-yeekee-history-300d.csv")
LIVE_URL = "http://localhost:5001/live.json"
STATUS_URL = "http://localhost:5001/status"

HOT  = {'97', '78', '69'}
COLD = {'95'}
LOOK = 3
BASE_OK = 0.302   # baseline OK/รอบ
BASE_ANY = 0.659  # baseline any-3

def is_ok(s):
    a, b, c = s[0], s[1], s[2]
    if a == b or b == c or a == c:
        return True
    x, y, z = int(a), int(b), int(c)
    return ((y-x) % 10 == 1 and (z-y) % 10 == 1) or ((x-y) % 10 == 1 and (y-z) % 10 == 1)
def is_up(s):
    x, y, z = int(s[0]), int(s[1]), int(s[2]); return (y-x) % 10 == 1 and (z-y) % 10 == 1
def is_down(s):
    x, y, z = int(s[0]), int(s[1]), int(s[2]); return (x-y) % 10 == 1 and (y-z) % 10 == 1

def eval_day(rows):
    """rows = [(round, up3, low2)] → นับ per-row & any-3 ของทุกสัญญาณ"""
    rows = sorted(rows, key=lambda r: r[0])
    oks = [is_ok(r[1]) for r in rows]
    n = len(rows)
    # keys: <sig>_n/_ok (per-row) , <sig>_any/_anyhit (any-3)
    R = {k: 0 for k in (
        'up_n','up_ok','up_any','up_anyhit', 'down_n','down_ok','down_any','down_anyhit',
        'hot_n','hot_ok','hot_any','hot_anyhit', 'cold_n','cold_ok','cold_any','cold_anyhit')}
    R['rows'] = n
    def bump(pfx, i):
        for k in range(1, LOOK+1):
            if i+k < n:
                R[pfx+'_n'] += 1
                if oks[i+k]: R[pfx+'_ok'] += 1
        if i+LOOK < n:
            R[pfx+'_any'] += 1
            if any(oks[i+1:i+1+LOOK]): R[pfx+'_anyhit'] += 1
    for i in range(n):
        up3, low2 = rows[i][1], rows[i][2]
        if is_up(up3):   bump('up', i)
        elif is_down(up3): bump('down', i)
        if low2 in HOT:  bump('hot', i)
        elif low2 in COLD: bump('cold', i)
    return R

def load_hist():
    if os.path.exists(HIST):
        with open(HIST, encoding='utf-8') as f:
            return json.load(f)
    return {}
def save_hist(h):
    with open(HIST, 'w', encoding='utf-8') as f:
        json.dump(h, f, ensure_ascii=False, indent=1)

def bootstrap():
    days = {}
    with open(CSV_HISTORY, encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            up3 = row['3 ตัวบน'].strip().zfill(3)
            if len(up3) == 3 and up3.isdigit():
                d = row['วันที่'].strip()
                days.setdefault(d, []).append(
                    (int(row['รอบ']), up3, row['2 ตัวล่าง'].strip().zfill(2)))
    hist = load_hist()
    added = 0
    for d, rows in days.items():
        if d in hist and hist[d].get('src') == 'csv':
            continue
        hist[d] = eval_day(rows); hist[d]['src'] = 'csv'
        added += 1
    save_hist(hist)
    print(f"✅ Bootstrap: เพิ่ม/อัปเดต {added} วันจาก CSV (รวมสะสม {len(hist)} วัน)")

def add_live():
    data_date = date.today().strftime("%Y-%m-%d")
    try:
        with urllib.request.urlopen(STATUS_URL, timeout=10) as r:
            info = json.load(r)
            if info.get('today'): data_date = info['today']
    except Exception:
        pass
    try:
        with urllib.request.urlopen(LIVE_URL, timeout=10) as r:
            live = json.load(r)
    except Exception as e:
        print(f"❌ ดึง LIVE ไม่ได้: {e}\n   (ต้องรัน yk_live_server.py ก่อน)")
        return
    rows = [(int(x['round']), x['top3'], x.get('bot2', '00'))
            for x in live if x.get('top3') and x['top3'] != '000']
    if not rows:
        print("⚠ LIVE ยังไม่มีข้อมูล"); return
    hist = load_hist()
    existed = data_date in hist
    hist[data_date] = eval_day(rows); hist[data_date]['src'] = 'live'
    save_hist(hist)
    h = hist[data_date]
    print(f"✅ {'อัปเดต' if existed else 'เก็บ'} ({data_date}): {len(rows)} รอบ · "
          f"⑩ขึ้น {h['up_any']} ลง {h['down_any']} · ⑪เด่น {h['hot_any']} เย็น {h['cold_any']} "
          f"(รวม {len(hist)} วัน)")

def show():
    hist = load_hist()
    if not hist:
        print("ยังไม่มีข้อมูล — รัน --bootstrap ก่อน"); return
    T = defaultdict(int)
    for d in hist.values():
        for k, v in d.items():
            if isinstance(v, int): T[k] += v

    print(f"\n{'='*68}")
    print(f"  สถิติสัญญาณสะสม {len(hist)} วัน (baseline per-row {BASE_OK*100:.1f}% · any-3 {BASE_ANY*100:.1f}%)")
    print(f"{'='*68}")

    def line(lbl, pfx):
        n, ok = T[pfx+'_n'], T[pfx+'_ok']
        an, ah = T[pfx+'_any'], T[pfx+'_anyhit']
        if not n:
            print(f"  {lbl}: ยังไม่มีข้อมูล"); return
        pr = ok/n*100; pa = ah/an*100 if an else 0
        fr = '🟢' if pa/(BASE_ANY*100) > 1.05 else ('🔴' if pa/(BASE_ANY*100) < 0.95 else '⚪')
        print(f"  {lbl}: per-row {ok}/{n}={pr:.1f}% (lift {pr/(BASE_OK*100):.2f}) · "
              f"any-3 {ah}/{an}={pa:.1f}% (lift {pa/(BASE_ANY*100):.2f}) {fr}")

    print("\n【 ⑩ เลขเรียง → 3 รอบถัดไป 】")
    line("เรียงขึ้น 012..901", 'up')
    line("เรียงลง  987..098", 'down')
    print("\n【 ⑪ 2ตัวล่าง → 3 รอบถัดไป 】")
    line("ล่างเด่น 97/78/69 ", 'hot')
    line("ล่างเย็น 95       ", 'cold')

    print(f"\n{'วันที่':<12}{'src':>5}  ⑩ขึ้น(any)  ⑩ลง(any)  ⑪เด่น(any) ⑪เย็น(any)")
    for d in sorted(hist):
        h = hist[d]
        f = lambda p: f"{h.get(p+'_anyhit',0)}/{h.get(p+'_any',0)}"
        print(f"{d:<12}{h.get('src','?'):>5}  {f('up'):>9}  {f('down'):>9}  {f('hot'):>9}  {f('cold'):>9}")

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    arg = sys.argv[1] if len(sys.argv) > 1 else ''
    if arg == '--bootstrap': bootstrap()
    elif arg == '--show': pass
    else: add_live()
    show()
