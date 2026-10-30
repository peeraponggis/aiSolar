# ============================================================================
#  ProInventive -- IP Protection for ALL Programs
#  Copyright (C) 2024-2569 ProInventive. All rights reserved.
#
#  1. Copy lungpee-pdpa.js to each program
#  2. Add PDPA script tag in HTML entry points
#  3. Add copyright header in .py files
#  4. Create VERSION.json + CHANGELOG.md where missing
#
#  Usage:  .\add-ip-protection-all.ps1
# ============================================================================

$ErrorActionPreference = 'Continue'
$Root = 'F:\LocalAI'

function Log($msg, $color='Gray') { Write-Host $msg -ForegroundColor $color }

# ── Programs ──────────────────────────────────────────────────────────────
$Programs = @(
    @{ d="aiSolar\design-auto";  n="Auto Solar Co-pilot Studio (Design Auto)"; v="0.118.0"; html=@("index.html","manual.html") }
    @{ d="battery_info";         n="Battery and System Dashboard"; v="1.3.0"; html=@("battery-dashboard.html","battery-system-spa.html","battery-report.html","console.html") }
    @{ d="cctv\phatchara";       n="Lungpee CCTV Viewer"; v="0.6.0"; html=@("login.html") }
    @{ d="ecu-scanner";          n="Lungpee ECU Scanner"; v="1.0.0"; html=@() }
    @{ d="gas_monitor";          n="GAS Monitor"; v="2.4.0"; html=@() }
    @{ d="remoterAIR";           n="RemoteAIR"; v="1.0.0"; html=@() }
    @{ d="yt";                   n="YT Shorts Automation"; v="2.2.0"; html=@("dashboard.html","gallery.html") }
    @{ d="translation";          n="Local Translator"; v="1.9.0"; html=@("index.html","voice-translator-free.html") }
    @{ d="lungpee-agent";        n="Lungpee Agent"; v="1.6.0"; html=@() }
    @{ d="gateway";              n="Lungpee AI Gateway"; v="1.6.0"; html=@() }
    @{ d="trading";              n="Trading Analytics"; v="1.0.0"; html=@("dashboard.html","number_dashboard.html") }
    @{ d="yk";                   n="Lek Dang (Yeekee)"; v="1.0.0"; html=@("yeekee_predictor_artifact.html") }
    @{ d="multi-tools";          n="Lungpee Multi-Tools"; v="1.0.0"; html=@("index.html") }
    @{ d="project_plan_spa";     n="Project Plan SPA"; v="1.0.0"; html=@("index.html","Solar Feasibility Calculator V4.1.html","site-survey.html","pee_ai.html","solarmatch_by_proinventive_V12.html") }
    @{ d="Thai-Lao";             n="Thai-Lao Dictionary"; v="1.0.0"; html=@("dictionary.html") }
)

$PY_HEADER = "# ============================================================================`n" +
             "# ProInventive Suite`n" +
             "# Copyright (C) 2024-2569 ProInventive. All rights reserved.`n" +
             "#`n" +
             "# PROPRIETARY AND CONFIDENTIAL`n" +
             "# Unauthorized use, copying, or distribution is prohibited.`n" +
             "# Author: Peerapong (Lungpee) -- ProInventive -- giskku@gmail.com`n" +
             "# ============================================================================`n`n"

$PDPA_TAG  = '    <script src="lungpee-pdpa.js"></script>'
$CLOSE_HEAD = '</head>'
$OPEN_BODY  = '<body'

$PdpaSrc = Join-Path $Root 'shared\lungpee-pdpa.js'
$addedPy = 0; $addedHtml = 0; $createdVer = 0

