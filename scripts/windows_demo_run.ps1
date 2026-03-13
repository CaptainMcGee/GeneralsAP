[CmdletBinding()]
param(
    [switch]$Rebuild,
    [switch]$NoBridge,
    [switch]$NoLaunch,
    [switch]$Wait,
    [switch]$PreserveSession,
    [string]$Fixture = "",
    [int]$RandomUnlockCount = -1,
    [int]$RandomUnlockSeed = 0,
    [string]$StarterGeneral = "",
    [int]$StartingCashBonus = 0,
    [double]$ProductionMultiplier = 1.0,
    [switch]$NoZoomLimit,
    [switch]$AiStress
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

    $fallback = Join-Path $env:LocalAppData "Programs\Python\Python312\python.exe"
    if (Test-Path -LiteralPath $fallback) {
        return ,@($fallback)
    }

    throw "Unable to locate python.exe or py.exe. Install Python 3 and make it available from PowerShell."
}

function Resolve-RuntimeDirFromPrepareOutput {
    param([Parameter(Mandatory = $true)][object[]]$PrepareOutput)

    for ($index = $PrepareOutput.Count - 1; $index -ge 0; --$index) {
        $candidate = $PrepareOutput[$index]
        if ($null -eq $candidate) {
            continue
        }
        $candidateText = $candidate.ToString().Trim()
        if (-not $candidateText) {
            continue
        }
        if ((Test-Path -LiteralPath $candidateText -PathType Container) -and (Test-Path -LiteralPath (Join-Path $candidateText "generalszh.exe") -PathType Leaf)) {
            return $candidateText
        }
    }

    throw "windows_debug_prepare.ps1 did not emit a usable runtime directory."
}

function Stop-ExistingBridgeProcesses {
    param([Parameter(Mandatory = $true)][string]$ArchipelagoDir)

    $processes = Get-CimInstance Win32_Process -Filter "name = 'python.exe'" |
        Where-Object {
            $commandLine = $_.CommandLine
            if (-not $commandLine) {
                return $false
            }

            return (
                $commandLine.IndexOf("archipelago_bridge_local.py", [System.StringComparison]::OrdinalIgnoreCase) -ge 0 -and
                $commandLine.IndexOf($ArchipelagoDir, [System.StringComparison]::OrdinalIgnoreCase) -ge 0
            )
        }

    foreach ($process in $processes) {
        try {
            Stop-Process -Id $process.ProcessId -Force -ErrorAction Stop
            Write-Host ("Stopped existing Archipelago bridge (PID {0}) for {1}" -f $process.ProcessId, $ArchipelagoDir)
        }
        catch {
            Write-Warning ("Failed to stop existing Archipelago bridge (PID {0}): {1}" -f $process.ProcessId, $_.Exception.Message)
        }
    }
}

$repoRoot = Get-RepoRoot
$prepareScript = Join-Path $repoRoot "scripts\windows_debug_prepare.ps1"
$launchScript = Join-Path $repoRoot "scripts\windows_debug_launch.ps1"
$bridgeScript = Join-Path $repoRoot "scripts\archipelago_bridge_local.py"

if ($PreserveSession) {
    foreach ($flagName in @("Fixture", "StarterGeneral")) {
        if ($PSBoundParameters.ContainsKey($flagName) -and $PSBoundParameters[$flagName]) {
            throw "-PreserveSession cannot be combined with -$flagName."
        }
    }
    if ($PSBoundParameters.ContainsKey("RandomUnlockCount") -and $RandomUnlockCount -ge 0) {
        throw "-PreserveSession cannot be combined with -RandomUnlockCount."
    }
    if ($PSBoundParameters.ContainsKey("RandomUnlockSeed")) {
        throw "-PreserveSession cannot be combined with -RandomUnlockSeed."
    }
}

if (-not $PreserveSession -and [string]::IsNullOrWhiteSpace($StarterGeneral)) {
    $StarterGeneral = "Superweapon"
}

if ($AiStress) {
    Write-Host "AI stress behavior is now the default demo path; -AiStress is a compatibility no-op."
}

$runtimeProfile = "demo-playable"

$prepareArgs = @(
    "-ExecutionPolicy", "Bypass",
    "-File", $prepareScript,
    "-Preset", "win32-vcpkg-playtest",
    "-RuntimeConfiguration", "Release",
    "-RuntimeProfile", $runtimeProfile
)

if ($Rebuild) {
    $prepareArgs += "-Rebuild"
}

