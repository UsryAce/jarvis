param([int]$Port = 4173)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$accessPath = Join-Path $projectRoot 'data\mobile-access.json'

& (Join-Path $PSScriptRoot 'start-mobile-access.ps1') -Port $Port

$task = Get-ScheduledTask -TaskName 'JarvisAutonomous' -ErrorAction SilentlyContinue
if ($task) {
    Stop-ScheduledTask -TaskName 'JarvisAutonomous' -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1
    Start-ScheduledTask -TaskName 'JarvisAutonomous'
} else {
    & (Join-Path $PSScriptRoot 'install-autostart.ps1')
    Start-ScheduledTask -TaskName 'JarvisAutonomous'
}

$deadline = (Get-Date).AddSeconds(90)
do {
    Start-Sleep -Milliseconds 500
    if (Test-Path -LiteralPath $accessPath) {
        try {
            $access = Get-Content -LiteralPath $accessPath -Raw | ConvertFrom-Json
            if ($access.url -and ([datetime]$access.updated_at) -gt (Get-Date).AddMinutes(-2)) {
                Write-Host "JARVIS REMOTE MOBILE READY: $($access.url)"
                Write-Host 'HTTPS enabled. Operator Unlock remains required.'
                exit 0
            }
        } catch {}
    }
} while ((Get-Date) -lt $deadline)

throw 'Jarvis remote mobile tunnel did not become ready. Check data/mobile-tunnel.log.'
