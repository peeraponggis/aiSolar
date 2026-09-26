# -*- coding: utf-8 -*-
"""
rag_gui.py — RAG ถาม-ตอบกับเอกสาร knowledge ผ่าน Ollama local (GUI)
embed: bge-m3 · generate: qwen2.5:7b (เลือกได้) · knowledge: F:/LocalAI/knowledge/*.md
"""
import json, glob, math, threading, urllib.request
from pathlib import Path
import tkinter as tk
from tkinter import ttk, scrolledtext

OLLAMA = "http://localhost:11434"
EMBED_MODEL = "bge-m3:latest"
KNOWLEDGE = Path(r"F:\LocalAI\knowledge")
TOP_K = 3
LLM_CHOICES = ["qwen2.5:7b", "llama3.1:8b", "qwen2.5:7b-instruct-q3_K_M",
               "scb10x/typhoon2.5-qwen3-4b:latest", "scb10x/llama3.2-typhoon2-3b-instruct:latest"]

def post(path, payload, timeout=180):
    req = urllib.request.Request(OLLAMA + path, data=json.dumps(payload).encode(),
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())

def embed(text):
    return post("/api/embed", {"model": EMBED_MODEL, "input": text})["embeddings"][0]

def cosine(a, b):
    dot = sum(x*y for x, y in zip(a, b))
    na = math.sqrt(sum(x*x for x in a)); nb = math.sqrt(sum(y*y for y in b))
    return dot/(na*nb) if na and nb else 0

