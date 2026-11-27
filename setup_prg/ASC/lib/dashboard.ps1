# dashboard.ps1 — หน้าเว็บในเครื่อง "ASC ปล่อยรุ่น" (ลุงพีสั่ง 7 พ.ย. 2569)
#   เซิร์ฟเวอร์เล็กบน http://127.0.0.1:8770 เสิร์ฟ dashboard.html + สถานะจริง (รุ่น · git · home · SQL ค้าง · ชุดติดตั้ง)
#   ปุ่มบนหน้าเว็บ → POST /run?n=menu|01..08 → เปิด .bat ในหน้าต่างใหม่ (เบราว์เซอร์เปิด bat เองไม่ได้ จึงต้องมีตัวนี้)
#   ปิด: ปิดหน้าต่างนี้ หรือกด "ปิดเซิร์ฟเวอร์" บนหน้าเว็บ
. "$PSScriptRoot\common.ps1"
$port = 8770; $html = "$PSScriptRoot\dashboard.html"
$bats = @{ menu = 'ASC-Menu.bat'; '01' = '01-ascs-release.bat'; '02' = '02-asca-release.bat'; '03' = '03-cloud-deploy.bat'; '04' = '04-crm-deploy.bat'; '05' = '05-translator-build.bat'; '06' = '06-sql-todo.bat'; '07' = '07-home.bat'; '08' = '08-new-pc.bat'; '09' = '09-homeguard.bat' }

# ---- สถานะคำนวณในเบื้องหลัง (runspace แยก) → หน้าเว็บไม่ค้างแม้ git/ssh/เว็บช้า (แก้ 7 พ.ย. 2569: หน้าเว็บเปิดไม่ได้เพราะ listener ติดรอ)
$shared = [hashtable]::Synchronized(@{ json = '{"loading":true}'; at = $null; busy = $false; want = $true })
$rs = [runspacefactory]::CreateRunspace(); $rs.Open(); $rs.SessionStateProxy.SetVariable('shared', $shared); $rs.SessionStateProxy.SetVariable('libDir', $PSScriptRoot)
$ps = [powershell]::Create(); $ps.Runspace = $rs
[void]$ps.AddScript({
  . "$libDir\dashboard-status.ps1"
  while ($true) {
    if ($shared.want -or (-not $shared.at) -or ((Get-Date) - $shared.at).TotalSeconds -gt 60) {
      if ($shared.want) { $script:cacheAt = [datetime]::MinValue; $script:homeAt = [datetime]::MinValue }   # กด ⟳ = อ่านใหม่ทุกอย่างรวม home
      $shared.want = $false; $shared.busy = $true
      try { $shared.json = (Status) | ConvertTo-Json -Depth 6 -Compress } catch { $shared.json = '{"error":' + ($_.Exception.Message | ConvertTo-Json) + '}' }
      $shared.at = Get-Date; $shared.busy = $false
    }
    Start-Sleep -Milliseconds 500
  }
})
$job = $ps.BeginInvoke()

$l = [System.Net.HttpListener]::new(); $l.Prefixes.Add("http://127.0.0.1:$port/")
try { $l.Start() } catch { Write-Host "เปิดพอร์ต $port ไม่ได้ (อาจเปิดอยู่แล้ว) — เปิดหน้าเว็บแทน"; Start-Process "http://127.0.0.1:$port/"; exit 0 }
Log "dashboard: http://127.0.0.1:$port/"
Start-Process "http://127.0.0.1:$port/"
Write-Host "ASC ปล่อยรุ่น — หน้าเว็บเปิดที่ http://127.0.0.1:$port/  (ปิดหน้าต่างนี้ = ปิดเซิร์ฟเวอร์ · สถานะอ่านใหม่ทุก 60 วิ)" -ForegroundColor Cyan
function Send($ctx, [string]$body, [string]$type = 'application/json; charset=utf-8', [int]$code = 200) {
  $b = [Text.Encoding]::UTF8.GetBytes($body); $ctx.Response.StatusCode = $code; $ctx.Response.ContentType = $type; $ctx.Response.ContentLength64 = $b.Length
  $ctx.Response.OutputStream.Write($b, 0, $b.Length); $ctx.Response.Close()
}
while ($l.IsListening) {
  $ctx = $l.GetContext(); $u = $ctx.Request.Url
  try {
    switch -Regex ($u.AbsolutePath) {
      '^/$'            { Send $ctx (Get-Content -LiteralPath $html -Raw -Encoding UTF8) 'text/html; charset=utf-8' }
      '^/api/status$'  { Send $ctx $shared.json }
      '^/api/refresh$' { $shared.want = $true; Send $ctx ('{"refreshing":true,"busy":' + ($shared.busy.ToString().ToLower()) + '}') }
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
try { $ps.Stop(); $rs.Close() } catch {}
