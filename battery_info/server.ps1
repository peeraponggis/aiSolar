# ============================================================
# Battery & Process Monitor Server  |  Port 8765
# F:\LocalAI\battery_info\server.ps1
# ============================================================
param([int]$Port = 8765)

$script:History  = @{}
$script:PublicIp   = $null
$script:PublicIpAt = [datetime]::MinValue
$script:Settings = @{ idleMinutes = 30; cpuThreshold = 2.0 }
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Temp files (Add-Type compile output, Wi-Fi profile XML) must stay on F:
$TmpDir = Join-Path $ScriptDir 'tmp'
if (-not (Test-Path $TmpDir)) { New-Item -ItemType Directory -Path $TmpDir | Out-Null }
$env:TMP  = $TmpDir
$env:TEMP = $TmpDir

$script:WlanReady   = $false
$script:Profiles    = @()
$script:ProfilesAt  = [datetime]::MinValue
try {
    Add-Type -ErrorAction Stop -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class WlanNative {
    [DllImport("wlanapi.dll")] static extern uint WlanOpenHandle(uint ver, IntPtr res, out uint neg, out IntPtr h);
    [DllImport("wlanapi.dll")] static extern uint WlanCloseHandle(IntPtr h, IntPtr res);
    [DllImport("wlanapi.dll")] static extern uint WlanEnumInterfaces(IntPtr h, IntPtr res, out IntPtr list);
    [DllImport("wlanapi.dll")] static extern uint WlanScan(IntPtr h, ref Guid g, IntPtr ssid, IntPtr ie, IntPtr res);
    [DllImport("wlanapi.dll")] static extern void WlanFreeMemory(IntPtr p);
    public static int Scan() {
        uint neg; IntPtr h;
        if (WlanOpenHandle(2, IntPtr.Zero, out neg, out h) != 0) return -1;
        try {
            IntPtr list;
            if (WlanEnumInterfaces(h, IntPtr.Zero, out list) != 0) return -2;
            try {
                int n = Marshal.ReadInt32(list), ok = 0;
                for (int i = 0; i < n; i++) {
                    // WLAN_INTERFACE_INFO = GUID(16) + WCHAR[256](512) + state(4) = 532 bytes, list header = 8 bytes
                    Guid g = (Guid)Marshal.PtrToStructure(new IntPtr(list.ToInt64() + 8 + i * 532), typeof(Guid));
                    if (WlanScan(h, ref g, IntPtr.Zero, IntPtr.Zero, IntPtr.Zero) == 0) ok++;
                }
                return ok;
            } finally { WlanFreeMemory(list); }
        } finally { WlanCloseHandle(h, IntPtr.Zero); }
    }
}
'@
    $script:WlanReady = $true
} catch {}

# --- check port free ---
$inUse = (Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue | Measure-Object).Count -gt 0
if ($inUse) { Write-Host "Port $Port already in use - server may already be running."; exit 0 }

$listener = New-Object System.Net.HttpListener
$listener.Prefixes.Add("http://localhost:$Port/")
try { $listener.Start() } catch { Write-Host "Cannot start listener: $_"; exit 1 }
Write-Host "[$(Get-Date -f 'HH:mm:ss')] Battery Monitor listening on http://localhost:$Port/"

# ── Battery ──────────────────────────────────────────────────
function Get-Battery {
    try {
        $b = Get-WmiObject Win32_Battery -ErrorAction Stop
        if (-not $b) { return $null }
        @{
            level      = [int]$b.EstimatedChargeRemaining
            status     = [int]$b.BatteryStatus
            runtime    = [int]$b.EstimatedRunTime
            charging   = $b.BatteryStatus -in @(2,6,7,8,9)
            designCap  = 52500
            fullCap    = 44800
            healthPct  = 85.3
            cycles     = 407
            cycleRated = 1000
        }
    } catch { $null }
}

