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
    $preflightCode = @'
import sys
from src.core.audit import AuditService
from src.core.control import ControlService
from src.core.control_store import ControlStore
from src.security.secrets import ProtectedPathAcl

store = None
try:
    store = ControlStore()
    current_sid = ProtectedPathAcl.current_user_sid()
    owner_sid = store.query_value("SELECT owner_sid FROM audit_keyring WHERE state = 'active'")
    if owner_sid is not None and str(owner_sid) != current_sid:
        raise RuntimeError("preflight_identity_mismatch")
    audit = AuditService(store, protector=store.protector)
    if not audit.verify_chain().valid:
        raise RuntimeError("preflight_audit_invalid")
    ControlService(store, audit_service=audit).snapshot()
except Exception:
    sys.exit(20)
finally:
    if store is not None:
        store.close()
'@
    & $PythonPath -c $preflightCode *> $null
    return $LASTEXITCODE
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
        $preflightExit = Invoke-TrustPreflight $python
        if ($preflightExit -ne 0) {
            Write-SupervisorLog "TRUST_PREFLIGHT_FAILED_$preflightExit"
            Start-Sleep -Seconds ([Math]::Max(5, $CheckIntervalSeconds))
            continue
        }

        if (-not (Test-Port 8000)) {
            Start-Process -FilePath $python -ArgumentList '-m','uvicorn','src.api.server:app','--host','127.0.0.1','--port','8000' -WorkingDirectory $projectRoot -WindowStyle Hidden | Out-Null
            Write-SupervisorLog 'BACKEND_START_REQUESTED'
            for ($attempt = 0; $attempt -lt 20 -and -not (Test-BackendTrustReady); $attempt++) {
                Start-Sleep -Milliseconds 500
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
