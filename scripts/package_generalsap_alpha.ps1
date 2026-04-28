[CmdletBinding()]
param(
    [string]$RuntimeDir = "",
    [string]$OutputDir = "",
    [string]$PackageVersion = "0.1.0-alpha",
    [string]$BridgePath = "",
    [ValidateSet("staging_stub", "file_bridge", "real")]
    [string]$BridgeKind = "staging_stub",
    [switch]$NoZip
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-RepoRoot {
    return [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
}

function Copy-IfPresent {
    param(
        [Parameter(Mandatory = $true)][string]$SourceRoot,
        [Parameter(Mandatory = $true)][string]$RelativePath,
        [Parameter(Mandatory = $true)][string]$DestinationRoot,
        [AllowEmptyCollection()][Parameter(Mandatory = $true)][System.Collections.Generic.List[string]]$CopiedFiles
    )

    $source = Join-Path $SourceRoot $RelativePath
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
        return
    }

    $destination = Join-Path $DestinationRoot $RelativePath
    $destinationDir = Split-Path -Path $destination -Parent
    New-Item -ItemType Directory -Force -Path $destinationDir | Out-Null
    Copy-Item -LiteralPath $source -Destination $destination -Force
    $CopiedFiles.Add($RelativePath.Replace("\", "/")) | Out-Null
}

function Assert-NoRetailArchives {
    param([Parameter(Mandatory = $true)][string]$PackageRoot)

    $forbiddenExtensions = @(".big")
    $badFiles = Get-ChildItem -LiteralPath $PackageRoot -Recurse -File |
        Where-Object { $forbiddenExtensions -contains $_.Extension.ToLowerInvariant() }

    if ($badFiles) {
        $message = ($badFiles | ForEach-Object { $_.FullName }) -join [Environment]::NewLine
        throw "Package contains forbidden retail archive files:`n$message"
    }
}

function Get-GitValue {
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$Fallback
    )

    Push-Location $RepoRoot
    try {
        $value = & git @Arguments 2>$null
        if ($LASTEXITCODE -eq 0 -and $value) {
            return ($value | Select-Object -First 1).ToString().Trim()
        }
    }
    catch {
    }
    finally {
        Pop-Location
    }
    return $Fallback
}

$repoRoot = Get-RepoRoot
if (-not $RuntimeDir) {
    $RuntimeDir = Join-Path $repoRoot "build\win32-vcpkg-playtest\GeneralsMD\Release"
}
else {
    $RuntimeDir = [System.IO.Path]::GetFullPath($RuntimeDir)
}

if (-not $OutputDir) {
    $OutputDir = Join-Path $repoRoot "build\release"
}
else {
    $OutputDir = [System.IO.Path]::GetFullPath($OutputDir)
}

if (-not (Test-Path -LiteralPath $RuntimeDir -PathType Container)) {
    throw "RuntimeDir does not exist: $RuntimeDir"
}

$exePath = Join-Path $RuntimeDir "generalszh.exe"
if (-not (Test-Path -LiteralPath $exePath -PathType Leaf)) {
    throw "Prepared runtime is missing generalszh.exe: $exePath"
}

$packageName = "GeneralsAP-$PackageVersion"
$packageRoot = Join-Path $OutputDir $packageName
$payloadRoot = Join-Path $packageRoot "payload"
$gameRoot = Join-Path $payloadRoot "Game"
$bridgeRoot = Join-Path $payloadRoot "Bridge"
$apworldRoot = Join-Path $payloadRoot "APWorld"
$docsRoot = Join-Path $payloadRoot "Docs"

if (Test-Path -LiteralPath $packageRoot) {
    Remove-Item -LiteralPath $packageRoot -Recurse -Force
}

New-Item -ItemType Directory -Force -Path $gameRoot, $bridgeRoot, $apworldRoot, $docsRoot | Out-Null

$copiedFiles = New-Object System.Collections.Generic.List[string]
$allowlist = @(
    "generalszh.exe",
    "Game.dat",
    "Data\INI\Archipelago.ini",
    "Data\INI\ArchipelagoChallengeUnitProtection.ini",
    "Data\INI\UnlockableChecksDemo.ini",
    "MappedImages\HandCreated\zz_ArchipelagoLock.ini",
    "MappedImages\HandCreated\HandCreatedMappedImages.INI",
    "MappedImages\TextureSize_512\HandCreatedMappedImages.INI"
)

foreach ($relativePath in $allowlist) {
    Copy-IfPresent -SourceRoot $RuntimeDir -RelativePath $relativePath -DestinationRoot $gameRoot -CopiedFiles $copiedFiles
}

foreach ($requiredPath in @("generalszh.exe", "Data/INI/Archipelago.ini", "Data/INI/ArchipelagoChallengeUnitProtection.ini", "Data/INI/UnlockableChecksDemo.ini")) {
    if (-not $copiedFiles.Contains($requiredPath)) {
        throw "Prepared runtime missing required package overlay file: $requiredPath"
    }
}

$bridgeBundled = $false
$manifestBridgeKind = "none"
$bridgeManifestPath = $null
if ($BridgePath) {
    $bridgeFullPath = [System.IO.Path]::GetFullPath($BridgePath)
    if (-not (Test-Path -LiteralPath $bridgeFullPath -PathType Leaf)) {
        throw "BridgePath does not exist: $bridgeFullPath"
    }
    Copy-Item -LiteralPath $bridgeFullPath -Destination (Join-Path $bridgeRoot "GeneralsAPBridge.exe") -Force
    $bridgeBundled = $true
    $manifestBridgeKind = $BridgeKind
    $bridgeManifestPath = "payload/Bridge/GeneralsAPBridge.exe"
}
else {
    @"
Real AP bridge executable is not bundled in this package.

This overlay package is a release-staging artifact only until the real bridge sidecar exists.
"@ | Set-Content -LiteralPath (Join-Path $bridgeRoot "README-BRIDGE-NOT-BUNDLED.txt") -Encoding UTF8
}

$apworldSource = Join-Path $repoRoot "vendor\archipelago\overlay\worlds\generalszh"
if (-not (Test-Path -LiteralPath $apworldSource -PathType Container)) {
    throw "APWorld overlay source missing: $apworldSource"
}
$apworldFolder = Join-Path $apworldRoot "generalszh"
Copy-Item -LiteralPath $apworldSource -Destination $apworldFolder -Recurse -Force

Copy-Item -LiteralPath (Join-Path $repoRoot "Docs\Archipelago\Operations\Player-Release-Architecture.md") -Destination (Join-Path $docsRoot "Player-Release-Architecture.md") -Force
Copy-Item -LiteralPath (Join-Path $repoRoot "TESTING.md") -Destination (Join-Path $docsRoot "TESTING.md") -Force

@"
@echo off
pushd "%~dp0"
start "" "generalszh.exe" -win -userDataDir ".\UserData\"
popd
"@ | Set-Content -LiteralPath (Join-Path $gameRoot "Run-GeneralsAP.cmd") -Encoding ASCII
$copiedFiles.Add("Run-GeneralsAP.cmd") | Out-Null

$vendorMetadata = Get-Content -LiteralPath (Join-Path $repoRoot "vendor\archipelago\vendor.json") -Raw | ConvertFrom-Json
$worldMetadata = Get-Content -LiteralPath (Join-Path $apworldSource "archipelago.json") -Raw | ConvertFrom-Json
$constantsText = Get-Content -LiteralPath (Join-Path $apworldSource "constants.py") -Raw
$slotDataVersion = if ($constantsText -match "SLOT_DATA_VERSION\s*=\s*(\d+)") { [int]$Matches[1] } else { 2 }
$logicModel = if ($constantsText -match "LOGIC_MODEL\s*=\s*`"([^`"]+)`"") { $Matches[1] } else { "generalszh-alpha-grouped-v1" }

$manifest = [ordered]@{
    packageVersion = $PackageVersion
    releaseChannel = "alpha"
    generalsApCommit = Get-GitValue -RepoRoot $repoRoot -Arguments @("rev-parse", "HEAD") -Fallback "unknown"
    superHackersRef = Get-GitValue -RepoRoot $repoRoot -Arguments @("rev-parse", "HEAD") -Fallback "unknown"
    archipelagoVersion = [string]$vendorMetadata.upstream.current_release_tag
    apworldName = "generalszh.apworld"
    apworldVersion = [string]$worldMetadata.world_version
    bridgeVersion = 1
    bridgeBundled = $bridgeBundled
    bridgeKind = $manifestBridgeKind
    slotDataVersion = $slotDataVersion
    logicModel = $logicModel
    requiresExternalBasePatcher = $false
    requiredBaseGame = "Command & Conquer Generals Zero Hour 1.04-compatible healthy install"
    retailAssetsIncluded = $false
    userDataDirRequired = $true
    launchArgs = @("-win", "-userDataDir", ".\UserData\")
    payload = [ordered]@{
        gameOverlayFiles = @($copiedFiles | Sort-Object)
        forbiddenRetailExtensions = @(".big")
        bridgePath = $bridgeManifestPath
        apworldPayload = "folder"
    }
}

$manifestPath = Join-Path $packageRoot "GeneralsAP-Release-Manifest.json"
($manifest | ConvertTo-Json -Depth 8) + [Environment]::NewLine | Set-Content -LiteralPath $manifestPath -Encoding UTF8

@"
GeneralsAP alpha overlay package.

This package is not a standalone Zero Hour install.

Apply payload\Game onto a cloned healthy Zero Hour runtime, then launch Run-GeneralsAP.cmd from that clone.
Do not copy retail .big archives into this package.
"@ | Set-Content -LiteralPath (Join-Path $packageRoot "README-PACKAGE.txt") -Encoding UTF8

Assert-NoRetailArchives -PackageRoot $packageRoot

if (-not $NoZip) {
    $zipPath = Join-Path $OutputDir "$packageName.zip"
    if (Test-Path -LiteralPath $zipPath) {
        Remove-Item -LiteralPath $zipPath -Force
    }
    Compress-Archive -Path (Join-Path $packageRoot "*") -DestinationPath $zipPath -Force
    Assert-NoRetailArchives -PackageRoot $packageRoot
    Write-Host ("Wrote package zip: {0}" -f $zipPath)
}

Write-Host ("Wrote package root: {0}" -f $packageRoot)
Write-Host ("Bridge bundled: {0}" -f $bridgeBundled)
Write-Host ("Retail assets included: false")
