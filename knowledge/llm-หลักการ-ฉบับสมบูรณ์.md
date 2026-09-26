# หลักการทำงาน LLM (Large Language Model) — ฉบับสมบูรณ์

> เอกสารอ้างอิง (RAG source) สำหรับโมเดล local · อธิบายทุกขั้นตอนตั้งแต่พื้นฐานถึง deploy จริง

## ภาพรวม
LLM คือโครงข่ายประสาทเทียมขนาดใหญ่ (Transformer) ที่ทำสิ่งเดียว: **ทำนาย token ถัดไป** จากข้อความก่อนหน้า การตอบคำถามได้คือผลจากการทำนายคำถัดไปเก่ง ๆ ซ้ำ ๆ

---

# ส่วน A: การประมวลผล 1 ครั้ง (Inference)

## 1. Tokenization — แปลงข้อความเป็นตัวเลข
- แตกข้อความเป็น "token" (คำ/ชิ้นคำ) ด้วย **BPE / SentencePiece** — เริ่มจากตัวอักษรแล้วรวมคู่ที่พบบ่อยสุดซ้ำ ๆ จนได้ vocab (32k–128k tokens)
- สมดุลระหว่าง vocab เล็ก (char) กับความหมายครบ (word) · จัดการคำใหม่/สะกดผิดได้
- ภาษาไทยท้าทาย: ไม่มีเว้นวรรค → tokenizer ตัดผิดได้
- ผลลัพธ์: `input_ids` = เวกเตอร์ integer

## 2. Embedding — token → เวกเตอร์
- ตาราง `E` ขนาด `[vocab_size × d_model]` (เช่น 128k × 4096)
- token id → หยิบแถวตรงกัน = เวกเตอร์ d_model มิติ (เก็บ "ความหมาย" เชิงตัวเลข คำคล้ายอยู่ใกล้กัน)
- input → เมทริกซ์ `X` ขนาด `[seq_len × d_model]`

## 3. Positional Encoding — บอกลำดับ
- Transformer ไม่รู้ลำดับโดยธรรมชาติ → เพิ่มข้อมูลตำแหน่ง
- **RoPE (Rotary)**: หมุนเวกเตอร์ Q,K ด้วยมุมตามตำแหน่ง → encode ระยะห่างสัมพัทธ์ + ขยาย context ได้

## 4. Transformer Layers (ทำซ้ำ N ชั้น)

### 4.1 Self-Attention (สูตรเต็ม)
```
Attention(Q,K,V) = softmax( Q·Kᵀ / √dₖ ) · V
```
1. `Q = X·Wq`, `K = X·Wk`, `V = X·Wv`
2. `Q·Kᵀ` = เมทริกซ์คะแนน `[seq × seq]`
3. หาร `√dₖ` กัน softmax อิ่มตัว (gradient หาย)
4. **Causal mask**: ปิด token อนาคต (−∞ ก่อน softmax)
5. softmax ต่อแถว → น้ำหนักรวม = 1
6. คูณ V → แต่ละ token ดูดข้อมูลจาก token ที่เกี่ยวข้อง
- **Multi-Head**: แบ่ง d_model เป็น h หัว ทำแยกกัน concat + คูณ Wo
- **GQA**: หลาย Q head ใช้ K,V ร่วมกัน → ลด KV cache

### 4.2 Feed-Forward Network (FFN)
```
FFN(x) = W₂ · activation(W₁·x)
```
- ขยายมิติ (4096→14336) แล้วหด · **SwiGLU** นิยมแทน ReLU/GELU
- FFN มีพารามิเตอร์ ~2/3 ของโมเดล = ที่เก็บ "ความรู้" หลัก

### 4.3 Normalization + Residual
- **RMSNorm** (แทน LayerNorm): เร็วกว่า · **Pre-norm** เทรน deep net เสถียร
- `output = x + Sublayer(norm(x))` — residual กัน gradient หาย
- ซ้อน N ชั้น (Llama-3-8B=32, 70B=80) แต่ละชั้นสกัดความหมายลึกขึ้น

## 5. Output Layer
- เวกเตอร์สุดท้าย → `logits = h · Eᵀ` ขนาด `[vocab_size]`
- `softmax(logits / T)` → การแจกแจงความน่าจะเป็น

## 6. Decoding — เลือก token
- **Temperature T**: `p_i = exp(z_i/T)/Σexp(z_j/T)` · T→0 greedy, สูง=สุ่ม
- **Top-k**: เก็บ k logit สูงสุด · **Top-p (nucleus)**: เก็บจนผลรวม ≤ p
- **Repetition penalty**: ลดคะแนน token ที่เพิ่งออก

## 7. Autoregressive Loop
- ได้ 1 token → ต่อท้าย input → วนทำนายคำถัดไป จนเจอ token หยุด
- **KV Cache**: เก็บ K,V เก่าไว้ ไม่คำนวณซ้ำ = เร็วขึ้นมาก

---

# ส่วน B: การฝึก (Training)

## 8. Pre-training
- ป้อนข้อความมหาศาล (ล้านล้าน token) · งาน = เดาคำถัดไป
- **Loss (Cross-Entropy)**: `L = −Σ log P(token_จริง)`
- **Backprop + Gradient Descent**: ปรับน้ำหนัก (พันล้าน–แสนล้านตัว) ให้เดาแม่นขึ้น
- **AdamW optimizer**: momentum + adaptive LR + weight decay
- **Scaling Laws (Chinchilla)**: N พารามิเตอร์ ควรเทรน ~20N tokens
- **LR schedule**: warmup → cosine decay

