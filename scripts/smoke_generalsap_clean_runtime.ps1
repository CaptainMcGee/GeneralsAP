[CmdletBinding()]
param(
    [string]$BaseRuntimeDir = "",
    [string]$PreparedRuntimeDir = "",
    [string]$BridgePath = "",
    [string]$BridgeConnect = "",
    [string]$BridgeSlotName = "",
    [string]$BridgePassword = "",
    [string]$BridgeUuid = "",
    [string]$SmokeMapFile = "",
    [string]$WorkDir = "",
    [string[]]$WaitForRuntimeKey = @(),
    [string[]]$SmokeCompleteRuntimeKey = @(),
    [string[]]$WaitForSpawnedRuntimeKey = @(),
    [int]$StartupWaitSeconds = 20,
    [int]$CompletionTimeoutSeconds = 0,
    [int]$SpawnedUnitStateTimeoutSeconds = 0,
    [switch]$UseFixtureRuntime,
    [switch]$NoLaunch,
    [switch]$KeepInstall,
    [switch]$LeaveGameRunning
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

    throw "Unable to locate python.exe or py.exe for slot-data fixture generation."
}

function Assert-RuntimeLayout {
    param(
        [Parameter(Mandatory = $true)][string]$RuntimeDir,
        [Parameter(Mandatory = $true)][string]$Label,
        [switch]$RequireLaunchExe
    )

    $requiredEntries = @(
        "Data",
        "Data\INI",
        "MSS",
        "ZH_Generals",
        "Game.dat",
        "BINKW32.DLL",
        "mss32.dll",
        "INIZH.big",
        "MapsZH.big",
        "TexturesZH.big",
        "W3DZH.big",
        "WindowZH.big"
    )

    if ($RequireLaunchExe) {
        $requiredEntries += "generalszh.exe"
    }

    $missing = $requiredEntries | Where-Object {
        -not (Test-Path -LiteralPath (Join-Path $RuntimeDir $_))
    }

    if (-not $RequireLaunchExe) {
        $baseExeCandidates = @("generalszh.exe", "Generals.exe")
        $hasBaseExe = $false
        foreach ($candidate in $baseExeCandidates) {
            if (Test-Path -LiteralPath (Join-Path $RuntimeDir $candidate) -PathType Leaf) {
                $hasBaseExe = $true
                break
            }
        }
        if (-not $hasBaseExe) {
            $missing += "generalszh.exe or Generals.exe"
        }
    }

    if ($missing) {
        $message = ($missing | ForEach-Object { " - $_" }) -join [Environment]::NewLine
        throw "$Label runtime is incomplete at '$RuntimeDir'. Missing:`n$message"
    }
}

function Assert-PreparedRuntimeLayout {
    param([Parameter(Mandatory = $true)][string]$RuntimeDir)

    $requiredFiles = @(
        "generalszh.exe",
        "zlib1.dll",
        "Data\INI\Archipelago.ini",
        "Data\INI\ArchipelagoChallengeUnitProtection.ini",
        "Data\INI\UnlockableChecksDemo.ini"
    )

    $missing = $requiredFiles | Where-Object {
        -not (Test-Path -LiteralPath (Join-Path $RuntimeDir $_) -PathType Leaf)
    }

    if ($missing) {
        $message = ($missing | ForEach-Object { " - $_" }) -join [Environment]::NewLine
        throw "Prepared GeneralsAP runtime is incomplete at '$RuntimeDir'. Missing:`n$message"
    }
}

