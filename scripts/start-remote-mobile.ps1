param([int]$Port = 4173)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$accessPath = Join-Path $projectRoot 'data\mobile-access.json'
$requestStartedAt = (Get-Date).ToUniversalTime()

function Test-BackendRuntimeReady {
    try {
        $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 2
        return (
            $health.status -eq 'ready' -and
            [bool]$health.initialized -and
            [bool]$health.runtime_ready
        )
    } catch {
        return $false
    }
}

function Test-RemoteOriginApiReady([string]$Origin) {
    if ($Origin -notmatch '^https://[a-z0-9-]+\.trycloudflare\.com$') { return $false }
    if (-not (Test-BackendRuntimeReady)) { return $false }

    # Vite handles public OPTIONS requests itself. Check the backend's exact
    # origin authorization locally, then check that the public /api proxy
    # reaches the protected backend (401 JSON is expected without a session).
    try {
        $headers = @{
            Origin = $Origin
            'Access-Control-Request-Method' = 'POST'
            'Access-Control-Request-Headers' = 'content-type,x-jarvis-csrf'
        }
        $preflight = Invoke-WebRequest -UseBasicParsing -Method Options `
            -Uri 'http://127.0.0.1:8000/api/auth/unlock' -Headers $headers -TimeoutSec 5
        if (
            $preflight.StatusCode -notin @(200, 204) -or
            [string]$preflight.Headers['Access-Control-Allow-Origin'] -ne $Origin
        ) { return $false }
    } catch {
        return $false
    }

    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri "$Origin/api/health" -TimeoutSec 5
        return (
            $response.StatusCode -eq 200 -and
            [string]$response.Headers['Content-Type'] -match '^application/json'
        )
    } catch {
        $errorResponse = $_.Exception.Response
        return (
            $errorResponse -and
            [int]$errorResponse.StatusCode -eq 401 -and
            [string]$errorResponse.Headers['Content-Type'] -match '^application/json'
        )
    }
}

& (Join-Path $PSScriptRoot 'start-mobile-access.ps1') -Port $Port
Remove-Item -LiteralPath $accessPath -Force -ErrorAction SilentlyContinue

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
            $origin = [string]$access.tunnel
            $publishedAt = [datetimeoffset]::Parse([string]$access.updated_at).UtcDateTime
            if (
                $access.url -eq "$origin/mobile" -and
                $publishedAt -ge $requestStartedAt -and
                (Test-RemoteOriginApiReady $origin)
            ) {
                Write-Host "JARVIS REMOTE MOBILE READY: $($access.url)"
                Write-Host 'HTTPS enabled. Operator Unlock remains required.'
                exit 0
            }
        } catch {}
    }
} while ((Get-Date) -lt $deadline)

throw 'Jarvis remote mobile tunnel did not become ready. Check data/mobile-tunnel.log.'
