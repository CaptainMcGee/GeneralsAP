[CmdletBinding()]
param(
    [switch]$FastRealApSmoke,
    [switch]$ContinueOnFailure,
    [string]$ReportDir = ""
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

    throw "Unable to locate python.exe or py.exe for non-human release checks."
}

function Add-ReportRow {
    param(
        [AllowEmptyCollection()][Parameter(Mandatory = $true)][System.Collections.Generic.List[object]]$Rows,
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Status,
        [Parameter(Mandatory = $true)][double]$Seconds,
        [Parameter(Mandatory = $true)][int]$ExitCode
    )

    $Rows.Add([ordered]@{
        name = $Name
        status = $Status
        seconds = [math]::Round($Seconds, 2)
        exitCode = $ExitCode
    }) | Out-Null
}

function Invoke-Gate {
    param(
        [AllowEmptyCollection()][Parameter(Mandatory = $true)][System.Collections.Generic.List[object]]$Rows,
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Executable,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [switch]$ContinueOnFailure
    )

    Write-Host ""
    Write-Host ("=== {0} ===" -f $Name)
    Write-Host ("> {0} {1}" -f $Executable, ($Arguments -join " "))
    $timer = [System.Diagnostics.Stopwatch]::StartNew()
    $exitCode = 0
    try {
        & $Executable @Arguments
        $exitCode = if ($null -ne $global:LASTEXITCODE) { [int]$global:LASTEXITCODE } else { 0 }
        if ($exitCode -ne 0) {
            throw "$Name failed with exit code $exitCode"
        }
        $timer.Stop()
        Add-ReportRow -Rows $Rows -Name $Name -Status "passed" -Seconds $timer.Elapsed.TotalSeconds -ExitCode $exitCode
    }
    catch {
        $timer.Stop()
        if ($exitCode -eq 0) {
            $exitCode = 1
        }
        Add-ReportRow -Rows $Rows -Name $Name -Status "failed" -Seconds $timer.Elapsed.TotalSeconds -ExitCode $exitCode
        Write-Host ("ERROR: {0}" -f $_.Exception.Message)
        if (-not $ContinueOnFailure) {
            throw
        }
    }
}

function Write-Reports {
    param(
        [Parameter(Mandatory = $true)][string]$ReportRoot,
        [AllowEmptyCollection()][Parameter(Mandatory = $true)][System.Collections.Generic.List[object]]$Rows
    )

    New-Item -ItemType Directory -Force -Path $ReportRoot | Out-Null
    $jsonPath = Join-Path $ReportRoot "nonhuman-release-checks.json"
    $markdownPath = Join-Path $ReportRoot "nonhuman-release-checks.md"
    $passed = @($Rows | Where-Object { $_.status -eq "passed" }).Count
    $failed = @($Rows | Where-Object { $_.status -ne "passed" }).Count

    $summary = [ordered]@{
        generatedAtUtc = [DateTime]::UtcNow.ToString("o")
        status = if ($failed -eq 0) { "passed" } else { "failed" }
        passed = $passed
        failed = $failed
        steps = @($Rows)
    }
    ($summary | ConvertTo-Json -Depth 6) + [Environment]::NewLine | Set-Content -LiteralPath $jsonPath -Encoding UTF8

    $lines = New-Object System.Collections.Generic.List[string]
    [void]$lines.Add("# GeneralsAP Non-Human Release Checks")
    [void]$lines.Add("")
    [void]$lines.Add(("Status: **{0}**" -f $summary.status))
    [void]$lines.Add(("Generated UTC: {0}" -f $summary.generatedAtUtc))
    [void]$lines.Add("")
    $pipe = [char]124
    [void]$lines.Add(($pipe + " Step " + $pipe + " Status " + $pipe + " Seconds " + $pipe + " Exit " + $pipe))
    [void]$lines.Add(($pipe + "---" + $pipe + "---" + $pipe + "---:" + $pipe + "---:" + $pipe))
    foreach ($row in $Rows) {
        [void]$lines.Add(("{4} {0} {4} {1} {4} {2} {4} {3} {4}" -f $row.name, $row.status, $row.seconds, $row.exitCode, $pipe))
    }
    [void]$lines.Add("")
    [void]$lines.Add("Fixture clean-runtime gate proves harness plumbing only. Legal-runtime launch remains human/asset-gated.")
    Set-Content -LiteralPath $markdownPath -Value $lines -Encoding UTF8

    Write-Host ("Wrote non-human report JSON: {0}" -f $jsonPath)
    Write-Host ("Wrote non-human report Markdown: {0}" -f $markdownPath)
}