function New-FixtureRuntime {
    param([Parameter(Mandatory = $true)][string]$Root)

    $runtime = Join-Path $Root ("FixtureRuntime-" + [guid]::NewGuid().ToString("N"))
    foreach ($dir in @("Data\INI", "MappedImages\HandCreated", "MappedImages\TextureSize_512", "MSS", "ZH_Generals")) {
        New-Item -ItemType Directory -Force -Path (Join-Path $runtime $dir) | Out-Null
    }

    foreach ($file in @(
        "generalszh.exe",
        "zlib1.dll",
        "Game.dat",
        "BINKW32.DLL",
        "mss32.dll",
        "INIZH.big",
        "MapsZH.big",
        "TexturesZH.big",
        "W3DZH.big",
        "WindowZH.big",
        "Data\INI\Archipelago.ini",
        "Data\INI\ArchipelagoChallengeUnitProtection.ini",
        "Data\INI\UnlockableChecksDemo.ini",
        "MappedImages\HandCreated\zz_ArchipelagoLock.ini",
        "MappedImages\HandCreated\HandCreatedMappedImages.INI",
        "MappedImages\TextureSize_512\HandCreatedMappedImages.INI"
    )) {
        $path = Join-Path $runtime $file
        $parent = Split-Path -Path $path -Parent
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
        Set-Content -LiteralPath $path -Value "fixture $file" -Encoding ASCII
    }

    return $runtime
}

function Copy-RuntimeTree {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination
    )

    if (Test-Path -LiteralPath $Destination) {
        throw "Install directory already exists; choose an empty WorkDir or remove it explicitly: $Destination"
    }
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null

    & robocopy $Source $Destination /E /R:1 /W:1 /NFL /NDL /NJH /NJS /NP /XD UserData UserDataProbe
    if ($LASTEXITCODE -gt 7) {
        throw "robocopy failed while cloning runtime with exit code $LASTEXITCODE"
    }
}

function Copy-OverlayPayload {
    param(
        [Parameter(Mandatory = $true)][string]$PackageRoot,
        [Parameter(Mandatory = $true)][string]$InstallRoot
    )

    $gamePayload = Join-Path $PackageRoot "payload\Game"
    if (-not (Test-Path -LiteralPath $gamePayload -PathType Container)) {
        throw "Package game payload missing: $gamePayload"
    }
    Copy-Item -Path (Join-Path $gamePayload "*") -Destination $InstallRoot -Recurse -Force
}

function Get-JsonFile {
    param([Parameter(Mandatory = $true)][string]$Path)
    return Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
}

function Wait-ForRuntimeKeys {
    param(
        [Parameter(Mandatory = $true)][string]$OutboundPath,
        [AllowEmptyCollection()][Parameter(Mandatory = $true)][string[]]$RuntimeKeys,
        [Parameter(Mandatory = $true)][int]$TimeoutSeconds
    )

    if ($RuntimeKeys.Count -eq 0) {
        return
    }
    if ($TimeoutSeconds -le 0) {
        throw "-CompletionTimeoutSeconds must be > 0 when -WaitForRuntimeKey is used."
    }

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-Path -LiteralPath $OutboundPath -PathType Leaf) {
            try {
                $outbound = Get-JsonFile -Path $OutboundPath
                $completed = @($outbound.completedChecks)
                $missing = @($RuntimeKeys | Where-Object { $completed -notcontains $_ })
                if ($missing.Count -eq 0) {
                    return
                }
            }
            catch {
            }
        }
        Start-Sleep -Seconds 2
    }

    throw "Timed out waiting for runtime keys in Bridge-Outbound.json: $($RuntimeKeys -join ', ')"
}

function Wait-ForSpawnedRuntimeKeys {
    param(
        [Parameter(Mandatory = $true)][string]$StatePath,
        [AllowEmptyCollection()][Parameter(Mandatory = $true)][string[]]$RuntimeKeys,
        [Parameter(Mandatory = $true)][int]$TimeoutSeconds
    )

    if ($RuntimeKeys.Count -eq 0) {
        return
    }
    if ($TimeoutSeconds -le 0) {
        throw "-SpawnedUnitStateTimeoutSeconds must be > 0 when -WaitForSpawnedRuntimeKey is used."
    }

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-Path -LiteralPath $StatePath -PathType Leaf) {
            try {
                $state = Get-JsonFile -Path $StatePath
                $units = @($state.units)
                $missing = New-Object System.Collections.Generic.List[string]
                foreach ($runtimeKey in $RuntimeKeys) {
                    $matched = $false
                    foreach ($unit in $units) {
                        if ([string]$unit.checkId -eq $runtimeKey -and
                            [bool]$unit.spawnedCheckUnit -eq $true -and
                            [bool]$unit.alive -eq $true -and
                            [int]$unit.objectId -gt 0 -and
                            $null -ne $unit.currentPosition) {
                            $matched = $true
                            break
                        }
                    }
                    if (-not $matched) {
                        $missing.Add($runtimeKey) | Out-Null
                    }
                }
                if ($missing.Count -eq 0) {
                    return
                }
            }
            catch {
            }
        }
        Start-Sleep -Seconds 2
    }

    throw "Timed out waiting for spawned runtime keys in ArchipelagoSpawnedUnitState.json: $($RuntimeKeys -join ', ')"
}

