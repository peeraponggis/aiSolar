# common.ps1 — ฟังก์ชันร่วมของชุด bat: log · ถามยืนยัน · รันคำสั่ง · เปิดลิงก์ · เวอร์ชัน · git
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\config.ps1"
New-Item -ItemType Directory -Force $LogDir | Out-Null
$script:LogFile = Join-Path $LogDir ("{0}.txt" -f (Get-Date).ToString('yyyy-MM-dd'))
$script:ThaiDate = { $d = Get-Date; "{0} {1} {2} {3}" -f $d.Day, ('ม.ค.','ก.พ.','มี.ค.','เม.ย.','พ.ค.','มิ.ย.','ก.ค.','ส.ค.','ก.ย.','ต.ค.','พ.ย.','ธ.ค.')[$d.Month-1], ($d.Year+543), $d.ToString('HH:mm') }

function Log([string]$m, [string]$color = 'Gray') {
  Write-Host $m -ForegroundColor $color
  Add-Content -LiteralPath $LogFile -Value ("[{0}] {1}" -f (Get-Date).ToString('HH:mm:ss'), $m) -Encoding UTF8
}
function Ok([string]$m)   { Log "  ✓ $m" Green }
function Warn([string]$m) { Log "  ⚠ $m" Yellow }
function Bad([string]$m)  { Log "  ✗ $m" Red }
function Title([string]$m) { Write-Host ''; Log "══ $m ══" Cyan }
function Pause-Menu { Write-Host ''; Read-Host 'กด Enter กลับเมนู' | Out-Null }

# ถามยืนยัน — ค่าเริ่ม = ไม่ (ปลอดภัยไว้ก่อน)
function Ask([string]$q) {
  $a = Read-Host "$q [y/N]"
  $yes = $a -match '^(y|yes|ใช่)$'
  Log ("ถาม: {0} → {1}" -f $q, ($(if ($yes) { 'y' } else { 'N' })))
  return $yes
}
# รันคำสั่งภายนอก · ไม่ผ่าน = throw (หยุดทั้งขั้น) · แสดง 20 บรรทัดท้ายเมื่อพลาด
function Run([string]$label, [string]$exe, [string[]]$args, [string]$cwd = $null) {
  Log "> $label" DarkCyan
  Add-Content -LiteralPath $LogFile -Value ("    {0} {1}" -f $exe, ($args -join ' ')) -Encoding UTF8
  $out = New-Object System.Collections.Generic.List[string]
  Push-Location ($(if ($cwd) { $cwd } else { Get-Location }))
  try {
    & $exe @args 2>&1 | ForEach-Object { $s = "$_"; $out.Add($s); Add-Content -LiteralPath $LogFile -Value "    $s" -Encoding UTF8 }
    $code = $LASTEXITCODE
  } finally { Pop-Location }
  if ($code -ne 0) {
    Bad "$label ไม่ผ่าน (exit $code) — 20 บรรทัดท้าย:"
    $out | Select-Object -Last 20 | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkGray }
    throw "$label ไม่ผ่าน"
  }
  Ok $label
  return $out
}
function Open-Url([string]$u) { Log "เปิด $u"; Start-Process $u }
function Copy-Clip([string]$path) { Get-Content -LiteralPath $path -Raw -Encoding UTF8 | Set-Clipboard }

