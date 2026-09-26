# -*- coding: utf-8 -*-
"""
rag_test.py — ทดสอบ RAG กับโมเดล local ใน Ollama
- อ่านเอกสาร knowledge (.md) → chunk → embed (bge-m3) → retrieve → generate (typhoon)
"""
import sys, glob, json, urllib.request, math
from pathlib import Path

OLLAMA = "http://localhost:11434"
EMBED_MODEL = "bge-m3:latest"
LLM_MODEL   = "scb10x/llama3.2-typhoon2-3b-instruct:latest"
KNOWLEDGE   = Path(r"F:\LocalAI\knowledge")
TOP_K = 3

def post(path, payload):
    req = urllib.request.Request(OLLAMA + path, data=json.dumps(payload).encode(),
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())

def embed(text):
    d = post("/api/embed", {"model": EMBED_MODEL, "input": text})
    return d["embeddings"][0]

def cosine(a, b):
    dot = sum(x*y for x, y in zip(a, b))
    na = math.sqrt(sum(x*x for x in a)); nb = math.sqrt(sum(y*y for y in b))
    return dot/(na*nb) if na and nb else 0

def chunk_md(text, size=600, overlap=100):
    # หั่นตามหัวข้อ ## ก่อน แล้วซอยย่อยถ้ายาว
    parts, cur = [], ""
    for line in text.split("\n"):
        if line.startswith("## ") and cur:
            parts.append(cur); cur = line + "\n"
        else:
            cur += line + "\n"
    if cur: parts.append(cur)
    # ซอยชิ้นที่ยาวเกิน
    chunks = []
    for p in parts:
        if len(p) <= size*2:
            chunks.append(p.strip())
        else:
            for i in range(0, len(p), size-overlap):
                chunks.append(p[i:i+size].strip())
    return [c for c in chunks if len(c) > 40]

def main():
    q = sys.argv[1] if len(sys.argv) > 1 else "self-attention ทำงานอย่างไร อธิบายสูตร"
    print(f"❓ คำถาม: {q}\n")

    # 1) โหลด + chunk เอกสาร
    docs = []
    for f in glob.glob(str(KNOWLEDGE/"*.md")):
        docs.extend((Path(f).name, c) for c in chunk_md(Path(f).read_text(encoding='utf-8')))
    print(f"📚 โหลด {len(docs)} chunks จาก {len(glob.glob(str(KNOWLEDGE/'*.md')))} ไฟล์")

    # 2) embed ทุก chunk
    print("🔢 กำลัง embed chunks (bge-m3)...")
    vecs = [embed(c) for _, c in docs]

    # 3) embed คำถาม + retrieve top-k
    qv = embed(q)
    scored = sorted(zip(docs, vecs), key=lambda x: -cosine(qv, x[1]))[:TOP_K]
    print(f"\n🎯 Top {TOP_K} chunks ที่เกี่ยวข้อง:")
    ctx = ""
    for (name, c), v in scored:
        print(f"   [{cosine(qv,v):.3f}] {name}: {c[:60].replace(chr(10),' ')}...")
        ctx += f"\n---\n{c}\n"

    # 4) generate ด้วย LLM ไทย
    prompt = f"""ใช้ข้อมูลต่อไปนี้ตอบคำถาม ตอบเป็นภาษาไทย กระชับ ตรงประเด็น ห้ามแต่งเพิ่มนอกข้อมูล

ข้อมูล:
{ctx}

คำถาม: {q}
คำตอบ:"""
    print(f"\n🤖 กำลังสร้างคำตอบ ({LLM_MODEL})...\n")
    d = post("/api/generate", {"model": LLM_MODEL, "prompt": prompt, "stream": False,
                               "options": {"temperature": 0.2}})
    print("="*60)
    print(d.get("response", "(ไม่มีคำตอบ)").strip())
    print("="*60)

if __name__ == "__main__":
    main()