function Normalize-RuntimeKeyArgs {
    param([AllowEmptyCollection()][string[]]$Values)

    $normalized = New-Object System.Collections.Generic.List[string]
    foreach ($value in @($Values)) {
        foreach ($part in ([string]$value -split ",")) {
            $trimmed = $part.Trim()
            if ($trimmed.Length -gt 0 -and -not $normalized.Contains($trimmed)) {
                $normalized.Add($trimmed)
            }
        }
    }
    return @($normalized)
}

function Write-RuntimeSmokeCompletionCommand {
    param(
        [Parameter(Mandatory = $true)][string]$ArchipelagoDir,
        [AllowEmptyCollection()][Parameter(Mandatory = $true)][string[]]$RuntimeKeys
    )

    if ($RuntimeKeys.Count -eq 0) {
        return
    }

    New-Item -ItemType Directory -Force -Path $ArchipelagoDir | Out-Null
    Set-Content -LiteralPath (Join-Path $ArchipelagoDir "Enable-Runtime-Smoke.flag") -Value "enabled" -Encoding ASCII
    $payload = [ordered]@{
        completedChecks = @($RuntimeKeys)
    }
    ($payload | ConvertTo-Json -Depth 4) | Set-Content -LiteralPath (Join-Path $ArchipelagoDir "Runtime-Smoke-Complete.json") -Encoding UTF8
}

function Write-RuntimeSmokeSpawnedDumpCommand {
    param(
        [Parameter(Mandatory = $true)][string]$ArchipelagoDir,
        [AllowEmptyCollection()][Parameter(Mandatory = $true)][string[]]$RuntimeKeys
    )

    if ($RuntimeKeys.Count -eq 0) {
        return
    }

    New-Item -ItemType Directory -Force -Path $ArchipelagoDir | Out-Null
    Set-Content -LiteralPath (Join-Path $ArchipelagoDir "Enable-Runtime-Smoke.flag") -Value "enabled" -Encoding ASCII
    Set-Content -LiteralPath (Join-Path $ArchipelagoDir "Runtime-Smoke-DumpSpawned.flag") -Value "enabled" -Encoding ASCII
}

function New-PackagedBridgeArgs {
    param(
        [Parameter(Mandatory = $true)][string]$ArchipelagoDir,
        [string]$SlotDataSource = "",
        [string]$BridgeConnect = "",
        [string]$BridgeSlotName = "",
        [string]$BridgePassword = "",
        [string]$BridgeUuid = "",
        [switch]$ResetSession
    )

    $args = @(
        "--once",
        "--archipelago-dir",
        $ArchipelagoDir
    )

    if ($BridgeConnect) {
        if (-not $BridgeSlotName) {
            throw "-BridgeSlotName is required when -BridgeConnect is used."
        }
        $args += @(
            "--connect",
            $BridgeConnect,
            "--slot-name",
            $BridgeSlotName,
            "--poll-interval",
            "0.1"
        )
        if ($BridgePassword) {
            $args += @("--password", $BridgePassword)
        }
        if ($BridgeUuid) {
            $args += @("--uuid", $BridgeUuid)
        }
    }
    elseif ($SlotDataSource) {
        $args += @("--slot-data", $SlotDataSource)
    }

    if ($ResetSession) {
        $args += "--reset-session"
    }

    return ,$args
}