function Ver([string]$key) {
  $p = $P[$key]; $f = Join-Path $p.dir $p.ver
  if (-not (Test-Path -LiteralPath $f)) { return '?' }
  try { (Get-Content -LiteralPath $f -Raw -Encoding UTF8 | ConvertFrom-Json).version } catch { '?' }
}
function GitDir([string]$key) { $p = $P[$key]; if ($p.git) { $p.git } else { $p.dir } }
# สถานะ git สั้น ๆ: ค้าง n ไฟล์ · ตามหลัง/นำหน้า origin
function GitState([string]$key) {
  $d = GitDir $key
  if (-not (Test-Path -LiteralPath "$d\.git")) { return 'ไม่ใช่ git' }
  $dirty = @(git -C $d status --porcelain --untracked-files=no 2>$null).Count
  git -C $d fetch -q 2>$null
  $ab = git -C $d rev-list --left-right --count 'HEAD...@{u}' 2>$null
  $s = @(); if ($dirty) { $s += "ค้าง $dirty" }
  if ($ab) { $a, $b = $ab -split '\s+'; if ([int]$a) { $s += "ยังไม่ push $a" }; if ([int]$b) { $s += "ตามหลัง origin $b" } }
  if (-not $s) { '✓ ตรง origin' } else { $s -join ' · ' }
}
# เริ่มงานทุก repo: pull --rebase --autostash · CONFLICT = หยุด
function GitPull([string]$key) {
  $d = GitDir $key
  $o = git -C $d pull --rebase --autostash 2>&1 | Out-String
  Add-Content -LiteralPath $LogFile -Value $o -Encoding UTF8
  if ($o -match 'CONFLICT') { Bad "git pull ชน (CONFLICT) ใน $d — หยุด ให้แก้ด้วยมือ/Claude ก่อน"; throw 'CONFLICT' }
  Ok "git pull $($P[$key].name)"
}
# สแกนคีย์ลับในไฟล์ที่ staged (repo public) — พบ = throw
function ScanSecrets([string]$dir, [string[]]$extraLiteral = @()) {
  $files = git -C $dir diff --cached --name-only | Where-Object { $_ -notmatch '\.(bin|png|jpg|webp|woff2?|ico|pdf|mp4)$' }
  $re = 'sk-[A-Za-z0-9]{20}|AIza[0-9A-Za-z_-]{30}|ghp_[A-Za-z0-9]{30}|gsk_[A-Za-z0-9]{20}|hf_[A-Za-z0-9]{20}|xai-[A-Za-z0-9]{20}|sb_secret_|service_role|eyJ[A-Za-z0-9_-]{30,}\.[A-Za-z0-9_-]{30,}'
  $hit = @()
  foreach ($f in $files) {
    $full = Join-Path $dir $f; if (-not (Test-Path -LiteralPath $full)) { continue }
    $c = Get-Content -LiteralPath $full -Raw -ErrorAction SilentlyContinue
    if ($c -match $re) { $hit += $f; continue }
    foreach ($lit in $extraLiteral) { if ($lit -and $c.Contains($lit)) { $hit += "$f (กุญแจ)"; break } }
  }
  if ($hit) { Bad "พบคีย์ลับใน: $($hit -join ', ') — ไม่ push"; throw 'secret' }
  Ok "สแกนคีย์ลับ $($files.Count) ไฟล์ ไม่พบ"
}
# commit + push หลังถาม · แสดงรายการไฟล์ก่อน
function CommitPush([string]$key, [string]$msg, [string[]]$paths) {
  $d = GitDir $key
  git -C $d add -- @paths 2>&1 | Out-Null
  $stat = git -C $d diff --cached --stat | Out-String
  if (-not $stat.Trim()) { Warn "$($P[$key].name): ไม่มีอะไรเปลี่ยน"; return $false }
  Write-Host $stat -ForegroundColor DarkGray
  if ($P[$key].url) { Warn "push แล้วเว็บจริงเปลี่ยนทันที ($($P[$key].url))" }
  if (-not (Ask "commit + push $($P[$key].name): `"$msg`" ?")) { git -C $d reset -q; Warn 'ยกเลิก (unstage แล้ว)'; return $false }
  $full = "$msg`n`nCo-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
  git -C $d commit -q -m $full; if ($LASTEXITCODE) { throw 'commit ไม่ผ่าน' }
  $o = git -C $d push 2>&1 | Out-String; Add-Content -LiteralPath $LogFile -Value $o -Encoding UTF8
  if ($LASTEXITCODE) { Bad "push ไม่ผ่าน: $o"; throw 'push' }
  Ok ("push {0} {1}" -f $P[$key].name, (git -C $d log --oneline -1))
  return $true
}
function Http([string]$u) { try { (Invoke-WebRequest -Uri $u -UseBasicParsing -TimeoutSec 20).StatusCode } catch { 0 } }
function HomeSsh([string]$cmd, [int]$timeout = 15) { $ErrorActionPreference = 'Continue'; ssh.exe -o ConnectTimeout=$timeout -o BatchMode=yes $SshHost $cmd 2>&1 | ForEach-Object { "$_" } }
function Tool([string]$exe) { [bool](Get-Command $exe -ErrorAction SilentlyContinue) }