## 9. Alignment (ปรับเป็นผู้ช่วย)
- **SFT**: เทรนคู่ instruction-response (loss เฉพาะ response)
- **RLHF**: เทรน Reward Model จากที่มนุษย์จัดอันดับ → PPO ปรับ policy
- **DPO** (นิยมกว่า): ปรับตรงจากคู่ preferred/rejected ไม่ต้องมี RM แยก

---

# ส่วน C: ขั้นสูง + Deploy จริง

## 10. Backpropagation ลึก
- computational graph · chain rule ไล่จากท้ายมาหน้า
- **Gradient checkpointing**: เก็บ activation บางจุด คำนวณซ้ำตอน backward (แลกเวลา↔RAM)
- **Mixed precision (bf16)**: คำนวณ 16-bit เร็วขึ้น เก็บ master fp32

## 11. Distributed Training
- **Data / Tensor / Pipeline Parallel** + **FSDP/ZeRO** (กระจาย optimizer+gradient+weight) → เทรน 70B+ ได้

## 12. FlashAttention
- แก้คอขวด O(n²): คำนวณ attention แบบ tiling ใน SRAM ไม่สร้างเมทริกซ์เต็ม → เร็ว+ประหยัด memory

## 13. Long Context
- **RoPE scaling / YaRN**: ยืด 4k → 32k+ · **Sliding Window** (Mistral): O(n) · **Attention Sink**

## 14. Inference Optimization
- **Continuous Batching** (vLLM) · **PagedAttention** (KV cache แบบ virtual memory)
- **Speculative Decoding**: โมเดลเล็กร่าง → ใหญ่ตรวจ → เร็ว 2-3 เท่า
- **Quantization**: `Q4_K_M` (4-bit), `Q8_0` (8-bit) → เล็ก/เร็ว แลกความแม่นเล็กน้อย

## 15. Fine-tuning ประหยัด (ทำบนเครื่องบ้านได้)
- **LoRA**: แช่แข็งน้ำหนักเดิม เพิ่มเมทริกซ์เล็ก rank ต่ำ เทรนแค่ <1%
- **QLoRA**: โหลด 4-bit + LoRA → fine-tune 7B บน GPU 8GB · ผลลัพธ์ = adapter เล็ก (MB)

## 16. Chat Template + Special Tokens
- โมเดล chat เทรนด้วยรูปแบบเฉพาะ (`<|system|>...<|user|>...<|assistant|>`)
- **ผิด template = ผลแย่มาก** · Ollama เก็บใน Modelfile · tokens: `<|eot_id|>` ฯลฯ

## 17. Function Calling / Agents
- โมเดล output JSON บอกว่าจะเรียกฟังก์ชันอะไร → ระบบภายนอก parse+รัน → ส่งผลกลับ context → ตอบต่อ
- **ReAct loop**: Reason → Act → Observe → ซ้ำ

## 18. RAG (Retrieval-Augmented Generation)
1. **Chunking**: หั่นเอกสาร (~500 token + overlap)
2. **Embedding model** (คนละตัวกับ LLM เช่น nomic-embed, bge-m3): chunk → เวกเตอร์
3. **Vector DB** (Chroma/FAISS/Qdrant): เก็บ + ค้น cosine similarity
4. **Retrieval**: คำถาม → embed → top-k chunk
5. **Augment**: ยัด chunk เข้า context
6. **Generate**: LLM ตอบจากข้อมูลจริง → ลด hallucination + อัปเดตความรู้ได้โดยไม่เทรนใหม่
- **Reranking**: จัดอันดับ chunk ให้แม่นก่อนส่ง LLM

## 19. Multimodal
- Vision encoder (CLIP/ViT) แปลงรูป → เวกเตอร์ → project เข้าปริภูมิเดียวกับ text → ประมวลผลปนกัน

## 20. Evaluation
- **Perplexity** (ต่ำ=ดี) · **Benchmarks**: MMLU, HumanEval, GSM8K, HellaSwag · **LLM-as-judge**

## 21. Distillation
- teacher ใหญ่สอน student เล็กให้เลียนการแจกแจง → โมเดลเล็กเก่งเกินตัว

---

# แผนที่ความเชื่อมโยง
```
ข้อความ → [tokenize] → [embed+pos] → [N× transformer: attention+FFN]
       → [logits→softmax] → [sample] → token → (วนซ้ำ)
เทรน: pretrain(next-token) → SFT → RLHF/DPO
local: quantize(GGUF) → Ollama serve → +RAG(vector DB) → +tools(agent)
```

# ทำไมตอบได้ + ข้อจำกัด
- ความรู้ = pattern บีบอัดในน้ำหนัก (lossy compression ของข้อมูลเทรน) — ไม่ได้ "ค้นหา" จากฐานข้อมูล
- **In-context Learning**: เรียนจากตัวอย่างใน prompt ได้โดยไม่เทรนใหม่
- **Emergent abilities**: reasoning โผล่เมื่อโมเดลใหญ่พอ
- **Hallucination**: เดาคำที่ฟังดูถูกได้แม้ผิด (optimize ความน่าจะเป็น ไม่ใช่ความจริง)
- **Knowledge cutoff**: รู้แค่ถึงวันเทรน · **Context window**: จำจำกัด
- **RAG** แก้ hallucination + cutoff ได้ (ดึงเอกสารจริงมาใส่ context)
