[CmdletBinding()]
param(
    [ValidateSet("prepare", "compose", "manifest", "deploy")]
    [string]$Action = "prepare",
    [string]$RuntimeDir = "",
    [switch]$Force
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

function Resolve-RuntimeDirectory {
    param([Parameter(Mandatory = $true)][string]$RepoRoot, [string]$Requested)

    if ($Requested) {
        return [System.IO.Path]::GetFullPath($Requested)
    }

    $candidates = @(
        (Join-Path $RepoRoot "build\win32-vcpkg-playtest\GeneralsMD\Release"),
        (Join-Path $RepoRoot "build\win32-vcpkg-debug\GeneralsMD\Debug")
    )

    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath (Join-Path $candidate "WindowZH.big") -PathType Leaf) {
            return $candidate
        }
    }

    throw "Unable to locate a runtime directory containing WindowZH.big. Pass -RuntimeDir explicitly."
}

function Invoke-PythonScript {
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    $pythonCommand = Resolve-PythonCommand
    $pythonExe = $pythonCommand[0]
    $argumentList = @()
    if ($pythonCommand.Length -gt 1) {
        $argumentList += $pythonCommand[1..($pythonCommand.Length - 1)]
    }
    $argumentList += $Arguments

    & $pythonExe @argumentList
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed with exit code $LASTEXITCODE"
    }
}

$repoRoot = Get-RepoRoot
$runtimeDir = Resolve-RuntimeDirectory -RepoRoot $repoRoot -Requested $RuntimeDir
$archivePath = Join-Path $runtimeDir "WindowZH.big"
$scriptPath = Join-Path $repoRoot "scripts\wnd_workbench.py"
$sourceRoot = Join-Path $repoRoot "build\archipelago\wnd-work\source"
$overrideRoot = Join-Path $repoRoot "build\archipelago\wnd-work\override"
$manifestRoot = Join-Path $repoRoot "build\archipelago\wnd-work\manifests"
$runtimeDataRoot = Join-Path $repoRoot "build\archipelago\wnd-work\runtime-data"

switch ($Action) {
    "prepare" {
        $extractArgs = @(
            $scriptPath,
            "extract",
            "--archive", $archivePath
        )
        if ($Force) {
            $extractArgs += "--force"
        }
        Invoke-PythonScript -RepoRoot $repoRoot -Arguments $extractArgs

        $composeArgs = @(
            $scriptPath,
            "compose"
        )
        Invoke-PythonScript -RepoRoot $repoRoot -Arguments $composeArgs

        $sourceManifestArgs = @(
            $scriptPath,
            "manifest",
            $sourceRoot,
            "--output", (Join-Path $manifestRoot "source-manifest.json")
        )
        Invoke-PythonScript -RepoRoot $repoRoot -Arguments $sourceManifestArgs

        $overrideManifestArgs = @(
            $scriptPath,
            "manifest",
            $overrideRoot,
            "--output", (Join-Path $manifestRoot "override-manifest.json")
        )
        Invoke-PythonScript -RepoRoot $repoRoot -Arguments $overrideManifestArgs

        Write-Host ("WND workbench prepared from {0}" -f $archivePath)
    }
    "compose" {
        $composeArgs = @(
            $scriptPath,
            "compose"
        )
        Invoke-PythonScript -RepoRoot $repoRoot -Arguments $composeArgs
        Write-Host ("WND overrides composed under {0}" -f $overrideRoot)
    }
    "manifest" {
        $sourceManifestArgs = @(
            $scriptPath,
            "manifest",
            $sourceRoot,
            "--output", (Join-Path $manifestRoot "source-manifest.json")
        )
        Invoke-PythonScript -RepoRoot $repoRoot -Arguments $sourceManifestArgs

        $overrideManifestArgs = @(
            $scriptPath,
            "manifest",
            $overrideRoot,
            "--output", (Join-Path $manifestRoot "override-manifest.json")
        )
        Invoke-PythonScript -RepoRoot $repoRoot -Arguments $overrideManifestArgs

        Write-Host ("WND manifests refreshed under {0}" -f $manifestRoot)
    }
    "deploy" {
        $composeArgs = @(
            $scriptPath,
            "compose"
        )
        Invoke-PythonScript -RepoRoot $repoRoot -Arguments $composeArgs

        $deployArgs = @(
            $scriptPath,
            "deploy",
            "--runtime-dir", $runtimeDir,
            "--runtime-data-root", $runtimeDataRoot
        )
        if ($Force) {
            $deployArgs += "--force"
        }
        Invoke-PythonScript -RepoRoot $repoRoot -Arguments $deployArgs
        Write-Host ("Loose WND overrides deployed to {0}" -f $runtimeDir)
    }
}
