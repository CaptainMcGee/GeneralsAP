[CmdletBinding()]
param(
    [string]$RuntimeDir = "",
    [string]$OutputDir = "",
    [int]$StartupWaitSeconds = 12,
    [string[]]$Targets = @("mainmenu", "hub", "connect", "mission-intel", "check-tracker"),
    [switch]$KillExisting
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Drawing
if (-not ("CodexAPShellCaptureUser32" -as [type])) {
    Add-Type @"
using System;
using System.Runtime.InteropServices;

public static class CodexAPShellCaptureUser32 {
    [StructLayout(LayoutKind.Sequential)]
    public struct RECT {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }

    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr hWnd);

    [DllImport("user32.dll")]
    public static extern bool ShowWindowAsync(IntPtr hWnd, int nCmdShow);

    [DllImport("user32.dll")]
    public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);

    [DllImport("user32.dll")]
    public static extern bool SetWindowPos(
        IntPtr hWnd,
        IntPtr hWndInsertAfter,
        int X,
        int Y,
        int cx,
        int cy,
        uint uFlags
    );
}
"@
}

function Get-RepoRoot {
    return [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
}

function Resolve-RuntimeDirectory {
    param([Parameter(Mandatory = $true)][string]$RepoRoot, [string]$Requested)

    if ($Requested) {
        return [System.IO.Path]::GetFullPath($Requested)
    }

    $candidate = Join-Path $RepoRoot "build\win32-vcpkg-playtest\GeneralsMD\Release"
    if (Test-Path -LiteralPath (Join-Path $candidate "generalszh.exe") -PathType Leaf) {
        return $candidate
    }

    throw "Unable to locate runtime dir. Pass -RuntimeDir explicitly."
}

function Resolve-OutputDirectory {
    param([Parameter(Mandatory = $true)][string]$RepoRoot, [string]$Requested)

    if ($Requested) {
        return [System.IO.Path]::GetFullPath($Requested)
    }

    return (Join-Path $RepoRoot "build\archipelago\wnd-work\screens\review")
}

function Wait-ForMainWindow {
    param(
        [Parameter(Mandatory = $true)][System.Diagnostics.Process]$Process,
        [int]$TimeoutSeconds = 15
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        Start-Sleep -Milliseconds 250
        $Process.Refresh()
        if ($Process.HasExited) {
            throw "generalszh.exe exited early with code $($Process.ExitCode)"
        }
        if ($Process.MainWindowHandle -ne [IntPtr]::Zero) {
            return $Process.MainWindowHandle
        }
    } while ((Get-Date) -lt $deadline)

    throw "Timed out waiting for generalszh.exe main window."
}

function Capture-WindowImage {
    param(
        [Parameter(Mandatory = $true)][System.Diagnostics.Process]$Process,
        [Parameter(Mandatory = $true)][string]$Path
    )

    $windowHandle = Wait-ForMainWindow -Process $Process
    $SWP_NOSIZE = [uint32]0x0001
    $SWP_NOMOVE = [uint32]0x0002
    $SWP_SHOWWINDOW = [uint32]0x0040
    $flags = $SWP_NOSIZE -bor $SWP_NOMOVE -bor $SWP_SHOWWINDOW
    $HWND_TOPMOST = [IntPtr](-1)
    $HWND_NOTOPMOST = [IntPtr](-2)

    [void][CodexAPShellCaptureUser32]::ShowWindowAsync($windowHandle, 9)
    [void][CodexAPShellCaptureUser32]::SetWindowPos($windowHandle, $HWND_TOPMOST, 0, 0, 0, 0, $flags)
    [void][CodexAPShellCaptureUser32]::SetForegroundWindow($windowHandle)
    Start-Sleep -Milliseconds 650

    $rect = New-Object CodexAPShellCaptureUser32+RECT
    if (-not [CodexAPShellCaptureUser32]::GetWindowRect($windowHandle, [ref]$rect)) {
        throw "GetWindowRect failed for generalszh.exe."
    }

    $width = $rect.Right - $rect.Left
    $height = $rect.Bottom - $rect.Top
    if ($width -le 0 -or $height -le 0) {
        throw "Invalid window rect for generalszh.exe: $width x $height"
    }

    $bitmap = New-Object System.Drawing.Bitmap $width, $height
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    try {
        $graphics.CopyFromScreen($rect.Left, $rect.Top, 0, 0, $bitmap.Size)
        New-Item -ItemType Directory -Force -Path ([System.IO.Path]::GetDirectoryName($Path)) | Out-Null
        $bitmap.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
    }
    finally {
        [void][CodexAPShellCaptureUser32]::SetWindowPos($windowHandle, $HWND_NOTOPMOST, 0, 0, 0, 0, $flags)
        $graphics.Dispose()
        $bitmap.Dispose()
    }
}

function Normalize-ReviewTarget {
    param([Parameter(Mandatory = $true)][string]$Target)

    $value = $Target.Trim().ToLowerInvariant()
    switch ($value) {
        "mainmenu" { return "mainmenu" }
        "hub" { return "hub" }
        "connect" { return "connect" }
        "mission-intel" { return "mission-intel" }
        "check-tracker" { return "check-tracker" }
        default { throw "Unknown review target '$Target'." }
    }
}

function Stop-ExistingGenerals {
    $existing = Get-Process generalszh -ErrorAction SilentlyContinue
    if (-not $existing) {
        return
    }

    foreach ($process in $existing) {
        Stop-Process -Id $process.Id -Force
    }
    Start-Sleep -Seconds 1
}

function New-ReviewContactSheet {
    param(
        [Parameter(Mandatory = $true)][object[]]$Records,
        [Parameter(Mandatory = $true)][string]$DestinationPath
    )

    if ($Records.Count -eq 0) {
        return
    }

    $images = @()
    try {
        foreach ($record in $Records) {
            $images += [System.Drawing.Image]::FromFile($record.ImagePath)
        }

        $columns = 2
        $rows = [Math]::Max(1, [int][Math]::Ceiling($images.Count / [double]$columns))
        $tileWidth = [Math]::Max(1, [int](($images | Measure-Object -Property Width -Maximum).Maximum))
        $tileHeight = [Math]::Max(1, [int](($images | Measure-Object -Property Height -Maximum).Maximum))
        $captionHeight = 28
        $padding = 12
        $sheetWidth = [Math]::Max(1, [int](($columns * $tileWidth) + (($columns + 1) * $padding)))
        $sheetHeight = [Math]::Max(1, [int](($rows * ($tileHeight + $captionHeight)) + (($rows + 1) * $padding)))

        $bitmap = New-Object System.Drawing.Bitmap $sheetWidth, $sheetHeight
        $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
        $font = New-Object System.Drawing.Font("Segoe UI", 10, [System.Drawing.FontStyle]::Bold)
        $whiteBrush = [System.Drawing.Brushes]::White
        $blackBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(255, 14, 16, 18))
        try {
            $graphics.Clear([System.Drawing.Color]::FromArgb(255, 14, 16, 18))
            for ($index = 0; $index -lt $images.Count; $index++) {
                $column = $index % $columns
                $row = [Math]::Floor($index / $columns)
                $x = $padding + ($column * ($tileWidth + $padding))
                $y = $padding + ($row * ($tileHeight + $captionHeight + $padding))
                $graphics.FillRectangle($blackBrush, $x - 2, $y - 2, $tileWidth + 4, $tileHeight + $captionHeight + 4)
                $graphics.DrawImage($images[$index], $x, $y, $images[$index].Width, $images[$index].Height)
                $graphics.DrawString($Records[$index].Target, $font, $whiteBrush, [float]$x, [float]($y + $tileHeight + 2))
            }

            New-Item -ItemType Directory -Force -Path ([System.IO.Path]::GetDirectoryName($DestinationPath)) | Out-Null
            $bitmap.Save($DestinationPath, [System.Drawing.Imaging.ImageFormat]::Png)
        }
        finally {
            $blackBrush.Dispose()
            $font.Dispose()
            $graphics.Dispose()
            $bitmap.Dispose()
        }
    }
    finally {
        foreach ($image in $images) {
            if ($image) {
                $image.Dispose()
            }
        }
    }
}

