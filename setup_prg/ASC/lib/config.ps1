# config.ps1 — path/ค่าตั้งทั้งหมดของชุด bat (แก้ที่เดียวเมื่อย้ายโฟลเดอร์ · ลุงพีสั่ง 7 พ.ย. 2569)
#   ไม่มีคีย์/รหัสผ่านในไฟล์นี้ · ไดรฟ์หาจากตำแหน่งโฟลเดอร์นี้เอง (laptop F: · ถ้าคัดลอกไป C: ก็ใช้ได้)
$script:Drive   = (Split-Path -Qualifier $PSScriptRoot)            # F:
$script:LocalAI = "$Drive\LocalAI"
$script:Ent     = "$Drive\enterprise"
$script:Here    = Split-Path -Parent $PSScriptRoot                  # setup_prg\ASC
$script:LogDir  = "$Here\logs"

$script:P = [ordered]@{
  ascs = @{ name = 'ASC Studio';      dir = "$LocalAI\aiSolar\design-auto";  ver = 'VERSION.json'; repo = 'peeraponggis/asc_auto' }
  asca = @{ name = 'ASC Architect';   dir = "$LocalAI\pee_architec";         ver = 'VERSION.json'; repo = 'peeraponggis/pee_architec' }
  asc  = @{ name = 'ASC Cloud';       dir = "$LocalAI\git\asc";              ver = 'VERSION.json'; repo = 'peeraponggis/asc'; url = 'https://peeraponggis.github.io/asc' }
  crm  = @{ name = 'CRM-Pi';          dir = "$Ent\picode\pi-system";         ver = 'pi_crm_erp\VERSION.json'; git = "$Ent\picode"; url = 'https://pi-system.pages.dev' }
  tr   = @{ name = 'Local Translator'; dir = "$LocalAI\translation";         ver = 'VERSION.json'; git = $LocalAI }
  hg   = @{ name = 'HomeGuard';        dir = "$LocalAI\tools\homeguard";     ver = 'VERSION.json'; nogit = $true }   # ไม่อยู่ใน git · ตัวจริงรันบน home C:\LocalAI\tools\homeguard
}
$script:Programs = "$LocalAI\PROGRAMS.md"
$script:KeyASCS  = "$LocalAI\apps\ASCS-release\password.txt"
$script:KeyASCA  = "$LocalAI\apps\ASCA-release\password.txt"
$script:Inno     = "$LocalAI\apps\InnoSetup6"
$script:SshHost  = 'home'                                            # Host home ใน ~/.ssh/config (Tailscale 100.118.18.110)
$script:HomeRoot = 'C:\LocalAI'                                       # home server ไม่มี F:

# Supabase — ลิงก์ SQL Editor ต้องแจ้งทุกครั้งที่ให้ลุงพีรัน SQL (กฎ 7 พ.ย. 2569)
$script:Supa = [ordered]@{
  asc = @{ name = 'ASC Cloud'; ref = 'rcaslesvgilknupqmwrp'; url = 'https://supabase.com/dashboard/project/rcaslesvgilknupqmwrp/sql/new' }
  crm = @{ name = 'CRM-Pi';    ref = 'zloxphgxhttrtgqlafsz'; url = 'https://supabase.com/dashboard/project/zloxphgxhttrtgqlafsz/sql/new' }
}
# ไฟล์ SQL ที่ต้องรัน "ทุกรุ่น/เมื่อเปลี่ยน" (06) · secret = มีกุญแจ ห้ามพิมพ์/ลง log
$script:SqlEach = @(
  @{ p = 'asc'; f = "$($P.ascs.dir)\out\cloud\kb-data.sql";          note = 'คลังความรู้ AI รุ่นเว็บ (npm run kb:sql)' }
  @{ p = 'asc'; f = "$($P.ascs.dir)\out\cloud\ascs-release-key.sql"; note = 'กุญแจชุดติดตั้ง (เมื่อกุญแจเปลี่ยน)'; secret = $true }
  @{ p = 'asc'; f = "$($P.ascs.dir)\out\cloud\standards-data.sql";   note = 'ตาราง วสท. รุ่นเว็บ (npm run standards:sql)' }
  @{ p = 'crm'; f = "$($P.crm.dir)\pi_crm_erp\supabase\20261031_asc_studio.sql";  note = 'CRM ↔ ASC Studio' }
  @{ p = 'crm'; f = "$($P.crm.dir)\pi_crm_erp\supabase\20261031_admin_users.sql"; note = 'สิทธิ์ admin (รันซ้ำหลัง full_install ทุกครั้ง)' }
)
# ลำดับติดตั้งครั้งแรก (06 [F])
$script:SqlFirst = [ordered]@{
  asc = @('schema.sql', 'kb.sql', 'ascs-studio.sql', 'ascs-release.sql', 'ai-install.sql', 'allow-domains.sql', 'devices.sql', 'menu-access.sql',
          'presence.sql', 'pi-monitor-telegram.sql', 'presence-ingest.sql', 'presence-device.sql', 'presence-apps.sql', 'device-menus.sql') | ForEach-Object { "$($P.asc.dir)\supabase\$_" }
  crm = @('pi_system_full_install.sql', '20261031_asc_studio.sql', '20261031_admin_users.sql') | ForEach-Object { "$($P.crm.dir)\pi_crm_erp\supabase\$_" }
}
# สคริปต์ของโปรแกรมที่ bat เรียก — ตรวจตอนเปิดเมนูว่ายังอยู่ครบ (ถ้าโปรแกรมเปลี่ยนชื่อสคริปต์ ต้องแก้ที่นี่)
$script:Needs = @(
  "$($P.ascs.dir)\installer\build-setup.ps1", "$($P.ascs.dir)\scripts\build-cloud.mjs", "$($P.ascs.dir)\scripts\kb-build.mjs",
  "$($P.ascs.dir)\scripts\pull-home.ps1", "$($P.ascs.dir)\scripts\sync-home.ps1", "$($P.ascs.dir)\scripts\send-laptop-data.ps1", "$($P.ascs.dir)\scripts\sync-home-gui.ps1",
  "$($P.asca.dir)\scripts\build_installer.py", "$($P.asca.dir)\scripts\build_cloud.py",
  "$($P.crm.dir)\pi_crm_erp\scripts\build_pages.mjs", "$($P.tr.dir)\LocalTranslator.spec",
  "$($P.hg.dir)\build.ps1", "$($P.hg.dir)\pack.ps1", "$($P.hg.dir)\Install-HomeGuard.cmd"
)
# ลำดับติดตั้ง desktop app บนเครื่องใหม่ (08 [9]) — ลุงพีสั่ง 7 พ.ย. 2569
$script:InstallOrder = @(
  @{ n = 1; name = 'เครื่องมือพื้นฐาน';  what = 'Python 3.12+ (ASCS) · Tailscale (ถ้าต้องต่อ home/ใช้ ASCA ผ่าน Tailscale) · git+gh เฉพาะเครื่องพัฒนา · .NET 4 มีใน Windows แล้ว' }
  @{ n = 2; name = 'HomeGuard';          what = 'ดูแลเครื่อง (RAM · ดิสก์ · เฝ้าโปรแกรม) ลงก่อนเพื่อให้เห็นสถานะเครื่องตั้งแต่ต้น — HomeGuard-Setup.exe' }
  @{ n = 3; name = 'ASC Studio';         what = 'ชุดติดตั้ง ASC-Studio-Setup-<v>.exe (ใส่ update.key ให้ อัปเดตเองได้) · เปิดครั้งแรกใช้เวลา pip/playwright' }
  @{ n = 4; name = 'ASC Architect';      what = 'ASCA-Setup-<v>.exe (ใส่รหัส) · มี Python ในตัว · ส่งงานจาก ASCS ได้หลังลงทั้งคู่' }
  @{ n = 5; name = 'Ollama + Local Translator'; what = 'เฉพาะเครื่องที่ใช้ AI ในเครื่อง: Ollama → แตก zip → Install-LocalTranslator.bat (ดึงโมเดล 2.5 GB)' }
  @{ n = 6; name = 'ไอคอน Desktop + ล็อกอิน'; what = 'ไอคอนทุกโปรแกรม · เปิด ASC Studio ล็อกอิน ASC Cloud · CRM-Pi ใช้ผ่านเว็บไม่ต้องติดตั้ง' }
)
