# ============================================================
# Battery Terminal Console  |  F:\LocalAI\battery_info
# รันใน Windows Terminal: wt.exe -p "PowerShell" --title "Battery Console" powershell.exe -ExecutionPolicy Bypass -File "F:\LocalAI\battery_info\console-terminal.ps1"
# ============================================================
param([int]$RefreshSec = 10, [int]$IdleMin = 30, [double]$CpuThresh = 2.0, [int]$LowBattPct = 20)

$Host.UI.RawUI.WindowTitle = "Battery Console - ThinkPad P16s Gen 2"
[Console]::CursorVisible = $false
$API = "http://localhost:8765/api/status"

# ANSI colors
function e($code) { "`e[$code`m" }
$RESET  = e 0; $BOLD   = e 1
$RED    = e 91; $YELLOW = e 93; $GREEN  = e 92
$BLUE   = e 94; $CYAN   = e 96; $ORANGE = e "38;5;214"
$PURPLE = e "38;5;141"; $MUTED  = e "38;5;245"; $DIM = e "38;5;238"
$BG_RED = e "41"; $BG_DARK = e "48;5;234"

$script:HistLocal = @{}
$script:AlertedPids = @{}
$script:LowBattAlerted = $false
$lang = "th"

function Clear-Screen { [Console]::Clear() }

function Write-Line([string]$text = "") { Write-Host $text }

function Draw-Bar([double]$pct, [int]$width = 30, [string]$fillColor = $GREEN) {
    $filled = [math]::Round($pct / 100 * $width)
    $empty  = $width - $filled
    $bar    = "$fillColor" + ("█" * $filled) + "$DIM" + ("░" * $empty) + "$RESET"
    return $bar
}

function Get-BattColor([int]$pct, [bool]$charging) {
    if ($charging) { return $YELLOW }
    if ($pct -le 20) { return $RED }
    if ($pct -le 40) { return $ORANGE }
    return $GREEN
}

function Get-CpuColor([double]$cpu) {
    if ($cpu -gt 50) { return $RED }
    if ($cpu -gt 20) { return $ORANGE }
    if ($cpu -gt 5)  { return $YELLOW }
    return $GREEN
}

function Format-Time([int]$minutes) {
    if ($minutes -lt 60) { return "${minutes}m" }
    $h = [math]::Floor($minutes / 60)
    $m = $minutes % 60
    if ($m -eq 0) { return "${h}h" }
    return "${h}h${m}m"
}

function Pad-Right([string]$s, [int]$len) {
    if ($s.Length -ge $len) { return $s.Substring(0, $len) }
    return $s + (" " * ($len - $s.Length))
}

function Play-Beep([string]$type = "warn") {
    if ($type -eq "low") {
        # Low battery: urgent descending tones
        [Console]::Beep(880, 200); Start-Sleep -Milliseconds 50
        [Console]::Beep(660, 200); Start-Sleep -Milliseconds 50
        [Console]::Beep(440, 400)
    } elseif ($type -eq "idle") {
        # Idle: soft descending
        [Console]::Beep(600, 150); Start-Sleep -Milliseconds 80
        [Console]::Beep(450, 150); Start-Sleep -Milliseconds 80
        [Console]::Beep(330, 250)
    }
}

function Get-DataFromServer {
    try {
        $r = Invoke-WebRequest -Uri $API -TimeoutSec 4 -UseBasicParsing
        return $r.Content | ConvertFrom-Json
    } catch { return $null }
}

