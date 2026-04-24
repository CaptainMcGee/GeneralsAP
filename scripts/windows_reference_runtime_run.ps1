[CmdletBinding()]
param(
    [switch]$NoBridge,
    [switch]$Wait,
    [switch]$UseUserDataDir
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-RepoRoot {
    return [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
}

function Get-ReferenceRuntimeDir {
    param([Parameter(Mandatory = $true)][string]$RepoRoot)

    $workspaceRoot = [System.IO.Path]::GetFullPath((Join-Path $RepoRoot "..\..\.."))
    $runtimeDir = Join-Path $workspaceRoot "build\win32-vcpkg-debug\GeneralsMD\Debug"
    if (-not (Test-Path -LiteralPath (Join-Path $runtimeDir "generalszh.exe") -PathType Leaf)) {
        throw "Known-good reference runtime not found at $runtimeDir"
    }
    return $runtimeDir
}

function Assert-RuntimeLayout {
    param([Parameter(Mandatory = $true)][string]$RuntimeDir)

    $requiredEntries = @(
        "generalszh.exe",
        "Game.dat",
        "Data",
        "Data\INI",
        "MSS",
        "ZH_Generals",
        "BINKW32.DLL",
        "mss32.dll",
        "INIZH.big",
        "MapsZH.big",
        "TexturesZH.big",
        "W3DZH.big",
        "WindowZH.big"
    )

    $missing = @($requiredEntries | Where-Object {
        -not (Test-Path -LiteralPath (Join-Path $RuntimeDir $_))
    })

    if ($missing.Count -gt 0) {
        $message = ($missing | ForEach-Object { " - $_" }) -join [Environment]::NewLine
        throw "Reference runtime is incomplete at '$RuntimeDir'. Missing:`n$message"
    }
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

$repoRoot = Get-RepoRoot
$runtimeDir = Get-ReferenceRuntimeDir -RepoRoot $repoRoot
Assert-RuntimeLayout -RuntimeDir $runtimeDir

Write-Host ("Using exact reference runtime: {0}" -f $runtimeDir)

$arguments = @("-win")
$archipelagoDir = Join-Path $runtimeDir "UserData\Archipelago"

if ($UseUserDataDir) {
    foreach ($relativePath in @("UserData", "UserData\Archipelago")) {
        New-Item -ItemType Directory -Force -Path (Join-Path $runtimeDir $relativePath) | Out-Null
    }
    $arguments += @("-userDataDir", ".\UserData\")
}

if (-not $NoBridge) {
    try {
        if (-not $UseUserDataDir) {
            throw "Bridge requires -UseUserDataDir so the runtime has a deterministic UserData\\Archipelago path."
        }

        $pythonCommand = Resolve-PythonCommand
        $pythonExe = $pythonCommand[0]
        $bridgeScript = Join-Path $repoRoot "scripts\archipelago_bridge_local.py"
        $bridgeArguments = @()
        if ($pythonCommand.Length -gt 1) {
            $bridgeArguments += $pythonCommand[1..($pythonCommand.Length - 1)]
        }
        $bridgeArguments += @($bridgeScript, "--archipelago-dir", $archipelagoDir)
        Start-Process -FilePath $pythonExe -ArgumentList $bridgeArguments -WorkingDirectory $repoRoot | Out-Null
        Write-Host ("Started Archipelago bridge with: {0}" -f $pythonExe)
    }
    catch {
        Write-Warning ("Bridge not started: {0}" -f $_.Exception.Message)
    }
}

$exePath = Join-Path $runtimeDir "generalszh.exe"
if ($Wait) {
    Push-Location $runtimeDir
    try {
        & $exePath @arguments
        if ($LASTEXITCODE -ne 0) {
            throw "generalszh.exe exited with code $LASTEXITCODE"
        }
    }
    finally {
        Pop-Location
    }
}
else {
    $process = Start-Process -FilePath $exePath -WorkingDirectory $runtimeDir -ArgumentList $arguments -PassThru
    Start-Sleep -Seconds 2
    $process.Refresh()
    if ($process.HasExited) {
        throw "Reference generalszh.exe exited early with code $($process.ExitCode)"
    }
    Write-Host ("Launched reference generalszh.exe (PID {0})" -f $process.Id)
}