foreach ($prog in $Programs) {
    $dir = Join-Path $Root $prog.d
    if (-not (Test-Path $dir)) { Log "  [!] not found: $($prog.d)" 'Yellow'; continue }

    Log "`n--- $($prog.n) ---" 'Cyan'

    # 1a. Copy lungpee-pdpa.js
    if ($prog.html.Count -gt 0) {
        $dst = Join-Path $dir 'lungpee-pdpa.js'
        if (-not (Test-Path $dst)) {
            Copy-Item $PdpaSrc $dst
            Log "  [+] copy lungpee-pdpa.js" 'Green'
        } else { Log "  [~] lungpee-pdpa.js exists" 'DarkGray' }
    }

    # 1b. Add PDPA tag to HTML entry points
    foreach ($htmlName in $prog.html) {
        $hp = Join-Path $dir $htmlName
        if (-not (Test-Path $hp)) { Log "  [!] not found: $htmlName" 'Yellow'; continue }

        $c = [System.IO.File]::ReadAllText($hp, [System.Text.Encoding]::UTF8)
        if ($c.Contains('lungpee-pdpa.js')) { Log "  [~] PDPA exists: $htmlName" 'DarkGray'; continue }

        $inserted = $false
        if ($c.Contains($CLOSE_HEAD)) {
            $c = $c.Replace($CLOSE_HEAD, "$PDPA_TAG`n$CLOSE_HEAD")
            $inserted = $true
        } elseif ($c.Contains($OPEN_BODY)) {
            $c = $c.Replace($OPEN_BODY, "$PDPA_TAG`n$OPEN_BODY")
            $inserted = $true
        }

        if ($inserted) {
            [System.IO.File]::WriteAllText($hp, $c, [System.Text.Encoding]::UTF8)
            Log "  [+] PDPA -> $htmlName" 'Green'
            $addedHtml++
        } else { Log "  [!] no head/body found: $htmlName" 'Yellow' }
    }

    # 2. Copyright headers in .py files
    $pyFiles = Get-ChildItem $dir -Filter '*.py' -Recurse -ErrorAction SilentlyContinue |
               Where-Object { $_.FullName -notmatch '\.venv|venv|node_modules|dist|build|__pycache__' }

    foreach ($f in $pyFiles) {
        $c = [System.IO.File]::ReadAllText($f.FullName, [System.Text.Encoding]::UTF8)
        if ($c.Contains('Copyright (C) 2024-2569 ProInventive')) { continue }
        $newC = $PY_HEADER + $c
        [System.IO.File]::WriteAllText($f.FullName, $newC, [System.Text.Encoding]::UTF8)
        Log "  [+] (c) $($f.Name)" 'Green'
        $addedPy++
    }

    # 3. Create VERSION.json + CHANGELOG.md if missing
    $verPath = Join-Path $dir 'VERSION.json'
    $chgPath = Join-Path $dir 'CHANGELOG.md'

    if (-not (Test-Path $verPath)) {
        $vj = '{"name":"' + $prog.n + '","version":"' + $prog.v + '","created":"2569-10-30","updated":"2569-10-30","author":"Lungpee Peerapong - ProInventive","copyright":"Copyright (C) 2024-2569 ProInventive. All rights reserved."}'
        [System.IO.File]::WriteAllText($verPath, $vj, [System.Text.Encoding]::UTF8)
        Log "  [+] VERSION.json ($($prog.v))" 'Green'
        $createdVer++
    } else { Log "  [~] VERSION.json exists ($((Get-Content $verPath | ConvertFrom-Json).version))" 'DarkGray' }

    if (-not (Test-Path $chgPath)) {
        $cl = "# Changelog -- $($prog.n)`n# by Lungpee Peerapong - ProInventive`n`n## [$($prog.v)] -- 2569-10-30`n### IP Protection + Version Tracking`n- Added copyright headers`n- Added PDPA consent modal`n- Started VERSION.json tracking`n"
        [System.IO.File]::WriteAllText($chgPath, $cl, [System.Text.Encoding]::UTF8)
        Log "  [+] CHANGELOG.md" 'Green'
    } else { Log "  [~] CHANGELOG.md exists" 'DarkGray' }
}

# Summary
Write-Host "`n=============================================" -ForegroundColor Cyan
Write-Host "IP Protection Complete" -ForegroundColor Green
Write-Host "  Python copyright headers: $addedPy files"
Write-Host "  HTML PDPA script tags:    $addedHtml files"
Write-Host "  VERSION.json created:     $createdVer programs"
