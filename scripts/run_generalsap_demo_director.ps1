[CmdletBinding()]
param(
    [string]$BaseRuntimeDir = "",
    [string]$PreparedRuntimeDir = "",
    [string]$Fixture = "human_demo_tank",
    [string]$DemoRoot = "",
    [int]$RuntimeStartupWaitSeconds = 25,
    [int]$RuntimeSmokeTimeoutSeconds = 240,
    [switch]$SkipNetworkProof,
    [switch]$FastRealApSmoke
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

    throw "Unable to locate python.exe or py.exe for demo proof."
}

function Resolve-BaseRuntimeDir {
    param([string]$Requested)

    if ($Requested) {
        return [System.IO.Path]::GetFullPath($Requested)
    }
    if ($env:GENERALSAP_BASE_RUNTIME_DIR) {
        return [System.IO.Path]::GetFullPath($env:GENERALSAP_BASE_RUNTIME_DIR)
    }

    $candidates = @(
        "C:\Program Files (x86)\Steam\steamapps\common\Command & Conquer Generals - Zero Hour",
        "C:\Program Files\EA Games\Command and Conquer Generals Zero Hour",
        "C:\Program Files (x86)\EA Games\Command and Conquer Generals Zero Hour"
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate -PathType Container) {
            return [System.IO.Path]::GetFullPath($candidate)
        }
    }

    throw "BaseRuntimeDir not found. Pass -BaseRuntimeDir or set GENERALSAP_BASE_RUNTIME_DIR to a legal healthy Zero Hour install/clone."
}

function Assert-SubdirOf {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Parent
    )

    $full = [System.IO.Path]::GetFullPath($Path)
    $root = [System.IO.Path]::GetFullPath($Parent).TrimEnd('\') + '\'
    if (-not $full.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to clean path outside demo root: $full"
    }
}

function Reset-Directory {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$DemoRootPath
    )

    Assert-SubdirOf -Path $Path -Parent $DemoRootPath
    if (Test-Path -LiteralPath $Path) {
        Remove-Item -LiteralPath $Path -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $Path | Out-Null
}

function Remove-DemoDirectoryIfPresent {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$DemoRootPath
    )

    Assert-SubdirOf -Path $Path -Parent $DemoRootPath
    if (Test-Path -LiteralPath $Path) {
        Remove-Item -LiteralPath $Path -Recurse -Force
    }
}

