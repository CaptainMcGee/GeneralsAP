[CmdletBinding()]
param(
    [switch]$Rebuild,
    [switch]$NoBridge,
    [switch]$NoLaunch,
    [switch]$Wait,
    [switch]$BuildCurrentExecutable
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-RepoRoot {
    return [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
}

function Resolve-PythonCommand {
    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($python) {
        return @($python.Source)
    }

    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($py) {
        return @($py.Source, "-3")
    }

    $fallback = Join-Path $env:LocalAppData "Programs\Python\Python312\python.exe"
    if (Test-Path -LiteralPath $fallback) {
        return @($fallback)
    }

    throw "Unable to locate python.exe or py.exe. Install Python 3 and make it available from PowerShell."
}

$repoRoot = Get-RepoRoot
$prepareScript = Join-Path $repoRoot "scripts\windows_debug_prepare.ps1"
$launchScript = Join-Path $repoRoot "scripts\windows_debug_launch.ps1"
$bridgeScript = Join-Path $repoRoot "scripts\archipelago_bridge_local.py"

$prepareArgs = @("-ExecutionPolicy", "Bypass", "-File", $prepareScript)
if ($Rebuild) {
    $prepareArgs += "-Rebuild"
}
if (-not $BuildCurrentExecutable) {
    $prepareArgs += "-UseReferenceExecutable"
}

$runtimeDir = & powershell.exe @prepareArgs
if ($LASTEXITCODE -ne 0) {
    throw "windows_debug_prepare.ps1 failed with exit code $LASTEXITCODE"
}

$runtimeDir = ($runtimeDir | Select-Object -Last 1).ToString().Trim()
if (-not $runtimeDir) {
    throw "windows_debug_prepare.ps1 did not return a runtime directory."
}

$archipelagoDir = Join-Path $runtimeDir "UserData\Archipelago"

if (-not $NoBridge) {
    $pythonCommand = Resolve-PythonCommand
    $pythonExe = $pythonCommand[0]
    $bridgeArguments = @()
    if ($pythonCommand.Length -gt 1) {
        $bridgeArguments += $pythonCommand[1..($pythonCommand.Length - 1)]
    }
    $bridgeArguments += @($bridgeScript, "--archipelago-dir", $archipelagoDir)
    $quotedBridgeArguments = $bridgeArguments | ForEach-Object { "'{0}'" -f (($_ -replace "'", "''")) }
    $bridgeCommand = "& '{0}' {1}" -f ($pythonExe -replace "'", "''"), ($quotedBridgeArguments -join " ")
    Start-Process -FilePath "powershell.exe" -ArgumentList @(
        "-NoExit",
        "-ExecutionPolicy", "Bypass",
        "-Command", $bridgeCommand
    ) -WorkingDirectory $repoRoot | Out-Null
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
