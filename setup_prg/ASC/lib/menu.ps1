# menu.ps1 — เมนูหลัก (ASC-Menu.bat)
. "$PSScriptRoot\common.ps1"
function HomeVer([string]$rel) { $o = HomeSsh "type $HomeRoot\$rel" 5; try { ($o -join '' | ConvertFrom-Json).version } catch { '-' } }
function SqlPending { & "$PSScriptRoot\06-sql.ps1" -Count }
while ($true) {
  Clear-Host
  Write-Host "══════ ASC — เมนูปล่อยรุ่น / ติดตั้ง / SQL / home server ══════" -ForegroundColor Cyan
  Write-Host "  $Here · $(& $ThaiDate)" -ForegroundColor DarkGray
  $missing = $Needs | Where-Object { -not (Test-Path -LiteralPath $_) }
  if ($missing) { Write-Host "  ✗ สคริปต์ที่ bat เรียกหายไป (แก้ lib\config.ps1):" -ForegroundColor Red; $missing | ForEach-Object { Write-Host "     $_" -ForegroundColor Red } }
  $homeOk = (HomeSsh 'echo ok' 4) -join '' -eq 'ok'
  Write-Host ("  {0,-26} {1,-28} {2}" -f 'รุ่นบน laptop', 'git', $(if ($homeOk) { 'home server' } else { 'home server: ไม่ตอบ' })) -ForegroundColor White
  $hv = @{}; if ($homeOk) { $hv.ascs = HomeVer 'aiSolar\design-auto\VERSION.json'; $hv.asca = HomeVer 'pee_architec\VERSION.json'; $hv.crm = HomeVer 'git\picode\pi-system\pi_crm_erp\VERSION.json' }
  foreach ($k in 'ascs', 'asca', 'asc', 'crm', 'tr') {
    $v = Ver $k; $h = $hv[$k]
    $hs = if ($h) { if ($h -eq $v) { "$h ✓" } else { "$h ≠" } } else { '' }
    Write-Host ("  {0,-16} {1,-9} {2,-28} {3}" -f $P[$k].name, $v, (GitState $k), $hs)
  }
  $n = SqlPending
  Write-Host ''
  Write-Host '  [1] ASC Studio    ปล่อยรุ่น (build · ชุดติดตั้ง · เว็บ · push)'
  Write-Host '  [2] ASC Architect ปล่อยรุ่น (ชุดติดตั้ง Inno · ชุดอัปเดต · เว็บ)'
  Write-Host '  [3] ASC Cloud     deploy + ตรวจเว็บจริง'
  Write-Host '  [4] CRM-Pi        deploy (laptop เท่านั้น)'
  Write-Host '  [5] Local Translator  build ชุดติดตั้ง'
  Write-Host ("  [6] SQL ที่ต้องรัน      {0}" -f $(if ($n) { "● ค้าง $n ไฟล์" } else { '✓ ไม่มีค้าง' })) -ForegroundColor $(if ($n) { 'Yellow' } else { 'Gray' })
  Write-Host '  [7] Home server   ดึง/ส่งข้อมูล · อัปเดตรุ่นบน home'
  Write-Host '  [8] ติดตั้งบนเครื่องใหม่'
  Write-Host '  [9] README    [L] log วันนี้    [0] ออก'
  $c = Read-Host 'เลือก'; if ($null -eq $c) { return }
  switch ($c.ToUpper()) {
    '1' { & "$PSScriptRoot\01-ascs.ps1" }   '2' { & "$PSScriptRoot\02-asca.ps1" }   '3' { & "$PSScriptRoot\03-cloud.ps1" }
    '4' { & "$PSScriptRoot\04-crm.ps1" }    '5' { & "$PSScriptRoot\05-translator.ps1" }   '6' { & "$PSScriptRoot\06-sql.ps1" }
    '7' { & "$PSScriptRoot\07-home.ps1" }   '8' { & "$PSScriptRoot\08-newpc.ps1" }
    '9' { Start-Process "$Here\README.md" }  'L' { Start-Process notepad $LogFile }
    '0' { return }
  }
}
