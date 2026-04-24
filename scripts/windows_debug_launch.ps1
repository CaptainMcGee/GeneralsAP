[CmdletBinding()]
param(
    [string]$RuntimeDir = "",
    [switch]$Wait,
    [int]$StartupWaitSeconds = 20
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-RepoRoot {
    return [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
}

function Assert-DebugRuntimeLayout {
    param([Parameter(Mandatory = $true)][string]$RuntimeDir)

    $requiredEntries = @(
        "Data",
        "Data\INI",
        "MappedImages",
        "MSS",
        "ZH_Generals",
        "generalszh.exe",
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
        throw "Direct debug runtime is incomplete at '$RuntimeDir'. Missing required runtime entries:`n$message"
    }
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

Assert-DebugRuntimeLayout -RuntimeDir $RuntimeDir

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
    $process = Start-Process -FilePath $exePath -WorkingDirectory $RuntimeDir -ArgumentList $arguments -PassThru
    Start-Sleep -Seconds $StartupWaitSeconds
    $process.Refresh()
    if ($process.HasExited) {
        $crashInfoPath = Join-Path $RuntimeDir "UserData\ReleaseCrashInfo.txt"
        if (Test-Path -LiteralPath $crashInfoPath -PathType Leaf) {
            $crashInfo = Get-Content -LiteralPath $crashInfoPath -ErrorAction SilentlyContinue | Select-Object -First 8
            $crashText = ($crashInfo -join [Environment]::NewLine)
            throw "generalszh.exe exited during startup with code $($process.ExitCode). Crash info:`n$crashText"
        }
        throw "generalszh.exe exited during startup with code $($process.ExitCode)"
    }
    Write-Host ("Launched generalszh.exe (PID {0}) from {1} and it remained alive for {2} seconds." -f $process.Id, $RuntimeDir, $StartupWaitSeconds)
}
