# 06-sql.ps1 — SQL ที่ต้องรันใน Supabase: แสดงลิงก์ SQL Editor ทุกครั้ง · คัดลอกไฟล์เข้า clipboard · จำว่ารันแล้ว (hash)
#   -Count = คืนจำนวนไฟล์ค้าง (ใช้ในเมนูหลัก) · -Project asc|crm = แสดงเฉพาะ project
param([switch]$Count, [string]$Project)
. "$PSScriptRoot\common.ps1"
$done = "$LogDir\sql-done.json"
$db = if (Test-Path -LiteralPath $done) { Get-Content -LiteralPath $done -Raw -Encoding UTF8 | ConvertFrom-Json } else { [pscustomobject]@{} }
function Hash($f) { (Get-FileHash -LiteralPath $f -Algorithm SHA256).Hash.Substring(0, 16) }
function Status($f) {
  if (-not (Test-Path -LiteralPath $f)) { return @{ s = 'ไม่มีไฟล์'; pend = $false } }
  $h = Hash $f; $r = $db.PSObject.Properties[$f]
  if ($r -and $r.Value.hash -eq $h) { return @{ s = "รันแล้ว $($r.Value.when)"; pend = $false } }
  if ($r) { return @{ s = "● ไฟล์เปลี่ยน $((Get-Item $f).LastWriteTime.ToString('d MMM HH:mm')) — ยังไม่รัน"; pend = $true } }
  return @{ s = '● ยังไม่เคยรัน'; pend = $true }
}
$list = $SqlEach | Where-Object { -not $Project -or $_.p -eq $Project }
if ($Count) { return @($list | Where-Object { (Status $_.f).pend }).Count }
function Show {
  Clear-Host; Title 'SQL ที่ต้องรัน (Supabase SQL Editor)'
  $i = 0
  foreach ($proj in ($list | ForEach-Object { $_.p } | Select-Object -Unique)) {
    Write-Host "  $($Supa[$proj].name)  — $($Supa[$proj].url)" -ForegroundColor White
    foreach ($e in ($list | Where-Object { $_.p -eq $proj })) {
      $i++; $st = Status $e.f
      Write-Host ("  {0,2}  {1}" -f $i, $e.f) -ForegroundColor $(if ($st.pend) { 'Yellow' } else { 'Gray' })
      Write-Host ("      {0}  · {1}{2}" -f $st.s, $e.note, $(if ($e.secret) { '  🔒 มีกุญแจ' } else { '' })) -ForegroundColor DarkGray
    }
  }
  Write-Host ''
  Write-Host '  กดเลข = คัดลอกไฟล์เข้า clipboard + เปิด SQL Editor ของ project นั้น → ในเบราว์เซอร์ Ctrl+V แล้วกด Run'
  Write-Host '  [F] ลำดับติดตั้งครั้งแรก   [R] ล้างสถานะ "รันแล้ว" ทั้งหมด   [0] กลับ'
}
function Mark($f) { $db | Add-Member -NotePropertyName $f -NotePropertyValue ([pscustomobject]@{ hash = (Hash $f); when = (& $ThaiDate) }) -Force; $db | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $done -Encoding UTF8 }
function RunOne($e) {
  if (-not (Test-Path -LiteralPath $e.f)) { Bad "ไม่มีไฟล์ $($e.f)"; return }
  $s = $Supa[$e.p]
  Copy-Clip $e.f
  Log ("คัดลอก {0} ({1} KB) เข้า clipboard" -f (Split-Path -Leaf $e.f), [math]::Round((Get-Item $e.f).Length / 1KB))
  Write-Host ''
  Write-Host "  project : $($s.name) ($($s.ref))" -ForegroundColor White
  Write-Host "  ลิงก์    : $($s.url)" -ForegroundColor Cyan
  Write-Host "  ไฟล์    : $($e.f)"
  if ($e.secret) { Write-Host '  🔒 ไฟล์นี้มีกุญแจ — ห้ามส่งต่อ/วางในแชต' -ForegroundColor Red }
  Open-Url $s.url
  Write-Host '  → ในเบราว์เซอร์: Ctrl+V ในช่อง SQL แล้วกด Run' -ForegroundColor Yellow
  $a = Read-Host '  รันแล้ว? [D=ใช่ / Enter=ยัง]'
  if ($a -match '^d') { Mark $e.f; Ok "บันทึกว่ารันแล้ว: $(Split-Path -Leaf $e.f)" } else { Warn 'ยังไม่ได้บันทึก (ไฟล์จะยังขึ้นค้าง)' }
}
while ($true) {
  Show; $c = Read-Host 'เลือก'
  if ($c -eq '0' -or $c -eq '') { return }
  if ($c -match '^[Ff]$') {
    Clear-Host; Title 'ลำดับติดตั้งครั้งแรก (รันซ้ำได้ · ตามลำดับ)'
    foreach ($proj in $SqlFirst.Keys) {
      Write-Host "  $($Supa[$proj].name) — $($Supa[$proj].url)" -ForegroundColor White
      $n = 0; foreach ($f in $SqlFirst[$proj]) { $n++; Write-Host ("  {0,2}. {1} {2}" -f $n, $f, $(if (Test-Path -LiteralPath $f) { '' } else { '(ไม่มีไฟล์)' })) }
    }
    $k = Read-Host 'พิมพ์ asc-เลข หรือ crm-เลข เพื่อคัดลอก+เปิดลิงก์ (Enter=กลับ)'
    if ($k -match '^(asc|crm)-(\d+)$') { $f = $SqlFirst[$Matches[1]][[int]$Matches[2] - 1]; if ($f) { RunOne @{ p = $Matches[1]; f = $f } } }
    continue
  }
  if ($c -match '^[Rr]$') { if (Ask 'ล้างสถานะทั้งหมด?') { Remove-Item -LiteralPath $done -ErrorAction SilentlyContinue; $db = [pscustomobject]@{} }; continue }
  if ($c -match '^\d+$' -and [int]$c -ge 1 -and [int]$c -le $list.Count) { RunOne $list[[int]$c - 1]; Pause-Menu }
}
