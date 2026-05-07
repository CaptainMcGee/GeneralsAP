param(
    [string]$BaseRuntimeDir = $env:GENERALSAP_BASE_RUNTIME_DIR,
    [string]$PreparedRuntimeDir = "",
    [string]$BridgePath = "",
    [string]$Fixture = "human_demo_tank",
    [string]$SmokeMapFile = "Maps\GC_TankGeneral.map",
    [int]$SmokeChallengePlayerGeneralIndex = 2,
    [string]$WaitForSpawnedRuntimeKey = "cluster.tank.c02.u01",
    [string]$ReviewRoot = "build\archipelago\visual-demo-gate",
    [int]$StartupWaitSeconds = 5,
    [int]$SpawnedUnitStateTimeoutSeconds = 240,
    [int]$CaptureIntervalSeconds = 2,
    [int]$PostSmokeCaptureSeconds = 8,
    [switch]$AllowScoreScreen,
    [switch]$NoSpawnProof,
    [switch]$KeepReviewInstall
)

$ErrorActionPreference = "Stop"
if ($NoSpawnProof) {
    $WaitForSpawnedRuntimeKey = ""
}

function Resolve-RepoPath([string]$Path) {
    if ([System.IO.Path]::IsPathRooted($Path)) {
        return $Path
    }
    return (Join-Path $RepoRoot $Path)
}

function Quote-ProcessArg([string]$Value) {
    if ($Value -match '[\s"]') {
        return '"' + ($Value -replace '"', '\"') + '"'
    }
    return $Value
}

function Get-VisualGateGameProcess([datetime]$Since) {
    $names = @("generalszh", "generals", "game.dat")
    Get-Process -ErrorAction SilentlyContinue |
        Where-Object {
            $processName = $_.ProcessName.ToLowerInvariant()
            if ($names -notcontains $processName) {
                return $false
            }
            try {
                return $_.StartTime -ge $Since.AddSeconds(-5)
            } catch {
                return $false
            }
        } |
        Sort-Object StartTime -Descending |
        Select-Object -First 1
}

function Capture-WindowPng([System.Diagnostics.Process]$Process, [string]$Path) {
    if (-not $Process -or $Process.MainWindowHandle -eq [IntPtr]::Zero) {
        return $false
    }

    [void][Win32Rect]::ShowWindow($Process.MainWindowHandle, 5)
    [void][Win32Rect]::SetForegroundWindow($Process.MainWindowHandle)
    Start-Sleep -Milliseconds 150

    $rect = New-Object Win32Rect+RECT
    if (-not [Win32Rect]::GetWindowRect($Process.MainWindowHandle, [ref]$rect)) {
        return $false
    }

    $width = $rect.Right - $rect.Left
    $height = $rect.Bottom - $rect.Top
    if ($width -le 0 -or $height -le 0) {
        return $false
    }

    $bitmap = New-Object System.Drawing.Bitmap $width, $height
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    try {
        $graphics.CopyFromScreen($rect.Left, $rect.Top, 0, 0, $bitmap.Size)
        $bitmap.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
    } finally {
        $graphics.Dispose()
        $bitmap.Dispose()
    }
    return $true
}

function Test-DefeatSplashPng([string]$Path) {
    $bitmap = [System.Drawing.Bitmap]::FromFile($Path)
    try {
        $width = $bitmap.Width
        $height = $bitmap.Height
        if ($width -le 0 -or $height -le 0) {
            return $false
        }

        $total = 0
        $black = 0
        $center = 0
        $centerLit = 0
        $edge = 0
        $edgeBlack = 0
        for ($y = 0; $y -lt $height; $y += 8) {
            for ($x = 0; $x -lt $width; $x += 8) {
                $pixel = $bitmap.GetPixel($x, $y)
                $brightness = ([int]$pixel.R + [int]$pixel.G + [int]$pixel.B) / 3.0
                $isBlack = $brightness -lt 24
                $total += 1
                if ($isBlack) {
                    $black += 1
                }

                $isCenter = (
                    $x -gt ($width * 0.15) -and $x -lt ($width * 0.85) -and
                    $y -gt ($height * 0.20) -and $y -lt ($height * 0.70)
                )
                if ($isCenter) {
                    $center += 1
                    if ($brightness -gt 65) {
                        $centerLit += 1
                    }
                }

                $isEdge = (
                    $x -lt ($width * 0.08) -or $x -gt ($width * 0.92) -or
                    $y -lt ($height * 0.12) -or $y -gt ($height * 0.82)
                )
                if ($isEdge) {
                    $edge += 1
                    if ($isBlack) {
                        $edgeBlack += 1
                    }
                }
            }
        }

        if ($total -eq 0 -or $center -eq 0 -or $edge -eq 0) {
            return $false
        }

        $blackRatio = $black / [double]$total
        $centerLitRatio = $centerLit / [double]$center
        $edgeBlackRatio = $edgeBlack / [double]$edge
        return ($blackRatio -gt 0.45 -and $centerLitRatio -gt 0.20 -and $edgeBlackRatio -gt 0.55)
    } finally {
        $bitmap.Dispose()
    }
}