# ── Processes ────────────────────────────────────────────────
function Get-Processes {
    $now   = Get-Date
    $cores = [math]::Max(1, [int]$env:NUMBER_OF_PROCESSORS)
    $livePids = @{}

    $rawProcs = @()
    try { $rawProcs = Get-Process -ErrorAction SilentlyContinue |
        Where-Object { $_.MainWindowTitle -ne '' -and $_.Id -gt 4 } } catch {}

    $out = foreach ($p in $rawProcs) {
        $key = "$($p.Id)"
        $livePids[$key] = $true

        # CPU %
        $cpuPct = 0.0
        if ($script:History.ContainsKey($key)) {
            $h = $script:History[$key]
            $elapsed = ($now - $h.Time).TotalSeconds
            if ($elapsed -gt 0.5) {
                $delta  = [math]::Max(0, $p.CPU - $h.CpuTotal)
                $cpuPct = [math]::Round($delta / $elapsed / $cores * 100, 1)
            }
        }

        # Idle tracking
        $idleMin = 0
        if ($script:History.ContainsKey($key)) {
            $h = $script:History[$key]
            if ($cpuPct -lt $script:Settings.cpuThreshold) {
                if ($null -eq $h.IdleStart) { $script:History[$key].IdleStart = $now }
                $idleMin = [math]::Round(($now - $script:History[$key].IdleStart).TotalMinutes)
            } else {
                $script:History[$key].IdleStart = $null
            }
            $script:History[$key].CpuTotal = $p.CPU
            $script:History[$key].Time     = $now
        } else {
            $script:History[$key] = @{ CpuTotal=$p.CPU; Time=$now; IdleStart=$now }
        }

        $runtimeMin = 0
        try { if ($p.StartTime) { $runtimeMin = [math]::Round(($now - $p.StartTime).TotalMinutes) } } catch {}

        $title = $p.MainWindowTitle
        if ($title.Length -gt 55) { $title = $title.Substring(0,52)+'...' }

        [PSCustomObject]@{
            pid        = [int]$p.Id
            name       = $p.ProcessName
            title      = $title
            cpu        = $cpuPct
            memMB      = [math]::Round($p.WorkingSet64 / 1MB, 0)
            runtimeMin = $runtimeMin
            idleMin    = $idleMin
            isIdle     = ($idleMin -ge $script:Settings.idleMinutes)
        }
    }

    # Clean stale history
    foreach ($k in @($script:History.Keys)) {
        if (-not $livePids.ContainsKey($k)) { $script:History.Remove($k) }
    }

    @($out | Sort-Object memMB -Descending)
}

# ── Thermal & fan assessment ─────────────────────────────────
# Fan RPM is not exposed via WMI on this machine, so fan status is inferred from temperature, CPU load and throttling.
function Get-Thermal {
    try {
        $tz = Get-CimInstance Win32_PerfFormattedData_Counters_ThermalZoneInformation -ErrorAction Stop |
              Sort-Object Temperature -Descending | Select-Object -First 1
        if (-not $tz) { return $null }
        $tempC  = [math]::Round($tz.Temperature - 273.15, 1)
        $load   = [int](Get-WmiObject Win32_Processor | Measure-Object LoadPercentage -Average).Average
        $throttled = $tz.PercentPassiveLimit -lt 100

        if ($tempC -ge 95 -or ($tempC -ge 90 -and $load -lt 40)) {
            $status = 'critical'
        } elseif ($tempC -ge 85 -and ($load -lt 40 -or $throttled)) {
            $status = 'abnormal'
        } elseif ($tempC -ge 80) {
            $status = 'warn'
        } else {
            $status = 'normal'
        }

        [PSCustomObject]@{
            tempC     = $tempC
            cpuLoad   = $load
            throttled = $throttled
            status    = $status
        }
    } catch { $null }
}