function Write-ReviewPacket {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][object[]]$Records,
        [string]$ContactSheetPath = ""
    )

    $lines = @(
        "# AP WND Shell Review Packet",
        "",
        ("Generated: {0}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz')),
        "",
        "## Runtime Walkthrough",
        "",
        "- Built with staged loose-file overrides only.",
        "- Runtime launches with `-quickstart` and APShell review targets so the requested AP screen opens directly.",
        "- `Archipelago` button and AP shell screens were captured from the live game window via desktop screen copy.",
        "- AP shell remains fixture-driven. No live AP networking, mission launch, or tracker backend was involved.",
        "",
        "## Captures",
        ""
    )

    foreach ($record in $Records) {
        $lines += ("- `{0}`: {1}" -f $record.Target, $record.ImagePath)
    }
    if ($ContactSheetPath) {
        $lines += ("- `contact-sheet`: {0}" -f $ContactSheetPath)
    }

    $lines += @(
        "",
        "## Known Stock Quirks",
        "",
        "- Stock `MainMenu.wnd` still lacks `ButtonTRAINING` even though `WindowTransitions.ini` references it. This predates AP shell work.",
        "",
        "## Critical Review Checklist",
        "",
        "- Confirm `Archipelago` belongs visually in the stock main stack.",
        "- Confirm AP Hub and all three child screens share one visual grammar.",
        "- Confirm Mission Intel feels like one coherent tactical screen, not two debug views taped together.",
        "- Confirm wording for connection, mission state, cluster state, and check text feels final enough for shell review.",
        "- Confirm no screen feels like a debug panel.",
        "- Manual follow-up still needed for direct click/ESC feel during live navigation."
    )

    New-Item -ItemType Directory -Force -Path ([System.IO.Path]::GetDirectoryName($Path)) | Out-Null
    Set-Content -LiteralPath $Path -Value $lines -Encoding utf8
}