function Get-PngVisualStats([string]$Path) {
    $hashText = ""
    try {
        $hashText = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
    } catch {
        $hashText = ""
    }

    $bitmap = [System.Drawing.Bitmap]::FromFile($Path)
    try {
        $width = $bitmap.Width
        $height = $bitmap.Height
        $sampleCount = 0
        $brightnessTotal = 0.0
        $darkCount = 0
        $buckets = @{}
        for ($y = 0; $y -lt $height; $y += 16) {
            for ($x = 0; $x -lt $width; $x += 16) {
                $pixel = $bitmap.GetPixel($x, $y)
                $brightness = ([int]$pixel.R + [int]$pixel.G + [int]$pixel.B) / 3.0
                $brightnessTotal += $brightness
                if ($brightness -lt 24) {
                    $darkCount += 1
                }
                $bucket = "{0:X1}{1:X1}{2:X1}" -f ([int]($pixel.R / 16)), ([int]($pixel.G / 16)), ([int]($pixel.B / 16))
                $buckets[$bucket] = $true
                $sampleCount += 1
            }
        }

        $meanBrightness = if ($sampleCount -gt 0) { $brightnessTotal / [double]$sampleCount } else { 0.0 }
        $darkRatio = if ($sampleCount -gt 0) { $darkCount / [double]$sampleCount } else { 1.0 }
        $usable = ($width -ge 320 -and $height -ge 200 -and $meanBrightness -gt 8.0 -and $buckets.Count -ge 4)
        return [ordered]@{
            path = $Path
            sha256 = $hashText
            width = $width
            height = $height
            meanBrightness = [math]::Round($meanBrightness, 2)
            darkRatio = [math]::Round($darkRatio, 4)
            colorBucketCount = $buckets.Count
            usable = $usable
        }
    } finally {
        $bitmap.Dispose()
    }
}

function Get-ApGeneralSmokeExpectation([int]$Index) {
    switch ($Index) {
        0 { return @{ template = "FactionAmericaAirForceGeneral"; side = "AmericaAirForceGeneral" } }
        1 { return @{ template = "FactionAmericaLaserGeneral"; side = "AmericaLaserGeneral" } }
        2 { return @{ template = "FactionAmericaSuperWeaponGeneral"; side = "AmericaSuperWeaponGeneral" } }
        3 { return @{ template = "FactionChinaTankGeneral"; side = "ChinaTankGeneral" } }
        4 { return @{ template = "FactionChinaInfantryGeneral"; side = "ChinaInfantryGeneral" } }
        5 { return @{ template = "FactionChinaNukeGeneral"; side = "ChinaNukeGeneral" } }
        6 { return @{ template = "FactionGLAToxinGeneral"; side = "GLAToxinGeneral" } }
        7 { return @{ template = "FactionGLADemolitionGeneral"; side = "GLADemolitionGeneral" } }
        8 { return @{ template = "FactionGLAStealthGeneral"; side = "GLAStealthGeneral" } }
        default { return $null }
    }
}

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptRoot
$SmokeScript = Join-Path $ScriptRoot "smoke_generalsap_clean_runtime.ps1"

if (-not $BaseRuntimeDir) {
    throw "BaseRuntimeDir is required. Pass -BaseRuntimeDir or set GENERALSAP_BASE_RUNTIME_DIR."
}
if (-not (Test-Path -LiteralPath $SmokeScript)) {
    throw "Missing clean runtime smoke script: $SmokeScript"
}

Add-Type -AssemblyName System.Drawing
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

public class Win32Rect {
    [StructLayout(LayoutKind.Sequential)]
    public struct RECT {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }

    [DllImport("user32.dll")]
    public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);

    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr hWnd);

    [DllImport("user32.dll")]
    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
}
"@

