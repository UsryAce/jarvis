param([int]$CheckIntervalSeconds = 10)

$ErrorActionPreference = 'Continue'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$frontendRoot = Join-Path $projectRoot 'frontend'
$dataRoot = Join-Path $projectRoot 'data'
$logPath = Join-Path $dataRoot 'supervisor.log'
$tunnelLogPath = Join-Path $dataRoot 'mobile-tunnel.log'
$mobileAccessPath = Join-Path $dataRoot 'mobile-access.json'
New-Item -ItemType Directory -Path $dataRoot -Force | Out-Null

$createdNew = $false
$mutex = New-Object System.Threading.Mutex($true, 'Local\JarvisAutonomousSupervisor', [ref]$createdNew)
if (-not $createdNew) { exit 0 }

function Write-SupervisorLog([string]$Message) {
    $line = "$(Get-Date -Format o) $Message"
    Add-Content -LiteralPath $logPath -Value $line -Encoding UTF8
}

function Test-Port([int]$Port) {
    return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

function Get-PublishedMobileOrigin {
    if (-not (Test-Path -LiteralPath $mobileAccessPath)) { return $null }
    try {
        $origin = [string](Get-Content -LiteralPath $mobileAccessPath -Raw | ConvertFrom-Json).tunnel
    } catch {
        return $null
    }
    if ($origin -match '^https://[a-z0-9-]+\.trycloudflare\.com$') { return $origin }
    return $null
}

function Set-JarvisAllowedOriginsEnvironment {
    $origins = @(
        'http://localhost:8080',
        'http://127.0.0.1:8080',
        'http://localhost:4173',
        'http://127.0.0.1:4173',
        'http://localhost:5173',
        'http://127.0.0.1:5173'
    )
    $mobileOrigin = Get-PublishedMobileOrigin
    if ($mobileOrigin) { $origins += $mobileOrigin }
    $env:JARVIS_ALLOWED_ORIGINS = $origins -join ','
}

function Restart-JarvisBackendForOriginChange {
    $listeners = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
    foreach ($listener in $listeners) {
        $process = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)" -ErrorAction SilentlyContinue
        if ($process.CommandLine -and $process.CommandLine.Contains('uvicorn src.api.server:app')) {
            Stop-Process -Id $listener.OwningProcess -Force -ErrorAction SilentlyContinue
            Write-SupervisorLog 'BACKEND_RESTARTED_FOR_MOBILE_ORIGIN_CHANGE'
        }
    }
}

function Get-CloudflaredPath {
    $candidates = @(
        (Join-Path $env:ProgramFiles 'cloudflared\cloudflared.exe'),
        (Join-Path ${env:ProgramFiles(x86)} 'cloudflared\cloudflared.exe'),
        (Join-Path $env:USERPROFILE '.cloudflared\cloudflared.exe')
    )
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) { return $candidate }
    }
    $command = Get-Command cloudflared.exe -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    return $null
}

function Get-JarvisTunnelProcess {
    return Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Name -eq 'cloudflared.exe' -and
            $_.CommandLine -match 'tunnel' -and
            $_.CommandLine -match '127\.0\.0\.1:4173'
        } |
        Select-Object -First 1
}

function Publish-MobileAccess {
    if (-not (Test-Path -LiteralPath $tunnelLogPath)) { return $false }
    $content = Get-Content -LiteralPath $tunnelLogPath -Raw -ErrorAction SilentlyContinue
    $match = [regex]::Match($content, 'https://[a-z0-9-]+\.trycloudflare\.com')
    if (-not $match.Success) { return $false }
    $existingTunnel = $null
    if (Test-Path -LiteralPath $mobileAccessPath) {
        try {
            $existingTunnel = (Get-Content -LiteralPath $mobileAccessPath -Raw | ConvertFrom-Json).tunnel
        } catch {}
    }
    $originChanged = $existingTunnel -ne $match.Value
    if ($originChanged) {
        try {
            $probe = Invoke-WebRequest -UseBasicParsing "$($match.Value)/mobile" -TimeoutSec 3
            if ($probe.StatusCode -ne 200) { return $false }
        } catch {
            return $false
        }
    }
    [ordered]@{
        url = "$($match.Value)/mobile"
        tunnel = $match.Value
        updated_at = (Get-Date).ToUniversalTime().ToString('o')
        security = 'operator-unlock-required'
    } | ConvertTo-Json | Set-Content -LiteralPath $mobileAccessPath -Encoding UTF8
    if ($originChanged) { Restart-JarvisBackendForOriginChange }
    return $true
}

