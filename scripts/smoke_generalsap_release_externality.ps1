[CmdletBinding()]
param(
    [string]$BaseRuntimeDir = $env:GENERALSAP_BASE_RUNTIME_DIR,
    [string]$PreparedRuntimeDir = "",
    [string]$BridgePath = "",
    [string]$WorkRoot = "",
    [int]$RuntimeStartupWaitSeconds = 5,
    [int]$RuntimeSmokeTimeoutSeconds = 240,
    [switch]$RunRuntimeLaunchSmoke,
    [switch]$RunSpawnedMaterializationSmoke,
    [switch]$KeepWorkRoot,
    [switch]$KeepRuntimeWorkDirs
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-RepoRoot {
    return [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
}

function Resolve-PythonCommand {
    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($python) {
        return ,@($python.Source)
    }

    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($py) {
        return ,@($py.Source, "-3")
    }

    throw "Unable to locate python.exe or py.exe for release externality smoke."
}

function Add-Step {
    param(
        [AllowEmptyCollection()][Parameter(Mandatory = $true)][System.Collections.Generic.List[object]]$Rows,
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Status,
        [Parameter(Mandatory = $true)][double]$Seconds,
        [string]$Detail = ""
    )

    $Rows.Add([ordered]@{
        name = $Name
        status = $Status
        seconds = [math]::Round($Seconds, 2)
        detail = $Detail
    }) | Out-Null
}

function Invoke-Step {
    param(
        [AllowEmptyCollection()][Parameter(Mandatory = $true)][System.Collections.Generic.List[object]]$Rows,
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][scriptblock]$Command
    )

    Write-Host ""
    Write-Host ("=== {0} ===" -f $Name)
    $timer = [System.Diagnostics.Stopwatch]::StartNew()
    try {
        & $Command
        $timer.Stop()
        Add-Step -Rows $Rows -Name $Name -Status "passed" -Seconds $timer.Elapsed.TotalSeconds
    }
    catch {
        $timer.Stop()
        Add-Step -Rows $Rows -Name $Name -Status "failed" -Seconds $timer.Elapsed.TotalSeconds -Detail $_.Exception.Message
        throw
    }
}

function Assert-NoRetailArchives {
    param([Parameter(Mandatory = $true)][string]$Root)

    $archives = @(Get-ChildItem -LiteralPath $Root -Recurse -File -Filter "*.big" -ErrorAction SilentlyContinue)
    if ($archives.Count -gt 0) {
        throw ("Release package contains retail archive files:`n{0}" -f (($archives | ForEach-Object { $_.FullName }) -join [Environment]::NewLine))
    }
}

function Assert-NoLocalPathLeak {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string[]]$ForbiddenFragments
    )

    $files = Get-ChildItem -LiteralPath $Root -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Length -lt 1048576 -and
            $_.Extension.ToLowerInvariant() -in @(".json", ".txt", ".md", ".cmd", ".ps1", ".py", ".yaml", ".yml")
        }

    foreach ($file in $files) {
        $text = Get-Content -LiteralPath $file.FullName -Raw -ErrorAction SilentlyContinue
        if ($null -eq $text) {
            continue
        }
        foreach ($fragment in $ForbiddenFragments) {
            if ($fragment -and $text.IndexOf($fragment, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) {
                throw "Release package leaked local path fragment '$fragment' in $($file.FullName)"
            }
        }
    }
}

