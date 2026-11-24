# git-sync.ps1 — Pull / Push หลาย repo พร้อมกันในคลิกเดียว (ลุงพี · Git Sync)
#   -Mode Pull   : ดึงงานล่าสุดทุก repo พร้อมกัน (pull --rebase --autostash) · CONFLICT = ยกเลิกให้กลับสภาพเดิมแล้วแจ้ง
#   -Mode Push   : ไล่ทีละ repo ให้เลือกว่าจะ commit ไฟล์ไหน → ตรวจคีย์/รหัสลับ + ไฟล์ใหญ่ → ส่งขึ้น GitHub พร้อมกัน
#   -Mode Status : ดูสถานะทุก repo (ค้าง commit · รอ push · ตามหลัง)
# ห้ามใช้ --force ทุกกรณี · รายชื่อ repo อยู่ใน repos.txt ข้างไฟล์นี้
param([ValidateSet('Pull', 'Push', 'Status')][string]$Mode = 'Status', [string]$RepoList = '')   # -RepoList = ไฟล์รายชื่ออื่น (ไว้ทดสอบ)

try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch {}
$OutputEncoding = [Text.Encoding]::UTF8
$ErrorActionPreference = 'Continue'
$here = $PSScriptRoot
$logFile = Join-Path $here 'git-sync.log'
$ver = try { (Get-Content (Join-Path $here 'VERSION.json') -Raw -Encoding UTF8 | ConvertFrom-Json).version } catch { '?' }

function Write-Log($msg) {
  try { Add-Content -LiteralPath $logFile -Value ('{0:yyyy-MM-dd HH:mm:ss}  [{1}] {2}' -f (Get-Date), $Mode, $msg) -Encoding UTF8 } catch {}
}
function Say($msg, $color = 'Gray') { Write-Host $msg -ForegroundColor $color }
# G = เอาเฉพาะผลลัพธ์ (ทิ้งข้อความเตือน) · GA = รวมข้อความ error ด้วย (ไว้แสดงเมื่อพัง)
function G { $r = $args[0]; $a = @($args | Select-Object -Skip 1); & git -C $r -c core.quotepath=false @a 2>$null }
function GA { $r = $args[0]; $a = @($args | Select-Object -Skip 1); & git -C $r -c core.quotepath=false @a 2>&1 | ForEach-Object { "$_" } }

# ---------- หา repo จาก repos.txt (ใต้ไดรฟ์ของเครื่องนี้) ----------
$driveRoot = Split-Path -Qualifier $here        # F: บน laptop · C: บน home server
$repos = @()
foreach ($line in Get-Content -LiteralPath $(if ($RepoList) { $RepoList } else { Join-Path $here 'repos.txt' }) -Encoding UTF8) {
  $t = $line.Trim()
  if (-not $t -or $t.StartsWith('#')) { continue }
  $cands = @("$driveRoot\$t", "F:\$t", "C:\$t") | Select-Object -Unique
  $p = $cands | Where-Object { Test-Path -LiteralPath (Join-Path $_ '.git') } | Select-Object -First 1
  if ($p) { $repos += $p } else { Say "  · ข้าม $t (ไม่มีในเครื่องนี้)" DarkGray }
}
if (-not $repos) { Say 'ไม่พบ repo ใดเลย — ตรวจ repos.txt' Red; exit 1 }

Say ''
Say ("=== Git Sync {0} · {1} · {2} repo ===" -f $ver, $Mode, $repos.Count) Cyan

# ---------- ตรวจเน็ต ----------
if ($Mode -ne 'Status') {
  try { $null = [System.Net.Dns]::GetHostAddresses('github.com') }
  catch { Say 'ไม่มีอินเทอร์เน็ต (ติดต่อ github.com ไม่ได้) — ยกเลิก ยังไม่ได้แตะอะไร' Red; Write-Log 'offline'; exit 1 }
}

