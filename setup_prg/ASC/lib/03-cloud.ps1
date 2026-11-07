# 03-cloud.ps1 — ASC Cloud deploy (GitHub Pages จาก docs/) + ตรวจเว็บจริง
param([switch]$VerifyOnly)
. "$PSScriptRoot\common.ps1"
$d = $P.asc.dir; $u = $P.asc.url
function Verify {
  Title 'ตรวจเว็บจริง'
  Log 'รอ GitHub Pages (gh run watch)…'; Start-Sleep 8
  $id = gh run list -R $P.asc.repo -L 1 --json databaseId -q '.[0].databaseId'
  if ($id) { gh run watch $id -R $P.asc.repo --exit-status | Out-Null; if ($LASTEXITCODE) { Bad 'deploy ไม่ผ่าน' } else { Ok 'deploy เสร็จ' } }
  foreach ($p in '/', '/studio/', '/architec/', '/ascs-release/latest.json', '/asca-release/latest.json') { $c = Http "$u$p"; if ($c -eq 200) { Ok "$p 200" } else { Bad "$p HTTP $c" } }
  try { Ok "ascs latest.json = $((Invoke-RestMethod "$u/ascs-release/latest.json?t=$(Get-Random)").version) · asca = $((Invoke-RestMethod "$u/asca-release/latest.json?t=$(Get-Random)").version)" } catch {}
  $ro = Select-String -LiteralPath "$d\docs\studio-config.js" -Pattern "rollout\s*:\s*'(\w+)'" | Select-Object -First 1 | ForEach-Object { $_.Matches[0].Groups[1].Value }
  if ($ro) { Log "rollout: $ro" }
}
try {
  if ($VerifyOnly) { Verify; return }
  Clear-Host; Title "ASC Cloud  ($d → $u)"
  GitPull 'asc'
  $chg = git -C $d status --porcelain | Out-String
  if (-not $chg.Trim()) { Ok 'ไม่มีอะไรเปลี่ยน'; Verify; Pause-Menu; return }
  foreach ($grp in 'docs/studio', 'docs/architec', 'docs/ascs-release', 'docs/asca-release', 'supabase') { $n = @(git -C $d status --porcelain -- $grp).Count; if ($n) { Log "  $grp : $n ไฟล์" } }
  $other = git -C $d status --porcelain | Where-Object { $_ -notmatch 'docs/(studio|architec|ascs-release|asca-release)|supabase' }
  if ($other) { Warn "ไฟล์อื่นที่เปลี่ยน:`n$($other -join "`n")" }
  if (git -C $d diff --name-only -- docs/sw.js) { Warn 'docs/sw.js เปลี่ยน — ถ้ารายการ SHELL เปลี่ยน ต้อง bump VERSION ใน sw.js' }
  git -C $d add -A
  ScanSecrets $d @((Get-Content -LiteralPath $KeyASCS -Raw -ErrorAction SilentlyContinue), (Get-Content -LiteralPath $KeyASCA -Raw -ErrorAction SilentlyContinue))
  $msg = Read-Host 'ข้อความ commit (Enter = "ASC Cloud: อัปเดต docs")'; if (-not $msg) { $msg = 'ASC Cloud: อัปเดต docs' }
  if (CommitPush 'asc' $msg @()) { Verify }
} catch { Bad "หยุด: $($_.Exception.Message)" }
Pause-Menu
