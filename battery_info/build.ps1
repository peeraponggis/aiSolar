# สร้าง BatteryDashboard.exe (ลุงพี 7 พ.ย. 2569)
#   - ตัวเปิดโปรแกรมแทน launch.vbs · เลขเวอร์ชันจาก VERSION.json ฝังใน exe (คลิกขวา > Properties > Details)
#   - ใช้ csc.exe ของ .NET Framework 4 ที่มีในทุก Windows 10/11
#   - สร้าง/อัปเดต shortcut "รายงานแบตเตอรี่" บน Desktop ทั้งสองที่ + Startup (ถ้ามีอยู่แล้ว) ให้ชี้มาที่ exe
# รัน:  powershell -NoProfile -ExecutionPolicy Bypass -File build.ps1
$ErrorActionPreference = 'Stop'
$Dir = $PSScriptRoot
$csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (-not (Test-Path $csc)) { $csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework\v4.0.30319\csc.exe' }
if (-not (Test-Path $csc)) { throw 'ไม่พบ csc.exe ของ .NET Framework 4' }
$v = Get-Content (Join-Path $Dir 'VERSION.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$ver = $v.version
$fileVer = (($ver -split '\.') + @('0', '0', '0', '0'))[0..3] -join '.'

$obj = Join-Path $Dir 'tmp\obj'
New-Item -ItemType Directory -Force $obj | Out-Null
$asm = Join-Path $obj 'AssemblyInfo.cs'
[IO.File]::WriteAllText($asm, @"
using System.Reflection;
[assembly: AssemblyTitle("Battery & System Dashboard")]
[assembly: AssemblyDescription("Battery & System Dashboard v$ver - แบตเตอรี่ โปรแกรม อินเทอร์เน็ต ปรับประสิทธิภาพ")]
[assembly: AssemblyProduct("Battery & System Dashboard")]
[assembly: AssemblyCompany("ลุงพี")]
[assembly: AssemblyCopyright("Battery & System Dashboard โดย ลุงพี")]
[assembly: AssemblyVersion("$fileVer")]
[assembly: AssemblyFileVersion("$fileVer")]
[assembly: AssemblyInformationalVersion("$ver")]
"@, (New-Object Text.UTF8Encoding($true)))

$exe = Join-Path $Dir 'BatteryDashboard.exe'
$out = & $csc /nologo /codepage:65001 /optimize+ /platform:anycpu /target:winexe "/out:$exe" "/win32icon:$(Join-Path $Dir 'battery.ico')" `
  /r:System.Windows.Forms.dll (Join-Path $Dir 'launcher\BatteryDashboard.cs') $asm 2>&1
if ($LASTEXITCODE -ne 0) { $out | Write-Host; throw "csc ผิดพลาด ($LASTEXITCODE)" }
Remove-Item $obj -Recurse -Force
"สร้างแล้ว: $exe · v$((Get-Item $exe).VersionInfo.ProductVersion)"

# shortcut: ลบแล้วสร้างใหม่ทุกครั้ง (ค่าเก่าเช่น "เปิดแบบย่อ" จะไม่ค้าง)
$sh = New-Object -ComObject WScript.Shell
function Set-Lnk([string]$path, [string]$arg) {
  if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Force }
  $l = $sh.CreateShortcut($path)
  $l.TargetPath = $exe; $l.Arguments = $arg; $l.WorkingDirectory = $Dir
  $l.IconLocation = "$(Join-Path $Dir 'battery.ico'),0"; $l.WindowStyle = 1
  $l.Description = "Battery & System Dashboard v$ver"
  $l.Save()
  "shortcut: $path -> $exe $arg (มีไฟล์: $(Test-Path -LiteralPath $path))"
}
$desktops = @([Environment]::GetFolderPath('Desktop'), (Join-Path $env:USERPROFILE 'Desktop'), (Join-Path $env:USERPROFILE 'OneDrive\Desktop')) |
  Where-Object { $_ -and (Test-Path $_) } | Select-Object -Unique
foreach ($d in $desktops) { Set-Lnk (Join-Path $d 'รายงานแบตเตอรี่.lnk') '' }
# เปิดตอนเปิดเครื่อง: มีอยู่แล้ว = อัปเดตให้ชี้มาที่ exe (ไม่สร้างใหม่ถ้าไม่ได้ตั้งไว้)
$startup = Join-Path ([Environment]::GetFolderPath('Startup')) 'BatteryMonitor.lnk'
if (Test-Path -LiteralPath $startup) { Set-Lnk $startup '' }
