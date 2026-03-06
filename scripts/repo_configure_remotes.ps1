#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Normalize Git remotes for GeneralsAP.

.DESCRIPTION
    Configures the repository so that:
    - origin   = your GeneralsAP GitHub repository
    - upstream = TheSuperHackers/GeneralsGameCode (or a supplied upstream URL)
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$OriginUrl,
    [string]$UpstreamUrl = "https://github.com/TheSuperHackers/GeneralsGameCode.git",
    [switch]$DryRun
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

function Get-GitUrl([string]$RemoteName) {
    if (-not (Test-GitRemote $RemoteName)) {
        return $null
    }
    $url = & git remote get-url $RemoteName 2>$null
    if ($LASTEXITCODE -ne 0) {
        return $null
    }
    return ($url | Out-String).Trim()
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
    if ($DryRun) {
        Write-Host ("git " + ($flatArgs -join " ")) -ForegroundColor Yellow
        return
    }
    & git @flatArgs
    if ($LASTEXITCODE -ne 0) {
        throw "git $($flatArgs -join ' ') failed"
    }
}

$currentOrigin = Get-GitUrl "origin"
$currentUpstream = Get-GitUrl "upstream"

if ($currentOrigin -and ($currentOrigin -eq $UpstreamUrl) -and (-not $currentUpstream)) {
    Invoke-Git @("remote", "rename", "origin", "upstream")
    $currentOrigin = $null
    $currentUpstream = $UpstreamUrl
}

if ($currentUpstream) {
    if ($currentUpstream -ne $UpstreamUrl) {
        Invoke-Git @("remote", "set-url", "upstream", $UpstreamUrl)
    }
} else {
    Invoke-Git @("remote", "add", "upstream", $UpstreamUrl)
}

if ($currentOrigin) {
    if ($currentOrigin -ne $OriginUrl) {
        Invoke-Git @("remote", "set-url", "origin", $OriginUrl)
    }
} else {
    Invoke-Git @("remote", "add", "origin", $OriginUrl)
}

if ($DryRun) {
    Write-Host "Dry run complete. Apply without -DryRun to update remotes." -ForegroundColor Green
} else {
    Write-Host "Updated remotes:" -ForegroundColor Green
    & git remote -v
}
