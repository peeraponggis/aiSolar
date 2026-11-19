# ทดลอง HyperFrames — การ์ดสถิติภาษาไทย (YT Shorts)

ทดลองเมื่อ 1 พ.ย. 2569 · โดย ลุงพี · HyperFrames 0.8.225 (HeyGen, Apache-2.0)

## ใช้งาน
ใช้ `hf.cmd` แทน `npx hyperframes` เสมอ — ตั้งทุกที่เก็บไว้บน F: (บ้านของ CLI = `F:\LocalAI\tools\hyperframes-home`,
แคช npm/puppeteer/เฟรม = F:, TEMP = `F:\LocalAI\tmp`) และปิด telemetry

```
hf check
hf render -o renders\card.mp4 --variables "{\"kicker\":\"คนไทยดื่มน้ำต่อวัน\",\"value\":2.5,\"unit\":\"ลิตร\",\"badge\":\"เป้าหมาย\",\"caption\":\"...\",\"accent\":\"#4fc3f7\"}"
```

ตัวแปรของการ์ด (`index.html`): `kicker` `value` `decimals` `unit` `badge` `caption` `accent`

## ผล
| เรื่อง | ผล |
|---|---|
| ความเร็ว | 5 วิ (150 เฟรม 1080×1920 30fps) เรนเดอร์ 17–18 วิ (~3.5× เวลาจริง, CPU, Chrome 5 ตัวขนาน) · รวมเปิด npx ~29 วิ |
| ไฟล์ | H.264 yuv420p 1080×1920 30fps · 415 KB |
| ภาษาไทย | สระ/วรรณยุกต์ซ้อนถูกต้อง (น้ำ ญ่ เป้า) · ตัดบรรทัดตามคำไทย (Chrome ICU) |
| ตรวจ (`hf check`) | ผ่าน · contrast WCAG AA 17/17 |
| เปลี่ยนข้อมูล | ส่ง `--variables` ได้เลย ไม่ต้องแก้ HTML → ทำเป็นแม่แบบให้ระบบ YT เติมค่าเองได้ |

## ข้อควรระวัง
- CLI เขียน `~/.hyperframes` (config + telemetry) — `hf.cmd` ย้าย USERPROFILE ไป F: แล้ว
- ฟอนต์ Kanit ดึงจาก Google Fonts และ GSAP จาก jsDelivr ตอนเรนเดอร์ (ต้องมีเน็ต) — ถ้าใช้จริงควรเก็บไฟล์ไว้ในเครื่อง
- ใช้ Chrome ของเครื่อง (`C:\Program Files\Google\Chrome`) ไม่ได้ดาวน์โหลดเพิ่ม
