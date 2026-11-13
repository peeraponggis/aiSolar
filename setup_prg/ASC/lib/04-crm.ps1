# 04-crm.ps1 — CRM-Pi deploy (laptop เท่านั้น · Cloudflare Pages · --branch production เสมอ)
. "$PSScriptRoot\common.ps1"
$d = $P.crm.dir
try {
  Clear-Host; Title "CRM-Pi $(Ver 'crm')  ($d → $($P.crm.url))"
  Log "git picode: $(GitState 'crm')"
  $pm = Select-String -LiteralPath $Programs -Pattern 'CRM-Pi[^|]*\|\s*([\d.]+)' | Select-Object -First 1
  $pv = if ($pm) { $pm.Matches[0].Groups[1].Value } else { $null }
  if ($pv -and $pv -ne (Ver 'crm')) { Warn "VERSION.json $(Ver 'crm') ≠ PROGRAMS.md $pv — ควรแก้ให้ตรง" }
  Write-Host ''; Write-Host '  [1] build + deploy production'; Write-Host '  [2] build อย่างเดียว (dist_pages)'; Write-Host '  [3] รายการ SQL ของ CRM'; Write-Host '  [0] กลับ'
  switch (Read-Host 'เลือก') {
    { $_ -in '1', '2' } {
      GitPull 'crm'
      Run 'build_pages.mjs' node @("$d\pi_crm_erp\scripts\build_pages.mjs") $d | Out-Null
      $re = 'sk-[A-Za-z0-9]{20}|service_role|sb_secret_|ghp_[A-Za-z0-9]{30}'
      $hit = Get-ChildItem "$d\dist_pages" -Recurse -Include *.js, *.html, *.json | Where-Object { (Get-Content -LiteralPath $_.FullName -Raw) -match $re }
      if ($hit) { Bad "พบคีย์ใน dist_pages: $($hit.Name -join ', ')"; throw 'secret' } else { Ok 'สแกนคีย์ใน dist_pages ไม่พบ' }
      if ($_ -eq '1') {
        Warn 'deploy production = ผู้ใช้จริงเห็นทันที'
        if (Ask 'deploy pi-system production?') {
          Run 'wrangler pages deploy' npx.cmd @('wrangler', 'pages', 'deploy', 'dist_pages', '--project-name', 'pi-system', '--branch', 'production') $d | Out-Null
          Open-Url $P.crm.url
        }
      }
    }
    '3' { & "$PSScriptRoot\06-sql.ps1" -Project crm; return }
    default { return }
  }
} catch { Bad "หยุด: $($_.Exception.Message)" }
Pause-Menu
