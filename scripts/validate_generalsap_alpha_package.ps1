[CmdletBinding(DefaultParameterSetName = "PackageRoot")]
param(
    [Parameter(Mandatory = $true, ParameterSetName = "PackageRoot")]
    [string]$PackageRoot,
    [Parameter(Mandatory = $true, ParameterSetName = "ZipPath")]
    [string]$ZipPath,
    [string]$RepoRoot = "",
    [switch]$KeepExtracted
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-RepoRoot {
    if ($RepoRoot) {
        return [System.IO.Path]::GetFullPath($RepoRoot)
    }
    return [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
}

function Get-JsonPropertyValue {
    param(
        [AllowNull()][object]$Object,
        [Parameter(Mandatory = $true)][string]$Name
    )

    if ($null -eq $Object) {
        return $null
    }
    if ($Object -is [System.Collections.IDictionary]) {
        if ($Object.ContainsKey($Name)) {
            $value = $Object[$Name]
            if ($value -is [System.Array]) {
                return ,$value
            }
            return $value
        }
        return $null
    }
    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) {
        return $null
    }
    if ($property.Value -is [System.Array]) {
        return ,$property.Value
    }
    return $property.Value
}

function Test-JsonProperty {
    param(
        [AllowNull()][object]$Object,
        [Parameter(Mandatory = $true)][string]$Name
    )

    if ($null -eq $Object) {
        return $false
    }
    if ($Object -is [System.Collections.IDictionary]) {
        return $Object.ContainsKey($Name)
    }
    return $null -ne $Object.PSObject.Properties[$Name]
}

function Get-JsonPropertyNames {
    param([AllowNull()][object]$Object)

    if ($null -eq $Object) {
        return @()
    }
    if ($Object -is [System.Collections.IDictionary]) {
        return @($Object.Keys)
    }
    return @($Object.PSObject.Properties | ForEach-Object { $_.Name })
}

function Read-JsonFile {
    param([Parameter(Mandatory = $true)][string]$Path)

    Add-Type -AssemblyName System.Web.Extensions
    $serializer = New-Object System.Web.Script.Serialization.JavaScriptSerializer
    $serializer.MaxJsonLength = [int]::MaxValue
    return $serializer.DeserializeObject((Get-Content -LiteralPath $Path -Raw))
}

function ConvertTo-ComparableJson {
    param([AllowNull()][object]$Value)

    if ($null -eq $Value) {
        return "null"
    }
    return ($Value | ConvertTo-Json -Depth 32 -Compress)
}

function Assert-JsonValueEquals {
    param(
        [AllowNull()][object]$Actual,
        [AllowNull()][object]$Expected,
        [Parameter(Mandatory = $true)][string]$Path
    )

    if ((ConvertTo-ComparableJson -Value $Actual) -ne (ConvertTo-ComparableJson -Value $Expected)) {
        throw "Manifest schema validation failed at ${Path}: expected $(ConvertTo-ComparableJson -Value $Expected), got $(ConvertTo-ComparableJson -Value $Actual)"
    }
}

function Test-JsonType {
    param(
        [AllowNull()][object]$Value,
        [Parameter(Mandatory = $true)][string]$Type
    )

    switch ($Type) {
        "null" { return $null -eq $Value }
        "string" { return $Value -is [string] }
        "boolean" { return $Value -is [bool] }
        "integer" {
            if ($Value -is [bool] -or $null -eq $Value) {
                return $false
            }
            if ($Value -is [byte] -or $Value -is [int16] -or $Value -is [int32] -or $Value -is [int64]) {
                return $true
            }
            if ($Value -is [single] -or $Value -is [double] -or $Value -is [decimal]) {
                $decimalValue = [decimal]$Value
                return ([decimal]::Floor($decimalValue) -eq $decimalValue)
            }
            return $false
        }
        "array" { return $Value -is [System.Array] }
        "object" { return ($Value -is [System.Collections.IDictionary] -or $Value -is [pscustomobject] -or $Value -is [hashtable]) -and -not ($Value -is [System.Array]) }
        default { throw "Unsupported JSON schema type '$Type'" }
    }
}

function Get-SchemaValues {
    param([AllowNull()][object]$Value)

    if ($null -eq $Value) {
        return @()
    }
    if ($Value -is [System.Array]) {
        return @($Value)
    }
    return @($Value)
}

function Assert-ValueMatchesJsonSchema {
    param(
        [AllowNull()][object]$Value,
        [Parameter(Mandatory = $true)][object]$Schema,
        [Parameter(Mandatory = $true)][string]$Path
    )

    if (Test-JsonProperty -Object $Schema -Name "type") {
        $typeOptions = Get-SchemaValues -Value (Get-JsonPropertyValue -Object $Schema -Name "type")
        $matchedType = $false
        foreach ($typeOption in $typeOptions) {
            if (Test-JsonType -Value $Value -Type ([string]$typeOption)) {
                $matchedType = $true
                break
            }
        }
        if (-not $matchedType) {
            throw "Manifest schema validation failed at ${Path}: expected type $($typeOptions -join '/'), got $(if ($null -eq $Value) { 'null' } else { $Value.GetType().Name })"
        }
    }

    if (Test-JsonProperty -Object $Schema -Name "const") {
        Assert-JsonValueEquals -Actual $Value -Expected (Get-JsonPropertyValue -Object $Schema -Name "const") -Path $Path
    }

    if (Test-JsonProperty -Object $Schema -Name "enum") {
        $enumValues = Get-SchemaValues -Value (Get-JsonPropertyValue -Object $Schema -Name "enum")
        $actualJson = ConvertTo-ComparableJson -Value $Value
        $matchedEnum = $false
        foreach ($enumValue in $enumValues) {
            if ($actualJson -eq (ConvertTo-ComparableJson -Value $enumValue)) {
                $matchedEnum = $true
                break
            }
        }
        if (-not $matchedEnum) {
            throw "Manifest schema validation failed at ${Path}: value $actualJson is not in enum"
        }
    }

    if ($Value -is [string]) {
        if (Test-JsonProperty -Object $Schema -Name "minLength") {
            $minLength = [int](Get-JsonPropertyValue -Object $Schema -Name "minLength")
            if ($Value.Length -lt $minLength) {
                throw "Manifest schema validation failed at ${Path}: string shorter than $minLength"
            }
        }
        if (Test-JsonProperty -Object $Schema -Name "pattern") {
            $pattern = [string](Get-JsonPropertyValue -Object $Schema -Name "pattern")
            if ($Value -notmatch $pattern) {
                throw "Manifest schema validation failed at ${Path}: value '$Value' does not match $pattern"
            }
        }
    }

    if (Test-JsonType -Value $Value -Type "integer") {
        if (Test-JsonProperty -Object $Schema -Name "minimum") {
            $minimum = [decimal](Get-JsonPropertyValue -Object $Schema -Name "minimum")
            if ([decimal]$Value -lt $minimum) {
                throw "Manifest schema validation failed at ${Path}: value below minimum $minimum"
            }
        }
    }

    if (Test-JsonType -Value $Value -Type "object") {
        $propertiesSchema = Get-JsonPropertyValue -Object $Schema -Name "properties"
        $allowedProperties = @()
        if ($null -ne $propertiesSchema) {
            $allowedProperties = Get-JsonPropertyNames -Object $propertiesSchema
        }

        if (Test-JsonProperty -Object $Schema -Name "required") {
            foreach ($requiredName in (Get-SchemaValues -Value (Get-JsonPropertyValue -Object $Schema -Name "required"))) {
                if (-not (Test-JsonProperty -Object $Value -Name ([string]$requiredName))) {
                    throw "Manifest schema validation failed at ${Path}: missing required property '$requiredName'"
                }
            }
        }

        if ((Test-JsonProperty -Object $Schema -Name "additionalProperties") -and
            ((Get-JsonPropertyValue -Object $Schema -Name "additionalProperties") -eq $false)) {
            foreach ($actualName in (Get-JsonPropertyNames -Object $Value)) {
                if ($allowedProperties -notcontains $actualName) {
                    throw "Manifest schema validation failed at ${Path}: unexpected property '$actualName'"
                }
            }
        }

        foreach ($propertyName in $allowedProperties) {
            if (Test-JsonProperty -Object $Value -Name $propertyName) {
                $childSchema = Get-JsonPropertyValue -Object $propertiesSchema -Name $propertyName
                $childValue = Get-JsonPropertyValue -Object $Value -Name $propertyName
                Assert-ValueMatchesJsonSchema -Value $childValue -Schema $childSchema -Path "$Path.$propertyName"
            }
        }
    }

    if (Test-JsonType -Value $Value -Type "array") {
        $items = @($Value)
        if (Test-JsonProperty -Object $Schema -Name "minItems") {
            $minItems = [int](Get-JsonPropertyValue -Object $Schema -Name "minItems")
            if ($items.Count -lt $minItems) {
                throw "Manifest schema validation failed at ${Path}: fewer than $minItems items"
            }
        }
        if (Test-JsonProperty -Object $Schema -Name "maxItems") {
            $maxItems = [int](Get-JsonPropertyValue -Object $Schema -Name "maxItems")
            if ($items.Count -gt $maxItems) {
                throw "Manifest schema validation failed at ${Path}: more than $maxItems items"
            }
        }

        $prefixItems = @()
        if (Test-JsonProperty -Object $Schema -Name "prefixItems") {
            $prefixItems = Get-SchemaValues -Value (Get-JsonPropertyValue -Object $Schema -Name "prefixItems")
            for ($index = 0; $index -lt [Math]::Min($items.Count, $prefixItems.Count); $index++) {
                Assert-ValueMatchesJsonSchema -Value $items[$index] -Schema $prefixItems[$index] -Path "$Path[$index]"
            }
        }

        if (Test-JsonProperty -Object $Schema -Name "items") {
            $itemsSchema = Get-JsonPropertyValue -Object $Schema -Name "items"
            if ($itemsSchema -is [bool]) {
                if (($itemsSchema -eq $false) -and ($items.Count -gt $prefixItems.Count)) {
                    throw "Manifest schema validation failed at ${Path}: additional array items are not allowed"
                }
            }
            elseif ($null -ne $itemsSchema) {
                for ($index = 0; $index -lt $items.Count; $index++) {
                    if ($index -ge $prefixItems.Count) {
                        Assert-ValueMatchesJsonSchema -Value $items[$index] -Schema $itemsSchema -Path "$Path[$index]"
                    }
                }
            }
        }

        if (Test-JsonProperty -Object $Schema -Name "contains") {
            $containsSchema = Get-JsonPropertyValue -Object $Schema -Name "contains"
            $matchedContains = $false
            foreach ($item in $items) {
                try {
                    Assert-ValueMatchesJsonSchema -Value $item -Schema $containsSchema -Path $Path
                    $matchedContains = $true
                    break
                }
                catch {
                }
            }
            if (-not $matchedContains) {
                throw "Manifest schema validation failed at ${Path}: no array item matched contains"
            }
        }
    }
}

function Assert-ManifestSchemaIfAvailable {
    param(
        [Parameter(Mandatory = $true)][object]$Manifest,
        [Parameter(Mandatory = $true)][string]$RepoRoot
    )

    $schemaPath = Join-Path $RepoRoot "Data\Archipelago\release_manifest_schema.json"
    if (-not (Test-Path -LiteralPath $schemaPath -PathType Leaf)) {
        Write-Warning "release_manifest_schema.json not found; skipping schema validation."
        return
    }

    $schema = Read-JsonFile -Path $schemaPath
    Assert-ValueMatchesJsonSchema -Value $Manifest -Schema $schema -Path "$"
}

function Assert-SafeRelativePackagePath {
    param([Parameter(Mandatory = $true)][string]$RelativePath)

    if ([string]::IsNullOrWhiteSpace($RelativePath)) {
        throw "Package manifest contains an empty relative path."
    }
    if ([System.IO.Path]::IsPathRooted($RelativePath)) {
        throw "Package manifest path must be relative: $RelativePath"
    }
    $normalized = $RelativePath.Replace("\", "/")
    if ($normalized -match "(^|/)\.\.(/|$)") {
        throw "Package manifest path must not traverse outside the package: $RelativePath"
    }
}

function Join-PackagePath {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$RelativePath
    )

    Assert-SafeRelativePackagePath -RelativePath $RelativePath
    return (Join-Path $Root ($RelativePath -replace "/", "\"))
}

function Assert-FileExists {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$RelativePath
    )

    $path = Join-PackagePath -Root $Root -RelativePath $RelativePath
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Package missing expected file: $RelativePath"
    }
}

function Assert-DirectoryExists {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$RelativePath
    )

    $path = Join-PackagePath -Root $Root -RelativePath $RelativePath
    if (-not (Test-Path -LiteralPath $path -PathType Container)) {
        throw "Package missing expected directory: $RelativePath"
    }
}

