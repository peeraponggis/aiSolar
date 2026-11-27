# dashboard-status.ps1 — คำนวณสถานะให้หน้าเว็บ (รันใน runspace เบื้องหลังของ dashboard.ps1)
. "$PSScriptRoot\common.ps1"
$script:cache = $null; $script:cacheAt = [datetime]::MinValue; $script:homeCache = $null; $script:homeAt = [datetime]::MinValue

function HomeInfo {
  if (((Get-Date) - $script:homeAt).TotalSeconds -lt 120 -and $script:homeCache) { return $script:homeCache }
  $r = @{ ok = $false }
  # ssh ครั้งเดียว อ่าน 3 ไฟล์ (คั่นด้วย ###) — เร็วกว่าเรียก 4 รอบ
  $keys = @('ascs', 'asca', 'crm', 'hg'); $files = @('aiSolar\design-auto\VERSION.json', 'pee_architec\VERSION.json', 'git\picode\pi-system\pi_crm_erp\VERSION.json', 'tools\homeguard\VERSION.json')
  $cmd = 'echo ok & ' + (($files | ForEach-Object { "echo ### & type $HomeRoot\$_" }) -join ' & ')
  $out = (HomeSsh $cmd 6) -join "`n"
  if ($out -match '^ok') {
    $r.ok = $true
    $parts = ($out -split '###') | Select-Object -Skip 1
    for ($i = 0; $i -lt $keys.Count; $i++) { $r[$keys[$i]] = try { ($parts[$i] | ConvertFrom-Json).version } catch { '-' } }
  }
  $script:homeCache = $r; $script:homeAt = Get-Date; $r
}
function SqlList {
  $done = "$LogDir\sql-done.json"
  $db = if (Test-Path -LiteralPath $done) { Get-Content -LiteralPath $done -Raw -Encoding UTF8 | ConvertFrom-Json } else { [pscustomobject]@{} }
  foreach ($e in $SqlEach) {
    $st = 'ไม่มีไฟล์'; $pend = $false
    if (Test-Path -LiteralPath $e.f) {
      $h = (Get-FileHash -LiteralPath $e.f -Algorithm SHA256).Hash.Substring(0, 16); $r = $db.PSObject.Properties[$e.f]
      if ($r -and $r.Value.hash -eq $h) { $st = "รันแล้ว $($r.Value.when)" } elseif ($r) { $st = 'ไฟล์เปลี่ยน — ยังไม่รัน'; $pend = $true } else { $st = 'ยังไม่เคยรัน'; $pend = $true }
    }
    @{ project = $Supa[$e.p].name; url = $Supa[$e.p].url; file = $e.f; note = $e.note; secret = [bool]$e.secret; status = $st; pending = $pend }
  }
}
function Status {
  if (((Get-Date) - $script:cacheAt).TotalSeconds -lt 45 -and $script:cache) { return $script:cache }
  $h = HomeInfo
  $progs = foreach ($k in 'ascs', 'asca', 'asc', 'crm', 'tr', 'hg') {
    $gs = GitState $k
    # ไฟล์ค้างที่ "ไม่ commit ตามกฎ" (out\usermanual\_pdfs.json · sync-home-gui.ps1) ไม่นับเป็นงานค้าง
    if ($k -eq 'ascs' -and $gs -match 'ค้าง') { $real = @(git -C $P[$k].dir status --porcelain --untracked-files=no | Where-Object { $_ -notmatch '_pdfs\.json|sync-home-gui\.ps1' }).Count; $gs = ($gs -replace 'ค้าง \d+', $(if ($real) { "ค้าง $real" } else { '' })).Trim(' ·'); if (-not $gs) { $gs = '✓ ตรง origin' } }
    @{ key = $k; name = $P[$k].name; dir = $P[$k].dir; ver = (Ver $k); git = $gs; dirty = ($gs -ne '✓ ตรง origin'); home = $h[$k]; url = $P[$k].url }
  }
  $exe = Get-ChildItem "$($P.ascs.dir)\out\setup\ASC-Studio-Setup-*.exe" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime | Select-Object -Last 1
  $asca = Get-ChildItem "$LocalAI\apps\ASCA-release\*\ASCA-Setup-*.exe" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime | Select-Object -Last 1
  $hg = Get-Item "$($P.hg.dir)\dist\HomeGuard-Setup.exe" -ErrorAction SilentlyContinue
  $rel = try { (Get-Content "$($P.asc.dir)\docs\ascs-release\latest.json" -Raw -Encoding UTF8 | ConvertFrom-Json).version } catch { '-' }
  $live = try { (Invoke-RestMethod "$($P.asc.url)/ascs-release/latest.json?t=$(Get-Random)" -TimeoutSec 8).version } catch { '-' }
  $sql = @(SqlList)
  $missing = @($Needs | Where-Object { -not (Test-Path -LiteralPath $_) })
  $log = if (Test-Path -LiteralPath $LogFile) { @(Get-Content -LiteralPath $LogFile -Encoding UTF8 -Tail 12) } else { @() }
  $script:cache = @{ at = (& $ThaiDate); here = $Here; programs = @($progs); homeOk = $h.ok
    installers = @(Sync-Installers | ForEach-Object { @{ kind = $_.kind; src = $_.src; dst = $_.dst; mb = $_.mb; when = $_.when } })
    installer = @{ ascs = $(if ($exe) { @{ name = $exe.Name; when = $exe.LastWriteTime.ToString('d/M HH:mm'); mb = [math]::Round($exe.Length / 1MB, 1) } }); asca = $(if ($asca) { @{ name = $asca.Name; when = $asca.LastWriteTime.ToString('d/M HH:mm') } }); hg = $(if ($hg) { @{ name = "HomeGuard-Setup.exe ($(Ver 'hg'))"; when = $hg.LastWriteTime.ToString('d/M HH:mm') } }); release = $rel; live = $live }
    order = @($InstallOrder | ForEach-Object { @{ n = $_.n; name = $_.name; what = $_.what } })
    sql = $sql; sqlPending = @($sql | Where-Object { $_.pending }).Count; missing = $missing; log = $log
    keys = @{ ascs = (Test-Path -LiteralPath $KeyASCS); asca = (Test-Path -LiteralPath $KeyASCA) } }
  $script:cacheAt = Get-Date; $script:cache
}
