# 08-newpc.ps1 — ติดตั้งบนเครื่องใหม่ (คัดลอกโฟลเดอร์ setup_prg\ASC + ชุดติดตั้งไปด้วย) · ถามก่อนติดตั้งทุกตัว
param([string]$Pick)
. "$PSScriptRoot\common.ps1"
# เลขรุ่นของเครื่องมือ (ไม่มี = $null) — ดึงเฉพาะตัวเลข ไม่พิมพ์ usage ยาว ๆ
function Has($exe, $a) {
  if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { return $null }
  $ErrorActionPreference = 'Continue'
  try { $o = (& $exe @a 2>&1 | ForEach-Object { "$_" } | Where-Object { $_ -match '\d+\.\d+' } | Select-Object -First 1); $m = [regex]::Match("$o", '\d+\.\d+(\.\d+)?'); if ($m.Success) { $m.Value } else { 'มี' } } catch { 'มี' }
}
function PyVer { $v = Has py @('-3.12', '--version'); if (-not $v) { $v = Has python @('--version') }; if ($v -and $v -ne 'มี' -and [version]$v -lt [version]'3.12') { return $null }; $v }
function NodeVer { $v = Has node @('--version'); if ($v) { return $v }; if (Get-Command npm.cmd -ErrorAction SilentlyContinue) { 'มี (ผ่าน npm)' } else { $null } }
function TsVer { if (Test-Path "$env:ProgramFiles\Tailscale\tailscale.exe") { Has "$env:ProgramFiles\Tailscale\tailscale.exe" @('version') } else { Has tailscale @('version') } }
try {
  Clear-Host; Title 'ติดตั้งบนเครื่องใหม่'
  $tools = [ordered]@{
    'Python 3.12+' = PyVer; 'Node' = NodeVer; 'git' = Has git @('--version'); 'gh' = Has gh @('--version')
    'Ollama' = Has ollama @('--version'); 'Tailscale' = TsVer; '.NET 4 csc' = $(if (Test-Path "$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe") { 'มี' } else { $null })
  }
  foreach ($k in $tools.Keys) { if ($tools[$k]) { Ok "$k : $($tools[$k])" } else { Bad "$k : ไม่มี" } }
  $setupAscs = Get-ChildItem "$($P.ascs.dir)\out\setup\ASC-Studio-Setup-*.exe", "$InstDir\ASC-Studio-Setup-*.exe" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime | Select-Object -Last 1
  $setupAsca = Get-ChildItem "$LocalAI\apps\ASCA-release\*\ASCA-Setup-*.exe", "$InstDir\ASCA-Setup-*.exe" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime | Select-Object -Last 1
  $zipTr     = Get-ChildItem "$($P.tr.dir)\LocalTranslator-setup*.zip", "$InstDir\LocalTranslator-setup*.zip" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime | Select-Object -Last 1
  $setupHg   = Get-ChildItem "$($P.hg.dir)\dist\HomeGuard-Setup.exe", "$InstDir\HomeGuard-Setup-*.exe" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime | Select-Object -Last 1
  Write-Host ''
  Write-Host '  ลำดับติดตั้ง desktop app บนเครื่องใหม่:' -ForegroundColor White
  foreach ($o in $InstallOrder) { Write-Host ("   {0}. {1,-26} {2}" -f $o.n, $o.name, $o.what) -ForegroundColor DarkGray }
  Write-Host ''
  Write-Host '  [9] ติดตั้งตามลำดับทั้งหมด (ถามทีละขั้น ข้ามได้)' -ForegroundColor Yellow
  Write-Host "  [7] HomeGuard      $(if ($setupHg) { $setupHg.Name } else { '(ไม่พบชุดติดตั้ง · สร้างจากเมนู 09)' })"
  Write-Host "  [1] ASC Studio     $(if ($setupAscs) { $setupAscs.Name } else { '(ไม่พบชุดติดตั้ง · มี git = clone + install.bat)' })"
  Write-Host "  [2] ASC Architect  $(if ($setupAsca) { $setupAsca.Name } else { '(ไม่พบชุดติดตั้ง)' })  รหัส: $KeyASCA"
  Write-Host "  [3] Local Translator $(if ($zipTr) { $zipTr.Name } else { '(ไม่พบ zip)' })"
  Write-Host '  [4] ASC Cloud / CRM-Pi — เว็บ ไม่ต้องติดตั้ง (เปิดลิงก์)'
  Write-Host '  [5] ติดตั้งเครื่องมือที่ขาดด้วย winget (ถามทีละตัว)'
  Write-Host '  [6] ไอคอน Desktop ทุกโปรแกรม'
  Write-Host '  [0] กลับ'
  $choice = if ($Pick) { $Pick } else { Read-Host 'เลือก' }
  if ($choice -eq '9') {
    # ติดตั้งตามลำดับ — แต่ละขั้นถามก่อน ข้ามได้ · เรียกเมนูย่อยซ้ำ
    $plan = @(@('5', 'เครื่องมือพื้นฐาน (winget ที่ขาด)'), @('7', 'HomeGuard'), @('1', 'ASC Studio'), @('2', 'ASC Architect'), @('3', 'Ollama + Local Translator'), @('6', 'ไอคอน Desktop'))
    foreach ($s in $plan) { Title "ขั้น: $($s[1])"; if (Ask "ทำขั้นนี้?") { & $PSCommandPath -Pick $s[0] } else { Warn 'ข้าม' } }
    Log 'ครบทุกขั้นแล้ว — เปิด ASC Studio แล้วล็อกอิน ASC Cloud · CRM-Pi ใช้ผ่านเว็บ'
    Pause-Menu; return
  }
  switch ($choice) {
    '7' { if ($setupHg) { Ok "เปิด $($setupHg.FullName) — เลือกโฟลเดอร์แล้วกด ติดตั้ง (ค่าเริ่ม C:\LocalAI\tools\homeguard)"; Start-Process $setupHg.FullName } else { Bad 'ไม่มีชุดติดตั้ง HomeGuard — สร้างจากเมนู [9] HomeGuard ก่อน' } }
    '1' {
      if ($tools['git'] -and (Ask 'มี git — ติดตั้งแบบ git (clone + install.bat) แทนชุดติดตั้ง?')) {
        $to = Read-Host "โฟลเดอร์ปลายทาง (Enter = $LocalAI\aiSolar\design-auto)"; if (-not $to) { $to = "$LocalAI\aiSolar\design-auto" }
        Run 'git clone' git @('clone', "https://github.com/$($P.ascs.repo).git", $to) | Out-Null
        Start-Process cmd @('/k', "`"$to\install.bat`"")
      } elseif ($setupAscs) { Ok "เปิด $($setupAscs.FullName)"; Start-Process $setupAscs.FullName } else { Bad 'ไม่มีชุดติดตั้ง — สร้างจากเมนู [1] บน laptop ก่อน' }
    }
    '2' { if ($setupAsca) { Log "รหัสชุดติดตั้งอยู่ในไฟล์ $KeyASCA (เปิดดูเองบน laptop ลุงพี)"; Start-Process $setupAsca.FullName } else { Bad 'ไม่มีชุดติดตั้ง — สร้างจากเมนู [2] ก่อน' } }
    '3' { if (-not (Get-Command ollama -ErrorAction SilentlyContinue) -and (Ask 'ยังไม่มี Ollama — ติดตั้งด้วย winget (Ollama.Ollama)?')) { Run 'winget Ollama' winget @('install', '-e', '--id', 'Ollama.Ollama', '--accept-source-agreements', '--accept-package-agreements') | Out-Null }
          if ($zipTr) { $to = "$LocalAI\translation\LocalTranslator"; New-Item -ItemType Directory -Force $to | Out-Null; Expand-Archive -LiteralPath $zipTr.FullName -DestinationPath $to -Force; Ok "แตกไป $to"; Start-Process "$to\Install-LocalTranslator.bat" -WorkingDirectory $to } else { Bad 'ไม่มี zip — สร้างจากเมนู [5] ก่อน' } }
    '4' { Open-Url $P.asc.url; Open-Url $P.crm.url; Log 'ขอสิทธิ์: ASC Cloud → supabase/allow-domains.sql หรือ invite-users.mjs · CRM-Pi → ตั้ง admin ใน Supabase CRM' }
    '5' { foreach ($w in @(@('git', 'Git.Git'), @('gh', 'GitHub.cli'), @('Tailscale', 'Tailscale.Tailscale'), @('Node', 'OpenJS.NodeJS.LTS'), @('Python 3.12+', 'Python.Python.3.12'))) {
            if (-not $tools[$w[0]] -and (Ask "ติดตั้ง $($w[0]) ($($w[1]))?")) { Run "winget $($w[1])" winget @('install', '-e', '--id', $w[1], '--accept-source-agreements', '--accept-package-agreements') | Out-Null } } }
    '6' { foreach ($sc in "$($P.ascs.dir)\scripts\make-shortcut.ps1", "$($P.asca.dir)\scripts\make-shortcut.ps1", "$Here\lib\make-shortcut.ps1") { if (Test-Path -LiteralPath $sc) { Run (Split-Path $sc -Leaf) powershell @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $sc) | Out-Null } } }
    default { return }
  }
} catch { Bad "หยุด: $($_.Exception.Message)" }
if (-not $Pick) { Pause-Menu }
