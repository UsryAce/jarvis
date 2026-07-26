param(
    [ValidateSet('status', 'refresh', 'sync', 'graph', 'vault', 'report', 'search')]
    [string]$Command = 'status',
    [string]$Query = ''
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VaultRoot = if ($env:JARVIS_VAULT_PATH) {
    $env:JARVIS_VAULT_PATH
} else {
    Join-Path $env:USERPROFILE 'OneDrive\Documents\Codex Agent Brain'
}
$GraphRoot = Join-Path $ProjectRoot '.planning\graphs'
$VaultJarvis = Join-Path $VaultRoot 'Projects\Jarvis'
$GsdTools = Join-Path $env:USERPROFILE '.codex\gsd-core\bin\gsd-tools.cjs'
$GraphifyExe = @(
    (Get-Command graphify -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue),
    (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311\Scripts\graphify.exe')
) | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1

function Sync-BrainArtifacts {
    New-Item -ItemType Directory -Path (Join-Path $VaultJarvis 'Graph') -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $GraphRoot 'GRAPH_REPORT.md') -Destination (Join-Path $VaultJarvis 'Graph\Graphify Report.md') -Force
    $graph = Get-Content -Raw (Join-Path $GraphRoot 'graph.json') | ConvertFrom-Json
    [ordered]@{
        generatedAt = (Get-Date).ToString('o')
        sourceCommit = $graph.built_at_commit
        nodes = @($graph.nodes).Count
        edges = @($graph.links).Count
        hyperedges = @($graph.hyperedges).Count
        explorer = (Join-Path $GraphRoot 'graph.html')
    } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $VaultJarvis 'Graph\graph-status.json') -Encoding utf8
}

switch ($Command) {
    'refresh' {
        Push-Location $ProjectRoot
        try {
            if (-not $GraphifyExe) {
                throw 'Graphify executable was not found on PATH or in the managed Python 3.11 Scripts directory.'
            }
            & $GraphifyExe update .
            if ($LASTEXITCODE -ne 0) { throw "Graphify failed with exit code $LASTEXITCODE" }
            Copy-Item -LiteralPath 'graphify-out\graph.json' -Destination '.planning\graphs\graph.json' -Force
            Copy-Item -LiteralPath 'graphify-out\graph.html' -Destination '.planning\graphs\graph.html' -Force
            Copy-Item -LiteralPath 'graphify-out\GRAPH_REPORT.md' -Destination '.planning\graphs\GRAPH_REPORT.md' -Force
            node $GsdTools graphify build snapshot
            Sync-BrainArtifacts
        } finally {
            Pop-Location
        }
    }
    'sync' { Sync-BrainArtifacts }
    'graph' { Invoke-Item (Join-Path $GraphRoot 'graph.html') }
    'vault' { Invoke-Item $VaultRoot }
    'report' { Invoke-Item (Join-Path $GraphRoot 'GRAPH_REPORT.md') }
    'search' {
        if (-not $Query.Trim()) { throw 'Provide -Query for brain search.' }
        $body = @{ query = $Query; limit = 30 } | ConvertTo-Json
        Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/brain/search' -Method Post -ContentType 'application/json' -Body $body
    }
    default {
        try {
            Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/brain' -TimeoutSec 5
        } catch {
            node $GsdTools graphify status
            Write-Output "Vault: $VaultRoot"
        }
    }
}
