[CmdletBinding()]
param(
    [switch]$Rebuild,
    [string]$Preset = "win32-vcpkg-debug",
    [string]$ReferenceRuntimeDir = "",
    [switch]$UseReferenceExecutable,
    [switch]$OverlayCurrentArchipelago
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-RepoRoot {
    return [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
}

function Invoke-External {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [string]$WorkingDirectory = ""
    )

    if ($WorkingDirectory) {
        Push-Location $WorkingDirectory
    }

    try {
        & $FilePath @Arguments
        if ($LASTEXITCODE -ne 0) {
            throw "$FilePath exited with code $LASTEXITCODE"
        }
    }
    finally {
        if ($WorkingDirectory) {
            Pop-Location
        }
    }
}

function Invoke-Robocopy {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    & robocopy $Source $Destination @Arguments
    $code = $LASTEXITCODE
    if ($code -gt 7) {
        throw "robocopy failed with exit code $code"
    }
}

function Get-VsWherePath {
    $candidate = Join-Path ${env:ProgramFiles(x86)} "Microsoft Visual Studio\Installer\vswhere.exe"
    if (Test-Path -LiteralPath $candidate) {
        return $candidate
    }

    $command = Get-Command vswhere.exe -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    throw "vswhere.exe not found. Install Visual Studio 2022 with the C++ workload."
}

function Import-VsDevEnvironment {
    $vswhere = Get-VsWherePath
    $installationPath = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
    if (-not $installationPath) {
        throw "Unable to locate a Visual Studio installation with x86/x64 C++ tools."
    }

    $vsDevCmd = Join-Path $installationPath "Common7\Tools\VsDevCmd.bat"
    if (-not (Test-Path -LiteralPath $vsDevCmd)) {
        throw "VsDevCmd.bat not found at $vsDevCmd"
    }

    $envDump = & cmd.exe /s /c "`"$vsDevCmd`" -no_logo -arch=x86 -host_arch=x64 >nul && set"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to import Visual Studio developer environment from $vsDevCmd"
    }

    foreach ($line in $envDump) {
        if ($line -notmatch "=") {
            continue
        }
        $name, $value = $line -split "=", 2
        Set-Item -Path "Env:$name" -Value $value
    }

    if (-not (Get-Command cl.exe -ErrorAction SilentlyContinue)) {
        throw "cl.exe is still not available after importing the Visual Studio developer environment."
    }
    if (-not $env:INCLUDE) {
        throw "INCLUDE is not set after importing the Visual Studio developer environment."
    }
}

function Assert-VcpkgRoot {
    if (-not $env:VCPKG_ROOT) {
        throw "VCPKG_ROOT is not set. Install/configure vcpkg before running this script."
    }
    if (-not (Test-Path -LiteralPath $env:VCPKG_ROOT)) {
        throw "VCPKG_ROOT points to a path that does not exist: $($env:VCPKG_ROOT)"
    }
}

function Resolve-ReferenceRuntimeDirectory {
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [string]$RequestedPath
    )

    if ($RequestedPath) {
        return [System.IO.Path]::GetFullPath($RequestedPath)
    }

    $workspaceRoot = [System.IO.Path]::GetFullPath((Join-Path $RepoRoot "..\..\.."))
    $candidate = Join-Path $workspaceRoot "build\win32-vcpkg-debug\GeneralsMD\Debug"
    if (Test-Path -LiteralPath (Join-Path $candidate "generalszh.exe")) {
        return $candidate
    }

    return ""
}

function Get-RuntimeDirectory {
    param([Parameter(Mandatory = $true)][string]$RepoRoot)

    $runtimeDir = Join-Path $RepoRoot "build\win32-vcpkg-debug\GeneralsMD\Debug"
    $exePath = Join-Path $runtimeDir "generalszh.exe"
    if (-not (Test-Path -LiteralPath $exePath)) {
        throw "Expected debug runtime executable was not found at $exePath"
    }

    return $runtimeDir
}

function Ensure-UserDataFolders {
    param([Parameter(Mandatory = $true)][string]$RuntimeDir)

    foreach ($relativePath in @("UserData", "UserData\Archipelago")) {
        New-Item -ItemType Directory -Force -Path (Join-Path $RuntimeDir $relativePath) | Out-Null
    }
}

function Assert-DebugRuntimeLayout {
    param([Parameter(Mandatory = $true)][string]$RuntimeDir)

    $requiredDirectories = @(
        "Data",
        "Data\Cursors",
        "Data\English",
        "Data\INI",
        "Data\Movies",
        "Data\Scripts",
        "Data\WaterPlane",
        "MappedImages",
        "MSS",
        "ZH_Generals"
    )

    $requiredFiles = @(
        "generalszh.exe",
        "BINKW32.DLL",
        "mss32.dll",
        "DebugWindow.dll",
        "AudioEnglishZH.big",
        "AudioZH.big",
        "EnglishZH.big",
        "gensecZH.big",
        "INIZH.big",
        "MapsZH.big",
        "Music.big",
        "MusicZH.big",
        "PatchData.big",
        "PatchINI.big",
        "PatchZH.big",
        "ShadersZH.big",
        "SpeechEnglishZH.big",
        "SpeechZH.big",
        "TerrainZH.big",
        "TexturesZH.big",
        "W3DEnglishZH.big",
        "W3DZH.big",
        "WindowZH.big"
    )

    $missing = New-Object System.Collections.Generic.List[string]

    foreach ($relativePath in $requiredDirectories) {
        if (-not (Test-Path -LiteralPath (Join-Path $RuntimeDir $relativePath) -PathType Container)) {
            $missing.Add($relativePath)
        }
    }

    foreach ($relativePath in $requiredFiles) {
        if (-not (Test-Path -LiteralPath (Join-Path $RuntimeDir $relativePath) -PathType Leaf)) {
            $missing.Add($relativePath)
        }
    }

    if ($missing.Count -gt 0) {
        $message = ($missing | Sort-Object | ForEach-Object { " - $_" }) -join [Environment]::NewLine
        throw "Direct debug runtime is incomplete at '$RuntimeDir'. Missing required runtime entries:`n$message"
    }
}

