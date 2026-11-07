# dashboard.ps1 — หน้าเว็บในเครื่อง "ASC ปล่อยรุ่น" (ลุงพีสั่ง 7 พ.ย. 2569)
#   เซิร์ฟเวอร์เล็กบน http://127.0.0.1:8770 เสิร์ฟ dashboard.html + สถานะจริง (รุ่น · git · home · SQL ค้าง · ชุดติดตั้ง)
#   ปุ่มบนหน้าเว็บ → POST /run?n=menu|01..08 → เปิด .bat ในหน้าต่างใหม่ (เบราว์เซอร์เปิด bat เองไม่ได้ จึงต้องมีตัวนี้)
#   ปิด: ปิดหน้าต่างนี้ หรือกด "ปิดเซิร์ฟเวอร์" บนหน้าเว็บ
. "$PSScriptRoot\common.ps1"
$port = 8770; $html = "$PSScriptRoot\dashboard.html"
$script:cache = $null; $script:cacheAt = [datetime]::MinValue; $script:homeCache = $null; $script:homeAt = [datetime]::MinValue

function HomeInfo {
  if (((Get-Date) - $script:homeAt).TotalSeconds -lt 120 -and $script:homeCache) { return $script:homeCache }
  $r = @{ ok = $false }
  # ssh ครั้งเดียว อ่าน 3 ไฟล์ (คั่นด้วย ###) — เร็วกว่าเรียก 4 รอบ
  $keys = @('ascs', 'asca', 'crm'); $files = @('aiSolar\design-auto\VERSION.json', 'pee_architec\VERSION.json', 'git\picode\pi-system\pi_crm_erp\VERSION.json')
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
  $progs = foreach ($k in 'ascs', 'asca', 'asc', 'crm', 'tr') {
    $gs = GitState $k
    # ไฟล์ค้างที่ "ไม่ commit ตามกฎ" (out\usermanual\_pdfs.json · sync-home-gui.ps1) ไม่นับเป็นงานค้าง
    if ($k -eq 'ascs' -and $gs -match 'ค้าง') { $real = @(git -C $P[$k].dir status --porcelain --untracked-files=no | Where-Object { $_ -notmatch '_pdfs\.json|sync-home-gui\.ps1' }).Count; $gs = ($gs -replace 'ค้าง \d+', $(if ($real) { "ค้าง $real" } else { '' })).Trim(' ·'); if (-not $gs) { $gs = '✓ ตรง origin' } }
    @{ key = $k; name = $P[$k].name; dir = $P[$k].dir; ver = (Ver $k); git = $gs; dirty = ($gs -ne '✓ ตรง origin'); home = $h[$k]; url = $P[$k].url }
  }
  $exe = Get-ChildItem "$($P.ascs.dir)\out\setup\ASC-Studio-Setup-*.exe" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime | Select-Object -Last 1
  $asca = Get-ChildItem "$LocalAI\apps\ASCA-release\*\ASCA-Setup-*.exe" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime | Select-Object -Last 1
  $rel = try { (Get-Content "$($P.asc.dir)\docs\ascs-release\latest.json" -Raw -Encoding UTF8 | ConvertFrom-Json).version } catch { '-' }
  $live = try { (Invoke-RestMethod "$($P.asc.url)/ascs-release/latest.json?t=$(Get-Random)" -TimeoutSec 8).version } catch { '-' }
  $sql = @(SqlList)
  $missing = @($Needs | Where-Object { -not (Test-Path -LiteralPath $_) })
  $log = if (Test-Path -LiteralPath $LogFile) { @(Get-Content -LiteralPath $LogFile -Encoding UTF8 -Tail 12) } else { @() }
  $script:cache = @{ at = (& $ThaiDate); here = $Here; programs = @($progs); homeOk = $h.ok
    installer = @{ ascs = $(if ($exe) { @{ name = $exe.Name; when = $exe.LastWriteTime.ToString('d/M HH:mm'); mb = [math]::Round($exe.Length / 1MB, 1) } }); asca = $(if ($asca) { @{ name = $asca.Name; when = $asca.LastWriteTime.ToString('d/M HH:mm') } }); release = $rel; live = $live }
    sql = $sql; sqlPending = @($sql | Where-Object { $_.pending }).Count; missing = $missing; log = $log
    keys = @{ ascs = (Test-Path -LiteralPath $KeyASCS); asca = (Test-Path -LiteralPath $KeyASCA) } }
  $script:cacheAt = Get-Date; $script:cache
}
$bats = @{ menu = 'ASC-Menu.bat'; '01' = '01-ascs-release.bat'; '02' = '02-asca-release.bat'; '03' = '03-cloud-deploy.bat'; '04' = '04-crm-deploy.bat'; '05' = '05-translator-build.bat'; '06' = '06-sql-todo.bat'; '07' = '07-home.bat'; '08' = '08-new-pc.bat' }

