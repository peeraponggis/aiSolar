# make-shortcut.ps1 — ไอคอน Desktop "Git Sync" → Git-Sync.bat (ทั้ง Desktop และ OneDrive\Desktop) · รันซ้ำได้ทั้ง 2 เครื่อง
$here = $PSScriptRoot
$ico = Join-Path $here 'git-sync.ico'
$ws = New-Object -ComObject WScript.Shell
foreach ($desk in @([Environment]::GetFolderPath('Desktop'), "$env:USERPROFILE\OneDrive\Desktop") | Select-Object -Unique) {
  if (-not (Test-Path -LiteralPath $desk)) { continue }
  $lnk = $ws.CreateShortcut("$desk\Git Sync.lnk")
  $lnk.TargetPath = "$here\Git-Sync.bat"; $lnk.WorkingDirectory = $here
  if (Test-Path -LiteralPath $ico) { $lnk.IconLocation = "$ico,0" }
  $lnk.Description = 'Git Sync — pull / push ทุก repo พร้อมกัน'
  $lnk.Save(); "สร้าง $desk\Git Sync.lnk"
}
