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

if (-not ('JarvisBrainPathGuard' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using Microsoft.Win32.SafeHandles;

public static class JarvisBrainPathGuard
{
    private const uint FILE_READ_ATTRIBUTES = 0x80;
    private const uint FILE_SHARE_READ = 0x1;
    private const uint FILE_SHARE_WRITE = 0x2;
    private const uint FILE_SHARE_DELETE = 0x4;
    private const uint OPEN_EXISTING = 3;
    private const uint FILE_FLAG_BACKUP_SEMANTICS = 0x02000000;
    private const uint FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000;
    private const uint FILE_ATTRIBUTE_REPARSE_POINT = 0x400;
    private const uint IO_REPARSE_TAG_NAME_SURROGATE = 0x20000000;
    private const uint CF_PLACEHOLDER_STATE_PLACEHOLDER = 0x1;
    private const uint CF_PLACEHOLDER_STATE_SYNC_ROOT = 0x2;
    private const uint CF_PLACEHOLDER_STATE_INVALID = 0xffffffff;
    private const int ERROR_HANDLE_EOF = 38;
    private static readonly IntPtr INVALID_HANDLE_VALUE = new IntPtr(-1);

    private enum FILE_INFO_BY_HANDLE_CLASS
    {
        FileAttributeTagInfo = 9
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct FILE_ATTRIBUTE_TAG_INFO
    {
        public uint FileAttributes;
        public uint ReparseTag;
    }

    private enum STREAM_INFO_LEVELS
    {
        FindStreamInfoStandard = 0
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct WIN32_FIND_STREAM_DATA
    {
        public long StreamSize;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 296)]
        public string StreamName;
    }

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern SafeFileHandle CreateFile(
        string fileName,
        uint desiredAccess,
        uint shareMode,
        IntPtr securityAttributes,
        uint creationDisposition,
        uint flagsAndAttributes,
        IntPtr templateFile);

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool GetFileInformationByHandleEx(
        SafeFileHandle file,
        FILE_INFO_BY_HANDLE_CLASS infoClass,
        out FILE_ATTRIBUTE_TAG_INFO info,
        uint size);

    [DllImport("CldApi.dll")]
    private static extern uint CfGetPlaceholderStateFromAttributeTag(
        uint fileAttributes,
        uint reparseTag);

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern IntPtr FindFirstStreamW(
        string fileName,
        STREAM_INFO_LEVELS infoLevel,
        out WIN32_FIND_STREAM_DATA data,
        uint flags);

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool FindNextStreamW(
        IntPtr findStream,
        out WIN32_FIND_STREAM_DATA data);

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool FindClose(IntPtr findFile);

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern uint GetFinalPathNameByHandleW(
        SafeFileHandle file,
        StringBuilder path,
        uint pathLength,
        uint flags);

    public static void AssertSafe(string path, bool allowCloudPlaceholder)
    {
        using (SafeFileHandle handle = CreateFile(
            path,
            FILE_READ_ATTRIBUTES,
            FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
            IntPtr.Zero,
            OPEN_EXISTING,
            FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_BACKUP_SEMANTICS,
            IntPtr.Zero))
        {
            if (handle.IsInvalid)
                throw new Win32Exception(Marshal.GetLastWin32Error(), "Could not inspect Brain path without following reparse points: " + path);

            FILE_ATTRIBUTE_TAG_INFO info;
            if (!GetFileInformationByHandleEx(
                handle,
                FILE_INFO_BY_HANDLE_CLASS.FileAttributeTagInfo,
                out info,
                (uint)Marshal.SizeOf(typeof(FILE_ATTRIBUTE_TAG_INFO))))
                throw new Win32Exception(Marshal.GetLastWin32Error(), "Could not inspect Brain reparse metadata: " + path);

            if ((info.FileAttributes & FILE_ATTRIBUTE_REPARSE_POINT) == 0)
                return;
            if ((info.ReparseTag & IO_REPARSE_TAG_NAME_SURROGATE) != 0)
                throw new InvalidOperationException("Brain refresh rejected a name-surrogate reparse point: " + path);
            if (!allowCloudPlaceholder)
                throw new InvalidOperationException("Brain refresh rejected an unapproved reparse point: " + path);

            uint state = CfGetPlaceholderStateFromAttributeTag(info.FileAttributes, info.ReparseTag);
            if (state == CF_PLACEHOLDER_STATE_INVALID ||
                (state & (CF_PLACEHOLDER_STATE_PLACEHOLDER | CF_PLACEHOLDER_STATE_SYNC_ROOT)) == 0)
                throw new InvalidOperationException("Brain refresh rejected a non-Cloud-Files reparse point: " + path);
        }
    }

    public static void AssertNoNamedStreams(string path)
    {
        WIN32_FIND_STREAM_DATA data;
        IntPtr find = FindFirstStreamW(path, STREAM_INFO_LEVELS.FindStreamInfoStandard, out data, 0);
        if (find == INVALID_HANDLE_VALUE)
        {
            int error = Marshal.GetLastWin32Error();
            if (error == ERROR_HANDLE_EOF)
                return;
            throw new Win32Exception(error, "Could not enumerate Brain artifact streams: " + path);
        }
        try
        {
            while (true)
            {
                if (!String.Equals(data.StreamName, "::$DATA", StringComparison.OrdinalIgnoreCase))
                    throw new InvalidOperationException("Brain refresh rejected a named alternate data stream: " + path);
                if (!FindNextStreamW(find, out data))
                {
                    int error = Marshal.GetLastWin32Error();
                    if (error != ERROR_HANDLE_EOF)
                        throw new Win32Exception(error, "Could not finish enumerating Brain artifact streams: " + path);
                    break;
                }
            }
        }
        finally
        {
            FindClose(find);
        }
    }

    public static string GetFinalPath(string path)
    {
        using (SafeFileHandle handle = CreateFile(
            path,
            FILE_READ_ATTRIBUTES,
            FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
            IntPtr.Zero,
            OPEN_EXISTING,
            FILE_FLAG_BACKUP_SEMANTICS,
            IntPtr.Zero))
        {
            if (handle.IsInvalid)
                throw new Win32Exception(Marshal.GetLastWin32Error(), "Could not resolve the final Brain path: " + path);
            StringBuilder buffer = new StringBuilder(512);
            uint length = GetFinalPathNameByHandleW(handle, buffer, (uint)buffer.Capacity, 0);
            if (length == 0)
                throw new Win32Exception(Marshal.GetLastWin32Error(), "Could not resolve the final Brain path: " + path);
            if (length >= buffer.Capacity)
            {
                buffer = new StringBuilder((int)length + 1);
                length = GetFinalPathNameByHandleW(handle, buffer, (uint)buffer.Capacity, 0);
                if (length == 0 || length >= buffer.Capacity)
                    throw new Win32Exception(Marshal.GetLastWin32Error(), "Could not resolve the final Brain path: " + path);
            }
            string result = buffer.ToString();
            if (result.StartsWith(@"\\?\UNC\", StringComparison.OrdinalIgnoreCase))
                return @"\\" + result.Substring(8);
            if (result.StartsWith(@"\\?\", StringComparison.OrdinalIgnoreCase))
                return result.Substring(4);
            return result;
        }
    }
}
'@
}

function Get-NormalizedBrainPath {
    param([Parameter(Mandatory = $true)][string]$Path)
    $full = [System.IO.Path]::GetFullPath($Path)
    $filesystemRoot = [System.IO.Path]::GetPathRoot($full)
    if (-not $filesystemRoot) { throw "Brain refresh could not resolve a filesystem root for: $full" }
    if (-not $full.Equals($filesystemRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        $full = $full.TrimEnd('\')
    }
    return $full
}

function Assert-SafeDirectoryTree {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Path,
        [switch]$Create,
        [switch]$AllowCloudPlaceholders
    )
    $rootFull = Get-NormalizedBrainPath $Root
    $pathFull = Get-NormalizedBrainPath $Path
    $rootPrefix = if ($rootFull.EndsWith('\')) { $rootFull } else { $rootFull + '\' }
    if ($pathFull -ne $rootFull -and -not $pathFull.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Brain refresh rejected a path outside its approved root: $pathFull"
    }
    $rootItem = Get-Item -LiteralPath $rootFull -Force -ErrorAction Stop
    if (-not $rootItem.PSIsContainer) {
        throw "Brain refresh rejected an unsafe root directory: $rootFull"
    }
    try {
        [JarvisBrainPathGuard]::AssertSafe($rootFull, $AllowCloudPlaceholders.IsPresent)
    } catch {
        throw "Brain refresh rejected an unsafe root directory: $rootFull ($($_.Exception.InnerException.Message))"
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
        if (-not $item.PSIsContainer) {
            throw "Brain refresh rejected an unsafe directory component: $cursor"
        }
        try {
            [JarvisBrainPathGuard]::AssertSafe($cursor, $AllowCloudPlaceholders.IsPresent)
        } catch {
            throw "Brain refresh rejected an unsafe directory component: $cursor ($($_.Exception.InnerException.Message))"
        }
    }
    return $pathFull
}

function Assert-SafeArtifactLeaf {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Path,
        [switch]$MustExist,
        [switch]$RequireContent,
        [switch]$AllowCloudPlaceholders
    )
    $pathFull = [System.IO.Path]::GetFullPath($Path)
    if ([System.IO.Path]::GetFileName($pathFull).Contains(':')) {
        throw "Brain refresh rejected an alternate data stream path: $pathFull"
    }
    Assert-SafeDirectoryTree -Root $Root -Path (Split-Path -Parent $pathFull) -AllowCloudPlaceholders:$AllowCloudPlaceholders | Out-Null
    if (-not (Test-Path -LiteralPath $pathFull)) {
        if ($MustExist) { throw "Brain refresh requires a missing artifact: $pathFull" }
        return $pathFull
    }
    $item = Get-Item -LiteralPath $pathFull -Force -ErrorAction Stop
    if ($item.PSIsContainer) {
        throw "Brain refresh rejected an unsafe artifact: $pathFull"
    }
    try {
        [JarvisBrainPathGuard]::AssertSafe($pathFull, $AllowCloudPlaceholders.IsPresent)
        [JarvisBrainPathGuard]::AssertNoNamedStreams($pathFull)
    } catch {
        throw "Brain refresh rejected an unsafe artifact: $pathFull ($($_.Exception.InnerException.Message))"
    }
    if ($RequireContent -and $item.Length -le 0) {
        throw "Brain refresh rejected an empty artifact: $pathFull"
    }
    return $pathFull
}

function Get-BrainFileHash {
    param([Parameter(Mandatory = $true)][string]$Path)
    [JarvisBrainPathGuard]::AssertNoNamedStreams([System.IO.Path]::GetFullPath($Path))
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant()
}

function Get-CanonicalSourceCommit {
    $priorErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $commitOutput = @(& git -C $ProjectRoot rev-parse HEAD 2>$null)
        $gitExitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $priorErrorActionPreference
    }
    $commit = if ($commitOutput.Count -gt 0) { [string]$commitOutput[0] } else { '' }
    if ($gitExitCode -ne 0 -or -not $commit.Trim()) {
        throw 'Brain refresh could not resolve the canonical source commit.'
    }
    return $commit.Trim()
}

function Assert-BrainSnapshotTopology {
    param(
        [Parameter(Mandatory = $true)]$Graph,
        [Parameter(Mandatory = $true)]$Snapshot
    )
    $graphNodeIds = @($Graph.nodes | ForEach-Object { [string]$_.id } | Sort-Object)
    $snapshotNodeIds = @($Snapshot.nodes | ForEach-Object { [string]$_.id } | Sort-Object)
    $graphEdges = @($Graph.links | ForEach-Object {
        $source = [string]$_.source
        $target = [string]$_.target
        $relation = [string]$_.relation
        "$($source.Length):$source$($target.Length):$target$($relation.Length):$relation"
    } | Sort-Object)
    $snapshotEdges = @($Snapshot.edges | ForEach-Object {
        $source = [string]$_.source
        $target = [string]$_.target
        $relation = [string]$_.relation
        "$($source.Length):$source$($target.Length):$target$($relation.Length):$relation"
    } | Sort-Object)
    if ($graphNodeIds.Count -ne $snapshotNodeIds.Count -or $graphEdges.Count -ne $snapshotEdges.Count) {
        throw 'Graphify snapshot does not match the generated graph topology.'
    }
    for ($index = 0; $index -lt $graphNodeIds.Count; $index++) {
        if (-not $graphNodeIds[$index].Equals($snapshotNodeIds[$index], [System.StringComparison]::Ordinal)) {
            throw 'Graphify snapshot does not match the generated graph topology.'
        }
    }
    for ($index = 0; $index -lt $graphEdges.Count; $index++) {
        if (-not $graphEdges[$index].Equals($snapshotEdges[$index], [System.StringComparison]::Ordinal)) {
            throw 'Graphify snapshot does not match the generated graph topology.'
        }
    }
}

function Invoke-WithBrainMutex {
    param(
        [Parameter(Mandatory = $true)][scriptblock]$Body,
        [int]$TimeoutMilliseconds = 30000
    )
    $canonicalKey = ([JarvisBrainPathGuard]::GetFinalPath($ProjectRoot)).TrimEnd('\').ToUpperInvariant()
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $hash = [System.BitConverter]::ToString(
            $sha.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($canonicalKey))
        ).Replace('-', '').ToLowerInvariant()
    } finally {
        $sha.Dispose()
    }
    $name = "Global\Jarvis.Brain.$hash"
    $sid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User
    $security = New-Object System.Security.AccessControl.MutexSecurity
    $security.SetAccessRuleProtection($true, $false)
    $security.SetOwner($sid)
    $rule = New-Object System.Security.AccessControl.MutexAccessRule(
        $sid,
        [System.Security.AccessControl.MutexRights]::FullControl,
        [System.Security.AccessControl.AccessControlType]::Allow
    )
    $security.AddAccessRule($rule)
    $created = $false
    $mutex = [System.Threading.Mutex]::new($false, $name, [ref]$created, $security)
    if (-not $created) {
        $existingSecurity = $mutex.GetAccessControl()
        $rules = @($existingSecurity.GetAccessRules(
            $true,
            $false,
            [System.Security.Principal.SecurityIdentifier]
        ))
        $validRule = $rules.Count -eq 1 -and
            $rules[0].IdentityReference.Value -eq $sid.Value -and
            $rules[0].AccessControlType -eq [System.Security.AccessControl.AccessControlType]::Allow -and
            ($rules[0].MutexRights -band [System.Security.AccessControl.MutexRights]::FullControl) -eq [System.Security.AccessControl.MutexRights]::FullControl
        $validOwner = $existingSecurity.GetOwner(
            [System.Security.Principal.SecurityIdentifier]
        ).Value -eq $sid.Value
        if (-not $existingSecurity.AreAccessRulesProtected -or -not $validRule -or -not $validOwner) {
            $mutex.Dispose()
            throw 'Brain refresh rejected an existing publication lock with an unexpected access policy.'
        }
    }
    $acquired = $false
    try {
        try {
            $acquired = $mutex.WaitOne($TimeoutMilliseconds)
        } catch [System.Threading.AbandonedMutexException] {
            $acquired = $true
            throw 'Brain refresh found an abandoned publication lock. Recovery inspection is required before retrying.'
        }
        if (-not $acquired) {
            throw "Brain refresh could not acquire its publication lock within $TimeoutMilliseconds milliseconds."
        }
        & $Body
    } finally {
        if ($acquired) { $mutex.ReleaseMutex() }
        $mutex.Dispose()
    }
}

function Copy-BrainFileDurably {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination
    )
    $input = $null
    $output = $null
    try {
        $input = [System.IO.FileStream]::new(
            $Source,
            [System.IO.FileMode]::Open,
            [System.IO.FileAccess]::Read,
            [System.IO.FileShare]::Read
        )
        $output = [System.IO.FileStream]::new(
            $Destination,
            [System.IO.FileMode]::CreateNew,
            [System.IO.FileAccess]::Write,
            [System.IO.FileShare]::None
        )
        $input.CopyTo($output)
        $output.Flush($true)
    } finally {
        if ($output) { $output.Dispose() }
        if ($input) { $input.Dispose() }
    }
}

function Remove-BrainKnownFiles {
    param([Parameter(Mandatory = $true)][object[]]$Files)
    foreach ($file in $Files) {
        if (Test-Path -LiteralPath $file.Path) {
            Assert-SafeArtifactLeaf -Root $file.Root -Path $file.Path -AllowCloudPlaceholders:$file.AllowCloud | Out-Null
            [System.IO.File]::Delete($file.Path)
        }
    }
}

function Remove-BrainKnownDirectories {
    param([Parameter(Mandatory = $true)][object[]]$Directories)
    foreach ($directory in $Directories) {
        if (Test-Path -LiteralPath $directory.Path) {
            Assert-SafeDirectoryTree -Root $directory.Root -Path $directory.Path -AllowCloudPlaceholders:$directory.AllowCloud | Out-Null
            [System.IO.Directory]::Delete($directory.Path, $false)
        }
    }
}

function Publish-BrainArtifactSet {
    param(
        [Parameter(Mandatory = $true)][object[]]$Artifacts,
        [Parameter(Mandatory = $true)][string]$TransactionId
    )
    $prepared = @()
    $journal = @()
    $publicationCommitted = $false
    $retainRecovery = $false
    try {
        $targetKeys = @{}
        foreach ($artifact in $Artifacts) {
            $source = [System.IO.Path]::GetFullPath([string]$artifact.Source)
            $target = [System.IO.Path]::GetFullPath([string]$artifact.Target)
            $root = [string]$artifact.Root
            $allowCloud = [bool]$artifact.AllowCloud
            Assert-SafeArtifactLeaf -Root $root -Path $source -MustExist -RequireContent -AllowCloudPlaceholders:$allowCloud | Out-Null
            Assert-SafeArtifactLeaf -Root $root -Path $target -AllowCloudPlaceholders:$allowCloud | Out-Null
            $targetKey = $target.ToUpperInvariant()
            if ($targetKeys.ContainsKey($targetKey)) { throw "Brain publication contains a duplicate target: $target" }
            $targetKeys[$targetKey] = $true

            $destinationDirectory = Split-Path -Parent $target
            $leaf = [System.IO.Path]::GetFileName($target)
            $swap = Join-Path $destinationDirectory ".$leaf.brain-txn-$TransactionId.tmp"
            $backup = Join-Path $destinationDirectory ".$leaf.brain-txn-$TransactionId.bak"
            $failed = Join-Path $destinationDirectory ".$leaf.brain-txn-$TransactionId.failed"
            foreach ($reserved in @($swap, $backup, $failed)) {
                Assert-SafeArtifactLeaf -Root $root -Path $reserved -AllowCloudPlaceholders:$allowCloud | Out-Null
                if (Test-Path -LiteralPath $reserved) { throw "Brain publication found a reserved transaction path: $reserved" }
            }
            if ([System.IO.Path]::GetPathRoot($swap) -ne [System.IO.Path]::GetPathRoot($target)) {
                throw "Brain publication requires same-volume replacement for: $target"
            }
            $candidateHash = Get-BrainFileHash $source
            $exists = Test-Path -LiteralPath $target -PathType Leaf
            $originalHash = if ($exists) { Get-BrainFileHash $target } else { $null }
            $preparedArtifact = [pscustomobject]@{
                Name = [string]$artifact.Name
                Root = $root
                AllowCloud = $allowCloud
                Target = $target
                Swap = $swap
                Backup = $backup
                Failed = $failed
                Existed = $exists
                OriginalHash = $originalHash
                CandidateHash = $candidateHash
                Applied = $false
            }
            $prepared += $preparedArtifact
            Copy-BrainFileDurably -Source $source -Destination $swap
            if ((Get-BrainFileHash $swap) -ne $candidateHash) {
                throw "Brain publication staging hash mismatch for: $target"
            }
        }

        try {
            foreach ($artifact in $prepared) {
                Assert-SafeArtifactLeaf -Root $artifact.Root -Path $artifact.Swap -MustExist -RequireContent -AllowCloudPlaceholders:$artifact.AllowCloud | Out-Null
                Assert-SafeArtifactLeaf -Root $artifact.Root -Path $artifact.Target -AllowCloudPlaceholders:$artifact.AllowCloud | Out-Null
                if ((Get-BrainFileHash $artifact.Swap) -ne $artifact.CandidateHash) {
                    throw "Brain publication swap changed before replacement: $($artifact.Target)"
                }
                foreach ($reserved in @($artifact.Backup, $artifact.Failed)) {
                    Assert-SafeArtifactLeaf -Root $artifact.Root -Path $reserved -AllowCloudPlaceholders:$artifact.AllowCloud | Out-Null
                    if (Test-Path -LiteralPath $reserved) {
                        throw "Brain publication reserved path appeared before replacement: $reserved"
                    }
                }
                $targetExistsNow = Test-Path -LiteralPath $artifact.Target -PathType Leaf
                if ($artifact.Existed) {
                    if (-not $targetExistsNow -or (Get-BrainFileHash $artifact.Target) -ne $artifact.OriginalHash) {
                        throw "Brain publication target changed before replacement: $($artifact.Target)"
                    }
                } elseif ($targetExistsNow) {
                    throw "Brain publication target appeared before first publication: $($artifact.Target)"
                }
                $journal += $artifact
                if ($artifact.Existed) {
                    [System.IO.File]::Replace($artifact.Swap, $artifact.Target, $artifact.Backup, $false)
                } else {
                    [System.IO.File]::Move($artifact.Swap, $artifact.Target)
                }
                $artifact.Applied = $true
            }
            foreach ($artifact in $prepared) {
                Assert-SafeArtifactLeaf -Root $artifact.Root -Path $artifact.Target -MustExist -RequireContent -AllowCloudPlaceholders:$artifact.AllowCloud | Out-Null
                if ((Get-BrainFileHash $artifact.Target) -ne $artifact.CandidateHash) {
                    throw "Brain publication readback hash mismatch for: $($artifact.Target)"
                }
            }
            $publicationCommitted = $true
        } catch {
            $publishFailure = $_
            $rollbackFailures = @()
            for ($index = $journal.Count - 1; $index -ge 0; $index--) {
                $artifact = $journal[$index]
                try {
                    if ($artifact.Existed) {
                        if (Test-Path -LiteralPath $artifact.Backup -PathType Leaf) {
                            if ((Get-BrainFileHash $artifact.Backup) -ne $artifact.OriginalHash) {
                                throw "Brain rollback backup hash mismatch for: $($artifact.Target)"
                            }
                            if (Test-Path -LiteralPath $artifact.Target -PathType Leaf) {
                                Assert-SafeArtifactLeaf -Root $artifact.Root -Path $artifact.Target -AllowCloudPlaceholders:$artifact.AllowCloud | Out-Null
                                [System.IO.File]::Replace($artifact.Backup, $artifact.Target, $artifact.Failed, $false)
                            } else {
                                [System.IO.File]::Move($artifact.Backup, $artifact.Target)
                            }
                        } elseif (-not (Test-Path -LiteralPath $artifact.Target -PathType Leaf) -or
                            (Get-BrainFileHash $artifact.Target) -ne $artifact.OriginalHash) {
                            throw "Brain rollback could not locate the original bytes for: $($artifact.Target)"
                        }
                    } elseif (Test-Path -LiteralPath $artifact.Target) {
                        Assert-SafeArtifactLeaf -Root $artifact.Root -Path $artifact.Target -AllowCloudPlaceholders:$artifact.AllowCloud | Out-Null
                        $targetIsThisTransaction = $artifact.Applied -or (
                            -not (Test-Path -LiteralPath $artifact.Swap) -and
                            (Get-BrainFileHash $artifact.Target) -eq $artifact.CandidateHash
                        )
                        if (-not $targetIsThisTransaction) {
                            throw "Brain rollback refused to delete an unrecognized newly-appeared target: $($artifact.Target)"
                        }
                        [System.IO.File]::Delete($artifact.Target)
                    }
                } catch {
                    $rollbackFailures += $_
                }
            }
            foreach ($artifact in $prepared) {
                try {
                    if ($artifact.Existed) {
                        if (-not (Test-Path -LiteralPath $artifact.Target -PathType Leaf) -or
                            (Get-BrainFileHash $artifact.Target) -ne $artifact.OriginalHash) {
                            throw "Brain rollback verification failed for: $($artifact.Target)"
                        }
                    } elseif (Test-Path -LiteralPath $artifact.Target) {
                        throw "Brain rollback left a newly-created target behind: $($artifact.Target)"
                    }
                } catch {
                    $rollbackFailures += $_
                }
            }
            if ($rollbackFailures.Count -gt 0) {
                $retainRecovery = $true
                $exception = [System.InvalidOperationException]::new(
                    "Brain publication $TransactionId failed and rollback was incomplete; recovery artifacts were retained. Original failure: $($publishFailure.Exception.Message)"
                )
                $exception.Data['BrainRecoveryArtifactsRetained'] = $true
                throw $exception
            }
            throw "Brain publication failed; the prior artifact set was restored. Cause: $($publishFailure.Exception.Message)"
        }
    } finally {
        if (-not $retainRecovery) {
            $known = @()
            foreach ($artifact in $prepared) {
                foreach ($path in @($artifact.Swap, $artifact.Backup, $artifact.Failed)) {
                    $known += [pscustomobject]@{ Path = $path; Root = $artifact.Root; AllowCloud = $artifact.AllowCloud }
                }
            }
            try {
                if ($known.Count -gt 0) { Remove-BrainKnownFiles -Files $known }
            } catch {
                if ($publicationCommitted) {
                    throw "Brain publication committed, but transaction cleanup was incomplete: $($_.Exception.Message)"
                }
                throw
            }
        }
    }
}

function New-BrainVaultStage {
    param(
        [Parameter(Mandatory = $true)][string]$TransactionId,
        [Parameter(Mandatory = $true)][string]$ReportSource,
        [Parameter(Mandatory = $true)]$Graph,
        [Parameter(Mandatory = $true)][string]$ExplorerMode,
        [Parameter(Mandatory = $true)][string]$ExplorerPath,
        [Parameter(Mandatory = $true)][bool]$ExplorerAvailable
    )
    $vaultGraphRoot = Join-Path $VaultJarvis 'Graph'
    $vaultFilesystemRoot = [System.IO.Path]::GetPathRoot([System.IO.Path]::GetFullPath($vaultGraphRoot))
    Assert-SafeDirectoryTree -Root $vaultFilesystemRoot -Path $VaultRoot -Create -AllowCloudPlaceholders | Out-Null
    $vaultSafetyRoot = Get-NormalizedBrainPath $VaultRoot
    Assert-SafeDirectoryTree -Root $vaultSafetyRoot -Path $vaultGraphRoot -Create -AllowCloudPlaceholders | Out-Null
    $stageRoot = Join-Path $vaultGraphRoot ".brain-txn-$TransactionId"
    if (Test-Path -LiteralPath $stageRoot) { throw "Brain vault staging path already exists: $stageRoot" }
    $reportCandidate = Join-Path $stageRoot 'Graphify Report.md'
    $statusCandidate = Join-Path $stageRoot 'graph-status.json'
    $stage = [pscustomobject]@{
        Root = $stageRoot
        SafetyRoot = $vaultSafetyRoot
        Report = $reportCandidate
        Status = $statusCandidate
        Files = @($reportCandidate, $statusCandidate)
    }
    try {
        Assert-SafeDirectoryTree -Root $vaultSafetyRoot -Path $stageRoot -Create -AllowCloudPlaceholders | Out-Null
        Copy-Item -LiteralPath $ReportSource -Destination $reportCandidate
        [ordered]@{
            generatedAt = (Get-Date).ToString('o')
            sourceCommit = $Graph.built_at_commit
            nodes = @($Graph.nodes).Count
            edges = @($Graph.links).Count
            hyperedges = @($Graph.hyperedges).Count
            explorerAvailable = $ExplorerAvailable
            explorerMode = if ($ExplorerAvailable) { $ExplorerMode } else { 'unavailable' }
            explorer = if ($ExplorerAvailable) { $ExplorerPath } else { $null }
        } | ConvertTo-Json | Set-Content -LiteralPath $statusCandidate -Encoding utf8
        Assert-SafeArtifactLeaf -Root $vaultSafetyRoot -Path $reportCandidate -MustExist -RequireContent -AllowCloudPlaceholders | Out-Null
        Assert-SafeArtifactLeaf -Root $vaultSafetyRoot -Path $statusCandidate -MustExist -RequireContent -AllowCloudPlaceholders | Out-Null
        Get-Content -Raw -LiteralPath $statusCandidate | ConvertFrom-Json | Out-Null
        return $stage
    } catch {
        $stageFailure = $_
        try {
            Remove-BrainVaultStage $stage
        } catch {
            throw "Brain vault staging failed and cleanup was incomplete for transaction $TransactionId. Original failure: $($stageFailure.Exception.Message)"
        }
        throw $stageFailure
    }
}

function Remove-BrainVaultStage {
    param([Parameter(Mandatory = $true)]$Stage)
    $files = @($Stage.Files | ForEach-Object {
        [pscustomobject]@{ Path = $_; Root = $Stage.SafetyRoot; AllowCloud = $true }
    })
    Remove-BrainKnownFiles -Files $files
    Remove-BrainKnownDirectories -Directories @(
        [pscustomobject]@{ Path = $Stage.Root; Root = $Stage.SafetyRoot; AllowCloud = $true }
    )
}

function Remove-BrainRepositoryStage {
    param([Parameter(Mandatory = $true)]$Stage)
    $files = @($Stage.Files | ForEach-Object {
        [pscustomobject]@{ Path = $_; Root = $ProjectRoot; AllowCloud = $false }
    })
    Remove-BrainKnownFiles -Files $files
    $directories = @($Stage.Directories | ForEach-Object {
        [pscustomobject]@{ Path = $_; Root = $ProjectRoot; AllowCloud = $false }
    })
    Remove-BrainKnownDirectories -Directories $directories
}

function Sync-BrainArtifacts {
    param(
        [ValidateSet('full', 'tree', 'existing', 'unavailable')]
        [string]$ExplorerMode = 'existing'
    )
    $graphPath = Join-Path $GraphRoot 'graph.json'
    $reportPath = Join-Path $GraphRoot 'GRAPH_REPORT.md'
    $explorerPath = Join-Path $GraphRoot 'graph.html'
    Assert-SafeArtifactLeaf -Root $ProjectRoot -Path $graphPath -MustExist -RequireContent | Out-Null
    Assert-SafeArtifactLeaf -Root $ProjectRoot -Path $reportPath -MustExist -RequireContent | Out-Null
    $explorerAvailable = Test-Path -LiteralPath $explorerPath -PathType Leaf
    if ($explorerAvailable) {
        Assert-SafeArtifactLeaf -Root $ProjectRoot -Path $explorerPath -MustExist -RequireContent | Out-Null
    }
    $graph = Get-Content -Raw -LiteralPath $graphPath | ConvertFrom-Json
    $transactionId = [guid]::NewGuid().ToString('N')
    $stage = $null
    $retainRecovery = $false
    try {
        $stage = New-BrainVaultStage `
            -TransactionId $transactionId `
            -ReportSource $reportPath `
            -Graph $graph `
            -ExplorerMode $ExplorerMode `
            -ExplorerPath $explorerPath `
            -ExplorerAvailable $explorerAvailable
        $vaultGraphRoot = Join-Path $VaultJarvis 'Graph'
        $artifacts = @(
            [pscustomobject]@{ Name = 'vault report'; Source = $stage.Report; Target = (Join-Path $vaultGraphRoot 'Graphify Report.md'); Root = $stage.SafetyRoot; AllowCloud = $true },
            [pscustomobject]@{ Name = 'vault status'; Source = $stage.Status; Target = (Join-Path $vaultGraphRoot 'graph-status.json'); Root = $stage.SafetyRoot; AllowCloud = $true }
        )
        Publish-BrainArtifactSet -Artifacts $artifacts -TransactionId $transactionId
    } catch {
        $retainRecovery = $_.Exception.Data['BrainRecoveryArtifactsRetained'] -eq $true
        throw
    } finally {
        if ($stage -and -not $retainRecovery) { Remove-BrainVaultStage $stage }
    }
}

switch ($Command) {
    'refresh' {
        Invoke-WithBrainMutex {
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
            $currentCommit = Get-CanonicalSourceCommit
            if ([string]$generatedGraph.built_at_commit -ne $currentCommit) {
                throw "Graphify provenance is stale: expected $currentCommit, got $($generatedGraph.built_at_commit)"
            }
            foreach ($target in @(
                (Join-Path $GraphRoot 'graph.json'),
                (Join-Path $GraphRoot 'GRAPH_REPORT.md'),
                $canonicalExplorer,
                (Join-Path $GraphRoot '.last-build-snapshot.json')
            )) {
                Assert-SafeArtifactLeaf -Root $ProjectRoot -Path $target | Out-Null
            }
            $transactionId = [guid]::NewGuid().ToString('N')
            $repositoryStage = $null
            $vaultStage = $null
            $retainRecovery = $false
            try {
                $repositoryStageRoot = Join-Path $GraphRoot ".brain-txn-$transactionId"
                if (Test-Path -LiteralPath $repositoryStageRoot) {
                    throw "Brain repository staging path already exists: $repositoryStageRoot"
                }
                $stageWorkspace = Join-Path $repositoryStageRoot 'workspace'
                $stagePlanning = Join-Path $stageWorkspace '.planning'
                $stageGraphRoot = Join-Path $stagePlanning 'graphs'
                $stageGraph = Join-Path $stageGraphRoot 'graph.json'
                $stageReport = Join-Path $stageGraphRoot 'GRAPH_REPORT.md'
                $stageExplorer = Join-Path $stageGraphRoot 'graph.html'
                $stageSnapshot = Join-Path $stageGraphRoot '.last-build-snapshot.json'
                $repositoryStage = [pscustomobject]@{
                    Root = $repositoryStageRoot
                    Files = @($stageGraph, $stageReport, $stageExplorer, $stageSnapshot)
                    Directories = @($stageGraphRoot, $stagePlanning, $stageWorkspace, $repositoryStageRoot)
                }
                Assert-SafeDirectoryTree -Root $ProjectRoot -Path $stageGraphRoot -Create | Out-Null
                Copy-Item -LiteralPath (Join-Path $intermediateRoot 'graph.json') -Destination $stageGraph
                Copy-Item -LiteralPath (Join-Path $intermediateRoot 'GRAPH_REPORT.md') -Destination $stageReport
                Copy-Item -LiteralPath $intermediateExplorer -Destination $stageExplorer
                foreach ($candidate in @($stageGraph, $stageReport, $stageExplorer)) {
                    Assert-SafeArtifactLeaf -Root $ProjectRoot -Path $candidate -MustExist -RequireContent | Out-Null
                }
                Push-Location $stageWorkspace
                try {
                    node $GsdTools graphify build snapshot
                    if ($LASTEXITCODE -ne 0) { throw "Graphify snapshot failed with exit code $LASTEXITCODE" }
                } finally {
                    Pop-Location
                }
                Assert-SafeArtifactLeaf -Root $ProjectRoot -Path $stageSnapshot -MustExist -RequireContent | Out-Null
                $stagedGraph = Get-Content -Raw -LiteralPath $stageGraph | ConvertFrom-Json
                $snapshot = Get-Content -Raw -LiteralPath $stageSnapshot | ConvertFrom-Json
                Assert-BrainSnapshotTopology -Graph $stagedGraph -Snapshot $snapshot
                $currentCommit = Get-CanonicalSourceCommit
                if ([string]$stagedGraph.built_at_commit -ne $currentCommit) {
                    throw "Graphify provenance changed before publication: expected $currentCommit, got $($stagedGraph.built_at_commit)"
                }
                $vaultStage = New-BrainVaultStage `
                    -TransactionId $transactionId `
                    -ReportSource $stageReport `
                    -Graph $stagedGraph `
                    -ExplorerMode $explorerMode `
                    -ExplorerPath $canonicalExplorer `
                    -ExplorerAvailable $true
                $vaultGraphRoot = Join-Path $VaultJarvis 'Graph'
                $artifacts = @(
                    [pscustomobject]@{ Name = 'canonical graph'; Source = $stageGraph; Target = (Join-Path $GraphRoot 'graph.json'); Root = $ProjectRoot; AllowCloud = $false },
                    [pscustomobject]@{ Name = 'canonical report'; Source = $stageReport; Target = (Join-Path $GraphRoot 'GRAPH_REPORT.md'); Root = $ProjectRoot; AllowCloud = $false },
                    [pscustomobject]@{ Name = 'canonical explorer'; Source = $stageExplorer; Target = $canonicalExplorer; Root = $ProjectRoot; AllowCloud = $false },
                    [pscustomobject]@{ Name = 'canonical snapshot'; Source = $stageSnapshot; Target = (Join-Path $GraphRoot '.last-build-snapshot.json'); Root = $ProjectRoot; AllowCloud = $false },
                    [pscustomobject]@{ Name = 'vault report'; Source = $vaultStage.Report; Target = (Join-Path $vaultGraphRoot 'Graphify Report.md'); Root = $vaultStage.SafetyRoot; AllowCloud = $true },
                    [pscustomobject]@{ Name = 'vault status'; Source = $vaultStage.Status; Target = (Join-Path $vaultGraphRoot 'graph-status.json'); Root = $vaultStage.SafetyRoot; AllowCloud = $true }
                )
                Publish-BrainArtifactSet -Artifacts $artifacts -TransactionId $transactionId
            } catch {
                $retainRecovery = $_.Exception.Data['BrainRecoveryArtifactsRetained'] -eq $true
                throw
            } finally {
                if (-not $retainRecovery) {
                    if ($vaultStage) { Remove-BrainVaultStage $vaultStage }
                    if ($repositoryStage) { Remove-BrainRepositoryStage $repositoryStage }
                }
            }
            } finally {
                Pop-Location
            }
        }
    }
    'sync' { Invoke-WithBrainMutex { Sync-BrainArtifacts } }
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
