# Player Release Architecture

## Goals

- Ship GeneralsAP as a prebuilt player release. Players should not need Visual Studio, CMake, Python, or Archipelago development tooling.
- Avoid redistributing retail Zero Hour assets.
- Keep the base game install recoverable and easy to support.
- Keep the release model compatible with future SuperHackers upstream merges and Archipelago bridge updates.

## Recommended Player Flow

1. Install Command & Conquer Generals Zero Hour from a legal source.
2. Apply GenPatcher to the clean base install before adding GeneralsAP.
3. Clone that fixed install into a separate GeneralsAP folder outside `Program Files`.
4. Launch GeneralsAP from that cloned folder with its own `-userDataDir`.
5. Apply the GeneralsAP release package to the cloned folder only.

This avoids modifying the only base install and avoids requiring a launcher with elevated trust just to play.

## Why A Separate Clone

GeneralsAP is not a data-only mod. It changes game code, GUI behavior, Archipelago runtime state, and generated INI data. That makes the usual "drop a mod into the base game and hope the launcher stack agrees" path too fragile for first release.

A dedicated clone gives us:

- a single tested executable and data set
- no dependence on players matching a specific SuperHackers binary manually
- easier rollback and support
- room for per-profile user data and Archipelago bridge files

## `-userDataDir` Foundation

The engine now supports `-userDataDir <path>` through:

- `GeneralsMD/Code/GameEngine/Source/Common/CommandLine.cpp`
- `GeneralsMD/Code/GameEngine/Source/Common/GlobalData.cpp`

Use this for every packaged GeneralsAP shortcut or launcher entry. That keeps `Options.ini`, save data, and Archipelago bridge state out of the default Documents path and prevents one install copy from stomping another.

Recommended layout:

```text
C:\Games\GeneralsAP\
  generalszh.exe
  Data\...
  UserData\
    Options.ini
    Save\
    Archipelago\
      Bridge-Inbound.json
      Bridge-Outbound.json
```

Launch example:

```powershell
generalszh.exe -win -userDataDir ".\\UserData\\"
```

## Release Artifact Shape

The first supported player release should contain only Generals-owned files:

- the prebuilt GeneralsAP executable and DLLs we produce from this fork
- GeneralsAP data and UI files
- generated `Data/INI/Archipelago.ini`
- Archipelago helper assets used by the mod
- a release manifest that records:
  - GeneralsAP version
  - SuperHackers upstream commit/tag
  - Archipelago vendor release/version
  - required base game expectations

Do not ship retail `.big` archives or any other copyrighted base-game assets.

## Tooling Position

- GenPatcher: supported as the base-install repair step before GeneralsAP is applied.
- GenLauncher: optional future distribution path, not the required path for the first stable GeneralsAP release.
- Custom installer/launcher: recommended for GeneralsAP because we need controlled clone creation, package overlay, and `-userDataDir` shortcuts.

## What The Future Installer Should Do

A first-party GeneralsAP setup tool should:

1. Detect a legal Zero Hour install.
2. Confirm the player is not pointing at a random repack or already-modded directory.
3. Clone the base install into a GeneralsAP target directory.
4. Create a dedicated `UserData` directory.
5. Apply the GeneralsAP package.
6. Create a shortcut that always passes `-userDataDir`.
7. Record a local manifest so upgrades know which SuperHackers/GeneralsAP baseline is installed.

## Release Prep Checklist

Before calling a build "player-ready":

- verify a fresh install + GenPatcher + clone + GeneralsAP overlay path
- verify `Bridge-Outbound.json` is created under the profile user-data directory
- verify Archipelago save/load still works from the cloned install
- verify the package does not require Python or CMake at install time
- verify no retail assets are being distributed from this repo or release bundle
