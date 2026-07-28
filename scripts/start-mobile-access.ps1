param([int]$Port = 4173)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$frontendRoot = Join-Path $projectRoot 'frontend'

function Get-PrimaryLanAddress {
    $candidate = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction Stop |
        Where-Object {
            $_.IPAddress -notlike '127.*' -and
            $_.IPAddress -notlike '169.254.*' -and
            $_.InterfaceAlias -notmatch 'vEthernet|WSL|Loopback|Bluetooth'
        } |
        Sort-Object -Property @{ Expression = { if ($_.PrefixOrigin -eq 'Dhcp') { 0 } else { 1 } } }, InterfaceMetric |
        Select-Object -First 1
    if (-not $candidate) { throw 'No private LAN IPv4 address was found.' }
    return $candidate.IPAddress
}

function Stop-JarvisListener([int]$ListenerPort, [string]$ExpectedFragment) {
    $listeners = Get-NetTCPConnection -LocalPort $ListenerPort -State Listen -ErrorAction SilentlyContinue
    foreach ($listener in $listeners) {
        $process = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)"
        if ($process.CommandLine -and $process.CommandLine.Contains($ExpectedFragment)) {
            Stop-Process -Id $listener.OwningProcess -Force
        }
    }
}

$lanAddress = Get-PrimaryLanAddress
$origins = @(
    'http://localhost:4173', 'http://127.0.0.1:4173',
    'http://localhost:5173', 'http://127.0.0.1:5173',
    "http://${lanAddress}:$Port"
)
$env:JARVIS_ALLOWED_ORIGINS = $origins -join ','

Stop-JarvisListener -ListenerPort 8000 -ExpectedFragment 'uvicorn src.api.server:app'
Stop-JarvisListener -ListenerPort $Port -ExpectedFragment 'vite'

$python = (Get-Command python -ErrorAction Stop).Source
$npm = (Get-Command npm.cmd -ErrorAction Stop).Source
Start-Process -FilePath $python -ArgumentList '-m','uvicorn','src.api.server:app','--host','127.0.0.1','--port','8000' -WorkingDirectory $projectRoot -WindowStyle Hidden | Out-Null
Start-Process -FilePath $npm -ArgumentList 'run','dev','--','--host','0.0.0.0','--port',"$Port" -WorkingDirectory $frontendRoot -WindowStyle Hidden | Out-Null

$deadline = (Get-Date).AddSeconds(45)
do {
    Start-Sleep -Milliseconds 500
    try { $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 2 } catch { $health = $null }
} while (-not $health -and (Get-Date) -lt $deadline)
if (-not $health) { throw 'Jarvis backend did not become healthy.' }

$url = "http://${lanAddress}:$Port/mobile"
Write-Host "JARVIS LAN MOBILE READY: $url"
Write-Host 'For cellular/remote HTTPS access, use scripts/start-remote-mobile.ps1.'
Write-Host 'Operator Unlock remains required.'