$l = [System.Net.HttpListener]::new(); $l.Prefixes.Add("http://127.0.0.1:$port/")
try { $l.Start() } catch { Write-Host "เปิดพอร์ต $port ไม่ได้ (อาจเปิดอยู่แล้ว) — เปิดหน้าเว็บแทน"; Start-Process "http://127.0.0.1:$port/"; exit 0 }
Log "dashboard: http://127.0.0.1:$port/"
Write-Host 'กำลังอ่านสถานะครั้งแรก (git · ssh home · เว็บ) ~15 วินาที…' -ForegroundColor DarkGray
Status | Out-Null
Start-Process "http://127.0.0.1:$port/"
Write-Host "ASC ปล่อยรุ่น — หน้าเว็บเปิดที่ http://127.0.0.1:$port/  (ปิดหน้าต่างนี้ = ปิดเซิร์ฟเวอร์)" -ForegroundColor Cyan
function Send($ctx, [string]$body, [string]$type = 'application/json; charset=utf-8', [int]$code = 200) {
  $b = [Text.Encoding]::UTF8.GetBytes($body); $ctx.Response.StatusCode = $code; $ctx.Response.ContentType = $type; $ctx.Response.ContentLength64 = $b.Length
  $ctx.Response.OutputStream.Write($b, 0, $b.Length); $ctx.Response.Close()
}
while ($l.IsListening) {
  $ctx = $l.GetContext(); $u = $ctx.Request.Url
  try {
    switch -Regex ($u.AbsolutePath) {
      '^/$'            { Send $ctx (Get-Content -LiteralPath $html -Raw -Encoding UTF8) 'text/html; charset=utf-8' }
      '^/api/status$'  { Send $ctx ((Status) | ConvertTo-Json -Depth 6 -Compress) }
      '^/api/refresh$' { $script:cacheAt = [datetime]::MinValue; $script:homeAt = [datetime]::MinValue; Send $ctx ((Status) | ConvertTo-Json -Depth 6 -Compress) }
      '^/run$' {
        $n = [System.Web.HttpUtility]::ParseQueryString($u.Query)['n']
        if ($ctx.Request.HttpMethod -eq 'POST' -and $bats[$n]) {
          Log "dashboard: เปิด $($bats[$n])"
          Start-Process cmd.exe -ArgumentList '/c', "start `"ASC $n`" cmd /c `"$Here\$($bats[$n])`"" -WorkingDirectory $Here
          Send $ctx '{"ok":true}'
        } else { Send $ctx '{"ok":false}' 'application/json' 400 }
      }
      '^/open$' {
        $p = [System.Web.HttpUtility]::ParseQueryString($u.Query)['p']
        if ($ctx.Request.HttpMethod -eq 'POST' -and $p -and ($p -like "$LocalAI*" -or $p -like "$Ent*" -or $p -like 'https://*')) { Start-Process $p; Send $ctx '{"ok":true}' } else { Send $ctx '{"ok":false}' 'application/json' 400 }
      }
      '^/quit$' { Send $ctx '{"ok":true}'; $l.Stop(); break }
      default { Send $ctx 'not found' 'text/plain' 404 }
    }
  } catch { try { Send $ctx ('{"error":' + ($_.Exception.Message | ConvertTo-Json) + '}') 'application/json' 500 } catch {} }
}