function Assert-ReleaseManifest {
    param([Parameter(Mandatory = $true)][string]$PackageRoot)

    $manifestPath = Join-Path $PackageRoot "GeneralsAP-Release-Manifest.json"
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
        throw "Missing release manifest: $manifestPath"
    }
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    if ($manifest.requiresExternalBasePatcher -ne $false) { throw "Manifest requires external base patcher." }
    if ($manifest.retailAssetsIncluded -ne $false) { throw "Manifest allows retail assets." }
    if ($manifest.bridgeBundled -ne $true) { throw "Manifest did not record bundled bridge." }
    if ($manifest.bridgeKind -ne "file_bridge") { throw "Externality package must use bridgeKind=file_bridge." }
    if ($manifest.slotDataVersion -ne 2) { throw "Manifest slotDataVersion drift." }
    if ($manifest.logicModel -ne "generalszh-alpha-grouped-v1") { throw "Manifest logicModel drift." }
    if ($manifest.payload.bridgePath -ne "payload/Bridge/GeneralsAPBridge.exe") {
        throw "Manifest bridgePath drift: $($manifest.payload.bridgePath)"
    }

    $runCmd = Join-Path $PackageRoot "payload\Game\Run-GeneralsAP.cmd"
    if (-not (Test-Path -LiteralPath $runCmd -PathType Leaf)) {
        throw "Missing Run-GeneralsAP.cmd in package."
    }
    $runText = Get-Content -LiteralPath $runCmd -Raw
    if ($runText -notmatch [regex]::Escape('-userDataDir ".\UserData\"')) {
        throw "Run-GeneralsAP.cmd does not preserve isolated -userDataDir launch contract."
    }

    return $manifest
}

function Invoke-CleanRuntimeSmoke {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$WorkDir,
        [Parameter(Mandatory = $true)][string[]]$ExtraArgs
    )

    $args = @(
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        (Join-Path $RepoRoot "scripts\smoke_generalsap_clean_runtime.ps1"),
        "-BaseRuntimeDir",
        $BaseRuntimeDir,
        "-PreparedRuntimeDir",
        $PreparedRuntimeDir,
        "-BridgePath",
        $ExtractedBridgePath,
        "-WorkDir",
        $WorkDir,
        "-StartupWaitSeconds",
        ([string]$RuntimeStartupWaitSeconds)
    ) + $ExtraArgs

    & powershell.exe @args
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE"
    }

    if (-not $KeepRuntimeWorkDirs -and (Test-Path -LiteralPath $WorkDir)) {
        $resolved = (Resolve-Path -LiteralPath $WorkDir).Path
        if (-not $resolved.StartsWith($RunRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to remove runtime smoke work dir outside release externality root: $resolved"
        }
        Remove-Item -LiteralPath $resolved -Recurse -Force
    }
}

$RepoRoot = Get-RepoRoot
if (-not $PreparedRuntimeDir) {
    $PreparedRuntimeDir = Join-Path $RepoRoot "build\win32-vcpkg-playtest\GeneralsMD\Release"
}
$PreparedRuntimeDir = [System.IO.Path]::GetFullPath($PreparedRuntimeDir)

if (-not $WorkRoot) {
    $WorkRoot = Join-Path $RepoRoot "build\archipelago\release-externality"
}
$WorkRoot = [System.IO.Path]::GetFullPath($WorkRoot)
$RunName = (Get-Date -Format "yyyyMMdd-HHmmss") + " with spaces " + ([guid]::NewGuid().ToString("N").Substring(0, 8))
$RunRoot = Join-Path $WorkRoot $RunName
$PackageOut = Join-Path $RunRoot "Package Out With Spaces"
$ZipExtractRoot = Join-Path $RunRoot "Zip Extract With Spaces"
$BridgeOut = Join-Path $RunRoot "Bridge Bin With Spaces\GeneralsAPBridge.exe"
$SummaryPath = Join-Path $RunRoot "Release-Externality-Smoke.json"
$PackageRoot = ""
$ZipPath = ""

if (Test-Path -LiteralPath $RunRoot) {
    throw "Release externality run root already exists: $RunRoot"
}
New-Item -ItemType Directory -Force -Path $RunRoot | Out-Null

$Rows = New-Object System.Collections.Generic.List[object]
$status = "RELEASE_EXTERNALITY_SMOKE_FAILED"
$ExtractedBridgePath = ""

