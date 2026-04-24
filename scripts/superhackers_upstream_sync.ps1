#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Create a merge-based upstream sync branch for GeneralsAP.

.DESCRIPTION
    Fetches origin/main and upstream/main, creates a fresh codex/upstream-sync-YYYY-MM-DD branch,
    merges upstream/main with --no-commit, regenerates Archipelago artifacts, and commits the result.
    This keeps upstream syncs reviewable and avoids rebasing published history.

.PARAMETER DryRun
    Show what would be merged without creating a branch or merge commit.

.PARAMETER SkipValidate
    Skip scripts/archipelago_run_checks.py before committing the merge branch.

.PARAMETER BaseBranch
    Local branch to branch from before merging upstream/main. Defaults to main.
#>

param(
    [switch]$DryRun,
    [switch]$SkipValidate,
    [string]$BaseBranch = "main"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

function Test-GitRemote([string]$RemoteName) {
    $remotes = & git remote
    if ($LASTEXITCODE -ne 0) {
        throw "git remote failed"
    }
    return (($remotes | ForEach-Object { $_.Trim() }) -contains $RemoteName)
}

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
    if ($py) { return ,@($py.Source, "-3") }

    throw "No usable Python interpreter found. Install Python 3 or set python/python3/py -3 on PATH."
}

function New-SyncBranchName([bool]$CheckOriginRemote) {
    $dateStamp = Get-Date -Format "yyyy-MM-dd"
    $baseName = "codex/upstream-sync-$dateStamp"
    $candidate = $baseName
    $suffix = 1
    while ($true) {
        $existsLocal = (Get-GitOutput @("show-ref", "--verify", "--quiet", "refs/heads/$candidate")) -ne $null
        $existsRemote = $false
        if ($CheckOriginRemote) {
            & git ls-remote --exit-code --heads origin $candidate *> $null
            $existsRemote = $LASTEXITCODE -eq 0
        }
        if (-not $existsLocal -and -not $existsRemote) {
            break
        }
        $candidate = "$baseName-$suffix"
        $suffix += 1
    }
    return $candidate
}

$status = Get-GitOutput @("status", "--porcelain")
if ($status) {
    Write-Error "Working directory is not clean. Commit or stash changes first."
    & git status --short
    exit 1
}

$originUrl = if (Test-GitRemote "origin") { Get-GitOutput @("remote", "get-url", "origin") } else { $null }
if ($originUrl -and ($originUrl -match "TheSuperHackers/GeneralsGameCode|GeneralsGameCode\.git")) {
    Write-Warning "origin still points to TheSuperHackers/GeneralsGameCode. Configure your GitHub fork as origin before pushing sync branches."
}

$upstreamUrl = if (Test-GitRemote "upstream") { Get-GitOutput @("remote", "get-url", "upstream") } else { $null }
if (-not $upstreamUrl) {
    if ($originUrl -and ($originUrl -match "TheSuperHackers/GeneralsGameCode|GeneralsGameCode\.git")) {
        Invoke-Git @("remote", "rename", "origin", "upstream")
        $upstreamUrl = Get-GitOutput @("remote", "get-url", "upstream")
        Write-Host "Renamed SuperHackers remote from origin to upstream." -ForegroundColor Yellow
    } else {
        Invoke-Git @("remote", "add", "upstream", "https://github.com/TheSuperHackers/GeneralsGameCode.git")
        $upstreamUrl = Get-GitOutput @("remote", "get-url", "upstream")
    }
}

Write-Host "Using upstream remote: $upstreamUrl" -ForegroundColor Cyan
Invoke-Git @("fetch", "upstream", "main")

$hasOrigin = $originUrl -ne $null -and $originUrl -ne ""
if ($hasOrigin) {
    Invoke-Git @("fetch", "origin", $BaseBranch)
}

$mergeBase = Get-GitOutput @("merge-base", "$BaseBranch", "upstream/main")
$upstreamTip = Get-GitOutput @("rev-parse", "upstream/main")
if (-not $mergeBase -or -not $upstreamTip) {
    Write-Error "Could not resolve merge base with upstream/main."
    exit 1
}

$commitsBehind = [int](Get-GitOutput @("rev-list", "--count", "$mergeBase..$upstreamTip"))
if ($commitsBehind -eq 0) {
    Write-Host "Already up to date with upstream/main." -ForegroundColor Green
    exit 0
}

Write-Host "`n$commitsBehind new commit(s) from upstream/main:" -ForegroundColor Yellow
& git log --oneline "$mergeBase..$upstreamTip"
if ($DryRun) {
    Write-Host "`nDry run only. No branch created." -ForegroundColor Green
    exit 0
}

Invoke-Git @("checkout", $BaseBranch)
if ($hasOrigin) {
    Invoke-Git @("pull", "--ff-only", "origin", $BaseBranch)
}

$branchName = New-SyncBranchName $hasOrigin
Invoke-Git @("checkout", "-b", $branchName)
Write-Host "`nCreated sync branch $branchName" -ForegroundColor Cyan

& git merge "upstream/main" "--no-ff" "--no-commit"
if ($LASTEXITCODE -ne 0) {
    $conflicted = & git diff --name-only --diff-filter=U 2>$null
    Write-Host "`nMerge had conflicts. Resolve them on $branchName, regenerate outputs, then commit." -ForegroundColor Red
    if ($conflicted) {
        $conflicted | ForEach-Object { Write-Host "  $_" }
    }
    Write-Host "See Docs/Archipelago/Operations/SuperHackers-Upstream-Sync.md for the merge policy and regeneration steps." -ForegroundColor Yellow
    exit 1
}

if (-not $SkipValidate) {
    $pythonCommand = Resolve-PythonCommand
    Write-Host "`nRunning scripts/archipelago_run_checks.py..." -ForegroundColor Cyan
    if ($pythonCommand.Length -gt 1) {
        & $pythonCommand[0] $pythonCommand[1] "scripts/archipelago_run_checks.py"
    } else {
        & $pythonCommand[0] "scripts/archipelago_run_checks.py"
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Validation failed. Resolve the issue, rerun the tests, then commit the branch manually." -ForegroundColor Red
        exit 1
    }
}

$generatedFiles = @(
    "Data/Archipelago/ingame_names.json",
    "Data/Archipelago/generated_unit_matchup_graph.json",
    "Data/Archipelago/generated_unit_matchup_graph.csv",
    "Data/Archipelago/generated_unit_matchup_graph_readable.txt",
    "Data/INI/Archipelago.ini"
)
foreach ($file in $generatedFiles) {
    if (Test-Path $file) {
        & git add $file
    }
}

$statusAfter = Get-GitOutput @("diff", "--cached", "--name-only")
if (-not $statusAfter) {
    Write-Error "No staged changes found after merging upstream/main."
    exit 1
}

Invoke-Git @("commit", "-m", "Merge upstream/main into $branchName")

Write-Host "`nSync branch committed successfully." -ForegroundColor Green
if ($hasOrigin) {
    Write-Host "Push it with: git push origin $branchName" -ForegroundColor Green
} else {
    Write-Host "Add your GitHub fork as origin before pushing this branch." -ForegroundColor Yellow
}
Write-Host "Open a PR into main after review and CI." -ForegroundColor Green
