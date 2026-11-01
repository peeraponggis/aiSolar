# ทะเบียนโปรแกรมของลุงพี (ศูนย์กลาง · ทั้ง Laptop + Home server)

อัปเดต 1 พ.ย. 2569 · laptop ใช้ `F:\` · home server ใช้ `C:\` (โครงสร้างโฟลเดอร์เหมือนกัน)
แบ่ง 4 หมวดตาม **"ใครเห็นได้"** — เช็กหมวดก่อนแก้หรือ push ทุกครั้ง

## ⚡ กฎเหล็ก 2 เครื่อง (ลุงพีสั่ง 31 ต.ค. 2569 · ใช้กับทุก repo · ทั้งคนและ Claude ทุก session)

1. **เริ่มงานบนเครื่องไหน → pull ก่อนทุกครั้ง** ก่อนแตะไฟล์ใดๆ
   `git -C <repo> pull --rebase --autostash` (เก็บงานที่ยังไม่ commit ไว้ให้ แล้วคืนกลับเอง)
2. **จบงาน → commit + push ทันที** ก่อนสลับเครื่อง/ปิดเครื่อง — ห้ามทิ้ง commit ค้างไว้เครื่องเดียว
3. **ก่อน push repo public** (aiSolar · asc · online · ai) → ตรวจว่าไม่มี API key / รหัสผ่าน / ข้อมูลลูกค้า (ดูหมวด 4)
4. **ถ้า pull ขึ้น diverged** → `pull --rebase --autostash` · **ถ้า CONFLICT → หยุด** ห้าม `--force` · ถาม Claude ใน session ศูนย์กลาง

เหตุที่ต้องมีกฎ: 31 ต.ค. 2569 laptop มี commit Free AI API Finder ที่ยังไม่ push ขณะที่ home server push PROGRAMS.md ขึ้นไปก่อน → สองฝั่งแยกทาง `pull --ff-only` ใช้ไม่ได้ ต้องแก้ด้วยมือ

อื่นๆ: bump VERSION.json + CHANGELOG ทุกครั้งที่แก้ · Claude บน home server push/pull เองได้ (GCM dpapi store · memory project_central_session)

---

## หมวด 1 · 🔒 งานบริษัท ProInventive — private · org `proinventive`

| โปรแกรม | โฟลเดอร์ (ใต้ `<ไดรฟ์>:\`) | repo |
|---|---|---|
| solar-engine + asc-enterprises + digitize-kit | `enterprise\solar-project-complete` | proinventive/solar-project-complete (private) |
| picode monorepo (aiSolar · asc · pi-boq-dev · solar-saas · webproinventive) | `LocalAI\git\picode` | proinventive/picode (private) |
| picode-cdn | – (ยังไม่ clone) | proinventive/picode-cdn (**public**) |
| **CRM-Pi / Pi System 1.2.2** (pi_crm_erp + pi_boq_app) | **ต้นฉบับจริง:** monorepo picode โฟลเดอร์ `pi-system\` → laptop `F:\enterprise\picode\pi-system\` · home `C:\LocalAI\git\picode\pi-system\` | proinventive/picode (private) |

⚠️ **CRM-Pi มีสำเนาเก่าอีกชุด** — `F:\enterprise\pi-system\` (laptop) = repo `proinventive/pi-system` (private · สร้าง 31 ต.ค. 2569) · clone ไว้ที่ home `C:\enterprise\pi-system\` · **ค้างที่ก่อนมีผู้ช่วย AI** — ห้ามแก้ที่นี่ ใช้ picode เท่านั้น · **ลุงพีให้เก็บไว้เป็นสำรอง** (1 พ.ย. 2569 · ไม่ลบ ไม่ push เพิ่ม)

CRM-Pi: เว็บ `pi-system.pages.dev` (Cloudflare Pages) · **deploy จาก laptop เท่านั้น** (ลุงพีสั่ง 1 พ.ย. 2569): ใน `F:\enterprise\picode\pi-system` → `node pi_crm_erp/scripts/build_pages.mjs` → `npx wrangler pages deploy dist_pages --project-name pi-system --branch production` · แผนเชื่อม ASC Studio: `design-auto\docs\crm-pi-integration.md`

## หมวด 2 · 🔒 ผลิตภัณฑ์ของลุงพี — private · `peeraponggis`

| โปรแกรม | เวอร์ชัน | โฟลเดอร์ | repo |
|---|---|---|---|
| Design Auto (Auto Solar Co-pilot Studio) | 0.133.0 | `LocalAI\aiSolar\design-auto` | peeraponggis/asc_auto |
| ASC Architect (ASCA) | 0.20.1 | `LocalAI\pee_architec` | peeraponggis/pee_architec (ห้ามปนกับ aiSolar) |

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
| YT Shorts Automation (คลิปอัตโนมัติ 3 โหมด · คิว · ภาพ AI · การ์ดตัวเลข) | 2.3.0 | `LocalAI\yt` |
| Free AI API Finder (ศูนย์รวม AI API ฟรี 87 ราย) | 1.1.0 | `LocalAI\free-ai-api` |

**3.2 repo แยก**

| โปรแกรม | เวอร์ชัน | โฟลเดอร์ | repo |
|---|---|---|---|
| ASC Studio (ASCS) | 4.5.0 | `LocalAI\git\asc` | peeraponggis/asc |
| courseweb (เว็บคอร์สออนไลน์) | – | `LocalAI\courseweb` | peeraponggis/online |
| webproinventive (เว็บ PROINVENTIVE + Pi Console) | 1.0.0 | home `C:\LocalAI\pi\webproinventive` · laptop โฟลเดอร์ Pi-web เดิม (ดู HANDOFF.md ข้อ 4) | peeraponggis/webproinventive · live peeraponggis.github.io/webproinventive (มีฉบับใน picode ด้วย) |

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
- ✅ push ขึ้น GitHub แล้ว (31 ต.ค. 2569 · commit 6caf209)
- ไม่ขึ้น: ConstructCAD (ของ francisreboucas · GPL) · Carport-CM (มีแค่รูป)

**3.4 repo ที่ยังไม่ได้ clone ลงเครื่องนี้** (clone เฉพาะตัวที่จะแก้)
aisolar2 · envi_pi · peechat · solar-relay · 3DPVs · deepseek · fs · present · carport_cm · pi-boq-dev · esri-leaflet-doc (pi-boq-dev มีฉบับใน picode ด้วย)

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