function Get-DataLocal {
    # Fallback: read directly via WMI + Get-Process
    $now   = Get-Date
    $cores = [math]::Max(1, [int]$env:NUMBER_OF_PROCESSORS)
    $batt  = $null
    try {
        $b = Get-WmiObject Win32_Battery -ErrorAction Stop
        if ($b) {
            $batt = [PSCustomObject]@{
                level    = [int]$b.EstimatedChargeRemaining
                charging = $b.BatteryStatus -in @(2,6,7,8,9)
                runtime  = [int]$b.EstimatedRunTime
                healthPct = 85.3; cycles = 407; cycleRated = 1000
            }
        }
    } catch {}

    $procs = @()
    try {
        $rawProcs = Get-Process -ErrorAction SilentlyContinue |
            Where-Object { $_.MainWindowTitle -ne "" -and $_.Id -gt 4 }
        foreach ($p in $rawProcs) {
            $key = "$($p.Id)"
            $cpuPct = 0.0
            if ($script:HistLocal.ContainsKey($key)) {
                $h = $script:HistLocal[$key]
                $elapsed = ($now - $h.Time).TotalSeconds
                if ($elapsed -gt 0.5) {
                    $delta = [math]::Max(0, $p.CPU - $h.CpuTotal)
                    $cpuPct = [math]::Round($delta / $elapsed / $cores * 100, 1)
                }
            }
            $idleMin = 0
            if ($script:HistLocal.ContainsKey($key)) {
                $h = $script:HistLocal[$key]
                if ($cpuPct -lt $CpuThresh) {
                    if ($null -eq $h.IdleStart) { $script:HistLocal[$key].IdleStart = $now }
                    $idleMin = [math]::Round(($now - $script:HistLocal[$key].IdleStart).TotalMinutes)
                } else { $script:HistLocal[$key].IdleStart = $null }
                $script:HistLocal[$key].CpuTotal = $p.CPU
                $script:HistLocal[$key].Time = $now
            } else {
                $script:HistLocal[$key] = @{ CpuTotal=$p.CPU; Time=$now; IdleStart=$now }
            }
            $runtimeMin = 0
            try { if ($p.StartTime) { $runtimeMin = [math]::Round(($now - $p.StartTime).TotalMinutes) } } catch {}
            $title = $p.MainWindowTitle
            if ($title.Length -gt 40) { $title = $title.Substring(0,37) + "..." }
            $procs += [PSCustomObject]@{
                pid=([int]$p.Id); name=$p.ProcessName; title=$title
                cpu=$cpuPct; memMB=([math]::Round($p.WorkingSet64/1MB))
                runtimeMin=$runtimeMin; idleMin=$idleMin
                isIdle=($idleMin -ge $IdleMin)
            }
        }
    } catch {}

    return [PSCustomObject]@{
        battery   = $batt
        processes = ($procs | Sort-Object memMB -Descending)
        idleCount = ($procs | Where-Object { $_.isIdle } | Measure-Object).Count
        settings  = @{ idleMinutes=$IdleMin; cpuThreshold=$CpuThresh }
        timestamp = (Get-Date -Format "HH:mm:ss")
        serverOk  = $false
    }
}

