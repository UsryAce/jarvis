$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

function Stop-JarvisBackend {
    $listeners = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
    foreach ($listener in $listeners) {
        $process = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)"
        if ($process.CommandLine -and $process.CommandLine.Contains('uvicorn src.api.server:app')) {
            Stop-Process -Id $listener.OwningProcess -Force
        }
    }
}

$task = Get-ScheduledTask -TaskName 'JarvisAutonomous' -ErrorAction SilentlyContinue
if ($task) { Stop-ScheduledTask -TaskName 'JarvisAutonomous' -ErrorAction SilentlyContinue }
Stop-JarvisBackend
Start-Sleep -Seconds 2

Push-Location -LiteralPath $projectRoot
try {
    Write-Host 'Create a new JARVIS Operator Unlock value (minimum 16 characters).'
    Write-Host 'Input is hidden and only a salted verifier will be stored.'
    python -m src.cli.main trust bootstrap
    if ($LASTEXITCODE -ne 0) { throw 'Operator access reset was not completed.' }
} finally {
    Pop-Location
    if ($task) { Start-ScheduledTask -TaskName 'JarvisAutonomous' }
}

Write-Host 'JARVIS OPERATOR ACCESS RESET COMPLETE.'
Write-Host 'Open Jarvis, unlock with the new value, then use the authenticated Reset control.'