try {
    Invoke-Step -Rows $Rows -Name "Build or resolve bridge" -Command {
        if ($BridgePath) {
            $resolvedBridge = [System.IO.Path]::GetFullPath($BridgePath)
            if (-not (Test-Path -LiteralPath $resolvedBridge -PathType Leaf)) {
                throw "BridgePath does not exist: $resolvedBridge"
            }
            $script:BridgeOut = $resolvedBridge
        }
        else {
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $BridgeOut) | Out-Null
            & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $RepoRoot "scripts\build_generalsap_bridge.ps1") -OutputPath $BridgeOut
            if ($LASTEXITCODE -ne 0) {
                throw "build_generalsap_bridge.ps1 failed with exit code $LASTEXITCODE"
            }
        }
        return $BridgeOut
    }

    Invoke-Step -Rows $Rows -Name "Package prepared runtime" -Command {
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $RepoRoot "scripts\package_generalsap_alpha.ps1") `
            -RuntimeDir $PreparedRuntimeDir `
            -OutputDir $PackageOut `
            -BridgePath $BridgeOut `
            -BridgeKind file_bridge
        if ($LASTEXITCODE -ne 0) {
            throw "package_generalsap_alpha.ps1 failed with exit code $LASTEXITCODE"
        }
        return $PackageOut
    }

    $PackageRoot = Join-Path $PackageOut "GeneralsAP-0.1.0-alpha"
    $ZipPath = Join-Path $PackageOut "GeneralsAP-0.1.0-alpha.zip"

    Invoke-Step -Rows $Rows -Name "Validate package root and zip" -Command {
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $RepoRoot "scripts\validate_generalsap_alpha_package.ps1") -PackageRoot $PackageRoot
        if ($LASTEXITCODE -ne 0) { throw "Package root validation failed." }
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $RepoRoot "scripts\validate_generalsap_alpha_package.ps1") -ZipPath $ZipPath
        if ($LASTEXITCODE -ne 0) { throw "Package zip validation failed." }
        [void](Assert-ReleaseManifest -PackageRoot $PackageRoot)
        Assert-NoRetailArchives -Root $PackageRoot
        Assert-NoLocalPathLeak -Root $PackageRoot -ForbiddenFragments @($RepoRoot, $RunRoot, $PreparedRuntimeDir)
        return $ZipPath
    }

    Invoke-Step -Rows $Rows -Name "Extract zip in path with spaces" -Command {
        New-Item -ItemType Directory -Force -Path $ZipExtractRoot | Out-Null
        Expand-Archive -LiteralPath $ZipPath -DestinationPath $ZipExtractRoot -Force
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $RepoRoot "scripts\validate_generalsap_alpha_package.ps1") -PackageRoot $ZipExtractRoot
        if ($LASTEXITCODE -ne 0) { throw "Extracted package validation failed." }
        [void](Assert-ReleaseManifest -PackageRoot $ZipExtractRoot)
        Assert-NoRetailArchives -Root $ZipExtractRoot
        Assert-NoLocalPathLeak -Root $ZipExtractRoot -ForbiddenFragments @($RepoRoot, $RunRoot, $PreparedRuntimeDir)
        $script:ExtractedBridgePath = Join-Path $ZipExtractRoot "payload\Bridge\GeneralsAPBridge.exe"
        if (-not (Test-Path -LiteralPath $ExtractedBridgePath -PathType Leaf)) {
            throw "Extracted packaged bridge missing: $ExtractedBridgePath"
        }
        return $ZipExtractRoot
    }

    Invoke-Step -Rows $Rows -Name "Extracted bridge file-mode smoke" -Command {
        $pythonCommand = Resolve-PythonCommand
        $pythonExe = $pythonCommand[0]
        $pythonArgs = @()
        if ($pythonCommand.Length -gt 1) {
            $pythonArgs += $pythonCommand[1..($pythonCommand.Length - 1)]
        }
        $pythonArgs += @(
            (Join-Path $RepoRoot "scripts\archipelago_bridge_executable_smoke.py"),
            "--bridge-exe",
            $ExtractedBridgePath
        )
        & $pythonExe @pythonArgs
        if ($LASTEXITCODE -ne 0) {
            throw "archipelago_bridge_executable_smoke.py failed with exit code $LASTEXITCODE"
        }
        return $ExtractedBridgePath
    }

    if ($RunRuntimeLaunchSmoke -or $RunSpawnedMaterializationSmoke) {
        if (-not $BaseRuntimeDir) {
            throw "BaseRuntimeDir is required for runtime launch externality smokes."
        }
        $BaseRuntimeDir = [System.IO.Path]::GetFullPath($BaseRuntimeDir)
        if (-not (Test-Path -LiteralPath $BaseRuntimeDir -PathType Container)) {
            throw "BaseRuntimeDir does not exist: $BaseRuntimeDir"
        }
    }

    if ($RunRuntimeLaunchSmoke) {
        Invoke-Step -Rows $Rows -Name "Clean-runtime launch from path with spaces" -Command {
            $workDir = Join-Path $RunRoot "Clean Runtime Auto With Spaces"
            Invoke-CleanRuntimeSmoke -Name "Clean-runtime launch from path with spaces" -WorkDir $workDir -ExtraArgs @(
                "-SmokeCompleteRuntimeKey",
                "mission.tank.victory,cluster.tank.c02.u01",
                "-CompletionTimeoutSeconds",
                ([string]$RuntimeSmokeTimeoutSeconds)
            )
            return $workDir
        }
    }

    if ($RunSpawnedMaterializationSmoke) {
        Invoke-Step -Rows $Rows -Name "Clean-runtime spawned materialization from path with spaces" -Command {
            $workDir = Join-Path $RunRoot "Clean Runtime Spawn With Spaces"
            Invoke-CleanRuntimeSmoke -Name "Clean-runtime spawned materialization from path with spaces" -WorkDir $workDir -ExtraArgs @(
                "-SmokeMapFile",
                "Maps\GC_TankGeneral.map",
                "-SmokeChallengePlayerGeneralIndex",
                "2",
                "-WaitForSpawnedRuntimeKey",
                "cluster.tank.c02.u01",
                "-SpawnedUnitStateTimeoutSeconds",
                ([string]$RuntimeSmokeTimeoutSeconds)
            )
            return $workDir
        }
    }

    $status = "RELEASE_EXTERNALITY_SMOKE_OK"
}
finally {
    $failed = @($Rows | Where-Object { $_.status -ne "passed" }).Count
    $summary = [ordered]@{
        status = if ($failed -eq 0 -and $status -eq "RELEASE_EXTERNALITY_SMOKE_OK") { "RELEASE_EXTERNALITY_SMOKE_OK" } else { "RELEASE_EXTERNALITY_SMOKE_FAILED" }
        generatedAtUtc = [DateTime]::UtcNow.ToString("o")
        runRoot = $RunRoot
        packageRoot = if ($PackageRoot) { $PackageRoot } else { $null }
        zipPath = if ($ZipPath) { $ZipPath } else { $null }
        zipExtractRoot = $ZipExtractRoot
        extractedBridgePath = $ExtractedBridgePath
        runRuntimeLaunchSmoke = [bool]$RunRuntimeLaunchSmoke
        runSpawnedMaterializationSmoke = [bool]$RunSpawnedMaterializationSmoke
        steps = $Rows
    }
    $summary | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $SummaryPath -Encoding UTF8

    if (-not $KeepWorkRoot -and $summary.status -eq "RELEASE_EXTERNALITY_SMOKE_OK" -and (Test-Path -LiteralPath $RunRoot)) {
        $preserveRoot = Join-Path $WorkRoot ("latest-summary-" + ([guid]::NewGuid().ToString("N").Substring(0, 8)))
        New-Item -ItemType Directory -Force -Path $preserveRoot | Out-Null
        Copy-Item -LiteralPath $SummaryPath -Destination (Join-Path $preserveRoot "Release-Externality-Smoke.json") -Force
        $resolvedRunRoot = (Resolve-Path -LiteralPath $RunRoot).Path
        if (-not $resolvedRunRoot.StartsWith($WorkRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to remove release externality run root outside work root: $resolvedRunRoot"
        }
        Remove-Item -LiteralPath $resolvedRunRoot -Recurse -Force
        $SummaryPath = Join-Path $preserveRoot "Release-Externality-Smoke.json"
    }
}

if ($status -ne "RELEASE_EXTERNALITY_SMOKE_OK") {
    Write-Error ("RELEASE_EXTERNALITY_SMOKE_FAILED: {0}" -f $SummaryPath)
    exit 1
}

Write-Host ("RELEASE_EXTERNALITY_SMOKE_OK: {0}" -f $SummaryPath)
