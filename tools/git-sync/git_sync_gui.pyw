# git_sync_gui.pyw — หน้าต่าง Git Sync: pull / push หลาย repo พร้อมกัน (ลุงพี)
# ขั้นตอน: ติ๊ก repo → เลือก ดึง/ส่ง → ① ดูแผน (ยังไม่แตะอะไร) → ② ดำเนินการ + ยืนยัน
# ไม่ใช้ --force · CONFLICT = ยกเลิก rebase กลับสภาพเดิม · เจอคีย์/ไฟล์ลับ/ไฟล์ใหญ่ = ไม่ commit repo นั้น
import json, os, queue, re, subprocess, sys, threading, datetime
from concurrent.futures import ThreadPoolExecutor
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog

HERE = os.path.dirname(os.path.abspath(__file__))
REPOS_TXT = os.path.join(HERE, 'repos.txt')
STATE_JSON = os.path.join(HERE, 'git-sync-gui.json')
LOG = os.path.join(HERE, 'git-sync.log')
DRIVE = os.path.splitdrive(HERE)[0] or 'F:'
try:
    VERSION = json.load(open(os.path.join(HERE, 'VERSION.json'), encoding='utf-8'))['version']
except Exception:
    VERSION = '?'
NOWIN = 0x08000000 if os.name == 'nt' else 0

SECRET_RX = re.compile('|'.join([
    r'sk-[A-Za-z0-9_-]{20,}', r'AIza[0-9A-Za-z_-]{30,}', r'ghp_[A-Za-z0-9]{30,}', r'gsk_[A-Za-z0-9]{20,}',
    r'hf_[A-Za-z0-9]{20,}', r'xai-[A-Za-z0-9]{20,}', 'sb_' + 'secret_', 'service' + '_role',
    r'eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{10,}']))
BADNAME_RX = re.compile(r'(^|/)(\.env(\..*)?|config\.ini|credentials\.json|settings\.local\.json)$|\.(key|pem|pfx|p12)$', re.I)
BIG = 95 * 1024 * 1024


def git(repo, *args, timeout=300):
    """รัน git คืน (code, stdout, stderr) เป็นข้อความ UTF-8"""
    try:
        p = subprocess.run(['git', '-C', repo, '-c', 'core.quotepath=false', *args], capture_output=True,
                           timeout=timeout, creationflags=NOWIN)
        dec = lambda b: b.decode('utf-8', 'replace')
        # stdout ตัดแค่ท้าย — status --porcelain มีช่องว่างนำหน้าที่มีความหมาย (" M ไฟล์")
        return p.returncode, dec(p.stdout).rstrip(), dec(p.stderr).strip()
    except FileNotFoundError:
        return 127, '', 'ไม่พบโปรแกรม git ในเครื่อง'
    except subprocess.TimeoutExpired:
        return 124, '', 'หมดเวลา (timeout)'


def log(msg):
    try:
        with open(LOG, 'a', encoding='utf-8') as f:
            f.write(f'{datetime.datetime.now():%Y-%m-%d %H:%M:%S}  [GUI] {msg}\n')
    except OSError:
        pass


def fmt_size(n):
    if n is None: return ''
    for u in ('B', 'KB', 'MB', 'GB'):
        if n < 1024: return f'{n:.0f} {u}' if u == 'B' else f'{n:.1f} {u}'
        n /= 1024
    return f'{n:.1f} TB'


# ---------------- รายชื่อ repo ----------------
def resolve(rel):
    for root in dict.fromkeys([DRIVE, 'F:', 'C:']):
        p = os.path.join(root + os.sep, rel)
        if os.path.isdir(os.path.join(p, '.git')) or os.path.isfile(os.path.join(p, '.git')):
            return p
    return None


def read_repos():
    out = []
    with open(REPOS_TXT, encoding='utf-8-sig') as f:
        for line in f:
            t = line.strip()
            if t and not t.startswith('#'):
                out.append(t)
    return out