$prepareStdOut = Join-Path ([System.IO.Path]::GetTempPath()) ("generalsap-demo-prepare-stdout-{0}.log" -f [guid]::NewGuid().ToString("N"))
$prepareStdErr = Join-Path ([System.IO.Path]::GetTempPath()) ("generalsap-demo-prepare-stderr-{0}.log" -f [guid]::NewGuid().ToString("N"))
try {
    $prepareProcess = Start-Process -FilePath "powershell.exe" -ArgumentList $prepareArgs -WorkingDirectory $repoRoot -RedirectStandardOutput $prepareStdOut -RedirectStandardError $prepareStdErr -PassThru -Wait
    $prepareOutput = @()
    if (Test-Path -LiteralPath $prepareStdOut) {
        $prepareOutput += Get-Content -Path $prepareStdOut
    }
    if (Test-Path -LiteralPath $prepareStdErr) {
        $prepareOutput += Get-Content -Path $prepareStdErr
    }
}
finally {
    if (Test-Path -LiteralPath $prepareStdOut) {
        Remove-Item -LiteralPath $prepareStdOut -Force -ErrorAction SilentlyContinue
    }
    if (Test-Path -LiteralPath $prepareStdErr) {
        Remove-Item -LiteralPath $prepareStdErr -Force -ErrorAction SilentlyContinue
    }
}

if ($prepareProcess.ExitCode -ne 0) {
    foreach ($line in $prepareOutput) {
        if ($null -eq $line) {
            continue
        }
        Write-Host ($line.ToString())
    }
    throw "windows_debug_prepare.ps1 failed with exit code $($prepareProcess.ExitCode)"
}

foreach ($line in $prepareOutput) {
    if ($null -eq $line) {
        continue
    }
    Write-Host ($line.ToString())
}

$runtimeDir = Resolve-RuntimeDirFromPrepareOutput -PrepareOutput $prepareOutput

$archipelagoDir = Join-Path $runtimeDir "UserData\Archipelago"

if (-not $NoBridge) {
    Stop-ExistingBridgeProcesses -ArchipelagoDir $archipelagoDir

    $pythonCommand = Resolve-PythonCommand
    $pythonExe = $pythonCommand[0]
    $bridgeArguments = @()
    if ($pythonCommand.Length -gt 1) {
        $bridgeArguments += $pythonCommand[1..($pythonCommand.Length - 1)]
    }
    $bridgeArguments += @($bridgeScript, "--archipelago-dir", $archipelagoDir)

    if ($PreserveSession) {
        $bridgeArguments += "--preserve-session"
    }
    else {
        $bridgeArguments += "--reset-session"
        if ($Fixture) {
            $bridgeArguments += @("--fixture", $Fixture)
        }
        if ($StarterGeneral) {
            $bridgeArguments += @("--starter-general", $StarterGeneral)
        }
        if ($RandomUnlockCount -ge 0) {
            $bridgeArguments += @("--random-unlock-count", "$RandomUnlockCount")
            $bridgeArguments += @("--random-unlock-seed", "$RandomUnlockSeed")
        }
    }

    if ($StartingCashBonus -ne 0) {
        $bridgeArguments += @("--starting-cash-bonus", "$StartingCashBonus")
    }
    if ($ProductionMultiplier -ne 1.0) {
        $bridgeArguments += @("--production-multiplier", "$ProductionMultiplier")
    }
    if ($NoZoomLimit) {
        $bridgeArguments += "--disable-zoom-limit"
    }

    $seedArguments = @($bridgeArguments + @("--once"))
    & $pythonExe @seedArguments
    if ($LASTEXITCODE -ne 0) {
        throw "archipelago_bridge_local.py failed while seeding the demo session."
    }

    $sessionPath = Join-Path $archipelagoDir "LocalBridgeSession.json"
    $inboundPath = Join-Path $archipelagoDir "Bridge-Inbound.json"
    foreach ($requiredPath in @($sessionPath, $inboundPath)) {
        if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
            throw "Archipelago bridge did not create expected file: $requiredPath"
        }
    }

    $monitorArguments = @()
    if ($pythonCommand.Length -gt 1) {
        $monitorArguments += $pythonCommand[1..($pythonCommand.Length - 1)]
    }
    $monitorArguments += @($bridgeScript, "--archipelago-dir", $archipelagoDir, "--preserve-session")
    if ($StartingCashBonus -ne 0) {
        $monitorArguments += @("--starting-cash-bonus", "$StartingCashBonus")
    }
    if ($ProductionMultiplier -ne 1.0) {
        $monitorArguments += @("--production-multiplier", "$ProductionMultiplier")
    }
    if ($NoZoomLimit) {
        $monitorArguments += "--disable-zoom-limit"
    }
    Start-Process -FilePath $pythonExe -ArgumentList $monitorArguments -WorkingDirectory $repoRoot | Out-Null
    Write-Host ("Started Archipelago bridge with: {0}" -f $pythonExe)
}

if (-not $NoLaunch) {
    $launchArgs = @("-ExecutionPolicy", "Bypass", "-File", $launchScript, "-RuntimeDir", $runtimeDir)
    if ($Wait) {
        $launchArgs += "-Wait"
    }
    & powershell.exe @launchArgs
    if ($LASTEXITCODE -ne 0) {
        throw "windows_debug_launch.ps1 failed with exit code $LASTEXITCODE"
    }
}
