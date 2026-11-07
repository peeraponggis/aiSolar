# 01-ascs.ps1 — ASC Studio ปล่อยรุ่น (bat ไม่ bump เวอร์ชัน — Claude bump ตามกฎก่อนเรียก)
param([switch]$All)
. "$PSScriptRoot\common.ps1"
$d = $P.ascs.dir; $asc = $P.asc.dir
$hdr = @"
/* ============================================================================
 *  Auto Solar Co-pilot Studio (ASC Studio / ASCS)
 *  Copyright (C) 2024-2569 ProInventive. All rights reserved.
 *
 *  PROPRIETARY AND CONFIDENTIAL
 *  This software is the exclusive property of ProInventive.
 *  Unauthorized copying, modification, distribution, reverse engineering,
 *  decompilation or disassembly of this file, in whole or in part, is strictly
 *  prohibited without prior written permission from ProInventive.
 * ============================================================================ */

"@
function Step-Build {
  Title 'build: kb:build → typecheck → test → build'
  Run 'npm run kb:build' npm.cmd @('run', 'kb:build') $d | Out-Null
  Run 'npm run typecheck' npm.cmd @('run', 'typecheck') $d | Out-Null
  $o = Run 'npm test' npm.cmd @('test', '--', '--run') $d
  ($o | Where-Object { $_ -match 'Tests\s' }) | Select-Object -Last 1 | ForEach-Object { Ok ($_ -replace '\x1b\[[0-9;]*m', '').Trim() }
  Run 'npm run build' npm.cmd @('run', 'build') $d | Out-Null
}
function Step-Setup {
  Title 'ชุดติดตั้ง + ชุดอัปเดต (installer\build-setup.ps1)'
  if (-not (Test-Path -LiteralPath $KeyASCS)) { Warn "ยังไม่มีกุญแจ $KeyASCS — build-setup จะสร้างใหม่ (เครื่องที่ติดตั้งแล้วจะอัปเดตไม่ได้ถ้ากุญแจเปลี่ยน)"; if (-not (Ask 'สร้างกุญแจใหม่?')) { throw 'ยกเลิก' } }
  $o = Run 'build-setup.ps1' powershell @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "$d\installer\build-setup.ps1") $d
  $o | Where-Object { $_ -match 'สร้างแล้ว|ชุดอัปเดต' } | ForEach-Object { Ok $_ }
}
function Step-Web {
  Title 'เว็บ: build-cloud → asc\docs\studio + หัวลิขสิทธิ์ + kb:sql'
  Run 'build-cloud.mjs --to' node @("$d\scripts\build-cloud.mjs", '--to', "$asc\docs\studio") $d | Out-Null
  $n = 0
  foreach ($f in Get-ChildItem "$asc\docs\studio\assets\*.js") { $s = Get-Content -LiteralPath $f.FullName -Raw -Encoding UTF8; if (-not $s.StartsWith('/* ====')) { [IO.File]::WriteAllText($f.FullName, $hdr + $s, [Text.UTF8Encoding]::new($false)); $n++ } }
  Ok "หัวลิขสิทธิ์ $n ไฟล์"
  Run 'npm run kb:sql' npm.cmd @('run', 'kb:sql') $d | Out-Null
  Ok "out\cloud\kb-data.sql (รันใน Supabase → เมนู [6])"
}
function Step-Push {
  Title 'commit + push → รอ deploy → ตรวจเว็บจริง'
  $v = Ver 'ascs'
  $note = ((Get-Content -LiteralPath "$d\CHANGELOG.md" -Encoding UTF8 | Where-Object { $_ -match '^\s*[-*] ' } | Select-Object -First 1) -replace '^\s*[-*]\s*', '')
  $files = @('VERSION.json', 'CHANGELOG.md', 'src', 'server', 'tests', 'docs/knowledge', 'public/kb', 'installer', 'scripts', 'vite.config.ts', 'package.json', 'package-lock.json', 'index.html', 'report.html', 'sim-lab.html', '.gitignore')
  $files = $files | Where-Object { Test-Path -LiteralPath (Join-Path $d $_) }
  Warn 'ไม่รวม: out\ · server\data · scripts\sync-home-gui.ps1 (ตามกฎ)'
  git -C $d add -- @files; git -C $d reset -q -- scripts/sync-home-gui.ps1 2>$null
  ScanSecrets $d @((Get-Content -LiteralPath $KeyASCS -Raw -ErrorAction SilentlyContinue))
  CommitPush 'ascs' "ASC Studio ${v}: $note โดย ลุงพี" @() | Out-Null
  git -C $asc add -- docs/studio docs/ascs-release
  ScanSecrets $asc @((Get-Content -LiteralPath $KeyASCS -Raw -ErrorAction SilentlyContinue))
  if (CommitPush 'asc' "ASC Studio $v (studio + ชุดอัปเดต)" @()) {
    Log 'รอ GitHub Pages (gh run watch)…'
    Start-Sleep 8; $id = gh run list -R $P.asc.repo -L 1 --json databaseId -q '.[0].databaseId'
    if ($id) { gh run watch $id -R $P.asc.repo --exit-status | Out-Null; if ($LASTEXITCODE) { Bad 'deploy ไม่ผ่าน' } else { Ok 'deploy เสร็จ' } }
    $u = $P.asc.url
    $main = (Invoke-WebRequest "$u/studio/index.html" -UseBasicParsing).Content -replace '[\s\S]*?(assets/main-[^"]+\.js)[\s\S]*', '$1'
    $live = ((Invoke-WebRequest "$u/studio/$main" -UseBasicParsing).Content -match [regex]::Escape("`"$v`""))
    if ($live) { Ok "เว็บจริง studio = $v" } else { Bad "เว็บจริงยังไม่ใช่ $v (แคช? รอ 1-2 นาทีแล้วลองใหม่)" }
    $lj = (Invoke-RestMethod "$u/ascs-release/latest.json?t=$(Get-Date -UFormat %s)").version
    if ($lj -eq $v) { Ok "latest.json = $v" } else { Bad "latest.json = $lj" }
    Ok "ascs-app bin HTTP $(Http "$u/ascs-release/ascs-app-$v.bin") · sim-lab.html HTTP $(Http "$u/studio/sim-lab.html")"
  }
}
function Step-Programs {
  Title 'PROGRAMS.md + push aiSolar'
  $v = Ver 'ascs'; GitPull 'tr'
  $c = Get-Content -LiteralPath $Programs -Encoding UTF8
  $i = ($c | Select-String -SimpleMatch 'Design Auto (Auto Solar Co-pilot Studio)' | Select-Object -First 1).LineNumber
  if (-not $i) { Warn 'ไม่พบบรรทัด ASC Studio ใน PROGRAMS.md'; return }
  $c[$i - 1] = [regex]::new('\|\s*[\d.]+\s*\|').Replace($c[$i - 1], "| $v |", 1)
  [IO.File]::WriteAllLines($Programs, $c, [Text.UTF8Encoding]::new($false))
  CommitPush 'tr' "PROGRAMS: ASC Studio $v" @('PROGRAMS.md') | Out-Null
}
try {
  Clear-Host; Title "ASC Studio $(Ver 'ascs')  ($d)"
  Log "git asc_auto: $(GitState 'ascs') · git asc: $(GitState 'asc')"
  $dirty = git -C $d status --porcelain --untracked-files=no | Out-String
  if ($dirty) { Warn "ไฟล์ค้าง:`n$dirty" }
  $exe = Get-ChildItem "$d\out\setup\ASC-Studio-Setup-*.exe" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime | Select-Object -Last 1
  if ($exe) { Log "ชุดติดตั้งล่าสุด: $($exe.Name) ($($exe.LastWriteTime.ToString('d MMM HH:mm')))" }
  Write-Host ''
  Write-Host '  [1] ทำครบทุกขั้น (2→3→4→5→6 — หยุดถามก่อน push)'
  Write-Host '  [2] build: kb:build → typecheck → test → build'
  Write-Host '  [3] ชุดติดตั้ง + ชุดอัปเดต'
  Write-Host '  [4] เว็บ: build-cloud + หัวลิขสิทธิ์ + kb:sql'
  Write-Host '  [5] commit + push (asc_auto · asc) → รอ deploy → ตรวจเว็บจริง'
  Write-Host '  [6] อัปเดต PROGRAMS.md + push aiSolar'
  Write-Host '  [0] กลับ'
  $c = if ($All) { '1' } else { Read-Host 'เลือก' }
  switch ($c) {
    '1' { GitPull 'ascs'; GitPull 'asc'; Step-Build; Step-Setup; Step-Web; Step-Push; Step-Programs; Title 'เสร็จ — ต่อไป: เมนู [6] SQL ที่ต้องรัน' }
    '2' { Step-Build } '3' { Step-Setup } '4' { Step-Web } '5' { GitPull 'asc'; Step-Push } '6' { Step-Programs }
    default { return }
  }
} catch { Bad "หยุด: $($_.Exception.Message)" }
Pause-Menu