$repoRoot = Get-RepoRoot
if (-not $ReportDir) {
    $ReportDir = Join-Path $repoRoot "build\archipelago\nonhuman-release-checks"
}
else {
    $ReportDir = [System.IO.Path]::GetFullPath($ReportDir)
}

$pythonCommand = Resolve-PythonCommand
$pythonExe = $pythonCommand[0]
$pythonPrefixArgs = @()
if ($pythonCommand.Length -gt 1) {
    $pythonPrefixArgs += $pythonCommand[1..($pythonCommand.Length - 1)]
}

$bridgeExe = Join-Path $repoRoot "build\release-tools\GeneralsAPBridge.exe"
$rows = New-Object System.Collections.Generic.List[object]

try {
    Invoke-Gate -Rows $rows -Name "Build packaged bridge" -Executable "powershell.exe" -Arguments @(
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        (Join-Path $repoRoot "scripts\build_generalsap_bridge.ps1"),
        "-OutputPath",
        $bridgeExe
    ) -ContinueOnFailure:$ContinueOnFailure

    Invoke-Gate -Rows $rows -Name "Archipelago data/world suite" -Executable $pythonExe -Arguments @(
        $pythonPrefixArgs +
        @((Join-Path $repoRoot "scripts\archipelago_run_checks.py"))
    ) -ContinueOnFailure:$ContinueOnFailure

    Invoke-Gate -Rows $rows -Name "Packaged bridge file-mode smoke" -Executable $pythonExe -Arguments @(
        $pythonPrefixArgs +
        @(
            (Join-Path $repoRoot "scripts\archipelago_bridge_executable_smoke.py"),
            "--bridge-exe",
            $bridgeExe
        )
    ) -ContinueOnFailure:$ContinueOnFailure

    Invoke-Gate -Rows $rows -Name "Packaged bridge fake AP network smoke" -Executable $pythonExe -Arguments @(
        $pythonPrefixArgs +
        @(
            (Join-Path $repoRoot "scripts\archipelago_bridge_network_smoke.py"),
            "--bridge-exe",
            $bridgeExe
        )
    ) -ContinueOnFailure:$ContinueOnFailure

    $realApArgs = @(
        $pythonPrefixArgs +
        @(
            (Join-Path $repoRoot "scripts\archipelago_bridge_real_ap_server_smoke.py"),
            "--bridge-exe",
            $bridgeExe
        )
    )
    if ($FastRealApSmoke) {
        $realApArgs += @("--skip-install", "--skip-materialize")
    }
    Invoke-Gate -Rows $rows -Name "Packaged bridge real local AP server smoke" -Executable $pythonExe -Arguments $realApArgs -ContinueOnFailure:$ContinueOnFailure

    Invoke-Gate -Rows $rows -Name "Alpha package fixture smoke" -Executable "powershell.exe" -Arguments @(
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        (Join-Path $repoRoot "scripts\smoke_generalsap_alpha_package.ps1"),
        "-UseFixtureRuntime"
    ) -ContinueOnFailure:$ContinueOnFailure

    Invoke-Gate -Rows $rows -Name "Clean-runtime fixture harness smoke" -Executable "powershell.exe" -Arguments @(
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        (Join-Path $repoRoot "scripts\smoke_generalsap_clean_runtime.ps1"),
        "-UseFixtureRuntime"
    ) -ContinueOnFailure:$ContinueOnFailure
}
finally {
    Write-Reports -ReportRoot $ReportDir -Rows $rows
}

$failed = @($rows | Where-Object { $_.status -ne "passed" }).Count
if ($failed -ne 0) {
    throw "Non-human release checks failed: $failed"
}

Write-Host "NONHUMAN_RELEASE_CHECKS_OK"