# ── Network ──────────────────────────────────────────────────
function Get-WifiInfo {
    $out = netsh wlan show interfaces 2>$null
    if (-not $out) { return $null }
    $h = @{}
    foreach ($line in $out) {
        if ($line -match '^\s*([^:]+?)\s*:\s*(.*?)\s*$' -and -not $h.ContainsKey($matches[1])) {
            $h[$matches[1]] = $matches[2]
        }
    }
    if (-not $h.ContainsKey('SSID')) { return $null }
    [PSCustomObject]@{
        ssid   = $h['SSID']
        band   = $h['Band']
        channel = $h['Channel']
        signal = $h['Signal']
        rssi   = $h['Rssi']
        rxRate = $h['Receive rate (Mbps)']
        txRate = $h['Transmit rate (Mbps)']
        auth   = $h['Authentication']
        state  = $h['State']
    }
}

function Get-WifiNetworks {
    $lines = netsh wlan show networks mode=bssid 2>$null
    $nets = @(); $cur = $null; $best = $false
    foreach ($l in $lines) {
        if ($l -match '^SSID \d+\s*:\s?(.*)$') {
            if ($cur) { $nets += [PSCustomObject]$cur }
            $cur = [ordered]@{ ssid = $matches[1].Trim(); auth = ''; enc = ''; signal = 0; band = ''; channel = ''; aps = 0 }
            continue
        }
        if (-not $cur) { continue }
        if     ($l -match '^\s+Authentication\s+:\s*(.+?)\s*$') { $cur.auth = $matches[1] }
        elseif ($l -match '^\s+Encryption\s+:\s*(.+?)\s*$')     { $cur.enc  = $matches[1] }
        elseif ($l -match '^\s+BSSID \d+\s+:')                  { $cur.aps++ }
        elseif ($l -match '^\s+Signal\s+:\s*(\d+)%') {
            $s = [int]$matches[1]; $best = $s -gt $cur.signal
            if ($best) { $cur.signal = $s }
        }
        elseif ($best -and $l -match '^\s+Band\s+:\s*(.+?)\s*$')  { $cur.band = $matches[1] }
        elseif ($best -and $l -match '^\s+Channel\s+:\s*(\d+)')   { $cur.channel = $matches[1] }
    }
    if ($cur) { $nets += [PSCustomObject]$cur }
    $nets | Where-Object { $_.ssid } | Group-Object ssid | ForEach-Object {
        $_.Group | Sort-Object signal -Descending | Select-Object -First 1
    } | Sort-Object signal -Descending
}

function Get-SavedProfiles([switch]$Force) {
    if ($Force -or ((Get-Date) - $script:ProfilesAt).TotalSeconds -gt 30) {
        $script:Profiles = @(netsh wlan show profiles 2>$null |
            Where-Object { $_ -match '(All User|Current User|User) Profile\s*:\s*(.+?)\s*$' } |
            ForEach-Object { $matches[2] } | Sort-Object -Unique)
        $script:ProfilesAt = Get-Date
    }
    $script:Profiles
}

function Get-WifiReport {
    $scanned = if ($script:WlanReady) { [WlanNative]::Scan() } else { -1 }
    $info  = Get-WifiInfo
    $saved = Get-SavedProfiles
    $top = @(Get-WifiNetworks | Select-Object -First 5 | ForEach-Object {
        [PSCustomObject]@{
            ssid      = $_.ssid
            signal    = $_.signal
            auth      = $_.auth
            enc       = $_.enc
            band      = $_.band
            channel   = $_.channel
            aps       = $_.aps
            saved     = $saved -contains $_.ssid
            connected = ($info -and $info.state -eq 'connected' -and $info.ssid -eq $_.ssid)
        }
    })
    [PSCustomObject]@{
        current  = if ($info -and $info.state -eq 'connected') { $info.ssid } else { $null }
        scanOk   = $scanned -gt 0
        networks = $top
        saved    = @($saved)
    }
}

