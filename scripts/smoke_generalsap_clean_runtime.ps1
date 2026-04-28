[CmdletBinding()]
param(
    [string]$BaseRuntimeDir = "",
    [string]$PreparedRuntimeDir = "",
    [string]$WorkDir = "",
    [string[]]$WaitForRuntimeKey = @(),
    [int]$StartupWaitSeconds = 20,
    [int]$CompletionTimeoutSeconds = 0,
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
        [Parameter(Mandatory = $true)][string]$Label
    )

    $requiredEntries = @(
        "Data",
        "Data\INI",
        "MappedImages",
        "MSS",
        "ZH_Generals",
        "generalszh.exe",
        "Game.dat",
        "BINKW32.DLL",
        "mss32.dll",
        "INIZH.big",
        "MapsZH.big",
        "TexturesZH.big",
        "W3DZH.big",
        "WindowZH.big"
    )

    $missing = $requiredEntries | Where-Object {
        -not (Test-Path -LiteralPath (Join-Path $RuntimeDir $_))
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
        [Parameter(Mandatory = $true)][string[]]$RuntimeKeys,
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

$repoRoot = Get-RepoRoot
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

    $bridgePath = Join-Path $tempRoot "GeneralsAPBridge.exe"
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $repoRoot "scripts\build_generalsap_bridge.ps1") -OutputPath $bridgePath
    if ($LASTEXITCODE -ne 0) {
        throw "build_generalsap_bridge.ps1 failed with exit code $LASTEXITCODE"
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

    $archipelagoDir = Join-Path $installRoot "UserData\Archipelago"
    New-Item -ItemType Directory -Force -Path $archipelagoDir | Out-Null

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
    $packagedBridge = Join-Path $packageRoot "payload\Bridge\GeneralsAPBridge.exe"
    & $packagedBridge --once --archipelago-dir $archipelagoDir --slot-data $slotDataSource --reset-session
    if ($LASTEXITCODE -ne 0) {
        throw "Packaged bridge failed to materialize seeded runtime files."
    }

    foreach ($requiredPath in @(
        (Join-Path $archipelagoDir "Seed-Slot-Data.json"),
        (Join-Path $archipelagoDir "Bridge-Inbound.json"),
        (Join-Path $archipelagoDir "LocalBridgeSession.json")
    )) {
        if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
            throw "Clean-runtime smoke missing bridge file: $requiredPath"
        }
    }

    if (-not $NoLaunch) {
        $exePath = Join-Path $installRoot "generalszh.exe"
        $gameProcess = Start-Process -FilePath $exePath -WorkingDirectory $installRoot -ArgumentList @("-win", "-userDataDir", ".\UserData\") -PassThru
        Start-Sleep -Seconds $StartupWaitSeconds
        $gameProcess.Refresh()
        if ($gameProcess.HasExited) {
            $crashInfoPath = Join-Path $installRoot "UserData\ReleaseCrashInfo.txt"
            if (Test-Path -LiteralPath $crashInfoPath -PathType Leaf) {
                $crashText = (Get-Content -LiteralPath $crashInfoPath -ErrorAction SilentlyContinue | Select-Object -First 12) -join [Environment]::NewLine
                throw "generalszh.exe exited during clean-runtime smoke with code $($gameProcess.ExitCode). Crash info:`n$crashText"
            }
            throw "generalszh.exe exited during clean-runtime smoke with code $($gameProcess.ExitCode)"
        }

        Wait-ForRuntimeKeys -OutboundPath (Join-Path $archipelagoDir "Bridge-Outbound.json") -RuntimeKeys $WaitForRuntimeKey -TimeoutSeconds $CompletionTimeoutSeconds

        if ($WaitForRuntimeKey.Count -gt 0) {
            & $packagedBridge --once --archipelago-dir $archipelagoDir
            if ($LASTEXITCODE -ne 0) {
                throw "Packaged bridge failed after manual runtime completions."
            }
            $session = Get-JsonFile -Path (Join-Path $archipelagoDir "LocalBridgeSession.json")
            $completed = @($session.completedChecks)
            $missing = @($WaitForRuntimeKey | Where-Object { $completed -notcontains $_ })
            if ($missing.Count -gt 0) {
                throw "Packaged bridge did not preserve completed runtime keys: $($missing -join ', ')"
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
        waitedForRuntimeKeys = @($WaitForRuntimeKey)
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