function Get-RuntimeKeyLocationIdMap {
    param([Parameter(Mandatory = $true)][string]$SlotDataPath)

    $slotData = Get-JsonFile -Path $SlotDataPath
    $map = @{}
    foreach ($mapEntry in @($slotData.maps.PSObject.Properties)) {
        $missionVictory = $mapEntry.Value.missionVictory
        if ($missionVictory -and $missionVictory.runtimeKey) {
            $map[[string]$missionVictory.runtimeKey] = [int]$missionVictory.apLocationId
        }
        foreach ($cluster in @($mapEntry.Value.clusters)) {
            foreach ($unit in @($cluster.units)) {
                if ($unit.runtimeKey) {
                    $map[[string]$unit.runtimeKey] = [int]$unit.apLocationId
                }
            }
        }
        foreach ($captured in @($mapEntry.Value.capturedBuildings)) {
            if ($captured.runtimeKey) {
                $map[[string]$captured.runtimeKey] = [int]$captured.apLocationId
            }
        }
        foreach ($threshold in @($mapEntry.Value.supplyPileThresholds)) {
            if ($threshold.runtimeKey) {
                $map[[string]$threshold.runtimeKey] = [int]$threshold.apLocationId
            }
        }
    }
    return $map
}

$repoRoot = Get-RepoRoot
$WaitForRuntimeKey = @(Normalize-RuntimeKeyArgs -Values $WaitForRuntimeKey)
$SmokeCompleteRuntimeKey = @(Normalize-RuntimeKeyArgs -Values $SmokeCompleteRuntimeKey)
$WaitForSpawnedRuntimeKey = @(Normalize-RuntimeKeyArgs -Values $WaitForSpawnedRuntimeKey)
if ($BridgeConnect -and -not $BridgeSlotName) {
    throw "-BridgeSlotName is required when -BridgeConnect is used."
}
if ($WaitForSpawnedRuntimeKey.Count -gt 0 -and -not $SmokeMapFile) {
    throw "-SmokeMapFile is required when -WaitForSpawnedRuntimeKey is used."
}
if ($SmokeMapFile) {
    $normalizedSmokeMapFile = $SmokeMapFile.Replace("/", "\")
    $smokeMapLeaf = [System.IO.Path]::GetFileNameWithoutExtension($normalizedSmokeMapFile)
    $smokeMapParent = [System.IO.Path]::GetFileName([System.IO.Path]::GetDirectoryName($normalizedSmokeMapFile))
    if ($smokeMapLeaf -and $smokeMapParent -and $smokeMapLeaf.Equals($smokeMapParent, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "-SmokeMapFile must use the short map form consumed by the game parser, for example Maps\GC_TankGeneral.map; do not pass Maps\GC_TankGeneral\GC_TankGeneral.map."
    }
}
foreach ($spawnedKey in $WaitForSpawnedRuntimeKey) {
    if ($SmokeCompleteRuntimeKey -contains $spawnedKey) {
        throw "Do not combine -WaitForSpawnedRuntimeKey and -SmokeCompleteRuntimeKey for the same key; completing a selected key can suppress spawned materialization."
    }
}
$tempRoot = if ($WorkDir) {
    [System.IO.Path]::GetFullPath($WorkDir)
}
else {
    Join-Path ([System.IO.Path]::GetTempPath()) ("GeneralsAP-CleanRuntimeSmoke-" + [guid]::NewGuid().ToString("N"))
}

if (Test-Path -LiteralPath $tempRoot) {
    throw "WorkDir already exists; clean-runtime smoke requires an empty directory: $tempRoot"
}
New-Item -ItemType Directory -Force -Path $tempRoot | Out-Null

$gameProcess = $null
$removeTempRoot = (-not $WorkDir) -and (-not $KeepInstall) -and (-not $LeaveGameRunning)

try {
    if ($UseFixtureRuntime) {
        $NoLaunch = $true
        $BaseRuntimeDir = New-FixtureRuntime -Root $tempRoot
        $PreparedRuntimeDir = New-FixtureRuntime -Root $tempRoot
    }

    $runtimeKeysToWaitFor = @($WaitForRuntimeKey + $SmokeCompleteRuntimeKey | Select-Object -Unique)
    if ($SmokeCompleteRuntimeKey.Count -gt 0) {
        if ($NoLaunch) {
            throw "-SmokeCompleteRuntimeKey requires launching the game runtime; remove -NoLaunch or -UseFixtureRuntime."
        }
        if ($CompletionTimeoutSeconds -le 0) {
            $CompletionTimeoutSeconds = 90
        }
    }
    if ($WaitForSpawnedRuntimeKey.Count -gt 0) {
        if ($NoLaunch) {
            throw "-WaitForSpawnedRuntimeKey requires launching the game runtime; remove -NoLaunch or -UseFixtureRuntime."
        }
        if ($SpawnedUnitStateTimeoutSeconds -le 0) {
            $SpawnedUnitStateTimeoutSeconds = 180
        }
    }

    if (-not $BaseRuntimeDir) {
        throw "BaseRuntimeDir is required. Pass a legal cloned Zero Hour runtime root, or use -UseFixtureRuntime for harness-only validation."
    }
    $BaseRuntimeDir = [System.IO.Path]::GetFullPath($BaseRuntimeDir)
    if (-not (Test-Path -LiteralPath $BaseRuntimeDir -PathType Container)) {
        throw "BaseRuntimeDir does not exist: $BaseRuntimeDir"
    }

    if (-not $PreparedRuntimeDir) {
        $PreparedRuntimeDir = Join-Path $repoRoot "build\win32-vcpkg-playtest\GeneralsMD\Release"
    }
    else {
        $PreparedRuntimeDir = [System.IO.Path]::GetFullPath($PreparedRuntimeDir)
    }

    Assert-RuntimeLayout -RuntimeDir $BaseRuntimeDir -Label "Base"
    Assert-PreparedRuntimeLayout -RuntimeDir $PreparedRuntimeDir

    $installRoot = Join-Path $tempRoot "InstalledRuntime"
    Copy-RuntimeTree -Source $BaseRuntimeDir -Destination $installRoot
    Assert-RuntimeLayout -RuntimeDir $installRoot -Label "Installed clone"

    if ($BridgePath) {
        $bridgePath = [System.IO.Path]::GetFullPath($BridgePath)
        if (-not (Test-Path -LiteralPath $bridgePath -PathType Leaf)) {
            throw "BridgePath does not exist: $bridgePath"
        }
    }
    else {
        $bridgePath = Join-Path $tempRoot "GeneralsAPBridge.exe"
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $repoRoot "scripts\build_generalsap_bridge.ps1") -OutputPath $bridgePath
        if ($LASTEXITCODE -ne 0) {
            throw "build_generalsap_bridge.ps1 failed with exit code $LASTEXITCODE"
        }
    }

    $packageOut = Join-Path $tempRoot "PackageOut"
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $repoRoot "scripts\package_generalsap_alpha.ps1") -RuntimeDir $PreparedRuntimeDir -OutputDir $packageOut -BridgePath $bridgePath -BridgeKind real -NoZip
    if ($LASTEXITCODE -ne 0) {
        throw "package_generalsap_alpha.ps1 failed with exit code $LASTEXITCODE"
    }

    $packageRoot = Join-Path $packageOut "GeneralsAP-0.1.0-alpha"
    $manifest = Get-JsonFile -Path (Join-Path $packageRoot "GeneralsAP-Release-Manifest.json")
    if ($manifest.bridgeKind -ne "real") {
        throw "Clean-runtime package must stage bridgeKind=real."
    }
    if ($manifest.requiresExternalBasePatcher -ne $false -or $manifest.retailAssetsIncluded -ne $false) {
        throw "Release manifest violates base-patcher/retail-asset policy."
    }

    Copy-OverlayPayload -PackageRoot $packageRoot -InstallRoot $installRoot
    Assert-RuntimeLayout -RuntimeDir $installRoot -Label "Installed launch" -RequireLaunchExe

    $archipelagoDir = Join-Path $installRoot "UserData\Archipelago"
    New-Item -ItemType Directory -Force -Path $archipelagoDir | Out-Null

    $packagedBridge = Join-Path $packageRoot "payload\Bridge\GeneralsAPBridge.exe"
    $sessionFileName = if ($BridgeConnect) { "BridgeSession.json" } else { "LocalBridgeSession.json" }
    $bridgeSeedArgs = @()
    if ($BridgeConnect) {
        $bridgeSeedArgs = New-PackagedBridgeArgs -ArchipelagoDir $archipelagoDir -BridgeConnect $BridgeConnect -BridgeSlotName $BridgeSlotName -BridgePassword $BridgePassword -BridgeUuid $BridgeUuid -ResetSession
    }
    else {
        $pythonCommand = Resolve-PythonCommand
        $pythonExe = $pythonCommand[0]
        $pythonArgs = @()
        if ($pythonCommand.Length -gt 1) {
            $pythonArgs += $pythonCommand[1..($pythonCommand.Length - 1)]
        }
        $slotSourceDir = Join-Path $tempRoot "SlotSource"
        $pythonArgs += @(
            (Join-Path $repoRoot "scripts\archipelago_bridge_local.py"),
            "--archipelago-dir",
            $slotSourceDir,
            "--reset-session",
            "--once"
        )
        & $pythonExe @pythonArgs
        if ($LASTEXITCODE -ne 0) {
            throw "archipelago_bridge_local.py failed while creating smoke slot data."
        }

        $slotDataSource = Join-Path $slotSourceDir "Seed-Slot-Data.json"
        $bridgeSeedArgs = New-PackagedBridgeArgs -ArchipelagoDir $archipelagoDir -SlotDataSource $slotDataSource -ResetSession
    }

    & $packagedBridge @bridgeSeedArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Packaged bridge failed to materialize seeded runtime files."
    }

    foreach ($requiredPath in @(
        (Join-Path $archipelagoDir "Seed-Slot-Data.json"),
        (Join-Path $archipelagoDir "Bridge-Inbound.json"),
        (Join-Path $archipelagoDir $sessionFileName)
    )) {
        if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
            throw "Clean-runtime smoke missing bridge file: $requiredPath"
        }
    }

    Write-RuntimeSmokeCompletionCommand -ArchipelagoDir $archipelagoDir -RuntimeKeys $SmokeCompleteRuntimeKey
    Write-RuntimeSmokeSpawnedDumpCommand -ArchipelagoDir $archipelagoDir -RuntimeKeys $WaitForSpawnedRuntimeKey

    if (-not $NoLaunch) {
        $exePath = Join-Path $installRoot "generalszh.exe"
        $launchArgs = @("-win", "-userDataDir", ".\UserData\")
        if ($SmokeMapFile) {
            $launchArgs += @("-file", $SmokeMapFile)
        }
        $gameProcess = Start-Process -FilePath $exePath -WorkingDirectory $installRoot -ArgumentList $launchArgs -PassThru
        Start-Sleep -Seconds $StartupWaitSeconds
        $gameProcess.Refresh()
        $spawnedStateAlreadySatisfied = $false
        if ($gameProcess.HasExited) {
            if ($WaitForSpawnedRuntimeKey.Count -gt 0 -and $runtimeKeysToWaitFor.Count -eq 0) {
                try {
                    Wait-ForSpawnedRuntimeKeys -StatePath (Join-Path $archipelagoDir "ArchipelagoSpawnedUnitState.json") -RuntimeKeys $WaitForSpawnedRuntimeKey -TimeoutSeconds 1
                    $spawnedStateAlreadySatisfied = $true
                }
                catch {
                    throw "generalszh.exe exited during clean-runtime smoke with code $($gameProcess.ExitCode), and spawned state proof was not present: $($_.Exception.Message)"
                }
            }
            else {
                $crashInfoPath = Join-Path $installRoot "UserData\ReleaseCrashInfo.txt"
                if (Test-Path -LiteralPath $crashInfoPath -PathType Leaf) {
                    $crashText = (Get-Content -LiteralPath $crashInfoPath -ErrorAction SilentlyContinue | Select-Object -First 12) -join [Environment]::NewLine
                    throw "generalszh.exe exited during clean-runtime smoke with code $($gameProcess.ExitCode). Crash info:`n$crashText"
                }
                throw "generalszh.exe exited during clean-runtime smoke with code $($gameProcess.ExitCode)"
            }
        }

        Wait-ForRuntimeKeys -OutboundPath (Join-Path $archipelagoDir "Bridge-Outbound.json") -RuntimeKeys $runtimeKeysToWaitFor -TimeoutSeconds $CompletionTimeoutSeconds
        if (-not $spawnedStateAlreadySatisfied) {
            Wait-ForSpawnedRuntimeKeys -StatePath (Join-Path $archipelagoDir "ArchipelagoSpawnedUnitState.json") -RuntimeKeys $WaitForSpawnedRuntimeKey -TimeoutSeconds $SpawnedUnitStateTimeoutSeconds
        }

        if ($runtimeKeysToWaitFor.Count -gt 0) {
            $bridgeSubmitArgs = New-PackagedBridgeArgs -ArchipelagoDir $archipelagoDir -BridgeConnect $BridgeConnect -BridgeSlotName $BridgeSlotName -BridgePassword $BridgePassword -BridgeUuid $BridgeUuid
            & $packagedBridge @bridgeSubmitArgs
            if ($LASTEXITCODE -ne 0) {
                throw "Packaged bridge failed after runtime completions."
            }
            $session = Get-JsonFile -Path (Join-Path $archipelagoDir $sessionFileName)
            $completed = @($session.completedChecks)
            $missing = @($runtimeKeysToWaitFor | Where-Object { $completed -notcontains $_ })
            if ($missing.Count -gt 0) {
                throw "Packaged bridge did not preserve completed runtime keys: $($missing -join ', ')"
            }
            $locationIdMap = Get-RuntimeKeyLocationIdMap -SlotDataPath (Join-Path $archipelagoDir "Seed-Slot-Data.json")
            $expectedLocationIds = @()
            foreach ($runtimeKey in $runtimeKeysToWaitFor) {
                if (-not $locationIdMap.ContainsKey($runtimeKey)) {
                    throw "Seed slot data has no AP location mapping for runtime key: $runtimeKey"
                }
                $expectedLocationIds += $locationIdMap[$runtimeKey]
            }
            $completedLocations = @($session.completedLocations)
            $missingLocations = @($expectedLocationIds | Where-Object { $completedLocations -notcontains $_ })
            if ($missingLocations.Count -gt 0) {
                throw "Packaged bridge did not translate runtime keys to AP numeric location IDs: $($missingLocations -join ', ')"
            }
        }
    }

    $summary = [ordered]@{
        status = "CLEAN_RUNTIME_SMOKE_OK"
        harnessOnly = [bool]$UseFixtureRuntime
        launched = [bool](-not $NoLaunch)
        packageRoot = $packageRoot
        installRoot = $installRoot
        archipelagoDir = $archipelagoDir
        bridgeMode = if ($BridgeConnect) { "network" } else { "file" }
        smokeMapFile = $SmokeMapFile
        waitedForRuntimeKeys = @($runtimeKeysToWaitFor)
        smokeCompletedRuntimeKeys = @($SmokeCompleteRuntimeKey)
        waitedForSpawnedRuntimeKeys = @($WaitForSpawnedRuntimeKey)
    }
    ($summary | ConvertTo-Json -Depth 5)
}
finally {
    if ($gameProcess -and -not $gameProcess.HasExited -and -not $LeaveGameRunning) {
        Stop-Process -Id $gameProcess.Id -Force -ErrorAction SilentlyContinue
    }
    if ($removeTempRoot -and (Test-Path -LiteralPath $tempRoot)) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