# ── MAIN DRAW ───────────────────────────────────────────────
function Draw-Dashboard($data, $blink) {
    $ts  = Get-Date -Format "HH:mm:ss"
    $b   = $data.battery
    $procs = @($data.processes)
    $w   = [math]::Max(70, [Console]::WindowWidth - 2)
    $srvStatus = if ($data.serverOk) { "${GREEN}● เชื่อมต่อ server${RESET}" } else { "${YELLOW}● โหมดโดยตรง (WMI)${RESET}" }

    [Console]::SetCursorPosition(0, 0)

    # ── HEADER ──
    $hdr = " Battery Console - Lenovo ThinkPad P16s Gen 2 "
    $pad = [math]::Max(0, $w - $hdr.Length - 1)
    Write-Host "$BG_DARK$CYAN$BOLD$hdr$RESET$BG_DARK$(" " * $pad)$RESET"
    Write-Host "$DIM$("─" * $w)$RESET"

    # ── BATTERY ──
    if ($b) {
        $pct      = [int]$b.level
        $charging = [bool]$b.charging
        $battColor = Get-BattColor $pct $charging
        $barColor  = $battColor
        $barWidth  = [math]::Min(40, $w - 30)
        $bar       = Draw-Bar $pct $barWidth $barColor
        $status    = if ($pct -ge 100 -and $charging) { "${GREEN}ชาร์จเต็มแล้ว ✓" }
                     elseif ($charging) { "${YELLOW}กำลังชาร์จ..." }
                     elseif ($pct -le 20) { "${RED}${BOLD}แบตต่ำ! ควรชาร์จด่วน" }
                     else { "${BLUE}กำลังใช้งาน" }
        Write-Host " $battColor${BOLD}$pct%$RESET  $bar  $status$RESET"
        $healthBar = Draw-Bar 85.3 20 $ORANGE
        Write-Host " ${MUTED}สุขภาพ ${ORANGE}${BOLD}85.3%$RESET  $healthBar  ${MUTED}407/1,000 รอบ  เหลือ ~593 รอบ$RESET"
    } else {
        Write-Host " ${RED}ไม่พบข้อมูลแบตเตอรี่$RESET"
    }

    # ── LOW BATTERY ALERT ──
    if ($b -and [int]$b.level -le $LowBattPct -and -not [bool]$b.charging) {
        if (-not $script:LowBattAlerted) {
            $script:LowBattAlerted = $true
            Play-Beep "low"
        }
        if ($blink % 2 -eq 0) {
            Write-Host "$BG_RED$BOLD  ⚡ แบตเตอรี่เหลือน้อย! กรุณาเสียบชาร์จโดยด่วน ($($b.level)%)  $RESET"
        } else {
            Write-Host "$RED$BOLD  ⚡ แบตเตอรี่เหลือน้อย! กรุณาเสียบชาร์จโดยด่วน ($($b.level)%)  $RESET"
        }
    } else {
        $script:LowBattAlerted = $false
        Write-Host ""
    }

    Write-Host "$DIM$("─" * $w)$RESET"

    # ── PROCESS TABLE HEADER ──
    $idleCount = [int]$data.idleCount
    $idleLabel  = if ($idleCount -gt 0) { " ${RED}⚠ $idleCount ไม่ได้ใช้งาน > ${IdleMin}m$RESET" } else { "" }
    Write-Host " ${CYAN}${BOLD}โปรแกรมที่ทำงานอยู่ ($($procs.Count))$RESET$idleLabel"
    Write-Host " $MUTED$(Pad-Right "ชื่อ" 22)$(Pad-Right "Title" 35)$(Pad-Right "CPU%" 7)$(Pad-Right "RAM" 8)$(Pad-Right "เวลา" 7)ไม่ใช้งาน$RESET"
    Write-Host "$DIM$("─" * $w)$RESET"

    # ── PROCESS ROWS ──
    $maxRows = [math]::Max(5, [Console]::WindowHeight - 18)
    $shown   = [math]::Min($procs.Count, $maxRows)
    for ($i = 0; $i -lt $shown; $i++) {
        $p   = $procs[$i]
        $cpuC = Get-CpuColor $p.cpu
        $memStr = if ($p.memMB -ge 1024) { "$([math]::Round($p.memMB/1024,1))G" } else { "$($p.memMB)M" }
        $idleStr = ""
        if ($p.isIdle) {
            $f = if ($blink % 2 -eq 0) { "$RED$BOLD" } else { "$ORANGE" }
            $idleStr = "${f}⚠ $(Format-Time $p.idleMin)$RESET"
            # Alert sound for newly idle process
            if (-not $script:AlertedPids.ContainsKey($p.pid)) {
                $script:AlertedPids[$p.pid] = $true
                Play-Beep "idle"
            }
        } elseif ($p.idleMin -gt 0) {
            $idleStr = "$MUTED$(Format-Time $p.idleMin)$RESET"
        } else {
            $idleStr = "$DIM-$RESET"
        }

        $nameTrunc  = Pad-Right $p.name 22
        $titleTrunc = Pad-Right $p.title 35
        $cpuStr     = Pad-Right "$($p.cpu)" 7
        $memPad     = Pad-Right $memStr 8
        $runPad     = Pad-Right (Format-Time $p.runtimeMin) 7
        $rowBg      = if ($p.isIdle) { "$BG_DARK" } else { "" }
        Write-Host " $rowBg${MUTED}$nameTrunc$RESET$rowBg${MUTED}$titleTrunc$RESET$rowBg${cpuC}${BOLD}$cpuStr$RESET$rowBg$MUTED$memPad$RESET$rowBg$MUTED$runPad$RESET$rowBg$idleStr$RESET"
    }

    # Clean alertedPids for processes that are no longer idle
    $livePids = @($procs | Where-Object { $_.isIdle } | Select-Object -ExpandProperty pid)
    $keys = @($script:AlertedPids.Keys)
    foreach ($k in $keys) { if ($livePids -notcontains $k) { $script:AlertedPids.Remove($k) } }

    # Fill remaining lines to avoid flicker
    $remaining = $maxRows - $shown
    for ($i = 0; $i -lt $remaining; $i++) { Write-Host (" " * $w) }

    # ── FOOTER ──
    Write-Host "$DIM$("─" * $w)$RESET"
    Write-Host " $srvStatus  ${MUTED}อัปเดต: $ts  รีเฟรชทุก ${RefreshSec}s  [Ctrl+C] ออก  [R] รีเฟรช$RESET"
}

# ── MAIN LOOP ───────────────────────────────────────────────
$blink   = 0
$lastFetch = (Get-Date).AddSeconds(-99)
$data    = $null

Write-Host "${CYAN}กำลังเริ่มต้น Battery Console...${RESET}"
Start-Sleep -Milliseconds 500

try {
    while ($true) {
        # Fetch every RefreshSec
        if (((Get-Date) - $lastFetch).TotalSeconds -ge $RefreshSec) {
            $fetched = Get-DataFromServer
            if ($null -eq $fetched) { $fetched = Get-DataLocal }
            $data    = $fetched
            $lastFetch = Get-Date
        }
        if ($data) { Draw-Dashboard $data $blink }
        $blink++
        Start-Sleep -Milliseconds 800

        # Handle key press
        if ([Console]::KeyAvailable) {
            $key = [Console]::ReadKey($true)
            if ($key.Key -eq "R") { $lastFetch = (Get-Date).AddSeconds(-99) }
        }
    }
} finally {
    [Console]::CursorVisible = $true
    [Console]::Clear()
    Write-Host "${GREEN}Battery Console ปิดแล้ว${RESET}"
}
