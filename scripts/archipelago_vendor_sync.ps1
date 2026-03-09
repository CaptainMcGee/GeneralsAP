#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Create a managed vendor sync branch for the vendored Archipelago release.
#>

param(
    [string]$Tag,
    [switch]$SkipMaterialize,
    [string]$BaseBranch = "main"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

function Invoke-Git {
    param([Parameter(ValueFromRemainingArguments = $true)][object[]]$Args)
    $flatArgs = @()
    foreach ($arg in $Args) {
        if ($arg -is [System.Array]) {
            $flatArgs += [string[]]$arg
        } else {
            $flatArgs += [string]$arg
        }
    }
    & git @flatArgs
    if ($LASTEXITCODE -ne 0) {
        throw "git $($flatArgs -join ' ') failed"
    }
}

function Get-GitOutput {
    param([Parameter(ValueFromRemainingArguments = $true)][object[]]$Args)
    $flatArgs = @()
    foreach ($arg in $Args) {
        if ($arg -is [System.Array]) {
            $flatArgs += [string[]]$arg
        } else {
            $flatArgs += [string]$arg
        }
    }
    $output = & git @flatArgs 2>$null
    if ($LASTEXITCODE -ne 0) {
        return $null
    }
    return ($output | Out-String).Trim()
}

function Resolve-PythonCommand {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) { return ,@($python.Source) }
    $python3 = Get-Command python3 -ErrorAction SilentlyContinue
    if ($python3) { return ,@($python3.Source) }
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) { return ,@($py.Source, '-3') }
    throw 'No usable Python interpreter found. Install Python 3 or set python/python3/py -3 on PATH.'
}

function Invoke-Python([string[]]$Args) {
    $command = Resolve-PythonCommand
    $prefix = @()
    if ($command.Count -gt 1) {
        $prefix = $command[1..($command.Count - 1)]
    }
    & $command[0] @($prefix + $Args)
    if ($LASTEXITCODE -ne 0) {
        throw 'Python command failed'
    }
}

function New-SyncBranchName([string]$ReleaseTag) {
    $baseName = "codex/archipelago-sync-$ReleaseTag"
    $candidate = $baseName
    $suffix = 1
    while ((Get-GitOutput @('show-ref', '--verify', '--quiet', "refs/heads/$candidate")) -ne $null) {
        $candidate = "$baseName-$suffix"
        $suffix += 1
    }
    return $candidate
}

$status = Get-GitOutput @('status', '--porcelain')
if ($status) {
    Write-Error 'Working directory is not clean. Commit or stash changes first.'
    & git status --short
    exit 1
}

if (-not $Tag) {
    $Tag = Invoke-Python @('scripts/archipelago_vendor_sync.py', '--print-latest-tag')
    $Tag = ($Tag | Out-String).Trim()
    if (-not $Tag) {
        throw 'Failed to resolve latest Archipelago release tag'
    }
}

$branchName = New-SyncBranchName $Tag
Invoke-Git @('switch', $BaseBranch)
Invoke-Git @('switch', '-c', $branchName)

$syncArgs = @('scripts/archipelago_vendor_sync.py', '--tag', $Tag)
if ($SkipMaterialize) {
    $syncArgs += '--skip-materialize'
}
Invoke-Python $syncArgs

Invoke-Git @('add', 'vendor/archipelago/upstream', 'vendor/archipelago/vendor.json')
$staged = Get-GitOutput @('diff', '--cached', '--name-only')
if ([string]::IsNullOrWhiteSpace($staged)) {
    Write-Host "No Archipelago vendor changes detected for $Tag" -ForegroundColor Yellow
    exit 0
}

Invoke-Git @('commit', '-m', "vendor(archipelago): import upstream $Tag")
Write-Host "Created $branchName" -ForegroundColor Green
