[CmdletBinding()]
param(
    [string]$OutputPath = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-RepoRoot {
    return [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
}

$repoRoot = Get-RepoRoot
if (-not $OutputPath) {
    $OutputPath = Join-Path $repoRoot "build\release-tools\GeneralsAPBridge.exe"
}
else {
    $OutputPath = [System.IO.Path]::GetFullPath($OutputPath)
}

$outputDir = Split-Path -Path $OutputPath -Parent
New-Item -ItemType Directory -Force -Path $outputDir | Out-Null
if (Test-Path -LiteralPath $OutputPath) {
    Remove-Item -LiteralPath $OutputPath -Force
}

$source = @"
using System;
using System.Reflection;

[assembly: AssemblyTitle("GeneralsAPBridge")]
[assembly: AssemblyProduct("GeneralsAP")]
[assembly: AssemblyDescription("GeneralsAP bridge staging stub. Not a real Archipelago network bridge.")]
[assembly: AssemblyCompany("GeneralsAP")]
[assembly: AssemblyVersion("0.0.0.0")]
[assembly: AssemblyFileVersion("0.0.0.0")]

public static class GeneralsAPBridgeStub
{
    public static int Main(string[] args)
    {
        foreach (string arg in args)
        {
            if (String.Equals(arg, "--version", StringComparison.OrdinalIgnoreCase))
            {
                Console.WriteLine("GeneralsAPBridge staging-stub 0.0.0");
                return 0;
            }
        }

        Console.Error.WriteLine("GeneralsAPBridge staging stub only.");
        Console.Error.WriteLine("This executable proves packaging/version wiring and must not be used as the real AP network bridge.");
        Console.Error.WriteLine("Build the real bridge sidecar before public alpha.");
        return 2;
    }
}
"@

Add-Type -TypeDefinition $source -OutputAssembly $OutputPath -OutputType ConsoleApplication -ReferencedAssemblies @("System.dll")

$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $OutputPath).Hash
Write-Host ("Wrote bridge staging stub: {0}" -f $OutputPath)
Write-Host ("SHA256: {0}" -f $hash)
