[CmdletBinding()]
param(
    [ValidateSet("reference-clean", "archipelago-bisect", "archipelago-current")]
    [string]$RuntimeProfile = "reference-clean",
    [int]$IntroSeconds = 15,
    [int]$SecondEscapeDelaySeconds = 5,
    [int]$ObserveSeconds = 20,
    [int]$MaxDialogs = 12,
    [switch]$BuildCurrentExecutable
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Windows.Forms
Add-Type @"
using System;
using System.Text;
using System.Collections.Generic;
using System.Runtime.InteropServices;

public static class PopupProbeNative {
    public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);

    [DllImport("user32.dll")]
    public static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);

    [DllImport("user32.dll")]
    public static extern bool EnumChildWindows(IntPtr hWndParent, EnumWindowsProc lpEnumFunc, IntPtr lParam);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    public static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    public static extern int GetWindowTextLength(IntPtr hWnd);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    public static extern int GetClassName(IntPtr hWnd, StringBuilder lpClassName, int nMaxCount);

    [DllImport("user32.dll")]
    public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);

    [DllImport("user32.dll")]
    public static extern bool IsWindowVisible(IntPtr hWnd);

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

    [void][PopupProbeNative]::ShowWindowAsync($windowHandle, 9)
    [void][PopupProbeNative]::SetForegroundWindow($windowHandle)
    Start-Sleep -Milliseconds 500

    for ($attempt = 1; $attempt -le 3; $attempt++) {
        [System.Windows.Forms.SendKeys]::SendWait("{ESC}")
        Start-Sleep -Milliseconds 500
    }
}

function Get-WindowTextValue {
    param([Parameter(Mandatory = $true)][IntPtr]$WindowHandle)

    $length = [PopupProbeNative]::GetWindowTextLength($WindowHandle)
    $builder = New-Object System.Text.StringBuilder ($length + 256)
    [void][PopupProbeNative]::GetWindowText($WindowHandle, $builder, $builder.Capacity)
    return $builder.ToString()
}

function Get-WindowClassValue {
    param([Parameter(Mandatory = $true)][IntPtr]$WindowHandle)

    $builder = New-Object System.Text.StringBuilder 256
    [void][PopupProbeNative]::GetClassName($WindowHandle, $builder, $builder.Capacity)
    return $builder.ToString()
}

function Get-ProcessWindows {
    param([Parameter(Mandatory = $true)][int]$ProcessId)

    $windows = New-Object System.Collections.Generic.List[object]
    $callback = [PopupProbeNative+EnumWindowsProc]{
        param([IntPtr]$hWnd, [IntPtr]$lParam)

        $windowProcessId = 0
        [void][PopupProbeNative]::GetWindowThreadProcessId($hWnd, [ref]$windowProcessId)
        if ($windowProcessId -ne $ProcessId) {
            return $true
        }
        if (-not [PopupProbeNative]::IsWindowVisible($hWnd)) {
            return $true
        }

        $title = Get-WindowTextValue -WindowHandle $hWnd
        $className = Get-WindowClassValue -WindowHandle $hWnd
        $windows.Add([PSCustomObject]@{
            Handle = $hWnd
            Title = $title
            ClassName = $className
        })
        return $true
    }

    [void][PopupProbeNative]::EnumWindows($callback, [IntPtr]::Zero)
    return $windows
}

function Get-ChildWindowTexts {
    param([Parameter(Mandatory = $true)][IntPtr]$WindowHandle)

    $texts = New-Object System.Collections.Generic.List[string]
    $callback = [PopupProbeNative+EnumWindowsProc]{
        param([IntPtr]$childHandle, [IntPtr]$lParam)

        $childClass = Get-WindowClassValue -WindowHandle $childHandle
        $childText = Get-WindowTextValue -WindowHandle $childHandle
        if ($childText -and $childText.Trim()) {
            $texts.Add(("{0}: {1}" -f $childClass, $childText.Trim()))
        }
        return $true
    }

    [void][PopupProbeNative]::EnumChildWindows($WindowHandle, $callback, [IntPtr]::Zero)
    return $texts
}

