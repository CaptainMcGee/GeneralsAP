[CmdletBinding()]
param(
    [switch]$Rebuild,
    [switch]$NoBridge,
    [switch]$NoLaunch,
    [switch]$Wait,
    [string]$Fixture = "",
    [switch]$ResetSession,
    [string]$ReferenceRuntimeDir = "",
    [ValidateSet("reference-clean", "demo-playable", "demo-ai-stress", "archipelago-bisect", "archipelago-current")]
    [string]$RuntimeProfile = "reference-clean",
    [ValidateSet("categorized", "individual", "per_general")]
    [string]$UnitGranularity = "categorized",
    [ValidateSet("categorized", "individual", "per_general")]
    [string]$BuildingGranularity = "categorized",
    [ValidateSet("categorized", "individual", "per_general")]
    [string]$UpgradeGranularity = "categorized"
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

$repoRoot = Get-RepoRoot
$prepareScript = Join-Path $repoRoot "scripts\windows_debug_prepare.ps1"
$launchScript = Join-Path $repoRoot "scripts\windows_debug_launch.ps1"
$bridgeScript = Join-Path $repoRoot "scripts\archipelago_bridge_local.py"

$prepareArgs = @(
    "-ExecutionPolicy", "Bypass",
    "-File", $prepareScript,
    "-Preset", "win32-vcpkg-playtest",
    "-RuntimeConfiguration", "Release",
    "-RuntimeProfile", $RuntimeProfile,
    "-UnitGranularity", $UnitGranularity,
    "-BuildingGranularity", $BuildingGranularity,
    "-UpgradeGranularity", $UpgradeGranularity
)
if ($Rebuild) {
    $prepareArgs += "-Rebuild"
}
if ($ReferenceRuntimeDir) {
    $prepareArgs += @("-ReferenceRuntimeDir", $ReferenceRuntimeDir)
}

$prepareOutput = & powershell.exe @prepareArgs 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "windows_debug_prepare.ps1 failed with exit code $LASTEXITCODE"
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
    try {
        $pythonCommand = Resolve-PythonCommand
        $pythonExe = $pythonCommand[0]
        $bridgeArguments = @()
        if ($pythonCommand.Length -gt 1) {
            $bridgeArguments += $pythonCommand[1..($pythonCommand.Length - 1)]
        }
        $bridgeArguments += @($bridgeScript, "--archipelago-dir", $archipelagoDir)
        if ($Fixture) {
            $bridgeArguments += @("--fixture", $Fixture)
        }
        if ($ResetSession) {
            $bridgeArguments += "--reset-session"
        }
        Start-Process -FilePath $pythonExe -ArgumentList $bridgeArguments -WorkingDirectory $repoRoot | Out-Null
        Write-Host ("Started Archipelago bridge with: {0}" -f $pythonExe)
        if ($Fixture) {
            Write-Host ("Archipelago bridge fixture: {0}" -f $Fixture)
        }
    }
    catch {
        Write-Warning ("Unable to start Archipelago bridge automatically: {0}" -f $_.Exception.Message)
    }
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
