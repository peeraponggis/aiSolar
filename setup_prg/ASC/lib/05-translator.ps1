# 05-translator.ps1 — Local Translator: build_exe.bat (2 ชุด) → zip → installers\ → ส่งชุดเต็มไป home
#   ชุดแจกจ่าย LocalTranslator-setup.zip (~31 MB ไม่มีพูดถามด้วยเสียง · อยู่ใน git) · ชุดเต็ม LocalTranslator-full.zip (~181 MB · ไม่ขึ้น git)
#   build_exe.bat build ลง build_dist ก่อนแล้วคัดลอกทับ dist → settings.json/history.json ใน dist ไม่หาย (ห้ามเรียก pyinstaller ลง dist ตรง ๆ)
. "$PSScriptRoot\common.ps1"
$d = $P.tr.dir; $v = Ver 'tr'
$exe = "$d\dist\LocalTranslator\LocalTranslator.exe"; $exeLite = "$d\dist_lite\LocalTranslator\LocalTranslator.exe"
$zipLite = "$d\LocalTranslator-setup.zip"; $zipFull = "$d\LocalTranslator-full.zip"
function ZipInfo([string]$z) { if (Test-Path -LiteralPath $z) { $i = Get-Item $z; "$($i.Name) $([math]::Round($i.Length/1MB,1)) MB ($($i.LastWriteTime.ToString('d MMM yyyy HH:mm')))" } else { "$(Split-Path $z -Leaf) (ยังไม่มี)" } }
try {
  Clear-Host; Title "Local Translator $v  ($d)"
  foreach ($e in @(@('exe ชุดเต็ม      dist\LocalTranslator', $exe), @('exe ชุดแจกจ่าย dist_lite\LocalTranslator', $exeLite))) {
    if (Test-Path -LiteralPath $e[1]) { Log "$($e[0]): $((Get-Item $e[1]).LastWriteTime.ToString('d MMM yyyy HH:mm'))" } else { Warn "ยังไม่มี $($e[0])" }
  }
  Log "zip แจกจ่าย: $(ZipInfo $zipLite)"; Log "zip ชุดเต็ม : $(ZipInfo $zipFull)"
  Write-Host ''
  Write-Host '  [1] build ทั้ง 2 ชุด   build_exe.bat all   (≈ 8 นาที) → setup.zip (แจกจ่าย ~31 MB) + full.zip (เต็ม ~181 MB) → สำเนาไป installers\'
  Write-Host '  [2] build ชุดแจกจ่าย   build_exe.bat lite  (≈ 3 นาที · ไม่มีพูดถามด้วยเสียง — ชุดที่ให้คนอื่น)'
  Write-Host '  [3] build ชุดเต็ม      build_exe.bat full  (≈ 5 นาที · เครื่องตัวเอง + home)'
  Write-Host '  [4] ส่งชุดเต็มไป home  scp LocalTranslator-full.zip → C:\LocalAI\translation (181 MB ≈ 15 นาที ผ่าน Tailscale)'
  Write-Host '  [0] กลับ'
  $pick = Read-Host 'เลือก'
  $what = switch ($pick) { '1' { 'all' } '2' { 'lite' } '3' { 'full' } default { $null } }
  if ($what) {
    if (-not (Test-Path -LiteralPath "$d\build_exe.bat")) { throw "ไม่พบ $d\build_exe.bat" }
    Warn 'build_exe.bat จะปิด LocalTranslator.exe ที่เปิดอยู่ก่อน build'
    Run "build_exe.bat $what" cmd.exe @('/c', "`"$d\build_exe.bat`" $what") $d | Out-Null
    Ok "zip แจกจ่าย: $(ZipInfo $zipLite)"; Ok "zip ชุดเต็ม : $(ZipInfo $zipFull)"
    Log 'ภายใน zip มี Install-LocalTranslator.bat — ลง Ollama + โมเดลให้เองทั้งหมด (ปลายทางไม่ต้องลง Ollama ก่อน)'
    Sync-Installers | Where-Object { $_.kind -like 'LocalTranslator*' } | ForEach-Object { Ok "พกไปเครื่องใหม่: $($_.dst)" }
    Log 'ชุดแจกจ่าย (setup.zip) อยู่ใน git → commit + push aiSolar ด้วย · ชุดเต็มไม่ขึ้น git (เกิน 100 MB)'
  } elseif ($pick -eq '4') {
    if (-not (Test-Path -LiteralPath $zipFull)) { throw 'ยังไม่มี LocalTranslator-full.zip — เลือก [1] หรือ [3] ก่อน' }
    Run 'scp → home' scp @($zipFull, "${SshHost}:$HomeRoot\translation\") | Out-Null
    Log "ต่อบน home (07 หรือ ssh): ปิดโปรแกรม → แตก $HomeRoot\translation\LocalTranslator-full.zip → คัดลอก _internal + exe ทับ $HomeRoot\LocalTranslator (เก็บ settings.json/history.json เดิม) → เปิดใหม่"
  } else { return }
} catch { Bad "หยุด: $($_.Exception.Message)" }
Pause-Menu