function Backup-RuntimeOverrides {
    param([Parameter(Mandatory = $true)][string]$RuntimeDir)

    $overridePaths = @(
        "Data\INI\Archipelago.ini",
        "Data\INI\UnlockableChecksDemo.ini",
        "Data\INI\CommandMap.ini",
        "Data\INI\CommandMapDebug.ini",
        "Data\INI\CommandMapDebug\Archipelago.ini",
        "MappedImages\HandCreated\zz_ArchipelagoLock.ini",
        "MappedImages\HandCreated\HandCreatedMappedImages.INI",
        "MappedImages\TextureSize_512\HandCreatedMappedImages.INI"
    )

    $backupRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("GeneralsAP-DebugRuntimeOverrides-" + [Guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null

    foreach ($relativePath in $overridePaths) {
        $sourcePath = Join-Path $RuntimeDir $relativePath
        if (-not (Test-Path -LiteralPath $sourcePath)) {
            continue
        }

        $destinationPath = Join-Path $backupRoot $relativePath
        $destinationDir = Split-Path -Path $destinationPath -Parent
        New-Item -ItemType Directory -Force -Path $destinationDir | Out-Null
        Copy-Item -LiteralPath $sourcePath -Destination $destinationPath -Force
    }

    return $backupRoot
}

function Backup-RuntimeFiles {
    param(
        [Parameter(Mandatory = $true)][string]$RuntimeDir,
        [Parameter(Mandatory = $true)][string[]]$RelativePaths
    )

    $backupRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("GeneralsAP-DebugRuntimeFiles-" + [Guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null

    foreach ($relativePath in $RelativePaths) {
        $sourcePath = Join-Path $RuntimeDir $relativePath
        if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
            continue
        }

        $destinationPath = Join-Path $backupRoot $relativePath
        $destinationDir = Split-Path -Path $destinationPath -Parent
        New-Item -ItemType Directory -Force -Path $destinationDir | Out-Null
        Copy-Item -LiteralPath $sourcePath -Destination $destinationPath -Force
    }

    return $backupRoot
}

function Restore-RuntimeOverrides {
    param(
        [Parameter(Mandatory = $true)][string]$BackupRoot,
        [Parameter(Mandatory = $true)][string]$RuntimeDir
    )

    if (-not (Test-Path -LiteralPath $BackupRoot)) {
        return
    }

    $backupFiles = Get-ChildItem -LiteralPath $BackupRoot -Recurse -File -ErrorAction SilentlyContinue
    foreach ($file in $backupFiles) {
        $relativePath = $file.FullName.Substring($BackupRoot.Length + 1)
        $destinationPath = Join-Path $RuntimeDir $relativePath
        $destinationDir = Split-Path -Path $destinationPath -Parent
        New-Item -ItemType Directory -Force -Path $destinationDir | Out-Null
        Copy-Item -LiteralPath $file.FullName -Destination $destinationPath -Force
    }

    Remove-Item -LiteralPath $BackupRoot -Recurse -Force
}

function Mirror-ReferenceRuntimeTree {
    param(
        [Parameter(Mandatory = $true)][string]$SourceRuntimeDir,
        [Parameter(Mandatory = $true)][string]$TargetRuntimeDir
    )

    & robocopy $SourceRuntimeDir $TargetRuntimeDir /MIR /R:1 /W:1 /NFL /NDL /NJH /NJS /NP /XD UserData UserDataProbe
    $code = $LASTEXITCODE
    if ($code -gt 7) {
        throw "robocopy failed with exit code $code"
    }
}

function Overlay-ArchipelagoRuntimeFiles {
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [Parameter(Mandatory = $true)][string]$RuntimeDir
    )

    $overlays = @(
        @{ Source = "Data\INI\Archipelago.ini"; Destination = "Data\INI\Archipelago.ini" },
        @{ Source = "Data\INI\UnlockableChecksDemo.ini"; Destination = "Data\INI\UnlockableChecksDemo.ini" },
        @{ Source = "Data\INI\CommandMap.ini"; Destination = "Data\INI\CommandMap.ini" },
        @{ Source = "Data\INI\CommandMapDebug.ini"; Destination = "Data\INI\CommandMapDebug.ini" },
        @{ Source = "Data\INI\CommandMapDebug\Archipelago.ini"; Destination = "Data\INI\CommandMapDebug\Archipelago.ini" },
        @{ Source = "Data\INI\MappedImages\HandCreated\HandCreatedMappedImages.INI"; Destination = "MappedImages\HandCreated\HandCreatedMappedImages.INI" },
        @{ Source = "Data\INI\MappedImages\HandCreated\zz_ArchipelagoLock.ini"; Destination = "MappedImages\HandCreated\zz_ArchipelagoLock.ini" },
        @{ Source = "Data\INI\MappedImages\TextureSize_512\HandCreatedMappedImages.INI"; Destination = "MappedImages\TextureSize_512\HandCreatedMappedImages.INI" }
    )

    foreach ($entry in $overlays) {
        $sourcePath = Join-Path $RepoRoot $entry.Source
        if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
            continue
        }

        $destinationPath = Join-Path $RuntimeDir $entry.Destination
        $destinationDir = Split-Path -Path $destinationPath -Parent
        New-Item -ItemType Directory -Force -Path $destinationDir | Out-Null
        Copy-Item -LiteralPath $sourcePath -Destination $destinationPath -Force
    }
}

function Sync-ReferenceRuntimeAssets {
    param(
        [Parameter(Mandatory = $true)][string]$SourceRuntimeDir,
        [Parameter(Mandatory = $true)][string]$TargetRuntimeDir,
        [switch]$SyncExecutable,
        [switch]$PreserveOverrides
    )

    $sourceFull = [System.IO.Path]::GetFullPath($SourceRuntimeDir)
    $targetFull = [System.IO.Path]::GetFullPath($TargetRuntimeDir)
    if ($sourceFull.Equals($targetFull, [System.StringComparison]::OrdinalIgnoreCase)) {
        return
    }

    Assert-DebugRuntimeLayout -RuntimeDir $sourceFull

    $backupRoot = $null
    $currentExecutableBackup = $null
    try {
        if ($PreserveOverrides) {
            $backupRoot = Backup-RuntimeOverrides -RuntimeDir $targetFull
        }
        if (-not $SyncExecutable) {
            $currentExecutableBackup = Backup-RuntimeFiles -RuntimeDir $targetFull -RelativePaths @("generalszh.exe", "generalszh.pdb", "Game.dat")
        }

        Mirror-ReferenceRuntimeTree -SourceRuntimeDir $sourceFull -TargetRuntimeDir $targetFull

        if (-not $SyncExecutable -and $currentExecutableBackup) {
            Restore-RuntimeOverrides -BackupRoot $currentExecutableBackup -RuntimeDir $targetFull
            $currentExecutableBackup = $null
        }
    }
    finally {
        if ($currentExecutableBackup) {
            Restore-RuntimeOverrides -BackupRoot $currentExecutableBackup -RuntimeDir $targetFull
        }
        if ($backupRoot) {
            Restore-RuntimeOverrides -BackupRoot $backupRoot -RuntimeDir $targetFull
        }
    }
}

function Assert-ReferenceExecutableSync {
    param(
        [Parameter(Mandatory = $true)][string]$ReferenceRuntimeDir,
        [Parameter(Mandatory = $true)][string]$RuntimeDir
    )

    foreach ($fileName in @("generalszh.exe", "Game.dat")) {
        $referenceFile = Join-Path $ReferenceRuntimeDir $fileName
        $runtimeFile = Join-Path $RuntimeDir $fileName
        if (-not (Test-Path -LiteralPath $referenceFile -PathType Leaf)) {
            throw "Reference runtime file missing: $referenceFile"
        }
        if (-not (Test-Path -LiteralPath $runtimeFile -PathType Leaf)) {
            throw "Prepared runtime file missing after sync: $runtimeFile"
        }

        $referenceHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $referenceFile).Hash
        $runtimeHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $runtimeFile).Hash
        if ($referenceHash -ne $runtimeHash) {
            throw "Reference executable sync failed for $fileName. Expected hash $referenceHash but found $runtimeHash."
        }
    }
}

