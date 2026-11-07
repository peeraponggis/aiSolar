# พจนานุกรมภาษาลาว — รวมทุก Format บนอินเทอร์เน็ต

> รวบรวมโดย ลุงพี | อัปเดต: 2026-10-18

---

## 1. ไทย ↔ ลาว

| แหล่ง | Format | หมายเหตุ | ลิขสิทธิ์ |
|--------|--------|---------|-----------|
| [Glosbe ลาว-ไทย](https://th.glosbe.com/lo/th) | ออนไลน์ | ใช้งานฟรีบนเว็บ | ฟรี |
| [LaoNLP (GitHub)](https://github.com/wannaphong/LaoNLP) | Python + CSV | มี `lao_to_thai()` / `thai_to_lao()` function | Apache 2.0 |
| [Thai-Lao Parallel Corpus (Zenodo)](https://zenodo.org/records/5807093) | CSV (ประโยค) | ประโยคคู่ไทย-ลาว ไม่ใช่ word-level | ฟรี |
| [SEACrowd tha_lao_embassy (Hugging Face)](https://huggingface.co/datasets/SEACrowd/tha_lao_embassy_parcor) | Hugging Face dataset | ประโยคระดับสถานทูต | ฟรี |
| [พจนานุกรมลาว-ไทย-อังกฤษ ฉบับเฉลิมพระเกียรติ](https://kukr.lib.ku.ac.th/kukr_es/BKN_HUMAN/search_detail/result/7510) | หนังสือ (ไม่ใช่ไฟล์) | ~8,000 คำหลัก งานวิชาการ มก. | วิชาการ |

> **หมายเหตุ:** ยังไม่มีไฟล์พจนานุกรมไทย-ลาว word-level ที่ดาวน์โหลดได้ฟรีโดยตรง  
> ทางออกที่แนะนำ: ใช้ **LaoNLP** เป็น pivot (`pip install laonlp`)

---

## 2. อังกฤษ ↔ ลาว

| แหล่ง | Format | จำนวนคำ | ลิขสิทธิ์ |
|--------|--------|---------|-----------|
| [LaoNLP lao-eng-dictionary.csv](https://github.com/wannaphong/LaoNLP/blob/master/laonlp/corpus/lao-eng-dictionary.csv) | **CSV** | 51,257 แถวดิบ | MIT (ข้อมูล: E-Government Center, Ministry of Posts and Telecommunications of Laos, 2015) |
| [FREELANG Lao-English](https://www.freelang.net/dictionary/lao.php) | Windows .exe → plain text 2 คอลัมน์ | Lao→Eng: **51,257** / Eng→Lao: **30,843** | ลิขสิทธิ์ (ใช้ส่วนตัวได้) |
| [Vocably Lao (GitHub)](https://github.com/vocably/lo) | JSON/TS | ไม่ระบุ | AGPL-3.0 |
| [lao-dictionary (rcampbellbassac)](https://github.com/rcampbellbassac/lao-dictionary) | Text wordlist | ไม่ระบุ | BSD-2-Clause ✅ |
| [Kaikki.org — Wiktionary Extract](https://kaikki.org/dictionary/index.html) | **JSONL** | ตาม Wiktionary coverage | CC BY-SA ✅ |
| [Wiktextract (tool)](https://github.com/tatuylonen/wiktextract) | JSONL (สร้างเอง) | ครบตาม Wiktionary dump | Apache 2.0 (tool) |
| [Awesome-Lao-NLP](https://github.com/wannaphong/Awesome-Lao-NLP) | รายการ links รวม | รวม resource ทั้งหมด | — |
| [Dictionary Lao-Eng App (Thaiware)](https://software.thaiware.com/12728.html) | Windows app | ไม่มี raw data | ฟรี |

---

## 3. คำอ่านภาษาอังกฤษ → ลาว (Romanization / Transliteration)

| แหล่ง | Format | หมายเหตุ |
|--------|--------|---------|
| [FREELANG Lao Romanized](https://www.freelang.net/dictionary/lao_romanized.php) | Windows .exe → plain text | **51,254 คำ** พร้อม romanization |
| [Wiktionary: Lao Transliteration](https://en.wiktionary.org/wiki/Wiktionary:Lao_transliteration) | เว็บ + API | ตาราง consonant / vowel / tone → romanization |
| [Library of Congress Romanization Table 2012](https://www.loc.gov/catdir/cpso/romanization/lao.pdf) | **PDF** | มาตรฐานอย่างเป็นทางการสหรัฐอเมริกา |
| [BGN/PCGN 1966 — UK Standard](https://assets.publishing.service.gov.uk/media/5ab4e2e4e5274a1aa2d4146d/ROMANIZATION_OF_LAO.pdf) | **PDF** | มาตรฐาน UK ราชการ (อัปเดต 2017) |
| [Wikipedia: Romanization of Lao](https://en.wikipedia.org/wiki/Romanization_of_Lao) | เว็บ | ภาพรวม French vs English-based system |
| [Lao English Dictionary Offline (Google Play)](https://play.google.com/store/apps/details?id=com.pasawahanappmaker.english.laos.lao.dictionary.translator.offline.free) | Android app | ทุก entry มี romanization |

---

## 4. สรุปตาม Use Case

| ต้องการทำอะไร | แนะนำ |
|--------------|-------|
| ไฟล์ CSV พร้อมใช้ทันที (ฟรี) | [`lao-eng-dictionary.csv`](https://github.com/wannaphong/LaoNLP/blob/master/laonlp/corpus/lao-eng-dictionary.csv) |
| ไฟล์ JSONL ละเอียดที่สุด | [Kaikki.org](https://kaikki.org/dictionary/index.html) |
| Romanization ครบที่สุด | [FREELANG Romanized](https://www.freelang.net/dictionary/lao_romanized.php) |
| ใช้งาน Python | `pip install laonlp` |
| ดูออนไลน์เลย | [Glosbe](https://th.glosbe.com/lo/th) |
| มาตรฐาน romanization อ้างอิง | [LOC PDF](https://www.loc.gov/catdir/cpso/romanization/lao.pdf) |

---

## 5. ไฟล์ที่สร้างแล้ว (โฟลเดอร์นี้)

| ไฟล์ | จำนวนแถว | เนื้อหา |
|------|---------|---------|
| `lao-eng-dictionary.csv` | 50,385 | ข้อมูลสะอาดจาก LaoNLP (ตัด header ซ้ำ 26 แถว, ซ้ำ 843 แถว, ไม่มีหัวคำลาว 3 แถว) |
| `1_thai-lao.csv` | 10,135 | คู่ไทย↔ลาวจับคู่ผ่านคำแปลอังกฤษ (kaikki.org Thai + Lao + lao-eng) ระบุ `Confidence` high/medium/low และ `Method` |
| `dictionary.html` | — | SPA ค้นหาทั้งหมดในไฟล์เดียว (ออฟไลน์ได้) แท็บ ลาว / อังกฤษ / คำอ่าน / ไทย↔ลาว |
| `2_eng-lao.csv` | 50,380 | หมวด อังกฤษ↔ลาว |
| `3_romanization.csv` | 50,381 | หมวด Romanization (base จาก FREELANG ผ่าน LaoNLP) |
| `4_standard-merged.csv` | 50,385 | `Romanization_LOC` จาก `lao_loc.py` (LOC 2012) 44,937 แถว; ที่แปลงไม่ได้ 5,448 แถว ใช้คำแปลอังกฤษ (`Source` = fallback-English) และเสริมคำไทยจาก `1_thai-lao.csv` (ระดับ high/medium) ถ้ามี; `FREELANG_ref` เก็บไว้เทียบ |
| `_build.py` | — | สคริปต์ที่ใช้สร้างไฟล์ทั้งหมดจาก `raw_lao-eng-dictionary.csv` |

> **`lao_loc.py`** แปลงอักษรลาวตามตาราง LOC 2012 (อ่านจากภาพหน้า PDF ที่ render แล้ว) ครอบคลุมพยัญชนะ สระ วรรณยุกต์ (ตัดทิ้ง) และกฎ Note 2–6 ทดสอบกับตัวอย่างในหมายเหตุ LOC ผ่านแล้ว
>
> **ข้อจำกัด:** รูปสระที่รวมกันนอกตาราง เช่น `เ◌ື` (เรือน), `ເ◌ິ` ไม่มีในตาราง จึงตกไปใช้คำแปลอังกฤษ ไม่ได้เทียบกับ BGN/PCGN (PDF ฉบับนั้นยังไม่ได้ทำ) ค่าความตรงกับ FREELANG ~35% เป็นการเทียบคนละหลักการ ไม่ใช่ตัวชี้วัดความถูกต้อง

---

## 6. แผนสร้าง Database รวม (ถ้าต้องการ)

```
1. ดึง lao-eng-dictionary.csv จาก LaoNLP  → ฐาน Eng↔Lao (MIT)
2. ดึง FREELANG Romanized (.exe ติดตั้ง → แตก text) → เพิ่ม phonetic column
3. สร้าง Thai↔Lao ผ่าน LaoNLP: lao_to_thai() / thai_to_lao()
4. เสริม definition ละเอียดจาก Kaikki.org JSONL
5. ใช้ LOC Romanization Table เป็น ground truth สำหรับ phonetic
```
