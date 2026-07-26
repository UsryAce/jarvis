param([int]$CheckIntervalSeconds = 10)

$ErrorActionPreference = 'Continue'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$frontendRoot = Join-Path $projectRoot 'frontend'
$dataRoot = Join-Path $projectRoot 'data'
$logPath = Join-Path $dataRoot 'supervisor.log'
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

        Start-Sleep -Seconds ([Math]::Max(5, $CheckIntervalSeconds))
    }
} catch {
    Write-SupervisorLog 'SUPERVISOR_FAILURE'
    throw
} finally {
    $mutex.ReleaseMutex()
    $mutex.Dispose()
}