def chunk_md(text, size=600, overlap=100):
    parts, cur = [], ""
    for line in text.split("\n"):
        if line.startswith("## ") and cur:
            parts.append(cur); cur = line + "\n"
        else:
            cur += line + "\n"
    if cur: parts.append(cur)
    chunks = []
    for p in parts:
        if len(p) <= size*2:
            chunks.append(p.strip())
        else:
            for i in range(0, len(p), size-overlap):
                chunks.append(p[i:i+size].strip())
    return [c for c in chunks if len(c) > 40]


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("RAG ถาม-ตอบเอกสาร (Ollama local)")
        self.configure(bg='#0f172a'); self.geometry("760x640")
        self.docs = []; self.vecs = []; self.indexed = False
        self._build()
        self.after(300, self._index)  # index อัตโนมัติตอนเปิด

    def _build(self):
        tk.Label(self, text="🔎 RAG ถาม-ตอบเอกสาร knowledge", bg='#0f172a', fg='#a78bfa',
                 font=('Tahoma', 15, 'bold')).pack(pady=(14, 2))
        tk.Label(self, text="ค้นเอกสารด้วย bge-m3 → ตอบด้วย LLM local (ตอบจากเอกสารจริง)",
                 bg='#0f172a', fg='#94a3b8', font=('Tahoma', 10)).pack(pady=(0, 8))

        top = tk.Frame(self, bg='#0f172a'); top.pack(fill='x', padx=14)
        tk.Label(top, text="โมเดล:", bg='#0f172a', fg='#cbd5e1', font=('Tahoma', 10)).pack(side='left')
        self.model = ttk.Combobox(top, values=LLM_CHOICES, width=38, state='readonly')
        self.model.set("qwen2.5:7b"); self.model.pack(side='left', padx=6)
        self.status = tk.Label(top, text="", bg='#0f172a', fg='#94a3b8', font=('Tahoma', 9))
        self.status.pack(side='left', padx=6)

        qf = tk.Frame(self, bg='#0f172a'); qf.pack(fill='x', padx=14, pady=8)
        self.q = tk.Entry(qf, bg='#1e293b', fg='#e2e8f0', relief='flat', bd=0,
                          font=('Tahoma', 12), insertbackground='white',
                          highlightthickness=1, highlightbackground='#334155')
        self.q.pack(side='left', fill='x', expand=True, ipady=6)
        self.q.insert(0, "self-attention ทำงานอย่างไร มีสูตรอะไร")
        self.q.bind('<Return>', lambda e: self._ask())
        self.btn = tk.Button(qf, text="🔎 ถาม", command=self._ask, bg='#7c3aed', fg='white',
                             relief='flat', bd=0, font=('Tahoma', 12, 'bold'), padx=18, cursor='hand2')
        self.btn.pack(side='left', padx=(8, 0))

        tk.Label(self, text="📄 เอกสารที่ค้นเจอ:", bg='#0f172a', fg='#86efac',
                 font=('Tahoma', 10), anchor='w').pack(fill='x', padx=14)
        self.chunks = scrolledtext.ScrolledText(self, bg='#0b1220', fg='#94a3b8', height=6,
                                                font=('Consolas', 9), relief='flat', bd=0, wrap='word')
        self.chunks.pack(fill='x', padx=14, pady=(2, 8))

        tk.Label(self, text="🤖 คำตอบ:", bg='#0f172a', fg='#fbbf24',
                 font=('Tahoma', 10), anchor='w').pack(fill='x', padx=14)
        self.ans = scrolledtext.ScrolledText(self, bg='#000', fg='#e2e8f0',
                                             font=('Tahoma', 12), relief='flat', bd=0, wrap='word',
                                             highlightthickness=1, highlightbackground='#334155')
        self.ans.pack(fill='both', expand=True, padx=14, pady=(2, 14))

    def _set_status(self, t):
        self.after(0, lambda: self.status.config(text=t))

    def _index(self):
        def run():
            try:
                self._set_status("● กำลัง index เอกสาร...")
                docs = []
                files = glob.glob(str(KNOWLEDGE/"*.md"))
                for f in files:
                    docs.extend((Path(f).name, c) for c in chunk_md(Path(f).read_text(encoding='utf-8')))
                vecs = [embed(c) for _, c in docs]
                self.docs, self.vecs, self.indexed = docs, vecs, True
                self._set_status(f"● พร้อม ({len(docs)} chunks / {len(files)} ไฟล์)")
            except Exception as e:
                self._set_status(f"● Ollama error: {str(e)[:40]}")
        threading.Thread(target=run, daemon=True).start()

    def _ask(self):
        if not self.indexed:
            self.ans.delete('1.0', 'end'); self.ans.insert('end', "⏳ ยัง index ไม่เสร็จ รอสักครู่..."); return
        q = self.q.get().strip()
        if not q: return
        self.btn.config(state='disabled')
        self.chunks.delete('1.0', 'end'); self.ans.delete('1.0', 'end')
        self.ans.insert('end', "⏳ กำลังค้นและสร้างคำตอบ...")
        def run():
            try:
                qv = embed(q)
                scored = sorted(zip(self.docs, self.vecs), key=lambda x: -cosine(qv, x[1]))[:TOP_K]
                ctx = ""
                cs = ""
                for (name, c), v in scored:
                    cs += f"[{cosine(qv,v):.3f}] {name}\n{c[:120]}...\n\n"
                    ctx += f"\n---\n{c}\n"
                self.after(0, lambda: (self.chunks.delete('1.0','end'), self.chunks.insert('end', cs)))
                prompt = f"""ใช้ข้อมูลต่อไปนี้ตอบคำถาม ตอบเป็นภาษาไทย กระชับ ตรงประเด็น อ้างเฉพาะข้อมูลที่ให้ ห้ามแต่งเพิ่ม

ข้อมูล:
{ctx}

คำถาม: {q}
คำตอบ:"""
                d = post("/api/generate", {"model": self.model.get(), "prompt": prompt,
                                           "stream": False, "options": {"temperature": 0.2}})
                ans = d.get("response", "(ไม่มีคำตอบ)").strip()
                self.after(0, lambda: (self.ans.delete('1.0','end'), self.ans.insert('end', ans)))
            except Exception as e:
                self.after(0, lambda: (self.ans.delete('1.0','end'), self.ans.insert('end', f"❌ error: {e}")))
            finally:
                self.after(0, lambda: self.btn.config(state='normal'))
        threading.Thread(target=run, daemon=True).start()


if __name__ == "__main__":
    App().mainloop()
