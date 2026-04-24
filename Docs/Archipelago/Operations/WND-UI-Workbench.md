# WND UI Workbench

**Purpose**: Canonical workflow for extracting real Zero Hour WND assets, auditing them, and iterating on Archipelago shell UI with minimal interference to gameplay/runtime work.

**Status**: Active workflow for `L5` menu-shell prep. This is tooling and process, not live in-game AP UI implementation.

---

## 1. Key Findings

### GenWND `v2.5.0` is usable, but parser automation is better than GUI automation

Checked tag:

- [GenWND `v2.5.0`](https://github.com/DevGeniusCode/GenWND/tree/v2.5.0)

Verified from upstream source:

- real WYSIWYG editor
- open file / open folder / drag-drop
- save / save-as
- visual move/resize
- undo/redo
- property editing
- parser-backed internal model

Important constraint:

- GenWND does not expose a clean batch CLI for repo automation

Recommended use in this project:

- automate extraction, structure audit, and deploy with local scripts
- use GenWND for visual edits after the files are already in the workbench

### Real WND assets already exist in the staged runtime

Local staged runtimes already contain `WindowZH.big`, including:

- `Window/Menus/MainMenu.wnd`
- `Window/Menus/NetworkDirectConnect.wnd`
- `Window/Menus/SinglePlayerMenu.wnd`
- `Window/Menus/MapSelectMenu.wnd`

That means the first UI lane does not need a retail install-side extraction workflow.

### Loose files override archive WNDs

Relevant local code:

- `GeneralsMD/Code/GameEngine/Source/GameLogic/System/GameLogic.cpp:2269`
- `GeneralsMD/Code/GameEngine/Source/GameClient/GUI/GameWindowManagerScript.cpp:2698`
- `Core/GameEngine/Source/Common/System/FileSystem.cpp:138`

Behavior:

- shell starts from `Menus/MainMenu.wnd`
- engine resolves that to `Window\Menus\MainMenu.wnd`
- local filesystem is checked before archive filesystem

Result:

- loose `Window\...` files are the safest first iteration path
- no archive repack is needed for the first UI lane

### Initial audit already found one stock mismatch

The generated manifest for stock `MainMenu.wnd` currently reports:

- `WindowTransitions.ini` references `MainMenu.wnd:ButtonTRAINING`
- extracted stock `MainMenu.wnd` does not define `ButtonTRAINING`

Treat this as baseline stock drift to account for during AP menu work, not as an AP-specific regression.

---

## 2. Generated-Only Asset Policy

Raw extracted WNDs are **generated workbench assets**, not canonical tracked source.

Policy:

- extract from staged runtime into ignored `build/archipelago/wnd-work`
- do not commit extracted stock WNDs
- commit tooling, manifests, docs, and later any deliberate original AP-owned WND assets if that becomes the chosen ownership model

This keeps repo clean and avoids treating extracted retail-derived files as hand-authored project source.

---

## 3. Working Set

Machine-readable source:

- `Data/Archipelago/wnd_working_set.json`

Current working set:

- `Window/Menus/MainMenu.wnd`
- `Window/Menus/NetworkDirectConnect.wnd`
- `Window/Menus/SinglePlayerMenu.wnd`
- `Window/Menus/MapSelectMenu.wnd`
- `Window/Menus/BlankWindow.wnd`
- `Window/Menus/MessageBox.wnd`
- `Window/Menus/OptionsMenu.wnd`

Intent:

- `MainMenu.wnd` is the entry seam
- `NetworkDirectConnect.wnd` is the best reference for future AP connect flow
- `MapSelectMenu.wnd` is the best reference for future mission-select structure
- `BlankWindow.wnd` is the best seed for AP-owned layouts

---

## 4. Automation Commands

### One-command Windows wrapper

Use:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows_wnd_workbench.ps1 -Action prepare
```

This will:

- locate a staged runtime with `WindowZH.big`
- extract the configured working set into `build/archipelago/wnd-work/source`
- seed editable copies into `build/archipelago/wnd-work/override`
- generate manifests for both trees

Refresh manifests only:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows_wnd_workbench.ps1 -Action manifest
```

Deploy loose overrides into staged runtime:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows_wnd_workbench.ps1 -Action deploy
```

### Direct Python entrypoint

Script:

- `scripts/wnd_workbench.py`

Examples:

```bash
python scripts/wnd_workbench.py extract --archive build/win32-vcpkg-playtest/GeneralsMD/Release/WindowZH.big --force
python scripts/wnd_workbench.py compose
python scripts/wnd_workbench.py manifest build/archipelago/wnd-work/source --output build/archipelago/wnd-work/manifests/source-manifest.json
python scripts/wnd_workbench.py deploy --runtime-dir build/win32-vcpkg-playtest/GeneralsMD/Release
```

Capabilities:

- extract selected WNDs from `WindowZH.big`
- seed editable loose override tree
- build JSON manifests with hierarchy and audit data
- cross-check WND control names against `Data/INI/WindowTransitions.ini`
- deploy loose overrides into a staged runtime

### Review screenshot harness

Script:

- `scripts/windows_ap_shell_review_capture.ps1`

Use:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows_ap_shell_review_capture.ps1 -KillExisting
```

This generates review screenshots for:

- `mainmenu`
- `hub`
- `connect`
- `mission-select`
- `logic-tracker`
- `check-tracker`

Mechanism:

- writes optional review target to `UserData\Archipelago\APShellReviewOpen.txt`
- launches staged runtime in windowed mode
- captures main window screenshot
- stops runtime cleanly between targets

---

## 5. Minimal-Interference Lane Order

Recommended order:

1. prepare WND workbench
2. inspect generated `source-manifest.json` and `override-manifest.json`
3. edit WNDs in the override tree with GenWND
4. regenerate manifests after each meaningful pass
5. deploy loose overrides into staged runtime
6. smoke test menu load and navigation before any live AP/backend wiring

Do **not** start with:

- live AP connection code
- mission launching
- tracker backend wiring
- archive repack

---

## 6. First UI Slice Boundaries

Locked first slice:

- top-level `Archipelago` button on main menu
- dedicated AP hub
- connect screen shell
- mission select shell
- logic tracker shell
- check tracker shell
- back/forward navigation only

Not part of first slice:

- live AP connection
- real mission dispatch
- real tracker data
- gameplay logic integration

Use fixture data and placeholder text first.
