# make-shortcut.ps1 — ไอคอน Desktop "ASC ปล่อยรุ่น" → ASC-Menu.bat (ทั้ง Desktop และ OneDrive\Desktop)
$here = Split-Path -Parent $PSScriptRoot
$ico = Join-Path (Split-Path -Parent (Split-Path -Parent $here)) 'aiSolar\design-auto\ascs.ico'
$ws = New-Object -ComObject WScript.Shell
foreach ($desk in @([Environment]::GetFolderPath('Desktop'), "$env:USERPROFILE\OneDrive\Desktop") | Select-Object -Unique) {
  if (-not (Test-Path -LiteralPath $desk)) { continue }
  $lnk = $ws.CreateShortcut("$desk\ASC ปล่อยรุ่น.lnk")
  $lnk.TargetPath = "$here\ASC-Menu.bat"; $lnk.WorkingDirectory = $here
  if (Test-Path -LiteralPath $ico) { $lnk.IconLocation = $ico }
  $lnk.Description = 'ASC — ปล่อยรุ่น · ติดตั้ง · SQL · home server'
  $lnk.Save(); "สร้าง $desk\ASC ปล่อยรุ่น.lnk"
}