function Invoke-ProcessText {
    param(
        [Parameter(Mandatory = $true)][string]$Executable,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$WorkingDirectory
    )

    Write-Host ("> {0} {1}" -f $Executable, ($Arguments -join " "))
    Push-Location $WorkingDirectory
    try {
        $global:LASTEXITCODE = 0
        $output = @(& $Executable @Arguments 2>&1)
        $exitCode = if ($null -ne $global:LASTEXITCODE) { [int]$global:LASTEXITCODE } else { 0 }
    }
    finally {
        Pop-Location
    }
    foreach ($line in $output) {
        Write-Host ($line.ToString())
    }
    if ($exitCode -ne 0) {
        throw "Command failed with exit code $exitCode`: $Executable $($Arguments -join ' ')"
    }
    return ($output | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine
}

function Convert-LastJsonObject {
    param([Parameter(Mandatory = $true)][string]$Text)

    $lines = @($Text -split "\r?\n")
    for ($index = $lines.Count - 1; $index -ge 0; --$index) {
        if ($lines[$index].Trim() -ne "{") {
            continue
        }
        $candidate = ($lines[$index..($lines.Count - 1)] -join [Environment]::NewLine).Trim()
        try {
            return $candidate | ConvertFrom-Json
        }
        catch {
        }
    }
    throw "Command did not end with a JSON object summary."
}

function Read-JsonFile {
    param([Parameter(Mandatory = $true)][string]$Path)
    return Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
}

function Test-SlotRuntimeKey {
    param(
        [Parameter(Mandatory = $true)]$SlotData,
        [Parameter(Mandatory = $true)][string]$RuntimeKey
    )

    foreach ($mapEntry in @($SlotData.maps.PSObject.Properties)) {
        $mission = $mapEntry.Value.missionVictory
        if ($mission -and [string]$mission.runtimeKey -eq $RuntimeKey) {
            return $true
        }
        foreach ($cluster in @($mapEntry.Value.clusters)) {
            foreach ($unit in @($cluster.units)) {
                if ([string]$unit.runtimeKey -eq $RuntimeKey) {
                    return $true
                }
            }
        }
    }
    return $false
}

function Get-SpawnedProof {
    param(
        [Parameter(Mandatory = $true)][string]$ArchipelagoDir,
        [Parameter(Mandatory = $true)][string]$RuntimeKey
    )

    $statePath = Join-Path $ArchipelagoDir "ArchipelagoSpawnedUnitState.json"
    $state = Read-JsonFile -Path $statePath
    $matches = @()
    foreach ($unit in @($state.units)) {
        if ([string]$unit.checkId -eq $RuntimeKey) {
            $matches += $unit
        }
    }
    if ($matches.Count -eq 0) {
        throw "Spawned-unit state did not contain runtime key: $RuntimeKey"
    }
    return [ordered]@{
        statePath = $statePath
        runtimeKey = $RuntimeKey
        matchedUnits = $matches.Count
        objectIds = @($matches | ForEach-Object { [int]$_.objectId })
    }
}

function Get-CompletionProof {
    param(
        [Parameter(Mandatory = $true)][string]$ArchipelagoDir,
        [Parameter(Mandatory = $true)][string[]]$RuntimeKeys
    )

    $sessionPath = Join-Path $ArchipelagoDir "LocalBridgeSession.json"
    $outboundPath = Join-Path $ArchipelagoDir "Bridge-Outbound.json"
    $session = Read-JsonFile -Path $sessionPath
    $outbound = Read-JsonFile -Path $outboundPath
    $completedChecks = @($session.completedChecks | ForEach-Object { $_.ToString() })
    $outboundChecks = @($outbound.completedChecks | ForEach-Object { $_.ToString() })
    foreach ($runtimeKey in $RuntimeKeys) {
        if ($completedChecks -notcontains $runtimeKey) {
            throw "LocalBridgeSession.json missing completed runtime key: $runtimeKey"
        }
        if ($outboundChecks -notcontains $runtimeKey) {
            throw "Bridge-Outbound.json missing completed runtime key: $runtimeKey"
        }
    }
    return [ordered]@{
        sessionPath = $sessionPath
        outboundPath = $outboundPath
        completedChecks = @($completedChecks)
        completedLocations = @($session.completedLocations)
    }
}

$repoRoot = Get-RepoRoot
if (-not $DemoRoot) {
    $DemoRoot = Join-Path $repoRoot "build\archipelago\demo"
}
else {
    $DemoRoot = [System.IO.Path]::GetFullPath($DemoRoot)
}
New-Item -ItemType Directory -Force -Path $DemoRoot | Out-Null

$BaseRuntimeDir = Resolve-BaseRuntimeDir -Requested $BaseRuntimeDir
if (-not $PreparedRuntimeDir) {
    $PreparedRuntimeDir = Join-Path $repoRoot "build\win32-vcpkg-playtest\GeneralsMD\Release"
}
else {
    $PreparedRuntimeDir = [System.IO.Path]::GetFullPath($PreparedRuntimeDir)
}

$pythonCommand = Resolve-PythonCommand
$pythonExe = $pythonCommand[0]
$pythonArgs = @()
if ($pythonCommand.Length -gt 1) {
    $pythonArgs += $pythonCommand[1..($pythonCommand.Length - 1)]
}

$missionRuntimeKey = "mission.tank.victory"
$clusterRuntimeKey = "cluster.tank.c02.u01"
$bridgeExe = Join-Path $repoRoot "build\release-tools\GeneralsAPBridge.exe"
$fixtureDir = Join-Path $DemoRoot "fixture-bridge"
$materializationDir = Join-Path $DemoRoot "materialization"
$completionDir = Join-Path $DemoRoot "completion"
$proofPath = Join-Path $DemoRoot "Demo-Proof.json"

$steps = New-Object System.Collections.ArrayList

Reset-Directory -Path $fixtureDir -DemoRootPath $DemoRoot
$fixtureOutput = Invoke-ProcessText -Executable $pythonExe -Arguments @(
    $pythonArgs +
    @(
        (Join-Path $repoRoot "scripts\archipelago_bridge_local.py"),
        "--archipelago-dir",
        $fixtureDir,
        "--fixture",
        $Fixture,
        "--reset-session",
        "--once"
    )
) -WorkingDirectory $repoRoot
$slotData = Read-JsonFile -Path (Join-Path $fixtureDir "Seed-Slot-Data.json")
$inbound = Read-JsonFile -Path (Join-Path $fixtureDir "Bridge-Inbound.json")
if ([string]$inbound.seedId -ne "demo-human-tank") {
    throw "Demo fixture did not seed expected seedId."
}
if (-not (Test-SlotRuntimeKey -SlotData $slotData -RuntimeKey $missionRuntimeKey)) {
    throw "Fixture slot data missing $missionRuntimeKey."
}
if (-not (Test-SlotRuntimeKey -SlotData $slotData -RuntimeKey $clusterRuntimeKey)) {
    throw "Fixture slot data missing $clusterRuntimeKey."
}
$steps.Add([ordered]@{
    name = "fixture_slot_data"
    status = "passed"
    fixture = $Fixture
    seedId = $inbound.seedId
    receivedItemCount = @($inbound.receivedItems).Count
    runtimeKeys = @($missionRuntimeKey, $clusterRuntimeKey)
}) | Out-Null

Invoke-ProcessText -Executable "powershell.exe" -Arguments @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    (Join-Path $repoRoot "scripts\build_generalsap_bridge.ps1"),
    "-OutputPath",
    $bridgeExe
) -WorkingDirectory $repoRoot | Out-Null
$steps.Add([ordered]@{
    name = "build_packaged_bridge"
    status = "passed"
    bridgeExe = $bridgeExe
}) | Out-Null

