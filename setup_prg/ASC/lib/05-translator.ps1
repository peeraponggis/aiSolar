# 05-translator.ps1 — Local Translator: PyInstaller → zip ชุดติดตั้ง → ส่ง home
. "$PSScriptRoot\common.ps1"
$d = $P.tr.dir; $v = Ver 'tr'; $exe = "$d\dist\LocalTranslator\LocalTranslator.exe"; $zip = "$d\LocalTranslator-setup-$v.zip"
try {
  Clear-Host; Title "Local Translator $v  ($d)"
  if (Test-Path -LiteralPath $exe) { $ev = (Get-Item $exe).VersionInfo.ProductVersion; if (-not $ev) { $ev = '(ไม่มีเลขรุ่นใน exe)' }; Log "dist exe: $ev ($((Get-Item $exe).LastWriteTime.ToString('d MMM yyyy')))" } else { Warn 'ยังไม่มี dist\LocalTranslator.exe' }
  $old = Get-ChildItem "$d\LocalTranslator-setup*.zip" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime | Select-Object -Last 1
  if ($old) { Log "zip ล่าสุด: $($old.Name) ($($old.LastWriteTime.ToString('d MMM yyyy')))" }
  Write-Host ''; Write-Host '  [1] pyinstaller LocalTranslator.spec (≈ 4 นาที)'; Write-Host "  [2] zip ชุดติดตั้ง → LocalTranslator-setup-$v.zip"; Write-Host '  [3] ส่ง zip ไป home (C:\LocalAI\translation)'; Write-Host '  [0] กลับ'
  switch (Read-Host 'เลือก') {
    '1' {
      $pi = if (Test-Path "$d\.venv\Scripts\pyinstaller.exe") { "$d\.venv\Scripts\pyinstaller.exe" } elseif (Tool pyinstaller) { 'pyinstaller' } else { throw 'ไม่พบ pyinstaller' }
      Run 'pyinstaller' $pi @('--noconfirm', "$d\LocalTranslator.spec") $d | Out-Null
    }
    '2' {
      if (-not (Test-Path -LiteralPath $exe)) { throw 'ยังไม่มี dist — เลือก [1] ก่อน' }
      if (Test-Path -LiteralPath $zip) { Remove-Item -LiteralPath $zip }
      $items = Get-ChildItem "$d\dist\LocalTranslator" | Where-Object { $_.Name -notmatch '\.bak' }
      Compress-Archive -LiteralPath $items.FullName -DestinationPath $zip -CompressionLevel Optimal
      Ok "$zip ($([math]::Round((Get-Item $zip).Length/1MB,1)) MB) — ภายในมี Install-LocalTranslator.bat"
      Sync-Installers | ForEach-Object { Ok "พกไปเครื่องใหม่: $($_.dst)" }
    }
    '3' { if (-not (Test-Path -LiteralPath $zip)) { throw 'ยังไม่มี zip — เลือก [2] ก่อน' }; Run 'scp → home' scp @($zip, "${SshHost}:$HomeRoot\translation\") | Out-Null }
    default { return }
  }
} catch { Bad "หยุด: $($_.Exception.Message)" }
Pause-Menu