function Dismiss-DialogWindow {
    param([Parameter(Mandatory = $true)][IntPtr]$WindowHandle)

    [void][PopupProbeNative]::ShowWindowAsync($WindowHandle, 9)
    [void][PopupProbeNative]::SetForegroundWindow($WindowHandle)
    Start-Sleep -Milliseconds 300
    [System.Windows.Forms.SendKeys]::SendWait("{ENTER}")
    Start-Sleep -Milliseconds 300
}

$repoRoot = Get-RepoRoot
$prepareScript = Join-Path $repoRoot "scripts\windows_debug_prepare.ps1"
$prepareArgs = @("-ExecutionPolicy", "Bypass", "-File", $prepareScript, "-UseReferenceExecutable", "-RuntimeProfile", $RuntimeProfile)
if ($BuildCurrentExecutable) {
    $prepareArgs = @("-ExecutionPolicy", "Bypass", "-File", $prepareScript, "-RuntimeProfile", $RuntimeProfile)
}

$prepareOutput = & powershell.exe @prepareArgs 2>&1
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

$existingProcesses = Get-Process -Name "generalszh" -ErrorAction SilentlyContinue
foreach ($process in $existingProcesses) {
    Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
}

$exePath = Join-Path $runtimeDir "generalszh.exe"
$gameArgs = @("-win", "-userDataDir", ".\\UserData\\")
$gameProcess = Start-Process -FilePath $exePath -WorkingDirectory $runtimeDir -ArgumentList $gameArgs -PassThru

Start-Sleep -Seconds $IntroSeconds
if (-not $gameProcess.HasExited) {
    Send-IntroSkipEscape -Process $gameProcess
    if ($SecondEscapeDelaySeconds -gt 0) {
        Start-Sleep -Seconds $SecondEscapeDelaySeconds
        if (-not $gameProcess.HasExited) {
            Send-IntroSkipEscape -Process $gameProcess
        }
    }
}

$deadline = (Get-Date).AddSeconds($ObserveSeconds)
$captured = New-Object System.Collections.Generic.List[object]
$seenKeys = New-Object System.Collections.Generic.HashSet[string]

while ((Get-Date) -lt $deadline) {
    if ($gameProcess.HasExited) {
        break
    }

    $windows = Get-ProcessWindows -ProcessId $gameProcess.Id
    foreach ($window in $windows) {
        $isDialog = $window.ClassName -eq "#32770" -or $window.Title -match "Assertion|Error|Warning"
        if (-not $isDialog) {
            continue
        }

        $childTexts = Get-ChildWindowTexts -WindowHandle $window.Handle
        $key = "{0}|{1}|{2}" -f $window.Title, $window.ClassName, ($childTexts -join " || ")
        if ($seenKeys.Contains($key)) {
            continue
        }

        [void]$seenKeys.Add($key)
        $entry = [PSCustomObject]@{
            Title = $window.Title
            ClassName = $window.ClassName
            ChildTexts = $childTexts
        }
        $captured.Add($entry)

        Write-Host ""
        Write-Host ("=== Captured Dialog {0} ===" -f $captured.Count)
        Write-Host ("Title: {0}" -f $window.Title)
        Write-Host ("Class: {0}" -f $window.ClassName)
        foreach ($text in $childTexts) {
            Write-Host $text
        }

        Dismiss-DialogWindow -WindowHandle $window.Handle
        if ($captured.Count -ge $MaxDialogs) {
            break
        }
    }

    if ($captured.Count -ge $MaxDialogs) {
        break
    }

    Start-Sleep -Milliseconds 500
    $gameProcess.Refresh()
}

if (-not $gameProcess.HasExited) {
    Stop-Process -Id $gameProcess.Id -Force -ErrorAction SilentlyContinue
}

$outPath = Join-Path $runtimeDir "PopupProbe.json"
$payload = [PSCustomObject]@{
    runtimeProfile = $RuntimeProfile
    runtimeDir = $runtimeDir
    capturedDialogs = $captured
}
$payload | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $outPath -Encoding UTF8
Write-Host ""
Write-Host ("Wrote popup capture to {0}" -f $outPath)