$repoRoot = Get-RepoRoot
$buildDir = Join-Path $repoRoot ("build\" + $Preset)
$referenceRuntimeDir = Resolve-ReferenceRuntimeDirectory -RepoRoot $repoRoot -RequestedPath $ReferenceRuntimeDir

if ($Rebuild -and (Test-Path -LiteralPath $buildDir)) {
    Remove-Item -LiteralPath $buildDir -Recurse -Force
}

Import-VsDevEnvironment
Assert-VcpkgRoot

Invoke-External -FilePath "cmake" -Arguments @("--preset", $Preset) -WorkingDirectory $repoRoot
Invoke-External -FilePath "cmake" -Arguments @("--build", "--preset", $Preset, "--target", "archipelago_config", "z_generals") -WorkingDirectory $repoRoot

$runtimeDir = Get-RuntimeDirectory -RepoRoot $repoRoot
Ensure-UserDataFolders -RuntimeDir $runtimeDir
if ($referenceRuntimeDir) {
    $preserveOverrides = $OverlayCurrentArchipelago.IsPresent
    Sync-ReferenceRuntimeAssets -SourceRuntimeDir $referenceRuntimeDir -TargetRuntimeDir $runtimeDir -SyncExecutable:$UseReferenceExecutable -PreserveOverrides:$preserveOverrides
    if ($UseReferenceExecutable) {
        Assert-ReferenceExecutableSync -ReferenceRuntimeDir $referenceRuntimeDir -RuntimeDir $runtimeDir
    }
}
if ($OverlayCurrentArchipelago) {
    Overlay-ArchipelagoRuntimeFiles -RepoRoot $repoRoot -RuntimeDir $runtimeDir
}
Assert-DebugRuntimeLayout -RuntimeDir $runtimeDir

$preparedExeHash = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $runtimeDir "generalszh.exe")).Hash

Write-Host ("Prepared direct debug runtime: {0}" -f $runtimeDir)
if ($referenceRuntimeDir) {
    Write-Host ("Synced runtime assets from: {0}" -f $referenceRuntimeDir)
    if ($UseReferenceExecutable) {
        Write-Host "Using reference runtime executable (generalszh.exe/Game.dat) from the known-good debug build."
    }
    if ($OverlayCurrentArchipelago) {
        Write-Host "Applied current Archipelago loose-file overrides on top of the reference runtime."
    } else {
        Write-Host "Reference runtime kept exact; current Archipelago loose-file overrides were not applied."
    }
}
Write-Host ("Prepared generalszh.exe SHA256: {0}" -f $preparedExeHash)
$runtimeDir