$resolvedReviewRoot = Resolve-RepoPath $ReviewRoot
$runName = (Get-Date -Format "yyyyMMdd-HHmmss") + "-" + ([guid]::NewGuid().ToString("N").Substring(0, 8))
$runRoot = Join-Path $resolvedReviewRoot $runName
$runDir = Join-Path $runRoot "smoke-run"
$screenshotDir = Join-Path $runRoot "screenshots"
New-Item -ItemType Directory -Force -Path $runRoot, $screenshotDir | Out-Null

$stdoutPath = Join-Path $runRoot "smoke.stdout.txt"
$stderrPath = Join-Path $runRoot "smoke.stderr.txt"
$summaryPath = Join-Path $runRoot "Visual-Demo-Gate.json"
$spawnProofRequested = -not [string]::IsNullOrWhiteSpace($WaitForSpawnedRuntimeKey)

$smokeArgs = @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    $SmokeScript,
    "-BaseRuntimeDir",
    $BaseRuntimeDir,
    "-LocalBridgeFixture",
    $Fixture,
    "-WorkDir",
    $runDir,
    "-KeepInstall",
    "-LeaveGameRunning",
    "-StartupWaitSeconds",
    [string]$StartupWaitSeconds,
    "-SmokeMapFile",
    $SmokeMapFile,
    "-SmokeChallengePlayerGeneralIndex",
    [string]$SmokeChallengePlayerGeneralIndex
)
if ($spawnProofRequested) {
    $smokeArgs += @(
        "-WaitForSpawnedRuntimeKey",
        $WaitForSpawnedRuntimeKey,
        "-SpawnedUnitStateTimeoutSeconds",
        [string]$SpawnedUnitStateTimeoutSeconds
    )
}
if ($PreparedRuntimeDir) {
    $smokeArgs += @("-PreparedRuntimeDir", $PreparedRuntimeDir)
}
if ($BridgePath) {
    $smokeArgs += @("-BridgePath", $BridgePath)
}

