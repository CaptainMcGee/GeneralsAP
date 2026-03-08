[CmdletBinding()]
param(
    [switch]$Rebuild,
    [string]$Preset = "win32-vcpkg-debug"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-RepoRoot {
    return [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
}

function Invoke-External {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [string]$WorkingDirectory = ""
    )

    if ($WorkingDirectory) {
        Push-Location $WorkingDirectory
    }

    try {
        & $FilePath @Arguments
        if ($LASTEXITCODE -ne 0) {
            throw "$FilePath exited with code $LASTEXITCODE"
        }
    }
    finally {
        if ($WorkingDirectory) {
            Pop-Location
        }
    }
}

function Get-VsWherePath {
    $candidate = Join-Path ${env:ProgramFiles(x86)} "Microsoft Visual Studio\Installer\vswhere.exe"
    if (Test-Path -LiteralPath $candidate) {
        return $candidate
    }

    $command = Get-Command vswhere.exe -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    throw "vswhere.exe not found. Install Visual Studio 2022 with the C++ workload."
}

function Import-VsDevEnvironment {
    $vswhere = Get-VsWherePath
    $installationPath = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
    if (-not $installationPath) {
        throw "Unable to locate a Visual Studio installation with x86/x64 C++ tools."
    }

    $vsDevCmd = Join-Path $installationPath "Common7\Tools\VsDevCmd.bat"
    if (-not (Test-Path -LiteralPath $vsDevCmd)) {
        throw "VsDevCmd.bat not found at $vsDevCmd"
    }

    $envDump = & cmd.exe /s /c "`"$vsDevCmd`" -no_logo -arch=x86 -host_arch=x64 >nul && set"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to import Visual Studio developer environment from $vsDevCmd"
    }

    foreach ($line in $envDump) {
        if ($line -notmatch "=") {
            continue
        }
        $name, $value = $line -split "=", 2
        Set-Item -Path "Env:$name" -Value $value
    }

    if (-not (Get-Command cl.exe -ErrorAction SilentlyContinue)) {
        throw "cl.exe is still not available after importing the Visual Studio developer environment."
    }
    if (-not $env:INCLUDE) {
        throw "INCLUDE is not set after importing the Visual Studio developer environment."
    }
}

function Assert-VcpkgRoot {
    if (-not $env:VCPKG_ROOT) {
        throw "VCPKG_ROOT is not set. Install/configure vcpkg before running this script."
    }
    if (-not (Test-Path -LiteralPath $env:VCPKG_ROOT)) {
        throw "VCPKG_ROOT points to a path that does not exist: $($env:VCPKG_ROOT)"
    }
}

function Get-RuntimeDirectory {
    param([Parameter(Mandatory = $true)][string]$RepoRoot)

    $runtimeDir = Join-Path $RepoRoot "build\win32-vcpkg-debug\GeneralsMD\Debug"
    $exePath = Join-Path $runtimeDir "generalszh.exe"
    if (-not (Test-Path -LiteralPath $exePath)) {
        throw "Expected debug runtime executable was not found at $exePath"
    }

    return $runtimeDir
}

function Ensure-UserDataFolders {
    param([Parameter(Mandatory = $true)][string]$RuntimeDir)

    foreach ($relativePath in @("UserData", "UserData\Archipelago")) {
        New-Item -ItemType Directory -Force -Path (Join-Path $RuntimeDir $relativePath) | Out-Null
    }
}

function Assert-DebugRuntimeLayout {
    param([Parameter(Mandatory = $true)][string]$RuntimeDir)

    $requiredDirectories = @(
        "Data",
        "Data\Cursors",
        "Data\English",
        "Data\INI",
        "Data\Movies",
        "Data\Scripts",
        "Data\WaterPlane",
        "MSS",
        "ZH_Generals"
    )

    $requiredFiles = @(
        "generalszh.exe",
        "Game.dat",
        "Generals.dat",
        "BINKW32.DLL",
        "mss32.dll",
        "DebugWindow.dll",
        "AudioEnglishZH.big",
        "AudioZH.big",
        "EnglishZH.big",
        "gensecZH.big",
        "INIZH.big",
        "MapsZH.big",
        "Music.big",
        "MusicZH.big",
        "PatchData.big",
        "PatchINI.big",
        "PatchZH.big",
        "ShadersZH.big",
        "SpeechEnglishZH.big",
        "SpeechZH.big",
        "TerrainZH.big",
        "TexturesZH.big",
        "W3DEnglishZH.big",
        "W3DZH.big",
        "WindowZH.big"
    )

    $missing = New-Object System.Collections.Generic.List[string]

    foreach ($relativePath in $requiredDirectories) {
        if (-not (Test-Path -LiteralPath (Join-Path $RuntimeDir $relativePath) -PathType Container)) {
            $missing.Add($relativePath)
        }
    }

    foreach ($relativePath in $requiredFiles) {
        if (-not (Test-Path -LiteralPath (Join-Path $RuntimeDir $relativePath) -PathType Leaf)) {
            $missing.Add($relativePath)
        }
    }

    if ($missing.Count -gt 0) {
        $message = ($missing | Sort-Object | ForEach-Object { " - $_" }) -join [Environment]::NewLine
        throw "Direct debug runtime is incomplete at '$RuntimeDir'. Missing required runtime entries:`n$message"
    }
}

$repoRoot = Get-RepoRoot
$buildDir = Join-Path $repoRoot ("build\" + $Preset)

if ($Rebuild -and (Test-Path -LiteralPath $buildDir)) {
    Remove-Item -LiteralPath $buildDir -Recurse -Force
}

Import-VsDevEnvironment
Assert-VcpkgRoot

Invoke-External -FilePath "cmake" -Arguments @("--preset", $Preset) -WorkingDirectory $repoRoot
Invoke-External -FilePath "cmake" -Arguments @("--build", "--preset", $Preset, "--target", "archipelago_config", "z_generals") -WorkingDirectory $repoRoot

$runtimeDir = Get-RuntimeDirectory -RepoRoot $repoRoot
Ensure-UserDataFolders -RuntimeDir $runtimeDir
Assert-DebugRuntimeLayout -RuntimeDir $runtimeDir

Write-Host ("Prepared direct debug runtime: {0}" -f $runtimeDir)
$runtimeDir
