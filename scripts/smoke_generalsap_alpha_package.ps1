[CmdletBinding()]
param(
    [string]$RuntimeDir = "",
    [string]$OutputDir = "",
    [switch]$UseFixtureRuntime,
    [switch]$NoSeededBridgeLoop
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

    throw "Unable to locate python.exe or py.exe for seeded bridge loop smoke."
}

function New-FixtureRuntime {
    param([Parameter(Mandatory = $true)][string]$Root)

    $runtime = Join-Path $Root "FixtureRuntime"
    New-Item -ItemType Directory -Force -Path (Join-Path $runtime "Data\INI") | Out-Null
    New-Item -ItemType Directory -Force -Path (Join-Path $runtime "MappedImages\HandCreated") | Out-Null
    Set-Content -LiteralPath (Join-Path $runtime "generalszh.exe") -Value "fixture exe" -Encoding ASCII
    Set-Content -LiteralPath (Join-Path $runtime "Game.dat") -Value "fixture dat" -Encoding ASCII
    Set-Content -LiteralPath (Join-Path $runtime "Data\INI\Archipelago.ini") -Value "; fixture archipelago" -Encoding ASCII
    Set-Content -LiteralPath (Join-Path $runtime "Data\INI\ArchipelagoChallengeUnitProtection.ini") -Value "; fixture protection" -Encoding ASCII
    Set-Content -LiteralPath (Join-Path $runtime "Data\INI\UnlockableChecksDemo.ini") -Value "; fixture checks" -Encoding ASCII
    Set-Content -LiteralPath (Join-Path $runtime "MappedImages\HandCreated\zz_ArchipelagoLock.ini") -Value "; fixture image" -Encoding ASCII
    return $runtime
}

$repoRoot = Get-RepoRoot
$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("GeneralsAP-AlphaPackageSmoke-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $tempRoot | Out-Null

try {
    if ($UseFixtureRuntime -or -not $RuntimeDir) {
        $RuntimeDir = New-FixtureRuntime -Root $tempRoot
    }
    else {
        $RuntimeDir = [System.IO.Path]::GetFullPath($RuntimeDir)
    }

    if (-not $OutputDir) {
        $OutputDir = Join-Path $tempRoot "Out"
    }
    else {
        $OutputDir = [System.IO.Path]::GetFullPath($OutputDir)
    }

    $bridgePath = Join-Path $tempRoot "GeneralsAPBridge.exe"
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $repoRoot "scripts\build_generalsap_bridge_stub.ps1") -OutputPath $bridgePath
    if ($LASTEXITCODE -ne 0) {
        throw "build_generalsap_bridge_stub.ps1 failed with exit code $LASTEXITCODE"
    }

    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $repoRoot "scripts\package_generalsap_alpha.ps1") -RuntimeDir $RuntimeDir -OutputDir $OutputDir -BridgePath $bridgePath -BridgeKind staging_stub -NoZip
    if ($LASTEXITCODE -ne 0) {
        throw "package_generalsap_alpha.ps1 failed with exit code $LASTEXITCODE"
    }

    $packageRoot = Join-Path $OutputDir "GeneralsAP-0.1.0-alpha"
    $manifestPath = Join-Path $packageRoot "GeneralsAP-Release-Manifest.json"
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json

    if ($manifest.requiresExternalBasePatcher -ne $false) { throw "release manifest requires external base patcher" }
    if ($manifest.retailAssetsIncluded -ne $false) { throw "release manifest allows retail assets" }
    if ($manifest.bridgeBundled -ne $true) { throw "bridge was not bundled in package smoke" }
    if ($manifest.bridgeKind -ne "staging_stub") { throw "bridgeKind did not record staging_stub" }
    if ($manifest.slotDataVersion -ne 2) { throw "slotDataVersion drift" }
    if ($manifest.logicModel -ne "generalszh-alpha-grouped-v1") { throw "logicModel drift" }

    foreach ($relativePath in @(
        "payload\Game\generalszh.exe",
        "payload\Game\Run-GeneralsAP.cmd",
        "payload\Game\Data\INI\Archipelago.ini",
        "payload\Bridge\GeneralsAPBridge.exe",
        "payload\APWorld\generalszh\archipelago.json",
        "README-PACKAGE.txt"
    )) {
        if (-not (Test-Path -LiteralPath (Join-Path $packageRoot $relativePath) -PathType Leaf)) {
            throw "Package smoke missing $relativePath"
        }
    }

    $retailArchives = Get-ChildItem -LiteralPath $packageRoot -Recurse -File -Filter "*.big"
    if ($retailArchives) {
        throw "Package smoke found forbidden retail archives: $($retailArchives.FullName -join ', ')"
    }

    $cloneRoot = Join-Path $tempRoot "Clone"
    New-Item -ItemType Directory -Force -Path $cloneRoot | Out-Null
    Copy-Item -Path (Join-Path $packageRoot "payload\Game\*") -Destination $cloneRoot -Recurse -Force
    if (-not (Test-Path -LiteralPath (Join-Path $cloneRoot "Run-GeneralsAP.cmd") -PathType Leaf)) {
        throw "Overlay clone smoke did not install Run-GeneralsAP.cmd"
    }

    if (-not $NoSeededBridgeLoop) {
        $pythonCommand = Resolve-PythonCommand
        $pythonExe = $pythonCommand[0]
        $pythonArgs = @()
        if ($pythonCommand.Length -gt 1) {
            $pythonArgs += $pythonCommand[1..($pythonCommand.Length - 1)]
        }
        $pythonArgs += @(Join-Path $repoRoot "scripts\archipelago_seeded_bridge_loop_smoke.py")
        & $pythonExe @pythonArgs
        if ($LASTEXITCODE -ne 0) {
            throw "archipelago_seeded_bridge_loop_smoke.py failed with exit code $LASTEXITCODE"
        }
    }

    Write-Host ("PACKAGE_SMOKE_OK: {0}" -f $packageRoot)
}
finally {
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