Remove-DemoDirectoryIfPresent -Path $materializationDir -DemoRootPath $DemoRoot
$materializationOutput = Invoke-ProcessText -Executable "powershell.exe" -Arguments @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    (Join-Path $repoRoot "scripts\smoke_generalsap_clean_runtime.ps1"),
    "-BaseRuntimeDir",
    $BaseRuntimeDir,
    "-PreparedRuntimeDir",
    $PreparedRuntimeDir,
    "-BridgePath",
    $bridgeExe,
    "-LocalBridgeFixture",
    $Fixture,
    "-WorkDir",
    $materializationDir,
    "-KeepInstall",
    "-StartupWaitSeconds",
    ([string]$RuntimeStartupWaitSeconds),
    "-SmokeMapFile",
    "Maps\GC_TankGeneral.map",
    "-SmokeChallengePlayerGeneralIndex",
    "2",
    "-WaitForSpawnedRuntimeKey",
    $clusterRuntimeKey,
    "-SpawnedUnitStateTimeoutSeconds",
    ([string]$RuntimeSmokeTimeoutSeconds)
) -WorkingDirectory $repoRoot
$materializationSummary = Convert-LastJsonObject -Text $materializationOutput
$spawnedProof = Get-SpawnedProof -ArchipelagoDir $materializationSummary.archipelagoDir -RuntimeKey $clusterRuntimeKey
$steps.Add([ordered]@{
    name = "selected_cluster_materialization"
    status = "passed"
    summary = $materializationSummary
    spawned = $spawnedProof
}) | Out-Null