def write_repos(add=None, remove=()):
    """เพิ่ม/เอาออกทีละบรรทัด — คงคอมเมนต์และบรรทัดที่ปิด (#) ไว้เหมือนเดิม"""
    with open(REPOS_TXT, encoding='utf-8-sig') as f:
        lines = [l.rstrip('\r\n') for l in f]
    lines = [l for l in lines if l.strip() not in remove]
    if add:
        k = max((n for n, l in enumerate(lines) if l.strip() and not l.strip().startswith('#')), default=len(lines) - 1)
        lines.insert(k + 1, add)
    with open(REPOS_TXT, 'w', encoding='utf-8', newline='\r\n') as f:
        f.write('\n'.join(lines) + '\n')


def load_state():
    try:
        return json.load(open(STATE_JSON, encoding='utf-8'))
    except Exception:
        return {'unchecked': [], 'include_new': False}


def save_state(st):
    try:
        json.dump(st, open(STATE_JSON, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    except OSError:
        pass


# ---------------- งาน git ต่อ 1 repo ----------------
def upstream(repo):
    c, o, _ = git(repo, 'rev-parse', '--abbrev-ref', '@{u}')
    return o if c == 0 else None


def plan_pull(repo):
    rows = []
    br = git(repo, 'branch', '--show-current')[1]
    up = upstream(repo)
    if not br: return 'skip', 'detached HEAD — ข้าม', rows
    if not up: return 'skip', f'branch {br} ไม่มี upstream — ข้าม', rows
    c, _, e = git(repo, 'fetch', '--quiet')
    if c: return 'err', 'fetch ไม่สำเร็จ: ' + (e.splitlines()[-1] if e else f'exit {c}'), rows
    behind = git(repo, 'rev-list', '--count', f'HEAD..{up}')[1] or '0'
    ahead = git(repo, 'rev-list', '--count', f'{up}..HEAD')[1] or '0'
    dirty = [l for l in git(repo, 'status', '--porcelain')[1].splitlines() if l]
    if behind == '0':
        return 'same', 'ล่าสุดแล้ว' + (f' · มี commit รอ push {ahead}' if ahead != '0' else ''), rows
    for l in git(repo, 'log', '--format=%h  %s', f'HEAD..{up}', '-n', '30')[1].splitlines():
        rows.append(('⬇ ใหม่', l, None))
    note = f'จะดึงมา {behind} commit'
    if dirty: note += f' · มีไฟล์ค้าง {len(dirty)} (เก็บพักให้อัตโนมัติแล้วคืนกลับ)'
    return 'todo', note, rows


def plan_push(repo, include_new):
    rows = []
    br = git(repo, 'branch', '--show-current')[1]
    up = upstream(repo)
    if not br: return 'skip', 'detached HEAD — ข้าม', rows
    if not up: return 'skip', f'branch {br} ไม่มี upstream — ข้าม', rows
    git(repo, 'fetch', '--quiet')
    ahead = git(repo, 'rev-list', '--count', f'{up}..HEAD')[1] or '0'
    blocked = False
    files = []
    for l in git(repo, 'status', '--porcelain', '--untracked-files=' + ('all' if include_new else 'no'))[1].splitlines():
        if not l: continue
        st, path = l[:2], l[3:]
        if ' -> ' in path: path = path.split(' -> ')[1]
        path = path.strip('"')
        files.append((st, path))
    for st, path in files:
        full = os.path.join(repo, path)
        size = os.path.getsize(full) if os.path.isfile(full) else None
        tag = {'??': '＋ ใหม่', ' D': '－ ลบ', 'D ': '－ ลบ'}.get(st, '✎ แก้')
        if BADNAME_RX.search(path.replace('\\', '/')):
            tag, blocked = '⛔ ไฟล์ลับ', True
        elif size and size > BIG:
            tag, blocked = '⛔ ใหญ่เกิน', True
        elif size and size < 2_000_000 and os.path.isfile(full):
            try:
                with open(full, 'r', encoding='utf-8', errors='ignore') as f:
                    if SECRET_RX.search(f.read()):
                        tag, blocked = '⛔ มีคีย์', True
            except OSError:
                pass
        rows.append((tag, path, size))
    if not files and ahead == '0':
        return 'same', 'ไม่มีอะไรเปลี่ยน', rows
    if blocked:
        return 'block', 'หยุด — เจอคีย์/ไฟล์ลับ/ไฟล์ใหญ่ จะไม่ commit repo นี้ (แก้ไฟล์ก่อน)', rows
    note = []
    if files: note.append(f'จะ commit {len(files)} ไฟล์')
    if ahead != '0': note.append(f'มี commit รอ push {ahead}')
    if not include_new:
        n = len([l for l in git(repo, 'ls-files', '--others', '--exclude-standard')[1].splitlines() if l])
        if n: note.append(f'ไฟล์ใหม่ {n} ไม่รวม (ติ๊ก "รวมไฟล์ใหม่" ถ้าต้องการ)')
    return 'todo', ' · '.join(note), rows


def do_pull(repo):
    before = git(repo, 'rev-parse', 'HEAD')[1]
    c, o, e = git(repo, 'pull', '--rebase', '--autostash', timeout=600)
    gd = git(repo, 'rev-parse', '--absolute-git-dir')[1]
    if c:
        if os.path.isdir(os.path.join(gd, 'rebase-merge')) or os.path.isdir(os.path.join(gd, 'rebase-apply')):
            git(repo, 'rebase', '--abort')
            return False, 'CONFLICT — ยกเลิกแล้ว กลับสภาพเดิม ต้องแก้เอง'
        return False, 'pull ไม่สำเร็จ: ' + (e.splitlines()[-1] if e else f'exit {c}')
    if re.search(r'autostash.*conflict|conflicts.*autostash', o + e, re.I):
        return False, 'ดึงแล้ว แต่คืนงานค้างชนกัน — งานค้างอยู่ใน git stash'
    after = git(repo, 'rev-parse', 'HEAD')[1]
    n = git(repo, 'rev-list', '--count', f'{before}..{after}')[1] if before != after else '0'
    return True, f'ดึงมาแล้ว {n} commit' if n != '0' else 'ล่าสุดแล้ว'


def do_push(repo, include_new, msg):
    has_changes = bool(git(repo, 'status', '--porcelain', '--untracked-files=' + ('all' if include_new else 'no'))[1])
    if has_changes:
        git(repo, 'add', '-A' if include_new else '-u')
        staged = [l for l in git(repo, 'diff', '--cached', '--name-only')[1].splitlines() if l]
        added = [l for l in git(repo, 'diff', '--cached', '-U0', '--no-color', timeout=600)[1].splitlines()
                 if l.startswith('+') and not l.startswith('+++')]
        if any(BADNAME_RX.search(s) for s in staged) or any(SECRET_RX.search(l) for l in added):
            git(repo, 'reset', '--quiet')
            return False, '⛔ เจอคีย์/ไฟล์ลับตอนตรวจซ้ำ — ไม่ commit (ไฟล์ยังอยู่ครบ)'
        if staged:
            c, _, e = git(repo, 'commit', '-m', msg)
            if c: return False, 'commit ไม่สำเร็จ: ' + (e.splitlines()[-1] if e else '')
    ok, m = do_pull(repo)
    if not ok: return False, m + ' (ยังไม่ได้ push · commit อยู่ในเครื่อง)'
    up = upstream(repo)
    ahead = git(repo, 'rev-list', '--count', f'{up}..HEAD')[1] or '0'
    if ahead == '0': return True, 'ไม่มีอะไรต้อง push'
    c, _, e = git(repo, 'push', timeout=600)      # ห้าม --force
    if c: return False, 'push ไม่สำเร็จ: ' + (e.splitlines()[-1] if e else f'exit {c}')
    return True, f'push แล้ว {ahead} commit → {up}'


# ---------------- หน้าต่าง ----------------
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f'Git Sync · ดึง/ส่ง GitHub หลาย repo · v{VERSION} · ลุงพี')
        self.geometry('1180x820')
        self.minsize(900, 600)
        try: self.iconbitmap(os.path.join(HERE, 'git-sync.ico'))
        except Exception: pass
        st = ttk.Style(self)
        try: st.theme_use('vista')
        except Exception: pass
        f = ('Leelawadee UI', 10)
        st.configure('.', font=f); st.configure('Treeview', rowheight=26, font=f); st.configure('Treeview.Heading', font=f)
        self.q = queue.Queue()
        self.state = load_state()
        self.plan = None          # (mode, include_new, {repo: status})
        self.busy = False
        self._build()
        self.reload_repos()
        self.after(100, self._poll)

    def _build(self):
        top = ttk.Frame(self, padding=(8, 8, 8, 4)); top.pack(fill='x')
        ttk.Label(top, text='บัญชี GitHub (git user):').pack(side='left')
        self.user = ttk.Entry(top, width=22); self.user.pack(side='left', padx=8)
        self.user.insert(0, git(HERE, 'config', 'user.name')[1] or '(ยังไม่ตั้ง)'); self.user.state(['readonly'])
        ttk.Button(top, text='ทดสอบการเชื่อมต่อ', command=self.test_conn).pack(side='left', padx=6, ipadx=10)

        grp = ttk.LabelFrame(self, text='repo (ติ๊กตัวที่จะใช้ · ดับเบิลคลิก = เปิดโฟลเดอร์)', padding=4)
        grp.pack(fill='x', padx=8)
        left = ttk.Frame(grp); left.pack(side='left', fill='both', expand=True)
        self.tv = ttk.Treeview(left, columns=('path', 'branch', 'remote'), height=8)
        for c, t, w in (('#0', 'ชื่อ (ใต้ไดรฟ์)', 280), ('path', 'เครื่องนี้', 300), ('branch', 'branch', 90), ('remote', 'GitHub', 330)):
            self.tv.heading(c, text=t, anchor='w'); self.tv.column(c, width=w, anchor='w', stretch=(c != 'branch'))
        sb = ttk.Scrollbar(left, orient='vertical', command=self.tv.yview); self.tv.configure(yscrollcommand=sb.set)
        self.tv.pack(side='left', fill='both', expand=True); sb.pack(side='left', fill='y')
        self.tv.bind('<Button-1>', self._toggle); self.tv.bind('<Double-1>', self._open_folder)
        right = ttk.Frame(grp, padding=(8, 0, 0, 0)); right.pack(side='left', fill='y')
        for t, cmd in (('เพิ่ม repo', self.add_repo), ('ติ๊กทั้งหมด', lambda: self._check_all(True)),
                       ('ไม่ติ๊กทั้งหมด', lambda: self._check_all(False)), ('ลบออกจากรายการ', self.del_repo)):
            ttk.Button(right, text=t, command=cmd, width=21).pack(pady=3, ipady=3)

        mid = ttk.Frame(self, padding=(8, 8)); mid.pack(fill='x')
        self.mode = tk.StringVar(value='pull')
        ttk.Radiobutton(mid, text='ดึงจาก GitHub มาเครื่องนี้ (Pull)', variable=self.mode, value='pull', command=self._reset_plan).pack(side='left')
        ttk.Radiobutton(mid, text='ส่งจากเครื่องนี้ขึ้น GitHub (Push)', variable=self.mode, value='push', command=self._reset_plan).pack(side='left', padx=16)
        self.incnew = tk.BooleanVar(value=self.state.get('include_new', False))
        ttk.Checkbutton(mid, text='รวมไฟล์ใหม่ด้วย (ปกติ: commit เฉพาะไฟล์ที่ git รู้จักอยู่แล้ว)', variable=self.incnew, command=self._reset_plan).pack(side='left')

        msgf = ttk.Frame(self, padding=(8, 0)); msgf.pack(fill='x')
        ttk.Label(msgf, text='ข้อความ commit (ตอน Push):').pack(side='left')
        self.msg = ttk.Entry(msgf); self.msg.pack(side='left', fill='x', expand=True, padx=8)
        self.msg.insert(0, 'อัปเดตไฟล์ โดย ลุงพี')

        act = ttk.Frame(self, padding=(8, 8)); act.pack(fill='x')
        self.b1 = ttk.Button(act, text='① ดูแผน', command=self.make_plan, width=20); self.b1.pack(side='left', ipady=4)
        self.b2 = ttk.Button(act, text='② ดำเนินการ', command=self.execute, width=20, state='disabled'); self.b2.pack(side='left', padx=8, ipady=4)
        ttk.Button(act, text='เปิดโฟลเดอร์ log', command=lambda: os.startfile(HERE), width=18).pack(side='left', ipady=4)
        self.hint = ttk.Label(act, text='กด ① ดูแผน — ยังไม่มีการเปลี่ยนแปลงจนกว่าจะกด ② และยืนยัน'); self.hint.pack(side='left', padx=12)

        res = ttk.Frame(self, padding=(8, 0)); res.pack(fill='both', expand=True)
        self.rt = ttk.Treeview(res, columns=('status', 'repo', 'item', 'size'), show='headings')
        for c, t, w, a in (('status', 'สถานะ', 120, 'w'), ('repo', 'repo', 230, 'w'), ('item', 'ไฟล์ / รายละเอียด', 700, 'w'), ('size', 'ขนาด', 90, 'e')):
            self.rt.heading(c, text=t, anchor=a); self.rt.column(c, width=w, anchor=a, stretch=(c == 'item'))
        sb2 = ttk.Scrollbar(res, orient='vertical', command=self.rt.yview); self.rt.configure(yscrollcommand=sb2.set)
        self.rt.pack(side='left', fill='both', expand=True); sb2.pack(side='left', fill='y')
        for tag, col in (('ok', '#1a7f37'), ('err', '#c62828'), ('warn', '#b26a00'), ('head', '#0b57d0'), ('dim', '#777777')):
            self.rt.tag_configure(tag, foreground=col)

        bot = ttk.Frame(self, padding=8); bot.pack(fill='x')
        self.dot = tk.Label(bot, text='●', fg='#999'); self.dot.pack(side='left')
        self.pb = ttk.Progressbar(bot, mode='determinate'); self.pb.pack(side='left', fill='x', expand=True, padx=8)
        self.status = ttk.Label(self, text='พร้อม', padding=(8, 0, 8, 6)); self.status.pack(fill='x')

    # ---- รายการ repo ----
    def reload_repos(self):
        self.tv.delete(*self.tv.get_children())
        for rel in read_repos():
            p = resolve(rel)
            on = rel not in self.state.get('unchecked', []) and p is not None
            name = rel  # path เต็มใต้ไดรฟ์ — กันชื่อซ้ำ (picode มี 2 ที่)
            if p:
                br = git(p, 'branch', '--show-current')[1]
                rem = git(p, 'remote', 'get-url', 'origin')[1].replace('https://github.com/', '')
            else:
                br, rem = '', '(ไม่มีในเครื่องนี้)'
            self.tv.insert('', 'end', iid=rel, text=('☑ ' if on else '☐ ') + name, values=(p or rel, br, rem))
        self.tv.yview_moveto(0)

    def checked(self):
        return [(rel, self.tv.set(rel, 'path')) for rel in self.tv.get_children()
                if self.tv.item(rel, 'text').startswith('☑') and resolve(rel)]

    def _toggle(self, ev):
        if self.tv.identify_region(ev.x, ev.y) not in ('tree', 'cell'): return
        if self.tv.identify_column(ev.x) != '#0': return
        rel = self.tv.identify_row(ev.y)
        if not rel: return
        if not resolve(rel):
            self._say(f'{rel} ไม่มีในเครื่องนี้ — ติ๊กไม่ได้', 'warn'); return
        t = self.tv.item(rel, 'text')
        on = not t.startswith('☑')
        self.tv.item(rel, text=('☑ ' if on else '☐ ') + t[2:])
        un = set(self.state.get('unchecked', []))
        (un.discard if on else un.add)(rel)
        self.state['unchecked'] = sorted(un); save_state(self.state); self._reset_plan()

    def _check_all(self, on):
        for rel in self.tv.get_children():
            if resolve(rel): self.tv.item(rel, text=('☑ ' if on else '☐ ') + self.tv.item(rel, 'text')[2:])
        self.state['unchecked'] = [] if on else list(self.tv.get_children()); save_state(self.state); self._reset_plan()

    def _open_folder(self, ev):
        rel = self.tv.identify_row(ev.y)
        p = rel and resolve(rel)
        if p: os.startfile(p)

    def add_repo(self):
        d = filedialog.askdirectory(title='เลือกโฟลเดอร์ repo (ต้องมี .git)')
        if not d: return
        d = os.path.normpath(d)
        if not os.path.exists(os.path.join(d, '.git')):
            messagebox.showwarning('Git Sync', f'{d}\nไม่ใช่ git repo (ไม่มี .git) — ไม่ได้เพิ่ม'); return
        rel = os.path.splitdrive(d)[1].lstrip('\\/')
        rels = read_repos()
        if rel in rels: self._say(f'{rel} มีในรายการแล้ว', 'warn'); return
        write_repos(add=rel); self.reload_repos(); self._say(f'เพิ่ม {rel} แล้ว', 'ok')

    def del_repo(self):
        sel = self.tv.selection()
        if not sel: self._say('เลือกแถว repo ที่จะเอาออกก่อน (คลิกที่ชื่อ)', 'warn'); return
        if not messagebox.askyesno('Git Sync', 'เอาออกจากรายการ (ไม่ลบไฟล์ใด ๆ):\n' + '\n'.join(sel)): return
        write_repos(remove=set(sel)); self.reload_repos(); self._say('เอาออกจากรายการแล้ว (ไฟล์ยังอยู่ครบ)', 'ok')

    # ---- ทดสอบเชื่อมต่อ ----
    def test_conn(self):
        repos = self.checked()
        if not repos: self._say('ไม่มี repo ที่ติ๊กไว้', 'warn'); return
        self._run_bg('ทดสอบการเชื่อมต่อ', repos, lambda rel, p: (lambda r: (r[0] == 0, 'เชื่อมต่อ GitHub ได้' if r[0] == 0 else 'เชื่อมต่อไม่ได้: ' + (r[2].splitlines()[-1] if r[2] else '')))(git(p, 'ls-remote', '--heads', 'origin', timeout=60)), plan=False)

    # ---- แผน / ดำเนินการ ----
    def _reset_plan(self):
        self.plan = None; self.b2.state(['disabled'])
        self.state['include_new'] = self.incnew.get(); save_state(self.state)
        self.hint.config(text='กด ① ดูแผน — ยังไม่มีการเปลี่ยนแปลงจนกว่าจะกด ② และยืนยัน')

    def make_plan(self):
        repos = self.checked()
        if not repos: self._say('ยังไม่ได้ติ๊ก repo', 'warn'); return
        mode, inc = self.mode.get(), self.incnew.get()
        fn = (lambda rel, p: plan_pull(p)) if mode == 'pull' else (lambda rel, p: plan_push(p, inc))
        self.plan = (mode, inc, {})
        self._run_bg('ดูแผน', repos, fn, plan=True)

    def execute(self):
        if not self.plan: return
        mode, inc, st = self.plan
        todo = [(rel, p) for rel, (p, s) in st.items() if s == 'todo']
        if not todo: self._say('ไม่มี repo ที่ต้องทำ', 'warn'); return
        msg = self.msg.get().strip() or 'อัปเดตไฟล์ โดย ลุงพี'
        what = 'ดึงจาก GitHub' if mode == 'pull' else f'commit + push ขึ้น GitHub\nข้อความ: {msg}'
        if not messagebox.askyesno('ยืนยัน', f'{what}\n\n{len(todo)} repo:\n' + '\n'.join(r for r, _ in todo)): return
        fn = (lambda rel, p: do_pull(p)) if mode == 'pull' else (lambda rel, p: do_push(p, inc, msg))
        self.plan = None; self.b2.state(['disabled'])
        self._run_bg('ดำเนินการ', todo, fn, plan=False, log_it=True)

    def _run_bg(self, title, repos, fn, plan, log_it=False):
        if self.busy: return
        self.busy = True; self.b1.state(['disabled']); self.b2.state(['disabled'])
        self.rt.delete(*self.rt.get_children())
        self.pb.configure(maximum=len(repos), value=0); self.dot.config(fg='#0b57d0')
        self.status.config(text=f'{title} {len(repos)} repo พร้อมกัน ...')

        def work():
            def one(item):
                rel, p = item
                try:
                    r = fn(rel, p)
                except Exception as e:  # แจ้งบนจอเสมอ ห้ามเงียบ
                    r = ('err', f'ผิดพลาด: {e}', []) if plan else (False, f'ผิดพลาด: {e}')
                self.q.put(('row', title, rel, p, r, plan, log_it))
            with ThreadPoolExecutor(max_workers=6) as ex:
                list(ex.map(one, repos))
            self.q.put(('done', title, plan))
        threading.Thread(target=work, daemon=True).start()

    def _poll(self):
        try:
            while True:
                m = self.q.get_nowait()
                if m[0] == 'row': self._row(*m[1:])
                else: self._done(*m[1:])
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _row(self, title, rel, p, r, plan, log_it):
        name = rel
        if plan:
            s, note, rows = r
            self.plan[2][rel] = (p, s)
            tag = {'todo': 'head', 'same': 'dim', 'skip': 'warn', 'block': 'err', 'err': 'err'}[s]
            label = {'todo': '▶ จะทำ', 'same': '✓ ไม่ต้องทำ', 'skip': '⚠ ข้าม', 'block': '⛔ หยุด', 'err': '✗ ผิดพลาด'}[s]
            self.rt.insert('', 'end', values=(label, name, note, ''), tags=(tag,))
            for t, item, size in rows[:200]:
                self.rt.insert('', 'end', values=('   ' + t, '', item, fmt_size(size)), tags=('err' if t.startswith('⛔') else '',))
            if len(rows) > 200: self.rt.insert('', 'end', values=('', '', f'... อีก {len(rows) - 200} ไฟล์', ''), tags=('dim',))
        else:
            ok, note = r
            self.rt.insert('', 'end', values=('✓ สำเร็จ' if ok else '✗ ไม่สำเร็จ', name, note, ''), tags=('ok' if ok else 'err',))
            if log_it: log(f'{self.mode.get()} {p} — {"OK" if ok else "FAIL"} {note}')
        self.pb.step(1)

    def _done(self, title, plan):
        self.busy = False; self.b1.state(['!disabled'])
        if plan and self.plan:
            st = self.plan[2]
            n = sum(1 for _, s in st.values() if s == 'todo'); bad = sum(1 for _, s in st.values() if s in ('block', 'err'))
            if n: self.b2.state(['!disabled'])
            self.hint.config(text=f'แผน: จะทำ {n} repo' + (f' · หยุด/ผิดพลาด {bad}' if bad else '') + (' — กด ② ดำเนินการ' if n else ' — ไม่มีอะไรต้องทำ'))
            self.status.config(text=f'ดูแผนเสร็จ — ยังไม่ได้เปลี่ยนแปลงอะไร'); self.dot.config(fg='#1a7f37' if not bad else '#b26a00')
        else:
            vals = [self.rt.item(i, 'values')[0] for i in self.rt.get_children()]
            bad = sum(1 for v in vals if v.startswith('✗'))
            self.status.config(text=f'{title}เสร็จ — สำเร็จ {len(vals) - bad} · ไม่สำเร็จ {bad}' + (' (ดูแถวสีแดง)' if bad else ''))
            self.dot.config(fg='#c62828' if bad else '#1a7f37')
            self.hint.config(text='กด ① ดูแผน — ยังไม่มีการเปลี่ยนแปลงจนกว่าจะกด ② และยืนยัน')
            self.reload_repos()

    def _say(self, text, kind='ok'):
        self.status.config(text=text); self.dot.config(fg={'ok': '#1a7f37', 'warn': '#b26a00', 'err': '#c62828'}[kind])


if __name__ == '__main__':
    App().mainloop()
