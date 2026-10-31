# ทะเบียนโปรแกรมของลุงพี (ศูนย์กลาง · ทั้ง Laptop + Home server)

อัปเดต 31 ต.ค. 2569 · laptop ใช้ `F:\` · home server ใช้ `C:\` (โครงสร้างโฟลเดอร์เหมือนกัน)
แบ่ง 4 หมวดตาม **"ใครเห็นได้"** — เช็กหมวดก่อนแก้หรือ push ทุกครั้ง

กฎ: ก่อนเริ่ม `git pull --ff-only` · จบงาน commit + push ก่อนสลับเครื่อง · bump VERSION.json + CHANGELOG ทุกครั้งที่แก้ · push ต้องล็อกอิน GitHub (ลุงพีทำเอง)

---

## หมวด 1 · 🔒 งานบริษัท ProInventive — private · org `proinventive`

| โปรแกรม | โฟลเดอร์ (ใต้ `<ไดรฟ์>:\`) | repo |
|---|---|---|
| solar-engine + asc-enterprises + digitize-kit | `enterprise\solar-project-complete` | proinventive/solar-project-complete (private) |
| picode monorepo (aiSolar · asc · pi-boq-dev · solar-saas · webproinventive) | `LocalAI\git\picode` | proinventive/picode (private) |
| picode-cdn | – (ยังไม่ clone) | proinventive/picode-cdn (**public**) |
| **CRM-Pi / Pi System** (pi_crm_erp + pi_boq_app) | `F:\enterprise\pi-system\` **(laptop เท่านั้น)** | ⚠️ **ยังไม่มี remote** — ต้องสร้าง private repo ใต้ proinventive แล้ว push จาก laptop (ถ้า laptop เสียงานหาย) |

CRM-Pi: เว็บ `pi-system.pages.dev` (Cloudflare Pages) · build `node pi_crm_erp/scripts/build_pages.mjs` · แผนเชื่อม ASC Studio: `design-auto\docs\crm-pi-integration.md`

## หมวด 2 · 🔒 ผลิตภัณฑ์ของลุงพี — private · `peeraponggis`

| โปรแกรม | เวอร์ชัน | โฟลเดอร์ | repo |
|---|---|---|---|
| Design Auto (Auto Solar Co-pilot Studio) | 0.125.0 | `LocalAI\aiSolar\design-auto` | peeraponggis/asc_auto |
| ASC Architect (ASCA) | 0.15.0 | `LocalAI\pee_architec` | peeraponggis/pee_architec (ห้ามปนกับ aiSolar) |

## หมวด 3 · 🌐 โค้ดเปิดเผยได้ — public · `peeraponggis`

**3.1 repo หลัก `C:\LocalAI` → peeraponggis/aiSolar (branch master)**

| โปรแกรม | เวอร์ชัน | โฟลเดอร์ |
|---|---|---|
| Local Translator | 1.9.0 | `LocalAI\translation` |
| Lungpee AI Gateway | 1.6.0 | `LocalAI\gateway` |
| Lungpee Agent | 1.6.0 | `LocalAI\lungpee-agent` |
| Lek Dang (Yeekee) | 1.0.0 | `LocalAI\yk` |
| Thai-Lao Dictionary | 1.0.0 | `LocalAI\Thai-Lao` |
| Battery & System Dashboard | 1.3.0 | `LocalAI\battery_info` |
| GAS Monitor | 2.4.0 | `LocalAI\gas_monitor` |
| RemoteAIR (รีโมทแอร์ Android/iOS) | 1.0.0 | `LocalAI\remoterAIR` |
| YT dashboard | – | `LocalAI\yt` |

**3.2 repo แยก**

| โปรแกรม | เวอร์ชัน | โฟลเดอร์ | repo |
|---|---|---|---|
| ASC Studio (ASCS) | 4.2.0 | `LocalAI\git\asc` | peeraponggis/asc |
| courseweb (เว็บคอร์สออนไลน์) | – | `LocalAI\courseweb` | peeraponggis/online |

**3.3 repo `ai` — โปรแกรมเล็ก เฉพาะโค้ด** → `LocalAI\git\ai\<ชื่อโปรแกรม>\` · peeraponggis/ai

| sub folder | ต้นฉบับ (ยังทำงานที่นี่) | เวอร์ชัน |
|---|---|---|
| Trading | `LocalAI\Trading` | 1.0.0 |
| HomeGuard | `LocalAI\tools\homeguard` | 2.0.3 |
| Multi-Tools | `LocalAI\multi-tools` | – |
| CCTV | `LocalAI\cctv` | – |
| Desktop-App | `LocalAI\desktop_app` | – |
| Tune-PC | `LocalAI\tools\Tune-PC` (ต้นฉบับ J:) | – |
| EV-Charger-Research | `LocalAI\aiSolar\EV_Charger_Research` (ต้นฉบับ I:) | – |
| AMI-Fetcher · AMR-Fetcher · PEA-Build | `LocalAI\AMI_Fetcher` · `AMR_Fetcher` · `PEA_build` | – |
| FB-Fetcher · FB-Extension | `LocalAI\FB_Fetcher` · `FB_Extension` | – |

- อัปเดต: `bash LocalAI/git/ai/tools/sync_from_localai.sh` → commit + push · สคริปต์คัดเฉพาะโค้ด ล้างบัญชี/รหัสผ่าน/อีเมล และหยุดถ้าเจอรหัสผ่านเหลือ
- แก้บน laptop แล้วต้องคัดลอกกลับโฟลเดอร์ต้นฉบับเอง
- ⏳ commit แล้ว (31 ต.ค. 2569) **ยังไม่ได้ push** — รอลุงพีล็อกอิน: `git -C C:/LocalAI/git/ai push origin main`
- ไม่ขึ้น: ConstructCAD (ของ francisreboucas · GPL) · Carport-CM (มีแค่รูป)

**3.4 repo ที่ยังไม่ได้ clone ลงเครื่องนี้** (clone เฉพาะตัวที่จะแก้)
aisolar2 · envi_pi · peechat · solar-relay · 3DPVs · deepseek · fs · present · carport_cm · pi-boq-dev · webproinventive · esri-leaflet-doc (2 ตัวหลังมีฉบับใน picode ด้วย)

## หมวด 4 · ⛔ ห้ามขึ้น git ทุกกรณี — คัดลอกผ่าน Tailscale/SSH เท่านั้น

| อะไร | อยู่ที่ | เหตุผล |
|---|---|---|
| ผลงาน Design Auto (~3.8 GB) | `design-auto\out` | ใหญ่ |
| ข้อมูล server Design Auto | `design-auto\server\data` | ข้อมูลผู้ใช้ |
| ภาพสแกนมาตรฐาน วสท. | `solar-project-complete\eit` | ลิขสิทธิ์ |
| ข้อมูลลูกค้า + มิเตอร์ | `AMR_Fetcher\data` | ข้อมูลลูกค้าจริง |
| วิดีโอกล้อง | `cctv\` (mp4) | ความเป็นส่วนตัว |
| บัญชี/รหัสผ่าน PEA | ต้นฉบับ `AMI_Fetcher` · `AMR_Fetcher` · `PEA_build` | รหัสผ่านจริง (ควรเปลี่ยนรหัส ถ้าเคยส่งต่อ) |
| คีย์ API ผู้ช่วย AI | localStorage ในเบราว์เซอร์ | ห้ามลงไฟล์ |

**ด่านกันพลาด:** `C:\LocalAI\.gitignore` (repo aiSolar ซึ่งเป็น public) บล็อกโฟลเดอร์หมวด 4 + โปรแกรมหมวด 3.3 ต้นฉบับ + repo แยกใต้ `git\` + `config.ini` `.env` `*.key` `*.pem` `*.db` `*.xls(x)` วิดีโอ — ไฟล์ที่ track อยู่แล้วไม่ได้รับผล

---

## การเข้าถึงข้ามเครื่อง
- home server: Tailscale (IP ดูใน memory project_homeserver_ssh · ไม่ใส่ใน repo public) · session ศูนย์กลางเปิด Remote Control → สั่งงานจาก claude.ai/code หรือแอปมือถือ
- laptop: `tools\git-autopull.ps1` pull อัตโนมัติตอน login (Design Auto + solar-project-complete) · home server ยังไม่มี auto-pull
- ไม่พบบัญชีบน GitLab / Bitbucket / Codeberg