# Reveals the saved password for ONE network this laptop already connected to (same as Windows Settings "Show characters").
# One SSID per call, on explicit user click; the temporary XML export is deleted immediately.
function Get-SavedKey([string]$name) {
    if ([string]::IsNullOrWhiteSpace($name) -or $name.Contains('"')) { return $null }
    if (-not ((Get-SavedProfiles) -contains $name)) { return $null }
    $dir = Join-Path $TmpDir ('k_' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $dir | Out-Null
    try {
        netsh wlan export profile name="$name" key=clear folder="$dir" | Out-Null
        $f = Get-ChildItem $dir -Filter *.xml | Select-Object -First 1
        if (-not $f) { return $null }
        $x = [xml][IO.File]::ReadAllText($f.FullName)
        [PSCustomObject]@{
            name = $x.WLANProfile.name
            auth = $x.WLANProfile.MSM.security.authEncryption.authentication
            key  = $x.WLANProfile.MSM.security.sharedKey.keyMaterial
        }
    } finally { Remove-Item $dir -Recurse -Force -ErrorAction SilentlyContinue }
}

function Connect-Wifi([string]$ssid, [string]$password) {
    if ([string]::IsNullOrWhiteSpace($ssid) -or $ssid.Contains('"')) { return @{ ok = $false; code = 'invalid' } }
    $saved = (Get-SavedProfiles -Force) -contains $ssid
    $created = $false

    if (-not $saved -or $password) {
        $net = Get-WifiNetworks | Where-Object { $_.ssid -eq $ssid } | Select-Object -First 1
        if (-not $net) { return @{ ok = $false; code = 'notfound' } }
        $authEnc = switch -Regex ($net.auth) {
            'Enterprise'    { $null; break }
            'WPA3'          { 'WPA3SAE','AES'; break }
            'WPA2-Personal' { 'WPA2PSK','AES'; break }
            'WPA-Personal'  { 'WPAPSK','AES'; break }
            '^Open$'        { 'open','none'; break }
            default         { $null }
        }
        if (-not $authEnc) { return @{ ok = $false; code = 'unsupported'; auth = $net.auth } }
        $isOpen = $authEnc[0] -eq 'open'
        if (-not $isOpen -and [string]::IsNullOrEmpty($password)) { return @{ ok = $false; code = 'needpw' } }

        $e = [Security.SecurityElement]::Escape($ssid)
        $shared = if ($isOpen) { '' } else {
            "<sharedKey><keyType>passPhrase</keyType><protected>false</protected><keyMaterial>$([Security.SecurityElement]::Escape($password))</keyMaterial></sharedKey>"
        }
        $xml = "<?xml version=`"1.0`"?><WLANProfile xmlns=`"http://www.microsoft.com/networking/WLAN/profile/v1`"><name>$e</name><SSIDConfig><SSID><name>$e</name></SSID></SSIDConfig><connectionType>ESS</connectionType><connectionMode>auto</connectionMode><MSM><security><authEncryption><authentication>$($authEnc[0])</authentication><encryption>$($authEnc[1])</encryption><useOneX>false</useOneX></authEncryption>$shared</security></MSM></WLANProfile>"
        $file = Join-Path $TmpDir ('p_' + [guid]::NewGuid().ToString('N') + '.xml')
        try {
            [IO.File]::WriteAllText($file, $xml, (New-Object Text.UTF8Encoding $false))
            netsh wlan add profile filename="$file" | Out-Null
            if ($LASTEXITCODE -ne 0) { netsh wlan add profile filename="$file" user=current | Out-Null }
        } finally { Remove-Item $file -Force -ErrorAction SilentlyContinue }
        if ($LASTEXITCODE -ne 0) { return @{ ok = $false; code = 'profile' } }
        $created = -not $saved
    }

    netsh wlan connect name="$ssid" ssid="$ssid" | Out-Null
    for ($i = 0; $i -lt 15; $i++) {
        Start-Sleep -Seconds 1
        $info = Get-WifiInfo
        if ($info -and $info.state -eq 'connected' -and $info.ssid -eq $ssid) {
            Get-SavedProfiles -Force | Out-Null
            return @{ ok = $true; ssid = $ssid }
        }
    }
    if ($created) { netsh wlan delete profile name="$ssid" | Out-Null; Get-SavedProfiles -Force | Out-Null }
    @{ ok = $false; code = 'failed' }
}

# Wi-Fi endpoints expose passwords and can switch networks, so only the dashboard's own page may call them.
function Test-SameOrigin($req) {
    $origin = $req.Headers['Origin']
    if ($origin -and $origin -ne "http://localhost:$Port") { return $false }
    $site = $req.Headers['Sec-Fetch-Site']
    if ($site -and $site -notin @('same-origin', 'none')) { return $false }
    $true
}

function Read-JsonBody($req) {
    $reader = New-Object System.IO.StreamReader($req.InputStream, [Text.Encoding]::UTF8)
    try { $reader.ReadToEnd() | ConvertFrom-Json } finally { $reader.Dispose() }
}

function Get-PingStats([string]$target) {
    $pinger = New-Object System.Net.NetworkInformation.Ping
    $times  = @()
    for ($n = 0; $n -lt 4; $n++) {
        try {
            $reply = $pinger.Send($target, 1000)
            if ($reply.Status -eq 'Success') { $times += [double]$reply.RoundtripTime }
        } catch {}
    }
    $pinger.Dispose()
    $loss    = [math]::Round((1 - $times.Count / 4) * 100)
    if ($times.Count -eq 0) {
        return [PSCustomObject]@{ target=$target; min=$null; avg=$null; max=$null; jitter=$null; loss=$loss }
    }
    $jitter = 0
    if ($times.Count -gt 1) {
        $diffs = @()
        for ($i = 1; $i -lt $times.Count; $i++) { $diffs += [math]::Abs($times[$i] - $times[$i-1]) }
        $jitter = ($diffs | Measure-Object -Average).Average
    }
    [PSCustomObject]@{
        target = $target
        min    = ($times | Measure-Object -Minimum).Minimum
        avg    = [math]::Round(($times | Measure-Object -Average).Average, 1)
        max    = ($times | Measure-Object -Maximum).Maximum
        jitter = [math]::Round($jitter, 1)
        loss   = $loss
    }
}

function Get-NetReport {
    # Pick the real active adapter: a default-route interface that is Up and (for Wi-Fi) actually connected.
    # Avoids picking a radio-disconnected Wi-Fi or a VPN tunnel when a LAN cable is the live link.
    $routes = @(Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue |
                Sort-Object { $_.RouteMetric + $_.InterfaceMetric })
    $ad = $null
    foreach ($r in $routes) {
        $a = Get-NetAdapter -InterfaceIndex $r.InterfaceIndex -ErrorAction SilentlyContinue
        if (-not $a -or $a.Status -ne 'Up') { continue }
        if ($a.PhysicalMediaType -eq 'Unspecified') { continue }   # skip VPN tunnels (e.g. Tailscale)
        if ($a.MediaType -eq 'Native 802.11') {
            $wi = Get-WifiInfo
            if (-not ($wi -and $wi.state -eq 'connected')) { continue }   # Wi-Fi radio is off/disconnected
        }
        $ad = $a; break
    }
    if (-not $ad -and $routes.Count) { $ad = Get-NetAdapter -InterfaceIndex $routes[0].InterfaceIndex -ErrorAction SilentlyContinue }
    $cfg = if ($ad) { Get-NetIPConfiguration -InterfaceIndex $ad.ifIndex -ErrorAction SilentlyContinue } else { $null }
    $st  = if ($ad) { Get-NetAdapterStatistics -Name $ad.Name -ErrorAction SilentlyContinue } else { $null }

    $gateway = if ($cfg -and $cfg.IPv4DefaultGateway) { $cfg.IPv4DefaultGateway[0].NextHop } else { $null }
    $localIp = if ($cfg -and $cfg.IPv4Address) { $cfg.IPv4Address[0].IPAddress } else { $null }
    $dns = @()
    if ($cfg) { $dns = @($cfg.DNSServer.ServerAddresses | Where-Object { $_ -match '^\d+\.' }) }

    if (((Get-Date) - $script:PublicIpAt).TotalMinutes -gt 10) {
        try { $script:PublicIp = (Invoke-RestMethod 'https://api.ipify.org?format=json' -TimeoutSec 5).ip } catch { $script:PublicIp = $null }
        $script:PublicIpAt = Get-Date
    }

    $sw = [Diagnostics.Stopwatch]::StartNew()
    try { Resolve-DnsName -Name ("{0}.google.com" -f [guid]::NewGuid().ToString('N')) -Type A -DnsOnly -QuickTimeout -ErrorAction Stop | Out-Null } catch {}
    $dnsMs = [math]::Round($sw.Elapsed.TotalMilliseconds, 1)

    $targets = @()
    if ($gateway) { $targets += $gateway }
    $targets += '1.1.1.1', '8.8.8.8'
    $pings = @($targets | ForEach-Object { Get-PingStats $_ })

    $isWifiAd = $ad -and $ad.MediaType -eq 'Native 802.11'
    $wifi  = if ($isWifiAd) { Get-WifiInfo } else { $null }

    # Wired/Ethernet detail (shown when the active adapter is a cable, not Wi-Fi)
    $linkType = 'other'
    $wired = $null
    if ($ad) {
        if ($isWifiAd) { $linkType = 'wifi' }
        elseif ($ad.PhysicalMediaType -eq '802.3' -or $ad.MediaType -eq '802.3') {
            $linkType = 'wired'
            $wired = [PSCustomObject]@{
                name      = $ad.Name
                adapter   = $ad.InterfaceDescription
                linkSpeed = $ad.LinkSpeed
                duplex    = if ($ad.FullDuplex) { 'Full Duplex' } else { 'Half Duplex' }
                mtu       = $ad.MtuSize
                mac       = $ad.MacAddress
                driver    = $ad.DriverVersion
                state     = $ad.Status
            }
        }
    }

    [PSCustomObject]@{
        adapter   = if ($ad) { $ad.InterfaceDescription } else { $null }
        linkSpeed = if ($ad) { $ad.LinkSpeed } else { $null }
        linkType  = $linkType
        localIp   = $localIp
        publicIp  = $script:PublicIp
        gateway   = $gateway
        dns       = $dns
        dnsMs     = $dnsMs
        rxMB      = if ($st) { [math]::Round($st.ReceivedBytes / 1MB, 1) } else { $null }
        txMB      = if ($st) { [math]::Round($st.SentBytes / 1MB, 1) } else { $null }
        pings     = $pings
        wifi      = $wifi
        wired     = $wired
        timestamp = (Get-Date -Format 'HH:mm:ss')
    }
}

# ── HTTP helpers ─────────────────────────────────────────────
function Send-Response($res, $status, $mime, $body, [switch]$Private) {
    $res.StatusCode = $status
    $res.ContentType = $mime
    if (-not $Private) {
        $res.Headers.Add('Access-Control-Allow-Origin','*')
        $res.Headers.Add('Access-Control-Allow-Methods','GET,POST,OPTIONS')
        $res.Headers.Add('Access-Control-Allow-Headers','Content-Type')
    }
    $res.Headers.Add('Cache-Control','no-store')
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($body)
    $res.ContentLength64 = $bytes.Length
    $res.OutputStream.Write($bytes, 0, $bytes.Length)
    $res.OutputStream.Close()
}

function Send-File($res, $filePath) {
    if (Test-Path $filePath) {
        $bytes = [System.IO.File]::ReadAllBytes($filePath)
        $ext   = [System.IO.Path]::GetExtension($filePath).ToLower()
        $mime  = switch ($ext) { '.html'{'text/html; charset=utf-8'} '.ico'{'image/x-icon'} default{'application/octet-stream'} }
        $res.StatusCode = 200
        $res.ContentType = $mime
        $res.Headers.Add('Cache-Control','no-cache')
        $res.ContentLength64 = $bytes.Length
        $res.OutputStream.Write($bytes, 0, $bytes.Length)
        $res.OutputStream.Close()
    } else { Send-Response $res 404 'text/plain' 'Not found' }
}

# ── Main loop ────────────────────────────────────────────────
while ($listener.IsListening) {
    try {
        $ctx  = $listener.GetContext()
        $req  = $ctx.Request
        $res  = $ctx.Response
        $path = $req.Url.LocalPath

        $isWifi = $path -like '/api/wifi*'
        if ($req.HttpMethod -eq 'OPTIONS') {
            if ($isWifi) { Send-Response $res 403 'text/plain' '' -Private } else { Send-Response $res 200 'text/plain' '' }
            continue
        }
        if ($isWifi -and -not (Test-SameOrigin $req)) { Send-Response $res 403 'text/plain' 'Forbidden' -Private; continue }
        if ($isWifi -and $path -ne '/api/wifi' -and ($req.HttpMethod -ne 'POST' -or $req.ContentType -notlike 'application/json*')) {
            Send-Response $res 405 'text/plain' 'POST application/json only' -Private; continue
        }

        switch ($path) {
            '/api/wifi' {
                Send-Response $res 200 'application/json; charset=utf-8' ((Get-WifiReport) | ConvertTo-Json -Depth 5 -Compress) -Private
            }
            '/api/wifi/key' {
                $b = Read-JsonBody $req
                $k = Get-SavedKey ([string]$b.ssid)
                $out = if ($k) { @{ found = $true; ssid = $k.name; key = $k.key; auth = $k.auth } } else { @{ found = $false } }
                Send-Response $res 200 'application/json; charset=utf-8' ($out | ConvertTo-Json -Compress) -Private
            }
            '/api/wifi/connect' {
                $b = Read-JsonBody $req
                $r = Connect-Wifi ([string]$b.ssid) ([string]$b.password)
                Send-Response $res 200 'application/json; charset=utf-8' ($r | ConvertTo-Json -Compress) -Private
            }
            '/api/status' {
                $procs = Get-Processes
                $data  = @{
                    battery   = Get-Battery
                    thermal   = Get-Thermal
                    processes = $procs
                    idleCount = ($procs | Where-Object { $_.isIdle } | Measure-Object).Count
                    settings  = $script:Settings
                    timestamp = (Get-Date -Format 'HH:mm:ss')
                    serverOk  = $true
                }
                Send-Response $res 200 'application/json; charset=utf-8' ($data | ConvertTo-Json -Depth 6 -Compress)
            }
            '/api/settings' {
                if ($req.HttpMethod -eq 'POST') {
                    $body = (New-Object System.IO.StreamReader($req.InputStream)).ReadToEnd()
                    $s    = $body | ConvertFrom-Json
                    if ($null -ne $s.idleMinutes)  { $script:Settings.idleMinutes  = [int]$s.idleMinutes }
                    if ($null -ne $s.cpuThreshold) { $script:Settings.cpuThreshold = [double]$s.cpuThreshold }
                    Write-Host "[$(Get-Date -f 'HH:mm:ss')] Settings: idle=$($script:Settings.idleMinutes)m cpu=$($script:Settings.cpuThreshold)%"
                }
                Send-Response $res 200 'application/json' '{"ok":true}'
            }
            '/'            { Send-File $res (Join-Path $ScriptDir 'battery-dashboard.html') }
            '/battery'     { Send-File $res (Join-Path $ScriptDir 'battery-dashboard.html') }
            '/console'     { Send-File $res (Join-Path $ScriptDir 'console.html') }
            '/spa'         { Send-File $res (Join-Path $ScriptDir 'battery-system-spa.html') }
            '/api/net'     { Send-Response $res 200 'application/json; charset=utf-8' ((Get-NetReport) | ConvertTo-Json -Depth 6 -Compress) }
            '/battery-report.html' { Send-File $res (Join-Path $ScriptDir 'battery-report.html') }
            '/favicon.ico' { Send-File $res (Join-Path $ScriptDir 'battery.ico') }
            default        { Send-Response $res 404 'text/plain' 'Not found' }
        }
    } catch {
        try { $ctx.Response.OutputStream.Close() } catch {}
    }
}
