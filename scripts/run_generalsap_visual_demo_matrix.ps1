[CmdletBinding()]
param(
    [string]$BaseRuntimeDir = $env:GENERALSAP_BASE_RUNTIME_DIR,
    [string]$PreparedRuntimeDir = "",
    [string]$BridgePath = "",
    [string]$Fixture = "human_demo_all_generals",
    [int[]]$GeneralIndices = @(0, 1, 2, 3, 4, 5, 6, 7, 8),
    [string]$SmokeMapFile = "Maps\GC_TankGeneral.map",
    [string]$WaitForSpawnedRuntimeKey = "cluster.tank.c02.u01",
    [string]$ReviewRoot = "build\archipelago\visual-demo-matrix",
    [int]$StartupWaitSeconds = 5,
    [int]$SpawnedUnitStateTimeoutSeconds = 240,
    [int]$CaptureIntervalSeconds = 2,
    [int]$PostSmokeCaptureSeconds = 8,
    [switch]$ContinueOnFailure
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-RepoPath([string]$Path) {
    if ([System.IO.Path]::IsPathRooted($Path)) {
        return $Path
    }
    return (Join-Path $RepoRoot $Path)
}

function Get-ApGeneralExpectedTemplate([int]$Index) {
    switch ($Index) {
        0 { return "FactionAmericaAirForceGeneral" }
        1 { return "FactionAmericaLaserGeneral" }
        2 { return "FactionAmericaSuperWeaponGeneral" }
        3 { return "FactionChinaTankGeneral" }
        4 { return "FactionChinaInfantryGeneral" }
        5 { return "FactionChinaNukeGeneral" }
        6 { return "FactionGLAToxinGeneral" }
        7 { return "FactionGLADemolitionGeneral" }
        8 { return "FactionGLAStealthGeneral" }
        default { return "" }
    }
}

function Get-VisualDemoMatrixCase([int]$Index, [string]$DefaultMapFile, [string]$DefaultSpawnedRuntimeKey) {
    $mapFile = $DefaultMapFile
    $spawnedRuntimeKey = $DefaultSpawnedRuntimeKey
    $note = "Tank-opponent selected cluster materialization proof."

    if ($DefaultMapFile -match "GC_TankGeneral" -and $Index -eq 3) {
        $mapFile = "Maps\GC_ChemGeneral.map"
        $spawnedRuntimeKey = ""
        $note = "Tank starter self-match is not present in retail Challenge campaigns; this row proves Tank starter Challenge launch on a valid opponent map."
    }

    return [ordered]@{
        smokeMapFile = $mapFile
        waitForSpawnedRuntimeKey = $spawnedRuntimeKey
        spawnProofRequested = -not [string]::IsNullOrWhiteSpace($spawnedRuntimeKey)
        minStartupWaitSeconds = if ([string]::IsNullOrWhiteSpace($spawnedRuntimeKey)) { 12 } else { 0 }
        minPostSmokeCaptureSeconds = if ([string]::IsNullOrWhiteSpace($spawnedRuntimeKey)) { 20 } else { 0 }
        note = $note
    }
}

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptRoot
$VisualGateScript = Join-Path $ScriptRoot "run_generalsap_visual_demo_gate.ps1"

if (-not $BaseRuntimeDir) {
    throw "BaseRuntimeDir is required. Pass -BaseRuntimeDir or set GENERALSAP_BASE_RUNTIME_DIR."
}
if (-not (Test-Path -LiteralPath $VisualGateScript -PathType Leaf)) {
    throw "Missing visual demo gate script: $VisualGateScript"
}

$resolvedReviewRoot = Resolve-RepoPath $ReviewRoot
$matrixName = (Get-Date -Format "yyyyMMdd-HHmmss") + "-" + ([guid]::NewGuid().ToString("N").Substring(0, 8))
$matrixRoot = Join-Path $resolvedReviewRoot $matrixName
New-Item -ItemType Directory -Force -Path $matrixRoot | Out-Null

if (-not $BridgePath) {
    $BridgePath = Join-Path $matrixRoot "GeneralsAPBridge.exe"
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $RepoRoot "scripts\build_generalsap_bridge.ps1") -OutputPath $BridgePath
    if ($LASTEXITCODE -ne 0) {
        throw "build_generalsap_bridge.ps1 failed with exit code $LASTEXITCODE"
    }
}
else {
    $BridgePath = [System.IO.Path]::GetFullPath($BridgePath)
}

$rows = New-Object System.Collections.Generic.List[object]
$failed = 0

