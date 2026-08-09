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

function Assert-SafeDirectoryTree {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Path,
        [switch]$Create
    )
    $rootFull = [System.IO.Path]::GetFullPath($Root).TrimEnd('\')
    $pathFull = [System.IO.Path]::GetFullPath($Path).TrimEnd('\')
    if ($pathFull -ne $rootFull -and -not $pathFull.StartsWith($rootFull + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Brain refresh rejected a path outside its approved root: $pathFull"
    }
    $rootItem = Get-Item -LiteralPath $rootFull -Force -ErrorAction Stop
    if (-not $rootItem.PSIsContainer -or ($rootItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint)) {
        throw "Brain refresh rejected an unsafe root directory: $rootFull"
    }
    $cursor = $rootFull
    $relative = $pathFull.Substring($rootFull.Length).TrimStart('\')
    foreach ($segment in @($relative -split '\\' | Where-Object { $_ })) {
        $cursor = Join-Path $cursor $segment
        if (-not (Test-Path -LiteralPath $cursor)) {
            if (-not $Create) {
                throw "Brain refresh requires a missing directory: $cursor"
            }
            New-Item -ItemType Directory -Path $cursor | Out-Null
        }
        $item = Get-Item -LiteralPath $cursor -Force -ErrorAction Stop
        if (-not $item.PSIsContainer -or ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint)) {
            throw "Brain refresh rejected an unsafe directory component: $cursor"
        }
    }
    return $pathFull
}

function Assert-SafeArtifactLeaf {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Path,
        [switch]$MustExist,
        [switch]$RequireContent
    )
    $pathFull = [System.IO.Path]::GetFullPath($Path)
    Assert-SafeDirectoryTree -Root $Root -Path (Split-Path -Parent $pathFull) | Out-Null
    if (-not (Test-Path -LiteralPath $pathFull)) {
        if ($MustExist) { throw "Brain refresh requires a missing artifact: $pathFull" }
        return $pathFull
    }
    $item = Get-Item -LiteralPath $pathFull -Force -ErrorAction Stop
    if ($item.PSIsContainer -or ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint)) {
        throw "Brain refresh rejected an unsafe artifact: $pathFull"
    }
    if ($RequireContent -and $item.Length -le 0) {
        throw "Brain refresh rejected an empty artifact: $pathFull"
    }
    return $pathFull
}

function Sync-BrainArtifacts {
    param(
        [ValidateSet('full', 'tree', 'existing', 'unavailable')]
        [string]$ExplorerMode = 'existing'
    )
    $graphPath = Join-Path $GraphRoot 'graph.json'
    $reportPath = Join-Path $GraphRoot 'GRAPH_REPORT.md'
    $explorerPath = Join-Path $GraphRoot 'graph.html'
    if (-not (Test-Path -LiteralPath $graphPath -PathType Leaf)) {
        throw 'Canonical Graphify JSON is unavailable; run a successful Brain refresh first.'
    }
    if (-not (Test-Path -LiteralPath $reportPath -PathType Leaf)) {
        throw 'Canonical Graphify report is unavailable; run a successful Brain refresh first.'
    }
    $explorerAvailable = Test-Path -LiteralPath $explorerPath -PathType Leaf
    $graph = Get-Content -Raw $graphPath | ConvertFrom-Json
    New-Item -ItemType Directory -Path (Join-Path $VaultJarvis 'Graph') -Force | Out-Null
    Copy-Item -LiteralPath $reportPath -Destination (Join-Path $VaultJarvis 'Graph\Graphify Report.md') -Force
    [ordered]@{
        generatedAt = (Get-Date).ToString('o')
        sourceCommit = $graph.built_at_commit
        nodes = @($graph.nodes).Count
        edges = @($graph.links).Count
        hyperedges = @($graph.hyperedges).Count
        explorerAvailable = $explorerAvailable
        explorerMode = if ($explorerAvailable) { $ExplorerMode } else { 'unavailable' }
        explorer = if ($explorerAvailable) { $explorerPath } else { $null }
    } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $VaultJarvis 'Graph\graph-status.json') -Encoding utf8
}