$argumentLine = ($smokeArgs | ForEach-Object { Quote-ProcessArg $_ }) -join " "
$startTime = Get-Date
$smokeProcess = Start-Process -FilePath "powershell.exe" `
    -ArgumentList $argumentLine `
    -RedirectStandardOutput $stdoutPath `
    -RedirectStandardError $stderrPath `
    -WindowStyle Hidden `
    -PassThru

$captures = @()
$captureIndex = 0
$deadline = (Get-Date).AddSeconds($SpawnedUnitStateTimeoutSeconds + $PostSmokeCaptureSeconds)
$smokeFinishedAt = $null

while ((Get-Date) -lt $deadline) {
    if ($smokeProcess.HasExited -and -not $smokeFinishedAt) {
        $smokeFinishedAt = Get-Date
        $deadline = $smokeFinishedAt.AddSeconds($PostSmokeCaptureSeconds)
    }

    $gameProcess = Get-VisualGateGameProcess $startTime
    if ($gameProcess) {
        $captureIndex += 1
        $capturePath = Join-Path $screenshotDir ("frame-{0:D3}.png" -f $captureIndex)
        if (Capture-WindowPng $gameProcess $capturePath) {
            $captures += $capturePath
        }
    }

    Start-Sleep -Seconds $CaptureIntervalSeconds
}

if (-not $smokeProcess.HasExited) {
    $smokeProcess.Kill()
    $smokeProcess.WaitForExit()
} else {
    $smokeProcess.WaitForExit()
}

$gameProcess = Get-VisualGateGameProcess $startTime
if ($gameProcess) {
    try {
        Stop-Process -Id $gameProcess.Id -Force -ErrorAction SilentlyContinue
    } catch {
        Write-Warning ("Unable to stop game process {0}: {1}" -f $gameProcess.Id, $_.Exception.Message)
    }
}

$installedRuntime = Join-Path $runDir "InstalledRuntime"
$debugLogPath = Join-Path $installedRuntime "DebugLogFile.txt"
$spawnedStatePath = Join-Path $installedRuntime "UserData\Archipelago\ArchipelagoSpawnedUnitState.json"
$scoreScreenEventPath = Join-Path $installedRuntime "UserData\Archipelago\Runtime-Smoke-ScoreScreen.json"
$reviewDebugLogPath = Join-Path $runRoot "DebugLogFile.txt"
$reviewSpawnedStatePath = Join-Path $runRoot "ArchipelagoSpawnedUnitState.json"
$reviewScoreScreenEventPath = Join-Path $runRoot "Runtime-Smoke-ScoreScreen.json"
$debugLogTail = @()
$scoreScreenDetected = $false
$debugText = ""
if (Test-Path -LiteralPath $debugLogPath) {
    $debugText = Get-Content -LiteralPath $debugLogPath -Raw -Encoding UTF8 -ErrorAction SilentlyContinue
    $scoreScreenDetected = $debugText -match "Menus[/\\]ScoreScreen\.wnd"
    $debugLogTail = @(Get-Content -LiteralPath $debugLogPath -Tail 40 -ErrorAction SilentlyContinue | ForEach-Object { [string]$_ })
    Copy-Item -LiteralPath $debugLogPath -Destination $reviewDebugLogPath -Force
    $debugLogPath = $reviewDebugLogPath
}
if (Test-Path -LiteralPath $spawnedStatePath) {
    Copy-Item -LiteralPath $spawnedStatePath -Destination $reviewSpawnedStatePath -Force
    $spawnedStatePath = $reviewSpawnedStatePath
}
if (Test-Path -LiteralPath $scoreScreenEventPath) {
    Copy-Item -LiteralPath $scoreScreenEventPath -Destination $reviewScoreScreenEventPath -Force
    $scoreScreenEventPath = $reviewScoreScreenEventPath
}

$expectedGeneral = Get-ApGeneralSmokeExpectation $SmokeChallengePlayerGeneralIndex
$challengeLaunchDetected = $false
$expectedPlayerTemplateDetected = $false
$challengeEnemyTeamDetected = $false
$startingBuildingDetected = $false
$startingObjectDetected = $false
$controlBarSchemeDetected = $false
if ($expectedGeneral -ne $null -and $debugText) {
    $challengeLaunchDetected = $debugText -match ("Runtime smoke Challenge launch: apPlayerGeneral={0}" -f $SmokeChallengePlayerGeneralIndex)
    $expectedPlayerTemplateDetected = $debugText -match [regex]::Escape(("template={0}" -f $expectedGeneral["template"]))
    $challengeEnemyTeamDetected = $debugText -match "UnlockableCheckSpawner::getEnemyTeam: using ThePlayer enemy \(Challenge\)"
    $startingBuildingDetected = $debugText -match "Placing starting building at waypoint Player_1_Start"
    $startingObjectDetected = $debugText -match "Placing starting object"
    $controlBarSchemeDetected = $debugText -match [regex]::Escape(("setControlBarSchemeByPlayer used {0}" -f $expectedGeneral["side"]))
}
$challengeStartCoreVerified = (
    $challengeLaunchDetected -and
    $expectedPlayerTemplateDetected -and
    $startingBuildingDetected -and
    $startingObjectDetected -and
    $controlBarSchemeDetected
)
$challengeStartVerified = ($expectedGeneral -eq $null) -or (
    $challengeStartCoreVerified -and
    ((-not $spawnProofRequested) -or $challengeEnemyTeamDetected)
)

$runtimeScoreScreenEventDetected = Test-Path -LiteralPath $scoreScreenEventPath -PathType Leaf
$spawnedRuntimeKeyObserved = $null
if ($spawnProofRequested -and (Test-Path -LiteralPath $spawnedStatePath -PathType Leaf)) {
    $spawnedStateText = Get-Content -LiteralPath $spawnedStatePath -Raw -Encoding UTF8 -ErrorAction SilentlyContinue
    $spawnedRuntimeKeyObserved = $spawnedStateText -match [regex]::Escape($WaitForSpawnedRuntimeKey)
}
$defeatSplashDetected = $false
$visualFrameStats = @()
$usableScreenshotCount = 0
$uniqueScreenshotHashes = @{}
foreach ($capture in $captures) {
    $frameStats = Get-PngVisualStats $capture
    $visualFrameStats += $frameStats
    if ($frameStats["usable"]) {
        $usableScreenshotCount += 1
    }
    if ($frameStats["sha256"]) {
        $uniqueScreenshotHashes[$frameStats["sha256"]] = $true
    }
    if (Test-DefeatSplashPng $capture) {
        $defeatSplashDetected = $true
        break
    }
}

$stdoutText = ""
$stderrText = ""
if (Test-Path -LiteralPath $stdoutPath) {
    $stdoutText = [string](Get-Content -LiteralPath $stdoutPath -Raw -ErrorAction SilentlyContinue)
}
if (Test-Path -LiteralPath $stderrPath) {
    $stderrText = [string](Get-Content -LiteralPath $stderrPath -Raw -ErrorAction SilentlyContinue)
}
if ($null -eq $stdoutText) {
    $stdoutText = ""
}
if ($null -eq $stderrText) {
    $stderrText = ""
}
$smokeExitCode = $null
try {
    $smokeProcess.Refresh()
    $smokeExitCode = $smokeProcess.ExitCode
} catch {
    $smokeExitCode = $null
}
$smokeCompletedOk = ($smokeExitCode -eq 0) -or (($stdoutText -match "CLEAN_RUNTIME_SMOKE_OK") -and ($stderrText.Trim().Length -eq 0))

$status = "VISUAL_DEMO_GATE_OK"
$failureReason = $null
if (-not $smokeCompletedOk) {
    $status = "VISUAL_DEMO_GATE_FAILED_SMOKE"
    $failureReason = "Clean runtime smoke exited with code $smokeExitCode."
} elseif ($captures.Count -lt 1) {
    $status = "VISUAL_DEMO_GATE_FAILED_NO_SCREENSHOTS"
    $failureReason = "No game window screenshots were captured."
} elseif ($usableScreenshotCount -lt 1) {
    $status = "VISUAL_DEMO_GATE_FAILED_SCREENSHOT_QUALITY"
    $failureReason = "Screenshots were captured, but none looked like a usable game-window frame."
} elseif (-not $challengeStartVerified) {
    $status = "VISUAL_DEMO_GATE_FAILED_CHALLENGE_START"
    $failureReason = "The run did not prove proper Challenge start setup for the requested AP general."
} elseif ($spawnProofRequested -and -not $spawnedRuntimeKeyObserved) {
    $status = "VISUAL_DEMO_GATE_FAILED_SPAWN_PROOF"
    $failureReason = "The selected spawned runtime key was not observed in ArchipelagoSpawnedUnitState.json."
} elseif (($scoreScreenDetected -or $runtimeScoreScreenEventDetected -or $defeatSplashDetected) -and -not $AllowScoreScreen) {
    $status = "VISUAL_DEMO_GATE_FAILED_EARLY_SCORE_SCREEN"
    $failureReason = "The run reached a score-screen/defeat state during direct-map visual demo."
}

$expectedPlayerTemplate = $null
if ($expectedGeneral -ne $null) {
    $expectedPlayerTemplate = $expectedGeneral["template"]
}

$summary = [ordered]@{
    status = $status
    failureReason = $failureReason
    fixture = $Fixture
    smokeMapFile = $SmokeMapFile
    smokeChallengePlayerGeneralIndex = $SmokeChallengePlayerGeneralIndex
    waitForSpawnedRuntimeKey = $WaitForSpawnedRuntimeKey
    spawnProofRequested = $spawnProofRequested
    runRoot = $runRoot
    screenshotDir = $screenshotDir
    screenshotCount = $captures.Count
    usableScreenshotCount = $usableScreenshotCount
    uniqueScreenshotHashCount = $uniqueScreenshotHashes.Count
    screenshots = $captures
    visualFrameStats = $visualFrameStats
    smokeExitCode = $smokeExitCode
    smokeCompletedOk = $smokeCompletedOk
    scoreScreenDetected = $scoreScreenDetected
    runtimeScoreScreenEventDetected = $runtimeScoreScreenEventDetected
    defeatSplashDetected = $defeatSplashDetected
    spawnedRuntimeKeyObserved = $spawnedRuntimeKeyObserved
    challengeStartVerified = $challengeStartVerified
    challengeLaunchDetected = $challengeLaunchDetected
    expectedPlayerTemplateDetected = $expectedPlayerTemplateDetected
    challengeEnemyTeamDetected = $challengeEnemyTeamDetected
    startingBuildingDetected = $startingBuildingDetected
    startingObjectDetected = $startingObjectDetected
    controlBarSchemeDetected = $controlBarSchemeDetected
    expectedPlayerTemplate = $expectedPlayerTemplate
    debugLogPath = $debugLogPath
    spawnedStatePath = $spawnedStatePath
    scoreScreenEventPath = $scoreScreenEventPath
    debugLogTail = $debugLogTail
    stdoutPath = $stdoutPath
    stderrPath = $stderrPath
}
$summary | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $summaryPath -Encoding UTF8

if (-not $KeepReviewInstall -and (Test-Path -LiteralPath $runDir)) {
    $resolvedRunDir = (Resolve-Path -LiteralPath $runDir).Path
    if (-not $resolvedRunDir.StartsWith($runRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to clean visual demo install outside run root: $resolvedRunDir"
    }
    Remove-Item -LiteralPath $resolvedRunDir -Recurse -Force
}

if ($status -ne "VISUAL_DEMO_GATE_OK") {
    Write-Error ("{0}: {1} Summary: {2}" -f $status, $failureReason, $summaryPath)
    exit 1
}

Write-Host ("{0}: {1}" -f $status, $summaryPath)
