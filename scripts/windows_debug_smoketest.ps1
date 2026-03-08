[CmdletBinding()]
param(
    [ValidateSet("reference-clean", "archipelago-bisect", "archipelago-current")]
    [string]$RuntimeProfile = "reference-clean",
    [int]$IntroSeconds = 15,
    [int]$PostIntroSeconds = 15,
    [int]$SecondEscapeDelaySeconds = 5,
    [switch]$NoEscapeSkip
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Windows.Forms
Add-Type @"
using System;
using System.Runtime.InteropServices;

public static class GeneralsRuntimeWindow {
    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr hWnd);

    [DllImport("user32.dll")]
    public static extern bool ShowWindowAsync(IntPtr hWnd, int nCmdShow);
}
"@

function Get-RepoRoot {
    return [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
}

function Wait-ForMainWindow {
    param(
        [Parameter(Mandatory = $true)][System.Diagnostics.Process]$Process,
        [int]$TimeoutSeconds = 15
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        $Process.Refresh()
        if ($Process.HasExited) {
            return [IntPtr]::Zero
        }
        if ($Process.MainWindowHandle -ne [IntPtr]::Zero) {
            return $Process.MainWindowHandle
        }
        Start-Sleep -Milliseconds 250
    } while ((Get-Date) -lt $deadline)

    return [IntPtr]::Zero
}

function Send-IntroSkipEscape {
    param([Parameter(Mandatory = $true)][System.Diagnostics.Process]$Process)

    $windowHandle = Wait-ForMainWindow -Process $Process
    if ($windowHandle -eq [IntPtr]::Zero) {
        Write-Warning "Unable to locate the game main window before intro skip."
        return
    }

    [void][GeneralsRuntimeWindow]::ShowWindowAsync($windowHandle, 9)
    [void][GeneralsRuntimeWindow]::SetForegroundWindow($windowHandle)
    Start-Sleep -Milliseconds 500

    for ($attempt = 1; $attempt -le 3; $attempt++) {
        [System.Windows.Forms.SendKeys]::SendWait("{ESC}")
        Start-Sleep -Milliseconds 500
    }

    Write-Host ("Sent ESC to skip intro movie (window handle: {0})." -f $windowHandle)
}

$repoRoot = Get-RepoRoot
$prepareScript = Join-Path $repoRoot "scripts\windows_debug_prepare.ps1"

$prepareOutput = & powershell.exe -ExecutionPolicy Bypass -File $prepareScript -UseReferenceExecutable -RuntimeProfile $RuntimeProfile 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "windows_debug_prepare.ps1 failed with exit code $LASTEXITCODE"
}

foreach ($line in $prepareOutput) {
    if ($null -ne $line) {
        Write-Host ($line.ToString())
    }
}

$runtimeDir = ($prepareOutput | Select-Object -Last 1).ToString().Trim()
if (-not $runtimeDir) {
    throw "windows_debug_prepare.ps1 did not return a runtime directory."
}

$logCandidates = @(
    (Join-Path $runtimeDir "DebugLogFileD.txt"),
    (Join-Path $runtimeDir "DebugLogFile.txt")
)
foreach ($logPath in $logCandidates) {
    Remove-Item -LiteralPath $logPath -Force -ErrorAction SilentlyContinue
}

$processes = Get-Process -Name "generalszh" -ErrorAction SilentlyContinue
foreach ($process in $processes) {
    Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
}

$exePath = Join-Path $runtimeDir "generalszh.exe"
$gameArgs = @("-win", "-userDataDir", ".\\UserData\\")
$gameProcess = Start-Process -FilePath $exePath -WorkingDirectory $runtimeDir -ArgumentList $gameArgs -PassThru

Start-Sleep -Seconds $IntroSeconds

if (-not $NoEscapeSkip -and -not $gameProcess.HasExited) {
    try {
        Send-IntroSkipEscape -Process $gameProcess
        if ($SecondEscapeDelaySeconds -gt 0) {
            Start-Sleep -Seconds $SecondEscapeDelaySeconds
            if (-not $gameProcess.HasExited) {
                Send-IntroSkipEscape -Process $gameProcess
            }
        }
    }
    catch {
        Write-Warning ("Unable to send ESC to the game window automatically: {0}" -f $_.Exception.Message)
    }
}

Start-Sleep -Seconds $PostIntroSeconds

$launched = Get-Process -Name "generalszh" -ErrorAction SilentlyContinue
foreach ($process in $launched) {
    Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
}

$patterns = @(
    "ASSERTION FAILURE",
    "Asset error",
    "ASSET ERROR",
    "public bone",
    "TurretBone",
    "muzzle",
    "animation .* not found",
    "SubObject .* not found"
)

$matches = New-Object System.Collections.Generic.List[object]
foreach ($logPath in $logCandidates) {
    if (-not (Test-Path -LiteralPath $logPath -PathType Leaf)) {
        continue
    }

    $logMatches = Select-String -Path $logPath -Pattern $patterns -CaseSensitive:$false -ErrorAction SilentlyContinue
    foreach ($match in $logMatches) {
        $matches.Add($match)
    }
}

if ($matches.Count -gt 0) {
    Write-Host ("Runtime smoke test failed for profile '{0}'." -f $RuntimeProfile)
    $matches | Select-Object -First 40 | ForEach-Object { Write-Host $_.Line }
    exit 1
}

Write-Host ("Runtime smoke test passed for profile '{0}'." -f $RuntimeProfile)