# งานซิงก์ 1 repo (ใช้ทั้ง Pull และขั้นตอนก่อน Push) — รันใน Job แยกจึงทำพร้อมกันได้
$syncJob = {
  param([string]$repo, [bool]$doPush)
  function G { $r = $args[0]; $a = @($args | Select-Object -Skip 1); & git -C $r -c core.quotepath=false @a 2>$null }
  function GA { $r = $args[0]; $a = @($args | Select-Object -Skip 1); & git -C $r -c core.quotepath=false @a 2>&1 | ForEach-Object { "$_" } }
  $res = [ordered]@{ Repo = $repo; Ok = $false; Msg = ''; Detail = '' }
  $branch = (G $repo branch --show-current | Out-String).Trim()
  if (-not $branch) { $res.Msg = 'ไม่ได้อยู่บน branch (detached HEAD) — ข้าม'; return [pscustomobject]$res }
  $up = (G $repo rev-parse --abbrev-ref '@{u}' | Out-String).Trim()
  if ($LASTEXITCODE -ne 0) { $res.Msg = "branch $branch ไม่มี upstream — ข้าม"; return [pscustomobject]$res }
  $before = (G $repo rev-parse HEAD | Out-String).Trim()
  $out = GA $repo pull --rebase --autostash | Out-String
  $code = $LASTEXITCODE
  $gitDir = (G $repo rev-parse --absolute-git-dir | Out-String).Trim()
  if ($code -ne 0) {
    if ((Test-Path "$gitDir\rebase-merge") -or (Test-Path "$gitDir\rebase-apply")) {
      $null = G $repo rebase --abort
      $res.Msg = 'CONFLICT — ยกเลิก rebase กลับสภาพเดิมแล้ว ต้องแก้เอง (ไม่ได้ push)'
    } else { $res.Msg = "pull ไม่สำเร็จ (exit $code)" }
    $res.Detail = $out.Trim(); return [pscustomobject]$res
  }
  if ($out -match 'autostash.*conflict|conflicts.*autostash') {
    $res.Msg = 'pull แล้ว แต่คืนงานค้าง (autostash) ชนกัน — งานค้างอยู่ใน git stash ต้องแก้เอง'
    $res.Detail = $out.Trim(); return [pscustomobject]$res
  }
  $after = (G $repo rev-parse HEAD | Out-String).Trim()
  $newCount = if ($before -ne $after) { (G $repo rev-list --count "$before..$after" | Out-String).Trim() } else { '0' }
  $pullTxt = if ($newCount -ne '0') { "ดึงมาใหม่ $newCount commit" } else { 'ล่าสุดแล้ว' }
  if (-not $doPush) { $res.Ok = $true; $res.Msg = $pullTxt; return [pscustomobject]$res }
  $ahead = (G $repo rev-list --count "$up..HEAD" | Out-String).Trim()
  if ($ahead -eq '0') { $res.Ok = $true; $res.Msg = "$pullTxt · ไม่มีอะไรต้อง push"; return [pscustomobject]$res }
  $pout = GA $repo push | Out-String        # ห้าม --force
  if ($LASTEXITCODE -ne 0) { $res.Msg = "push ไม่สำเร็จ (exit $LASTEXITCODE)"; $res.Detail = $pout.Trim(); return [pscustomobject]$res }
  $res.Ok = $true; $res.Msg = "$pullTxt · push แล้ว $ahead commit → $up"
  return [pscustomobject]$res
}

function Invoke-Parallel([string[]]$list, [bool]$doPush) {
  $jobs = foreach ($r in $list) { Start-Job -ScriptBlock $syncJob -ArgumentList $r, $doPush }
  Say ("  กำลังทำพร้อมกัน {0} repo ..." -f $jobs.Count) DarkGray
  $results = $jobs | Wait-Job -Timeout 600 | Receive-Job
  $jobs | Where-Object State -eq 'Running' | ForEach-Object { Say "  ⚠ หมดเวลา: job $($_.Id)" Yellow }
  $jobs | Remove-Job -Force
  $okN = 0
  foreach ($r in $list) {
    $x = $results | Where-Object { $_.Repo -eq $r } | Select-Object -First 1
    if (-not $x) { Say "  ✗ $r — ไม่ได้ผลกลับมา (หมดเวลา/ผิดพลาด)" Red; Write-Log "$r — no result"; continue }
    if ($x.Ok) { $okN++; Say "  ✓ $r — $($x.Msg)" Green }
    else {
      Say "  ✗ $r — $($x.Msg)" Red
      if ($x.Detail) { ($x.Detail -split "`r?`n" | Select-Object -Last 6) | ForEach-Object { Say "      $_" DarkYellow } }
    }
    Write-Log ("{0} — {1} {2}" -f $r, $(if ($x.Ok) { 'OK' } else { 'FAIL' }), $x.Msg)
  }
  Say ''
  $bad = $list.Count - $okN
  if ($bad -eq 0) { Say "สำเร็จครบ $okN repo" Green } else { Say "สำเร็จ $okN · ไม่สำเร็จ/ต้องแก้เอง $bad (ดูรายการสีแดงด้านบน)" Yellow }
  return $bad
}

