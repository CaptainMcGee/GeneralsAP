[CmdletBinding()]
param(
    [ValidateSet("reference-clean", "archipelago-bisect", "archipelago-current")]
    [string]$RuntimeProfile = "reference-clean",
    [int]$Seconds = 25
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-RepoRoot {
    return [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
}

$repoRoot = Get-RepoRoot
$prepareScript = Join-Path $repoRoot "scripts\windows_debug_prepare.ps1"
$launchScript = Join-Path $repoRoot "scripts\windows_debug_launch.ps1"

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

$launchArgs = @("-ExecutionPolicy", "Bypass", "-File", $launchScript, "-RuntimeDir", $runtimeDir)
& powershell.exe @launchArgs
if ($LASTEXITCODE -ne 0) {
    throw "windows_debug_launch.ps1 failed with exit code $LASTEXITCODE"
}

Start-Sleep -Seconds $Seconds

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
