[CmdletBinding()]
param(
    [string]$OutputPath = "",
    [ValidateSet("win-x64")]
    [string]$RuntimeIdentifier = "win-x64",
    [switch]$FrameworkDependent
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-RepoRoot {
    return [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
}

$repoRoot = Get-RepoRoot
$projectPath = Join-Path $repoRoot "tools\bridge\GeneralsAPBridge\GeneralsAPBridge.csproj"
if (-not (Test-Path -LiteralPath $projectPath -PathType Leaf)) {
    throw "Bridge project missing: $projectPath"
}

if (-not $OutputPath) {
    $OutputPath = Join-Path $repoRoot "build\release-tools\GeneralsAPBridge.exe"
}
else {
    $OutputPath = [System.IO.Path]::GetFullPath($OutputPath)
}

$publishRoot = Join-Path $repoRoot "build\bridge-publish"
$selfContained = if ($FrameworkDependent) { "false" } else { "true" }

& dotnet publish $projectPath `
    -c Release `
    -r $RuntimeIdentifier `
    --self-contained:$selfContained `
    -p:PublishSingleFile=true `
    -p:IncludeNativeLibrariesForSelfExtract=true `
    -o $publishRoot

if ($LASTEXITCODE -ne 0) {
    throw "dotnet publish failed with exit code $LASTEXITCODE"
}

$publishedExe = Join-Path $publishRoot "GeneralsAPBridge.exe"
if (-not (Test-Path -LiteralPath $publishedExe -PathType Leaf)) {
    throw "Published bridge exe missing: $publishedExe"
}

$outputDir = Split-Path -Path $OutputPath -Parent
New-Item -ItemType Directory -Force -Path $outputDir | Out-Null
Copy-Item -LiteralPath $publishedExe -Destination $OutputPath -Force

$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $OutputPath).Hash
Write-Host ("Wrote bridge executable: {0}" -f $OutputPath)
Write-Host ("SHA256: {0}" -f $hash)
