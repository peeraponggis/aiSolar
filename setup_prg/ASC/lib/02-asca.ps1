# 02-asca.ps1 — ASC Architect ปล่อยรุ่น (private repo · ชุดติดตั้ง Inno + ชุดอัปเดต + เว็บ)
. "$PSScriptRoot\common.ps1"
$d = $P.asca.dir; $asc = $P.asc.dir; $py = "$d\.venv\Scripts\python.exe"
function Step-Installer {
  Title 'ชุดติดตั้ง Inno + ชุดอัปเดต (scripts\build_installer.py)'
  if (-not (Test-Path -LiteralPath "$Inno\ISCC.exe")) { throw "ไม่พบ Inno Setup ที่ $Inno" }
  if (-not (Test-Path -LiteralPath $KeyASCA)) { throw "ไม่พบรหัสชุดติดตั้ง $KeyASCA" }
  $o = Run 'build_installer.py' $py @("$d\scripts\build_installer.py") $d
  $v = Ver 'asca'
  $exe = Get-ChildItem "$LocalAI\apps\ASCA-release\$v\ASCA-Setup-$v.exe" -ErrorAction SilentlyContinue
  if ($exe) { Ok "$($exe.FullName) ($([math]::Round($exe.Length/1MB,1)) MB) · รหัสอยู่ที่ $KeyASCA (ไม่แสดง)" } else { Warn 'ไม่พบไฟล์ exe ที่คาดไว้ — ดู log' }
  Ok "asc\docs\asca-release: $((Get-ChildItem "$asc\docs\asca-release" -Name) -join ' · ')"
  Sync-Installers | ForEach-Object { Ok "พกไปเครื่องใหม่: $($_.dst)" }
}
function Step-Web { Title 'เว็บ: build_cloud.py → asc\docs\architec'; Run 'build_cloud.py --to' $py @("$d\scripts\build_cloud.py", '--to', "$asc\docs\architec") $d | Out-Null }
# build_installer.py ใช้เฉพาะไฟล์ใน git HEAD → ต้อง commit+push pee_architec ก่อนสร้างชุดติดตั้ง
function Step-PushAsca {
  Title 'commit + push pee_architec (private) — ก่อนสร้างชุดติดตั้ง'
  $v = Ver 'asca'
  $note = ((Get-Content -LiteralPath "$d\CHANGELOG.md" -Encoding UTF8 | Where-Object { $_ -match '^\*\*' } | Select-Object -First 1) -replace '\*', '')
  git -C $d add -A; git -C $d reset -q -- dist-cloud 2>$null
  CommitPush 'asca' "ASC Architect ${v}: $note โดย ลุงพี" @() | Out-Null
}
function Step-Push {
  Title 'push asc (architec + ชุดอัปเดต)'
  $v = Ver 'asca'
  git -C $asc add -- docs/architec docs/asca-release
  ScanSecrets $asc @((Get-Content -LiteralPath $KeyASCA -Raw -ErrorAction SilentlyContinue))
  if (CommitPush 'asc' "ASC Architect $v (architec + ชุดอัปเดต)" @()) { & "$PSScriptRoot\03-cloud.ps1" -VerifyOnly }
}
try {
  Clear-Host; Title "ASC Architect $(Ver 'asca')  ($d)"
  Log "git: $(GitState 'asca')"
  Write-Host ''; Write-Host '  [1] ทำครบ (2→3→4)'; Write-Host '  [2] ชุดติดตั้ง Inno + ชุดอัปเดต'; Write-Host '  [3] เว็บ: build_cloud → asc\docs\architec'; Write-Host '  [4] push pee_architec + asc → ตรวจเว็บ'; Write-Host '  [0] กลับ'
  switch (Read-Host 'เลือก') {
    '1' { GitPull 'asca'; GitPull 'asc'; Step-PushAsca; Step-Installer; Step-Web; Step-Push }
    '2' { Step-PushAsca; Step-Installer } '3' { Step-Web } '4' { GitPull 'asc'; Step-Push }
    default { return }
  }
} catch { Bad "หยุด: $($_.Exception.Message)" }
Pause-Menu