foreach ($index in $GeneralIndices) {
    $expectedTemplate = Get-ApGeneralExpectedTemplate $index
    if (-not $expectedTemplate) {
        throw "Unknown AP general index in matrix: $index"
    }
    $case = Get-VisualDemoMatrixCase -Index $index -DefaultMapFile $SmokeMapFile -DefaultSpawnedRuntimeKey $WaitForSpawnedRuntimeKey
    $effectiveStartupWaitSeconds = [Math]::Max($StartupWaitSeconds, [int]$case["minStartupWaitSeconds"])
    $effectivePostSmokeCaptureSeconds = [Math]::Max($PostSmokeCaptureSeconds, [int]$case["minPostSmokeCaptureSeconds"])

    $indexRoot = Join-Path $matrixRoot ("ap-general-{0}" -f $index)
    New-Item -ItemType Directory -Force -Path $indexRoot | Out-Null

    $args = @(
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        $VisualGateScript,
        "-BaseRuntimeDir",
        $BaseRuntimeDir,
        "-BridgePath",
        $BridgePath,
        "-Fixture",
        $Fixture,
        "-SmokeMapFile",
        $case["smokeMapFile"],
        "-SmokeChallengePlayerGeneralIndex",
        ([string]$index),
        "-ReviewRoot",
        $indexRoot,
        "-StartupWaitSeconds",
        ([string]$effectiveStartupWaitSeconds),
        "-SpawnedUnitStateTimeoutSeconds",
        ([string]$SpawnedUnitStateTimeoutSeconds),
        "-CaptureIntervalSeconds",
        ([string]$CaptureIntervalSeconds),
        "-PostSmokeCaptureSeconds",
        ([string]$effectivePostSmokeCaptureSeconds)
    )
    if ($case["spawnProofRequested"]) {
        $args += @("-WaitForSpawnedRuntimeKey", $case["waitForSpawnedRuntimeKey"])
    }
    else {
        $args += @("-NoSpawnProof")
    }
    if ($PreparedRuntimeDir) {
        $args += @("-PreparedRuntimeDir", $PreparedRuntimeDir)
    }

    Write-Host ("=== Visual demo matrix AP general {0}: {1} ===" -f $index, $expectedTemplate)
    & powershell.exe @args
    $exitCode = $LASTEXITCODE

    $summaryFile = Get-ChildItem -LiteralPath $indexRoot -Recurse -Filter "Visual-Demo-Gate.json" -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    $summary = $null
    if ($summaryFile) {
        $summary = Get-Content -LiteralPath $summaryFile.FullName -Raw | ConvertFrom-Json
    }

    $passed = (
        $exitCode -eq 0 -and
        $summary -ne $null -and
        $summary.status -eq "VISUAL_DEMO_GATE_OK" -and
        $summary.challengeStartVerified -eq $true -and
        $summary.expectedPlayerTemplate -eq $expectedTemplate -and
        $summary.defeatSplashDetected -eq $false
    )
    if (-not $passed) {
        $failed += 1
    }

    $rows.Add([ordered]@{
        apGeneralIndex = $index
        expectedPlayerTemplate = $expectedTemplate
        exitCode = $exitCode
        status = if ($summary) { $summary.status } else { "missing_summary" }
        passed = $passed
        smokeMapFile = $case["smokeMapFile"]
        waitForSpawnedRuntimeKey = $case["waitForSpawnedRuntimeKey"]
        spawnProofRequested = $case["spawnProofRequested"]
        startupWaitSeconds = $effectiveStartupWaitSeconds
        postSmokeCaptureSeconds = $effectivePostSmokeCaptureSeconds
        note = $case["note"]
        challengeStartVerified = if ($summary) { $summary.challengeStartVerified } else { $false }
        spawnedRuntimeKeyObserved = if ($summary) { $summary.spawnedRuntimeKeyObserved } else { $false }
        defeatSplashDetected = if ($summary) { $summary.defeatSplashDetected } else { $null }
        usableScreenshotCount = if ($summary) { $summary.usableScreenshotCount } else { 0 }
        screenshotCount = if ($summary) { $summary.screenshotCount } else { 0 }
        summaryPath = if ($summaryFile) { $summaryFile.FullName } else { $null }
    }) | Out-Null

    if (-not $passed -and -not $ContinueOnFailure) {
        break
    }
}

$matrixStatus = if ($failed -eq 0 -and $rows.Count -eq $GeneralIndices.Count) { "VISUAL_DEMO_MATRIX_OK" } else { "VISUAL_DEMO_MATRIX_FAILED" }
$summaryPath = Join-Path $matrixRoot "Visual-Demo-Matrix.json"
$matrixSummary = [ordered]@{
    status = $matrixStatus
    matrixRoot = $matrixRoot
    fixture = $Fixture
    smokeMapFile = $SmokeMapFile
    waitForSpawnedRuntimeKey = $WaitForSpawnedRuntimeKey
    selfMatchFallback = "AP general 3 uses Maps\GC_ChemGeneral.map with start-only proof when default map is GC_TankGeneral because retail Challenge campaigns have no Tank-vs-Tank self-match."
    tested = $rows.Count
    requested = $GeneralIndices.Count
    failed = $failed
    bridgePath = $BridgePath
    rows = $rows
}
$matrixSummary | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $summaryPath -Encoding UTF8

if ($matrixStatus -ne "VISUAL_DEMO_MATRIX_OK") {
    Write-Error ("{0}: failed={1} summary={2}" -f $matrixStatus, $failed, $summaryPath)
    exit 1
}

Write-Host ("{0}: {1}" -f $matrixStatus, $summaryPath)