# ---------- Status ----------
if ($Mode -eq 'Status') {
  foreach ($r in $repos) {
    $null = G $r fetch --quiet
    $b = (G $r branch --show-current | Out-String).Trim()
    $dirty = @(G $r status --porcelain).Count
    $ab = (G $r rev-list --left-right --count '@{u}...HEAD' | Out-String).Trim() -split '\s+'
    if ($ab.Count -ne 2) { Say ("  {0,-45} [{1}]  ไฟล์ค้าง {2} · ⚠ branch นี้ไม่มี upstream (pull/push จะข้าม)" -f $r, $b, $dirty) Yellow; continue }
    $behind = $ab[0]; $ahead = $ab[1]
    $c = if ($dirty -or $ahead -ne '0' -or $behind -ne '0') { 'Yellow' } else { 'Green' }
    Say ("  {0,-45} [{1}]  ไฟล์ค้าง {2} · รอ push {3} · ตามหลัง {4}" -f $r, $b, $dirty, $ahead, $behind) $c
  }
  exit 0
}

# ---------- Pull ----------
if ($Mode -eq 'Pull') {
  $bad = Invoke-Parallel $repos $false
  exit $bad
}

# ---------- Push ----------
# ตรวจรหัสลับ (สร้างข้อความแบบต่อกันเพื่อไม่ให้ไฟล์นี้ถูกจับเอง)
$secretRx = @('sk-[A-Za-z0-9_-]{20,}', 'AIza[0-9A-Za-z_-]{30,}', 'ghp_[A-Za-z0-9]{30,}', 'gsk_[A-Za-z0-9]{20,}',
  'hf_[A-Za-z0-9]{20,}', 'xai-[A-Za-z0-9]{20,}', ('sb_' + 'secret_'), ('service' + '_role'),
  'eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{10,}') -join '|'
$badNameRx = '(^|/)(\.env(\..*)?|config\.ini|credentials\.json|settings\.local\.json)$|\.(key|pem|pfx|p12)$'