$repoRoot = Get-RepoRoot
$runtimeDir = Resolve-RuntimeDirectory -RepoRoot $repoRoot -Requested $RuntimeDir
$outputDir = Resolve-OutputDirectory -RepoRoot $repoRoot -Requested $OutputDir
$exePath = Join-Path $runtimeDir "generalszh.exe"
$reviewFlagPath = Join-Path $runtimeDir "UserData\Archipelago\APShellReviewOpen.txt"

if ($KillExisting) {
    Stop-ExistingGenerals
}

New-Item -ItemType Directory -Force -Path (Split-Path -Path $reviewFlagPath -Parent) | Out-Null
New-Item -ItemType Directory -Force -Path $outputDir | Out-Null
Get-ChildItem -LiteralPath $outputDir -File -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue

$index = 1
$records = New-Object System.Collections.Generic.List[object]
foreach ($rawTarget in $Targets) {
    $target = Normalize-ReviewTarget -Target $rawTarget
    Set-Content -LiteralPath $reviewFlagPath -Value $target -Encoding ascii

    $process = Start-Process -FilePath $exePath -WorkingDirectory $runtimeDir -ArgumentList @("-quickstart", "-win", "-userDataDir", ".\UserData\") -PassThru
    try {
        Wait-ForMainWindow -Process $process -TimeoutSeconds 15 | Out-Null
        Start-Sleep -Seconds $StartupWaitSeconds
        $outputPath = Join-Path $outputDir ("{0:D2}-{1}.png" -f $index, $target)
        Capture-WindowImage -Process $process -Path $outputPath
        $records.Add([pscustomobject]@{
            Target = $target
            ImagePath = $outputPath
        }) | Out-Null
        Write-Host ("Captured {0}" -f $outputPath)
    }
    finally {
        if (-not $process.HasExited) {
            Stop-Process -Id $process.Id -Force
            Wait-Process -Id $process.Id -ErrorAction SilentlyContinue
        }
    }

    if (Test-Path -LiteralPath $reviewFlagPath) {
        Remove-Item -LiteralPath $reviewFlagPath -Force
    }
    Start-Sleep -Seconds 1
    $index++
}

$contactSheetPath = Join-Path $outputDir "review-contact-sheet.png"
New-ReviewContactSheet -Records $records -DestinationPath $contactSheetPath
$packetPath = Join-Path $outputDir "review-packet.md"
Write-ReviewPacket -Path $packetPath -Records $records -ContactSheetPath $contactSheetPath

Write-Host ("AP shell review capture complete: {0}" -f $outputDir)