Remove-DemoDirectoryIfPresent -Path $completionDir -DemoRootPath $DemoRoot
$completionOutput = Invoke-ProcessText -Executable "powershell.exe" -Arguments @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    (Join-Path $repoRoot "scripts\smoke_generalsap_clean_runtime.ps1"),
    "-BaseRuntimeDir",
    $BaseRuntimeDir,
    "-PreparedRuntimeDir",
    $PreparedRuntimeDir,
    "-BridgePath",
    $bridgeExe,
    "-LocalBridgeFixture",
    $Fixture,
    "-WorkDir",
    $completionDir,
    "-KeepInstall",
    "-StartupWaitSeconds",
    ([string]$RuntimeStartupWaitSeconds),
    "-SmokeCompleteRuntimeKey",
    "$missionRuntimeKey,$clusterRuntimeKey",
    "-CompletionTimeoutSeconds",
    ([string]$RuntimeSmokeTimeoutSeconds)
) -WorkingDirectory $repoRoot
$completionSummary = Convert-LastJsonObject -Text $completionOutput
$completionProof = Get-CompletionProof -ArchipelagoDir $completionSummary.archipelagoDir -RuntimeKeys @($missionRuntimeKey, $clusterRuntimeKey)
$steps.Add([ordered]@{
    name = "guarded_runtime_completion_loop"
    status = "passed"
    summary = $completionSummary
    completion = $completionProof
}) | Out-Null

if ($SkipNetworkProof) {
    $steps.Add([ordered]@{
        name = "live_ap_network_loop"
        status = "skipped"
        reason = "SkipNetworkProof requested"
    }) | Out-Null
}
else {
    $networkArgs = @(
        $pythonArgs +
        @(
            (Join-Path $repoRoot "scripts\archipelago_bridge_real_ap_server_smoke.py"),
            "--bridge-exe",
            $bridgeExe,
            "--clean-runtime-smoke",
            "--base-runtime-dir",
            $BaseRuntimeDir,
            "--prepared-runtime-dir",
            $PreparedRuntimeDir,
            "--runtime-startup-wait-seconds",
            ([string]$RuntimeStartupWaitSeconds),
            "--runtime-completion-timeout-seconds",
            ([string]$RuntimeSmokeTimeoutSeconds)
        )
    )
    if ($FastRealApSmoke) {
        $networkArgs += @("--skip-install", "--skip-materialize")
    }
    $networkOutput = Invoke-ProcessText -Executable $pythonExe -Arguments $networkArgs -WorkingDirectory $repoRoot
    $networkSummary = Convert-LastJsonObject -Text $networkOutput
    $steps.Add([ordered]@{
        name = "live_ap_network_loop"
        status = "passed"
        summary = $networkSummary
    }) | Out-Null
}

$proof = [ordered]@{
    status = "DEMO_PROOF_OK"
    generatedAtUtc = [DateTime]::UtcNow.ToString("o")
    scope = "human_like_demo_nonhuman_proof"
    fixture = $Fixture
    baseRuntimeDir = $BaseRuntimeDir
    preparedRuntimeDir = $PreparedRuntimeDir
    map = "Maps\GC_TankGeneral.map"
    runtimeKeys = @($missionRuntimeKey, $clusterRuntimeKey)
    steps = @($steps.ToArray())
    caveats = @(
        "Completion proof uses explicit guarded runtime smoke input, not a natural 45-minute mission victory.",
        "Spawn proof verifies selected check object materialization, not combat fairness or player pathing.",
        "Fixture inbound unlock state is local-demo state, not AP item placement."
    )
}
($proof | ConvertTo-Json -Depth 12) + [Environment]::NewLine | Set-Content -LiteralPath $proofPath -Encoding UTF8

Write-Host ("Wrote demo proof: {0}" -f $proofPath)
Write-Host "GENERALSAP_DEMO_PROOF_OK"
