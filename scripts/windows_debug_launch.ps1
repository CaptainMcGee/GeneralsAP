[CmdletBinding()]
param(
    [string]$RuntimeDir = "",
    [switch]$Wait
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-RepoRoot {
    return [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
}

if (-not $RuntimeDir) {
    $RuntimeDir = Join-Path (Get-RepoRoot) "build\win32-vcpkg-debug\GeneralsMD\Debug"
}
else {
    $RuntimeDir = [System.IO.Path]::GetFullPath($RuntimeDir)
}

$exePath = Join-Path $RuntimeDir "generalszh.exe"
if (-not (Test-Path -LiteralPath $exePath)) {
    throw "generalszh.exe was not found at $exePath. Run windows_debug_prepare.ps1 first."
}

foreach ($relativePath in @("UserData", "UserData\Archipelago")) {
    New-Item -ItemType Directory -Force -Path (Join-Path $RuntimeDir $relativePath) | Out-Null
}

$arguments = @("-win", "-userDataDir", ".\UserData\")

if ($Wait) {
    Push-Location $RuntimeDir
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
    Start-Process -FilePath $exePath -WorkingDirectory $RuntimeDir -ArgumentList $arguments | Out-Null
}
