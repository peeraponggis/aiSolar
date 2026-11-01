# ติดตั้ง Skill ของลุงพีให้ Claude Code บนเครื่องนี้ (laptop / home server) — รันซ้ำได้ · โดย ลุงพี
# ใช้: powershell -ExecutionPolicy Bypass -File <ไดรฟ์>:\LocalAI\skills\install-skills.ps1
# คัดลอกทุกโฟลเดอร์ที่มี SKILL.md ใต้ skills\ ไปที่ %USERPROFILE%\.claude\skills\ (ทับฉบับเดิม)
$src = $PSScriptRoot
$dst = Join-Path $env:USERPROFILE '.claude\skills'
New-Item -ItemType Directory -Force -Path $dst | Out-Null
Get-ChildItem -Path $src -Directory | Where-Object { Test-Path (Join-Path $_.FullName 'SKILL.md') } | ForEach-Object {
    $to = Join-Path $dst $_.Name
    New-Item -ItemType Directory -Force -Path $to | Out-Null
    Copy-Item -Path (Join-Path $_.FullName '*') -Destination $to -Recurse -Force
    Write-Host "ติดตั้ง skill: $($_.Name) -> $to"
}
Write-Host 'เสร็จ — เปิด session ใหม่ของ Claude Code แล้วพิมพ์ /lungpee หรือเริ่มงานโปรแกรมได้เลย'