switch ($Command) {
    'refresh' {
        Push-Location $ProjectRoot
        try {
            if (-not $GraphifyExe) {
                throw 'Graphify executable was not found on PATH or in the managed Python 3.11 Scripts directory.'
            }
            $intermediateRoot = Join-Path $ProjectRoot 'graphify-out'
            $intermediateExplorer = Join-Path $intermediateRoot 'graph.html'
            $canonicalExplorer = Join-Path $GraphRoot 'graph.html'
            Assert-SafeDirectoryTree -Root $ProjectRoot -Path $intermediateRoot -Create | Out-Null
            Assert-SafeDirectoryTree -Root $ProjectRoot -Path $GraphRoot -Create | Out-Null
            foreach ($existingIntermediate in @(
                (Join-Path $intermediateRoot 'graph.json'),
                (Join-Path $intermediateRoot 'GRAPH_REPORT.md'),
                $intermediateExplorer
            )) {
                Assert-SafeArtifactLeaf -Root $ProjectRoot -Path $existingIntermediate | Out-Null
            }
            if (Test-Path -LiteralPath $intermediateExplorer) {
                Remove-Item -LiteralPath $intermediateExplorer -Force
            }
            & $GraphifyExe update .
            if ($LASTEXITCODE -ne 0) { throw "Graphify failed with exit code $LASTEXITCODE" }
            & $GraphifyExe cluster-only . --no-label
            if ($LASTEXITCODE -ne 0) { throw "Graphify provenance rebuild failed with exit code $LASTEXITCODE" }
            $explorerMode = 'full'
            if (-not (Test-Path -LiteralPath $intermediateExplorer -PathType Leaf)) {
                & $GraphifyExe tree --graph (Join-Path $intermediateRoot 'graph.json') --output $intermediateExplorer --root $ProjectRoot --label 'Jarvis'
                if ($LASTEXITCODE -ne 0) { throw "Graphify tree fallback failed with exit code $LASTEXITCODE" }
                $explorerMode = 'tree'
            }
            $requiredArtifacts = @(
                (Join-Path $intermediateRoot 'graph.json'),
                (Join-Path $intermediateRoot 'GRAPH_REPORT.md'),
                $intermediateExplorer
            )
            # Re-check after external generation before reading or publishing any output.
            Assert-SafeDirectoryTree -Root $ProjectRoot -Path $intermediateRoot | Out-Null
            Assert-SafeDirectoryTree -Root $ProjectRoot -Path $GraphRoot | Out-Null
            foreach ($artifact in $requiredArtifacts) {
                Assert-SafeArtifactLeaf -Root $ProjectRoot -Path $artifact -MustExist -RequireContent | Out-Null
            }
            $generatedGraph = Get-Content -Raw -LiteralPath (Join-Path $intermediateRoot 'graph.json') | ConvertFrom-Json
            $priorErrorActionPreference = $ErrorActionPreference
            try {
                $ErrorActionPreference = 'Continue'
                $commitOutput = @(& git -C $ProjectRoot rev-parse HEAD 2>$null)
                $gitExitCode = $LASTEXITCODE
            } finally {
                $ErrorActionPreference = $priorErrorActionPreference
            }
            $currentCommit = if ($commitOutput.Count -gt 0) { [string]$commitOutput[0] } else { '' }
            if ($gitExitCode -ne 0 -or -not $currentCommit.Trim()) {
                throw 'Brain refresh could not resolve the canonical source commit.'
            }
            if ([string]$generatedGraph.built_at_commit -ne $currentCommit.Trim()) {
                throw "Graphify provenance is stale: expected $($currentCommit.Trim()), got $($generatedGraph.built_at_commit)"
            }
            foreach ($target in @(
                (Join-Path $GraphRoot 'graph.json'),
                (Join-Path $GraphRoot 'GRAPH_REPORT.md'),
                $canonicalExplorer,
                (Join-Path $GraphRoot '.last-build-snapshot.json')
            )) {
                Assert-SafeArtifactLeaf -Root $ProjectRoot -Path $target | Out-Null
            }
            Copy-Item -LiteralPath (Join-Path $intermediateRoot 'graph.json') -Destination (Join-Path $GraphRoot 'graph.json') -Force
            Copy-Item -LiteralPath (Join-Path $intermediateRoot 'GRAPH_REPORT.md') -Destination (Join-Path $GraphRoot 'GRAPH_REPORT.md') -Force
            Copy-Item -LiteralPath $intermediateExplorer -Destination $canonicalExplorer -Force
            node $GsdTools graphify build snapshot
            if ($LASTEXITCODE -ne 0) { throw "Graphify snapshot failed with exit code $LASTEXITCODE" }
            $snapshotPath = Join-Path $GraphRoot '.last-build-snapshot.json'
            Assert-SafeArtifactLeaf -Root $ProjectRoot -Path $snapshotPath -MustExist -RequireContent | Out-Null
            $snapshot = Get-Content -Raw -LiteralPath $snapshotPath | ConvertFrom-Json
            if (@($snapshot.nodes).Count -ne @($generatedGraph.nodes).Count -or @($snapshot.edges).Count -ne @($generatedGraph.links).Count) {
                throw 'Graphify snapshot does not match the generated graph topology.'
            }
            Sync-BrainArtifacts -ExplorerMode $explorerMode
        } finally {
            Pop-Location
        }
    }
    'sync' { Sync-BrainArtifacts }
    'graph' {
        $explorerPath = Join-Path $GraphRoot 'graph.html'
        if (-not (Test-Path -LiteralPath $explorerPath -PathType Leaf)) {
            throw 'Graph explorer is unavailable because Graphify skipped optional HTML generation; use the report or graph query instead.'
        }
        Invoke-Item $explorerPath
    }
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
