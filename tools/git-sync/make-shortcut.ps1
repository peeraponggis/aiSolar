# make-shortcut.ps1 — ไอคอน Desktop "Git Sync" → หน้าต่าง git_sync_gui.pyw (ทั้ง Desktop และ OneDrive\Desktop) · รันซ้ำได้ทั้ง 2 เครื่อง
$here = $PSScriptRoot
$ico = Join-Path $here 'git-sync.ico'
$pyw = (Get-Command pyw -ErrorAction SilentlyContinue).Source      # ตัวเปิด Python แบบไม่มีหน้าจอดำ
$ws = New-Object -ComObject WScript.Shell
foreach ($desk in @([Environment]::GetFolderPath('Desktop'), "$env:USERPROFILE\OneDrive\Desktop") | Select-Object -Unique) {
  if (-not (Test-Path -LiteralPath $desk)) { continue }
  $lnk = $ws.CreateShortcut("$desk\Git Sync.lnk")
  if ($pyw) { $lnk.TargetPath = $pyw; $lnk.Arguments = "`"$here\git_sync_gui.pyw`"" }
  else { $lnk.TargetPath = "$here\Git-Sync-GUI.bat"; $lnk.Arguments = ''; Write-Warning 'ไม่พบ pyw — ใช้ Git-Sync-GUI.bat แทน' }
  $lnk.WorkingDirectory = $here
  if (Test-Path -LiteralPath $ico) { $lnk.IconLocation = "$ico,0" }
  $lnk.Description = 'Git Sync — pull / push ทุก repo พร้อมกัน (หน้าต่าง)'
  $lnk.Save(); "สร้าง $desk\Git Sync.lnk"
}
