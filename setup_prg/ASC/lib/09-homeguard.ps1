# 09-homeguard.ps1 — HomeGuard (ไม่อยู่ใน git · ตัวจริงรันบน home server): build → ชุดติดตั้ง → ส่ง/เทียบกับ home
#   ห้ามรัน homeguard.ps1 บน laptop เพื่อทดสอบ (มันตัด RAM/ปิด vite) — ทดสอบด้วยการ build เท่านั้น
. "$PSScriptRoot\common.ps1"
$d = $P.hg.dir; $v = Ver 'hg'; $homeDir = "$HomeRoot\tools\homeguard"
$core = 'homeguard.ps1', 'homeguard-console.ps1', 'appwatch.ps1', 'ramguard.ps1', 'sysinfo.ps1', 'aiwatch.ps1', 'diskcare.ps1', 'hook-wait.ps1', 'shortcuts.ps1', 'install.ps1', 'VERSION.json', 'CHANGELOG.md'
function Compare-Home {
  Title 'เทียบไฟล์ laptop ↔ home (hash)'
  $cmd = ($core | ForEach-Object { "certutil -hashfile `"$homeDir\$_`" SHA256 | findstr /v hash" }) -join ' & '
  $hv = try { (((HomeSsh "type $homeDir\VERSION.json" 6) -join '') | ConvertFrom-Json).version } catch { '-' }
  Log "รุ่น: laptop $v · home $hv $(if ($hv -eq $v) { '✓' } else { '≠' })"
  $remote = HomeSsh $cmd 20 | Where-Object { $_ -match '^[0-9a-f]{64}$' }
  for ($i = 0; $i -lt $core.Count; $i++) {
    $lf = Join-Path $d $core[$i]
    $lh = if (Test-Path -LiteralPath $lf) { (Get-FileHash -LiteralPath $lf -Algorithm SHA256).Hash.ToLower() } else { '' }
    $rh = "$($remote[$i])".ToLower()
    if (-not $lh) { Warn "$($core[$i]): ไม่มีบน laptop" } elseif (-not $rh) { Warn "$($core[$i]): อ่านจาก home ไม่ได้" } elseif ($lh -eq $rh) { Ok $core[$i] } else { Warn "$($core[$i]): ต่างกัน" }
  }
  Log 'ไฟล์ที่ต่างกัน: ดู CHANGELOG ทั้งสองฝั่งก่อนตัดสินใจว่าฝั่งไหนใหม่กว่า (ตัวจริง = home) ห้ามทับมั่ว'
}
try {
  Clear-Host; Title "HomeGuard $v  ($d · ไม่อยู่ใน git)"
  $exe = Get-Item "$d\dist\HomeGuard-Setup.exe" -ErrorAction SilentlyContinue
  if ($exe) { Log "ชุดติดตั้ง: dist\HomeGuard-Setup.exe ($([math]::Round($exe.Length/1MB,1)) MB · $($exe.LastWriteTime.ToString('d MMM HH:mm')))" } else { Warn 'ยังไม่มี dist\HomeGuard-Setup.exe' }
  Write-Host ''
  Write-Host '  [1] build (build.ps1): HomeGuard.exe · DiskCare.exe · dist\HomeGuard-Setup.zip/.exe'
  Write-Host '  [2] สำเนาชุดติดตั้งทุกโปรแกรมไป setup_prg\installers\ (ลบรุ่นเก่า · พกไปเครื่องใหม่)'
  Write-Host '  [3] เทียบไฟล์กับ home server (hash) — ดูว่าฝั่งไหนใหม่กว่า'
  Write-Host '  [4] ดึงตัวจริงจาก home → tools\homeguard\from-home\ (ไม่ทับตัวพัฒนา)'
  Write-Host '  [5] ส่งชุดติดตั้งไป home แล้วเปิดตัวติดตั้งบน home (ผ่าน ssh · ถามก่อน)'
  Write-Host '  [0] กลับ'
  switch (Read-Host 'เลือก') {
    '1' { Run 'build.ps1' powershell @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "$d\build.ps1") $d | Out-Null; Get-ChildItem "$d\dist\HomeGuard-Setup.*" | ForEach-Object { Ok "$($_.Name) $([math]::Round($_.Length/1MB,1)) MB" }; Sync-Installers | ForEach-Object { Ok "พกไปเครื่องใหม่: $($_.dst)" } }
    '2' { Sync-Installers | ForEach-Object { Ok "$($_.dst) ($($_.mb) MB)" } }
    '3' { Compare-Home }
    '4' { $to = "$d\from-home"; New-Item -ItemType Directory -Force $to | Out-Null; Run 'scp HomeGuard จาก home' scp @('-r', "${SshHost}:$homeDir\*", "$to\") | Out-Null; Ok "→ $to" }
    '5' { if (-not $exe) { throw 'ยังไม่มีชุดติดตั้ง — เลือก [1] ก่อน' }
          Compare-Home
          if (Ask "ส่ง HomeGuard-Setup.exe $v ไป home และเปิดตัวติดตั้งบนจอ home?") {
            Run 'scp → home' scp @($exe.FullName, "${SshHost}:$HomeRoot\laptop-data\HomeGuard-Setup-$v.exe") | Out-Null
            HomeSsh "schtasks /create /tn HG-Setup /tr `"$HomeRoot\laptop-data\HomeGuard-Setup-$v.exe`" /sc once /st 00:00 /f /it & schtasks /run /tn HG-Setup & schtasks /delete /tn HG-Setup /f" 20 | Out-Null
            Ok 'เปิดตัวติดตั้งบน home แล้ว — ไปกด "ติดตั้ง" ที่จอ home (RDP/Remote Control) · ติดตั้งทับ C:\LocalAI\tools\homeguard ไม่แตะ state/log' }
        }
    default { return }
  }
} catch { Bad "หยุด: $($_.Exception.Message)" }
Pause-Menu