function Get-RelativeFilePath {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Path
    )

    $rootFull = [System.IO.Path]::GetFullPath($Root).TrimEnd("\", "/")
    $pathFull = [System.IO.Path]::GetFullPath($Path)
    if (-not $pathFull.StartsWith($rootFull, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Path is not under expected root: $Path"
    }
    return $pathFull.Substring($rootFull.Length).TrimStart("\", "/").Replace("\", "/")
}

function Assert-NoForbiddenRetailPayload {
    param(
        [Parameter(Mandatory = $true)][string]$PackageRoot,
        [Parameter(Mandatory = $true)][object]$Manifest
    )

    $payload = Get-JsonPropertyValue -Object $Manifest -Name "payload"
    $forbiddenExtensions = New-Object System.Collections.Generic.HashSet[string] ([System.StringComparer]::OrdinalIgnoreCase)
    $forbiddenExtensions.Add(".big") | Out-Null
    foreach ($extension in (Get-SchemaValues -Value (Get-JsonPropertyValue -Object $payload -Name "forbiddenRetailExtensions"))) {
        if ($extension) {
            $forbiddenExtensions.Add(([string]$extension).ToLowerInvariant()) | Out-Null
        }
    }

    $badFiles = Get-ChildItem -LiteralPath $PackageRoot -Recurse -File |
        Where-Object { $forbiddenExtensions.Contains($_.Extension.ToLowerInvariant()) }
    if ($badFiles) {
        $message = ($badFiles | ForEach-Object { Get-RelativeFilePath -Root $PackageRoot -Path $_.FullName }) -join [Environment]::NewLine
        throw "Package contains forbidden retail payload files:`n$message"
    }
}

function Assert-ExpectedEntries {
    param([Parameter(Mandatory = $true)][string]$PackageRoot)

    $allowedTopLevel = @("payload", "GeneralsAP-Release-Manifest.json", "README-PACKAGE.txt")
    foreach ($entry in (Get-ChildItem -LiteralPath $PackageRoot -Force)) {
        if ($allowedTopLevel -notcontains $entry.Name) {
            throw "Unexpected top-level package entry: $($entry.Name)"
        }
    }

    $payloadRoot = Join-Path $PackageRoot "payload"
    Assert-DirectoryExists -Root $PackageRoot -RelativePath "payload"
    $allowedPayloadEntries = @("Game", "Bridge", "APWorld", "Docs")
    foreach ($entry in (Get-ChildItem -LiteralPath $payloadRoot -Force)) {
        if ($allowedPayloadEntries -notcontains $entry.Name) {
            throw "Unexpected package payload entry: payload/$($entry.Name)"
        }
    }
}

function Assert-ExpectedAlphaPackage {
    param(
        [Parameter(Mandatory = $true)][string]$PackageRoot,
        [Parameter(Mandatory = $true)][object]$Manifest
    )

    Assert-ExpectedEntries -PackageRoot $PackageRoot

    foreach ($relativePath in @(
        "GeneralsAP-Release-Manifest.json",
        "README-PACKAGE.txt",
        "payload/Game/generalszh.exe",
        "payload/Game/zlib1.dll",
        "payload/Game/Run-GeneralsAP.cmd",
        "payload/Game/Data/INI/Archipelago.ini",
        "payload/Game/Data/INI/ArchipelagoChallengeUnitProtection.ini",
        "payload/Game/Data/INI/UnlockableChecksDemo.ini"
    )) {
        Assert-FileExists -Root $PackageRoot -RelativePath $relativePath
    }

    $payload = Get-JsonPropertyValue -Object $Manifest -Name "payload"
    $gameRoot = Join-Path $PackageRoot "payload\Game"
    $claimedGameFiles = New-Object System.Collections.Generic.HashSet[string] ([System.StringComparer]::OrdinalIgnoreCase)
    foreach ($relativePath in (Get-SchemaValues -Value (Get-JsonPropertyValue -Object $payload -Name "gameOverlayFiles"))) {
        $normalized = ([string]$relativePath).Replace("\", "/")
        Assert-SafeRelativePackagePath -RelativePath $normalized
        $claimedGameFiles.Add($normalized) | Out-Null
        Assert-FileExists -Root $gameRoot -RelativePath $normalized
    }

    foreach ($requiredGameFile in @(
        "generalszh.exe",
        "zlib1.dll",
        "Run-GeneralsAP.cmd",
        "Data/INI/Archipelago.ini",
        "Data/INI/ArchipelagoChallengeUnitProtection.ini",
        "Data/INI/UnlockableChecksDemo.ini"
    )) {
        if (-not $claimedGameFiles.Contains($requiredGameFile)) {
            throw "Release manifest does not claim required game overlay file: $requiredGameFile"
        }
    }

    foreach ($actualFile in (Get-ChildItem -LiteralPath $gameRoot -Recurse -File)) {
        $relativePath = Get-RelativeFilePath -Root $gameRoot -Path $actualFile.FullName
        if (-not $claimedGameFiles.Contains($relativePath)) {
            throw "payload/Game contains an unclaimed file: $relativePath"
        }
    }

    $bridgeBundled = [bool](Get-JsonPropertyValue -Object $Manifest -Name "bridgeBundled")
    $bridgeKind = [string](Get-JsonPropertyValue -Object $Manifest -Name "bridgeKind")
    $bridgePath = Get-JsonPropertyValue -Object $payload -Name "bridgePath"
    if ($bridgeBundled) {
        if ($bridgeKind -eq "none") {
            throw "Release manifest claims bridgeBundled but bridgeKind is none."
        }
        if ($null -eq $bridgePath) {
            throw "Release manifest claims bridgeBundled but payload.bridgePath is null."
        }
        Assert-FileExists -Root $PackageRoot -RelativePath ([string]$bridgePath)
    }
    else {
        if ($bridgeKind -ne "none") {
            throw "Release manifest bridgeKind must be none when bridgeBundled is false."
        }
        if ($null -ne $bridgePath) {
            throw "Release manifest bridgePath must be null when bridgeBundled is false."
        }
        Assert-FileExists -Root $PackageRoot -RelativePath "payload/Bridge/README-BRIDGE-NOT-BUNDLED.txt"
    }

    $apworldPayload = [string](Get-JsonPropertyValue -Object $payload -Name "apworldPayload")
    if ($apworldPayload -eq "folder") {
        Assert-DirectoryExists -Root $PackageRoot -RelativePath "payload/APWorld/generalszh"
        foreach ($relativePath in @(
            "payload/APWorld/generalszh/archipelago.json",
            "payload/APWorld/generalszh/__init__.py",
            "payload/APWorld/generalszh/world.py",
            "payload/APWorld/generalszh/items.py",
            "payload/APWorld/generalszh/locations.py",
            "payload/APWorld/generalszh/slot_data.py"
        )) {
            Assert-FileExists -Root $PackageRoot -RelativePath $relativePath
        }
    }
    elseif ($apworldPayload -eq "apworld") {
        Assert-FileExists -Root $PackageRoot -RelativePath "payload/APWorld/generalszh.apworld"
    }
}

function Assert-SafeZipEntries {
    param([Parameter(Mandatory = $true)][string]$ZipPath)

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [System.IO.Compression.ZipFile]::OpenRead($ZipPath)
    try {
        foreach ($entry in $archive.Entries) {
            $entryName = $entry.FullName.Replace("\", "/")
            if ([string]::IsNullOrWhiteSpace($entryName)) {
                continue
            }
            if ([System.IO.Path]::IsPathRooted($entry.FullName) -or $entryName -match "(^|/)\.\.(/|$)") {
                throw "Package zip contains an unsafe entry path: $($entry.FullName)"
            }
            if ([System.IO.Path]::GetExtension($entry.FullName).Equals(".big", [System.StringComparison]::OrdinalIgnoreCase)) {
                throw "Package zip contains forbidden retail payload entry: $($entry.FullName)"
            }
        }
    }
    finally {
        $archive.Dispose()
    }
}

function Get-ExtractedPackageRoot {
    param([Parameter(Mandatory = $true)][string]$ExtractRoot)

    $directManifestPath = Join-Path $ExtractRoot "GeneralsAP-Release-Manifest.json"
    if (Test-Path -LiteralPath $directManifestPath -PathType Leaf) {
        return $ExtractRoot
    }

    $manifestPaths = @(Get-ChildItem -LiteralPath $ExtractRoot -Recurse -File -Filter "GeneralsAP-Release-Manifest.json")
    if ($manifestPaths.Count -ne 1) {
        throw "Package zip must contain exactly one GeneralsAP-Release-Manifest.json; found $($manifestPaths.Count)."
    }
    return (Split-Path -Path $manifestPaths[0].FullName -Parent)
}

function Assert-PackageRoot {
    param(
        [Parameter(Mandatory = $true)][string]$PackageRoot,
        [Parameter(Mandatory = $true)][string]$RepoRoot
    )

    $PackageRoot = [System.IO.Path]::GetFullPath($PackageRoot)
    if (-not (Test-Path -LiteralPath $PackageRoot -PathType Container)) {
        throw "PackageRoot does not exist: $PackageRoot"
    }

    $manifestPath = Join-Path $PackageRoot "GeneralsAP-Release-Manifest.json"
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
        throw "Package missing GeneralsAP-Release-Manifest.json: $PackageRoot"
    }

    $manifest = Read-JsonFile -Path $manifestPath
    Assert-ManifestSchemaIfAvailable -Manifest $manifest -RepoRoot $RepoRoot
    Assert-NoForbiddenRetailPayload -PackageRoot $PackageRoot -Manifest $manifest
    Assert-ExpectedAlphaPackage -PackageRoot $PackageRoot -Manifest $manifest
    Write-Host ("PACKAGE_VALIDATION_OK: {0}" -f $PackageRoot)
}

$resolvedRepoRoot = Get-RepoRoot
$tempRoot = $null
try {
    if ($PSCmdlet.ParameterSetName -eq "ZipPath") {
        $ZipPath = [System.IO.Path]::GetFullPath($ZipPath)
        if (-not (Test-Path -LiteralPath $ZipPath -PathType Leaf)) {
            throw "ZipPath does not exist: $ZipPath"
        }
        Assert-SafeZipEntries -ZipPath $ZipPath
        $tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("GeneralsAP-PackageValidation-" + [guid]::NewGuid().ToString("N"))
        New-Item -ItemType Directory -Force -Path $tempRoot | Out-Null
        Expand-Archive -LiteralPath $ZipPath -DestinationPath $tempRoot -Force
        $extractedPackageRoot = Get-ExtractedPackageRoot -ExtractRoot $tempRoot
        Assert-PackageRoot -PackageRoot $extractedPackageRoot -RepoRoot $resolvedRepoRoot
        Write-Host ("PACKAGE_ZIP_VALIDATION_OK: {0}" -f $ZipPath)
        if ($KeepExtracted) {
            Write-Host ("Extracted package kept at: {0}" -f $tempRoot)
            $tempRoot = $null
        }
    }
    else {
        Assert-PackageRoot -PackageRoot $PackageRoot -RepoRoot $resolvedRepoRoot
    }
}
finally {
    if ($tempRoot -and (Test-Path -LiteralPath $tempRoot)) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