$toSync = @()
foreach ($r in $repos) {
  Say ''
  Say "── $r" Cyan
  $b = (G $r branch --show-current | Out-String).Trim()
  if (-not $b) { Say '   detached HEAD — ข้าม' Yellow; continue }
  $null = G $r fetch --quiet
  $tracked = @(G $r status --porcelain --untracked-files=no | Where-Object { $_ })
  $untracked = @(G $r ls-files --others --exclude-standard | Where-Object { $_ })
  $ahead = (G $r rev-list --count '@{u}..HEAD' | Out-String).Trim()
  if ($LASTEXITCODE -ne 0) { $ahead = '0' }
  if (-not $tracked -and -not $untracked -and $ahead -eq '0') { Say '   ไม่มีอะไรเปลี่ยน — ข้าม' DarkGray; continue }

  if ($tracked) { Say "   ไฟล์ที่แก้ ($($tracked.Count)):" White; $tracked | Select-Object -First 20 | ForEach-Object { Say "     $_" } ; if ($tracked.Count -gt 20) { Say "     ... อีก $($tracked.Count - 20) ไฟล์" DarkGray } }
  if ($untracked) { Say "   ไฟล์ใหม่ยังไม่เคยขึ้น git ($($untracked.Count)):" White; $untracked | Select-Object -First 10 | ForEach-Object { Say "     ?? $_" DarkGray }; if ($untracked.Count -gt 10) { Say "     ... อีก $($untracked.Count - 10) ไฟล์" DarkGray } }
  if ($ahead -ne '0') { Say "   มี commit รอ push อยู่แล้ว $ahead" White }

  $opts = @()
  if ($tracked) { $opts += '[Y] commit ไฟล์ที่แก้' }
  if ($untracked) { $opts += '[A] commit ไฟล์ที่แก้ + ไฟล์ใหม่ทั้งหมด' }
  if ($ahead -ne '0' -and -not $tracked -and -not $untracked) { $opts += '[P] push อย่างเดียว' }
  elseif ($ahead -ne '0') { $opts += '[P] push เฉพาะ commit เดิม (ไม่ commit เพิ่ม)' }
  $opts += '[N] ข้าม'
  if ($untracked.Count -gt 30) { Say "   ⚠ ไฟล์ใหม่เยอะ ($($untracked.Count)) — ตรวจก่อนเลือก A อาจมีไฟล์ที่ไม่ควรขึ้น git" Yellow }
  $ans = (Read-Host ("   เลือก " + ($opts -join ' · '))).Trim().ToUpper()

  if ($ans -eq 'P' -and $ahead -ne '0') { $toSync += $r; continue }
  if ($ans -ne 'Y' -and $ans -ne 'A') { Say '   ข้าม' DarkGray; continue }
  if ($ans -eq 'Y' -and -not $tracked) { Say '   ไม่มีไฟล์ที่แก้ — ข้าม' DarkGray; continue }
  if ($ans -eq 'A' -and -not $untracked -and -not $tracked) { continue }

  # ถ้ามีของ stage ไว้ก่อนแล้ว ให้คงไว้ แล้วเพิ่มตามที่เลือก
  if ($ans -eq 'A') { $null = G $r add -A } else { $null = G $r add -u }

  $staged = @(G $r diff --cached --name-only | Where-Object { $_ })
  if (-not $staged) { Say '   ไม่มีไฟล์ถูกเลือก — ข้าม' DarkGray; continue }

  # ด่านกันพลาด 1: ชื่อไฟล์อันตราย
  $badNames = $staged | Where-Object { $_ -match $badNameRx }
  # ด่าน 2: รหัสลับในบรรทัดที่เพิ่ม
  $added = G $r diff --cached -U0 --no-color | Where-Object { $_ -like '+*' -and $_ -notlike '+++*' }
  $hits = @($added | Where-Object { $_ -match $secretRx })
  # ด่าน 3: ไฟล์ใหญ่เกิน 95 MB (GitHub รับไม่เกิน 100 MB)
  $big = @(G $r diff --cached --name-only --diff-filter=AM | Where-Object { $_ } | Where-Object {
      $f = Join-Path $r $_; (Test-Path -LiteralPath $f) -and ((Get-Item -LiteralPath $f).Length -gt 95MB) })
  if ($badNames -or $hits -or $big) {
    $null = G $r reset --quiet
    Say '   ⛔ หยุด repo นี้ — ไม่ commit (เอาไฟล์ออกจาก stage แล้ว ไฟล์ยังอยู่ครบ)' Red
    $badNames | ForEach-Object { Say "      ไฟล์ลับ: $_" Red }
    $hits | Select-Object -First 5 | ForEach-Object {
      $m = [regex]::Match($_, $secretRx).Value   # โชว์แค่ต้นคีย์ ไม่โชว์ทั้งตัว
      Say ("      เจอคล้ายคีย์: " + $m.Substring(0, [Math]::Min(8, $m.Length)) + '…') Red }
    $big | ForEach-Object { Say "      ไฟล์ใหญ่เกิน 95 MB: $_" Red }
    Write-Log "$r — BLOCKED (secret/bigfile)"
    continue
  }

  Say "   จะ commit ($($staged.Count) ไฟล์):" White
  G $r diff --cached --stat | Select-Object -Last 15 | ForEach-Object { Say "     $_" }
  $defMsg = 'อัปเดตไฟล์ {0:yyyy-MM-dd HH:mm} โดย ลุงพี' -f (Get-Date)
  $msg = Read-Host "   ข้อความ commit (Enter = '$defMsg' · พิมพ์ X = ยกเลิก)"
  if ($msg.Trim().ToUpper() -eq 'X') { $null = G $r reset --quiet; Say '   ยกเลิก (เอาออกจาก stage แล้ว)' DarkGray; continue }
  if (-not $msg.Trim()) { $msg = $defMsg }
  $cout = GA $r commit -m $msg | Out-String
  if ($LASTEXITCODE -ne 0) { Say "   ✗ commit ไม่สำเร็จ" Red; Say $cout DarkYellow; Write-Log "$r — commit FAIL"; continue }
  Say "   ✓ commit แล้ว: $((G $r log --oneline -1 | Out-String).Trim())" Green
  Write-Log "$r — commit: $msg"
  $toSync += $r
}

Say ''
if (-not $toSync) { Say 'ไม่มี repo ที่ต้อง push' Yellow; exit 0 }
Say "=== ส่งขึ้น GitHub พร้อมกัน $($toSync.Count) repo (pull --rebase ก่อน แล้ว push · ไม่ใช้ --force) ===" Cyan
$bad = Invoke-Parallel $toSync $true
exit $bad