function Ensure-RemoteMobileTunnel {
    if (Get-JarvisTunnelProcess) {
        [void](Publish-MobileAccess)
        return
    }
    $cloudflared = Get-CloudflaredPath
    if (-not $cloudflared) {
        Write-SupervisorLog 'MOBILE_TUNNEL_UNAVAILABLE_CLOUDFLARED_MISSING'
        return
    }
    Remove-Item -LiteralPath $tunnelLogPath -Force -ErrorAction SilentlyContinue
    Start-Process -FilePath $cloudflared `
        -ArgumentList 'tunnel','--no-autoupdate','--protocol','http2','--metrics','127.0.0.1:20242','--url','http://127.0.0.1:4173' `
        -RedirectStandardError $tunnelLogPath `
        -WindowStyle Hidden | Out-Null
    Write-SupervisorLog 'MOBILE_TUNNEL_START_REQUESTED'
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        Start-Sleep -Seconds 1
        if (Publish-MobileAccess) {
            Write-SupervisorLog 'MOBILE_TUNNEL_READY'
            return
        }
    }
    Write-SupervisorLog 'MOBILE_TUNNEL_URL_PENDING'
}

function Invoke-TrustPreflight([string]$PythonPath) {
    Push-Location -LiteralPath $projectRoot
    try {
        & $PythonPath -m src.cli.main trust verify --quiet *> $null
        return $LASTEXITCODE
    } finally {
        Pop-Location
    }
}

function Invoke-CredentialCutoverStatus([string]$PythonPath) {
    Push-Location -LiteralPath $projectRoot
    try {
        & $PythonPath -m src.cli.main credentials cutover-status --provider nvidia --quiet *> $null
        return $LASTEXITCODE
    } finally {
        Pop-Location
    }
}

function Confirm-SanitizedRestart([string]$PythonPath) {
    Push-Location -LiteralPath $projectRoot
    try {
        & $PythonPath -m src.cli.main credentials mark-restarted --provider nvidia *> $null
        return $LASTEXITCODE
    } finally {
        Pop-Location
    }
}

function Remove-LegacyNvidiaEnvironment {
    if (Test-Path Env:NVIDIA_API_KEY) {
        Remove-Item Env:NVIDIA_API_KEY
    }
}

function Test-BackendTrustReady {
    try {
        $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health' -Method Get -TimeoutSec 2
        return $health.status -in @(
            'ready', 'paused', 'cancel_requested', 'emergency_stopped',
            'stopping', 'stopped', 'partial', 'unconfirmed'
        )
    } catch {
        return $false
    }
}

try {
    Write-SupervisorLog 'SUPERVISOR_STARTED'
    while ($true) {
        $python = (Get-Command python -ErrorAction Stop).Source
        if (-not (Test-Port 8000)) {
            # The CLI owns the trust store only while the backend is stopped.
            # This verifies the scheduled/current user SID through DPAPI without
            # passing any credential or environment content to a child command.
            $preflightExit = Invoke-TrustPreflight $python
            if ($preflightExit -ne 0) {
                Write-SupervisorLog "TRUST_PREFLIGHT_FAILED_$preflightExit"
                Start-Sleep -Seconds ([Math]::Max(5, $CheckIntervalSeconds))
                continue
            }

            $cutoverExit = Invoke-CredentialCutoverStatus $python
            if ($cutoverExit -eq 31) {
                # No backend owns control.db at this point. Clear inherited
                # plaintext before acknowledging and launching the fresh process.
                Remove-LegacyNvidiaEnvironment
                $ackExit = Confirm-SanitizedRestart $python
                if ($ackExit -ne 0) {
                    Write-SupervisorLog "CREDENTIAL_RESTART_ACK_FAILED_$ackExit"
                    Start-Sleep -Seconds ([Math]::Max(5, $CheckIntervalSeconds))
                    continue
                }
                Write-SupervisorLog 'CREDENTIAL_CUTOVER_RESTART_REQUESTED'
            } elseif ($cutoverExit -eq 0) {
                Remove-LegacyNvidiaEnvironment
            } elseif ($cutoverExit -ne 30) {
                Write-SupervisorLog "CREDENTIAL_CUTOVER_PREFLIGHT_FAILED_$cutoverExit"
                Start-Sleep -Seconds ([Math]::Max(5, $CheckIntervalSeconds))
                continue
            }

            Set-JarvisAllowedOriginsEnvironment
            Start-Process -FilePath $python -ArgumentList '-m','uvicorn','src.api.server:app','--host','127.0.0.1','--port','8000' -WorkingDirectory $projectRoot -WindowStyle Hidden | Out-Null
            Write-SupervisorLog 'BACKEND_START_REQUESTED'
            for ($attempt = 0; $attempt -lt 20 -and -not (Test-BackendTrustReady); $attempt++) {
                Start-Sleep -Milliseconds 500
            }
            if ($cutoverExit -in @(0, 31) -and (Test-BackendTrustReady)) {
                Write-SupervisorLog 'CREDENTIAL_CUTOVER_RESTART_VERIFIED'
            }
        }

        if (-not (Test-BackendTrustReady)) {
            # A listener is transport evidence only; it is not trust readiness.
            Write-SupervisorLog 'BACKEND_TRUST_NOT_READY'
            Start-Sleep -Seconds ([Math]::Max(5, $CheckIntervalSeconds))
            continue
        }

        if (-not (Test-Port 4173)) {
            $npm = (Get-Command npm.cmd -ErrorAction Stop).Source
            Start-Process -FilePath $npm -ArgumentList 'run','dev','--','--host','127.0.0.1','--port','4173' -WorkingDirectory $frontendRoot -WindowStyle Hidden | Out-Null
            Write-SupervisorLog 'DASHBOARD_START_REQUESTED'
        }

        if (Test-Port 4173) {
            Ensure-RemoteMobileTunnel
        }

        Start-Sleep -Seconds ([Math]::Max(5, $CheckIntervalSeconds))
    }
} catch {
    Write-SupervisorLog 'SUPERVISOR_FAILURE'
    throw
} finally {
    $mutex.ReleaseMutex()
    $mutex.Dispose()
}
