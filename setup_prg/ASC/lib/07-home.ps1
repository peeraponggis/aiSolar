# 07-home.ps1 — home server (ssh home · C:\LocalAI · ไม่ดึงข้อมูลลูกค้าอัตโนมัติ)
. "$PSScriptRoot\common.ps1"
$s = "$($P.ascs.dir)\scripts"
try {
  Clear-Host; Title "Home server (ssh $SshHost)"
  $ok = (HomeSsh 'echo ok' 6) -join '' -eq 'ok'
  if (-not $ok) { Bad 'ssh home ไม่ตอบ — ตรวจ Tailscale/เครื่อง home เปิดอยู่ไหม'; Pause-Menu; return }
  Ok 'ssh ตอบ'
  foreach ($x in @(@('ASCS', 'aiSolar\design-auto\VERSION.json', 'ascs'), @('ASCA', 'pee_architec\VERSION.json', 'asca'), @('picode', 'git\picode\pi-system\pi_crm_erp\VERSION.json', 'crm'))) {
    $hv = try { ((HomeSsh "type $HomeRoot\$($x[1])" 6) -join '' | ConvertFrom-Json).version } catch { '-' }
    $lv = Ver $x[2]
    Log ("  {0,-8} home {1,-9} laptop {2,-9} {3}" -f $x[0], $hv, $lv, $(if ($hv -eq $lv) { '✓' } else { '≠' }))
  }
  $busy = HomeSsh 'tasklist /FI "IMAGENAME eq node.exe" /NH' 6 | Where-Object { $_ -match 'node.exe' }
  if ($busy) { Warn "home มี node ทำงานอยู่ $(@($busy).Count) ตัว (RAM 8 GB — อย่า build ซ้อน)" }
  Write-Host ''
  Write-Host '  [1] อัปเดต ASCS บน home (pull-home.ps1: git pull + build + รีสตาร์ต)'
  Write-Host '  [2] ดึง design-auto\out จาก home (ไม่ทับไฟล์ใหม่กว่า · ≈ 3.9 GB · dry-run ก่อน)'
  Write-Host '  [3] ส่ง design-auto\out ไป home'
  Write-Host '  [4] ดึง HomeGuard live copy → tools\homeguard\from-home\'
  Write-Host '  [5] ส่ง laptop-data (send-laptop-data.ps1)'
  Write-Host '  [6] GUI ซิงก์โฟลเดอร์ (sync-home-gui)'
  Write-Host '  [7] คัดลอกไฟล์เดียวจาก home → LocalAI\from-home\'
  Write-Host '  [8] Remote Control บน home (claude rc) · [9] RDP'
  Write-Host '  [0] กลับ'
  switch (Read-Host 'เลือก') {
    '1' { if ($busy -and -not (Ask 'home กำลัง build อยู่ ทำต่อ?')) { return }; Run 'pull-home.ps1' powershell @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "$s\pull-home.ps1", '-SshHost', $SshHost) $P.ascs.dir | Out-Null }
    '2' { Run 'sync-home Pull (dry-run)' powershell @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "$s\sync-home.ps1", '-Direction', 'Pull', '-DryRun') $P.ascs.dir | Out-Null
          if (Ask 'คัดลอกจริง?') { Run 'sync-home Pull' powershell @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "$s\sync-home.ps1", '-Direction', 'Pull') $P.ascs.dir | Out-Null } }
    '3' { Run 'sync-home Push (dry-run)' powershell @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "$s\sync-home.ps1", '-Direction', 'Push', '-DryRun') $P.ascs.dir | Out-Null
          if (Ask 'ส่งจริง?') { Run 'sync-home Push' powershell @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "$s\sync-home.ps1", '-Direction', 'Push') $P.ascs.dir | Out-Null } }
    '4' { $to = "$LocalAI\tools\homeguard\from-home"; New-Item -ItemType Directory -Force $to | Out-Null
          Run 'scp HomeGuard' scp @('-r', "${SshHost}:$HomeRoot\tools\homeguard\*", "$to\") | Out-Null; Ok "→ $to (ไม่ทับ F:\LocalAI\tools\homeguard ตัวพัฒนา)" }
    '5' { Run 'send-laptop-data.ps1' powershell @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "$s\send-laptop-data.ps1") $P.ascs.dir | Out-Null }
    '6' { Start-Process powershell @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "$s\sync-home-gui.ps1") }
    '7' { $r = Read-Host 'path บน home (เช่น C:\LocalAI\xxx\file.txt)'; if ($r) { $to = "$LocalAI\from-home"; New-Item -ItemType Directory -Force $to | Out-Null; Run "scp $r" scp @("${SshHost}:$r", "$to\") | Out-Null; Ok "→ $to" } }
    '8' { Start-Process cmd @('/k', "ssh -t $SshHost claude rc") }
    '9' { Start-Process mstsc @('/v:100.118.18.110') }
    default { return }
  }
} catch { Bad "หยุด: $($_.Exception.Message)" }
Pause-Menu
