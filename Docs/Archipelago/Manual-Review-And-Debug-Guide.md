# Manual Review Items, Tests, and Debug Console Guide

Use this for **items to manually verify**, **step-by-step tests**, and **debug console search terms** for Archipelago-related features.

---

## 1. Items You Should Manually Look Into

### 1.1 Matchup weights (graph)

**What**: The unit-vs-unit matchup ratings (0–10) drive logic. They are derived from archetype matrix + overrides and scaled by HP/DMG/veterancy.

**Where**:
- **Base weights / overrides**: `Data/Archipelago/unit_matchup_overrides.csv` and `Data/Archipelago/unit_matchup_archetype_weights.csv`
- **Config**: `Data/Archipelago/unit_matchup_archetypes.json` (balance_model, pattern_rules, explicit overrides)
- **Generated output**: `Data/Archipelago/generated_unit_matchup_graph.json` and `generated_unit_matchup_graph_readable.txt`

**What to do**:
1. Open `generated_unit_matchup_graph_readable.txt` and scan "Attacker vs Defender: weight" lines.
2. Pick a few matchups you know well (e.g. Ranger vs Overlord, Missile Defender vs Humvee). Check that the weight feels right (0 = can’t threaten, 10 = decisive).
3. If a weight is wrong, add or edit a row in `unit_matchup_overrides.csv` (attacker, defender, weight, optional rationale). Re-run:
   `python scripts/archipelago_generate_matchup_graph.py`
   and optionally with `--enemy-hp-multiplier 2 --enemy-dmg-multiplier 1.5` to see scaled weights.
4. For scaling: same script; check the JSON `notes.enemy_context` for the HP/DMG and veterancy assumptions.

**Manual checks**:
- [ ] A few “obvious” matchups (e.g. rocket infantry vs vehicles, overlord vs rangers) have sensible weights.
- [ ] Overrides you add appear in the generated graph and readable file.
- [ ] No combat unit you care about is missing from attackers or defenders (if it should be there per groups).

---

### 1.2 Defender / spawnable list (who can appear in clusters)

**What**: Only defenders in the graph can be spawned at clusters. Defenders are filtered by infantry allowlist, cluster exclusions, and tier (easy/medium/hard).

**Where**: `Data/Archipelago/unit_matchup_archetypes.json`
- `defender_allowed_infantry_regexes`
- `defender_cluster_exclude_regexes` / `defender_cluster_exclude_templates`
- `defender_cluster_tier_easy_regexes`, `defender_cluster_tier_medium_regexes`, `defender_cluster_tier_hard_regexes`
- `defender_cluster_tier_hard_include_templates` (e.g. Battle Chinook)

**What to do**:
1. Run `python scripts/archipelago_generate_matchup_graph.py` and open `generated_unit_matchup_graph.json`.
2. In the `"defenders"` array, confirm:
   - No Black Lotus, Terrorist, Saboteur, Hacker, Supply Outposts, Troop Crawler, or utility-only units (except where intended, e.g. Dozer/Worker/Supply Truck in easy only).
   - Only one Chinook type: AmericaVehicleChinook, and its `cluster_tier` is `"hard"`.
   - Base defenses (Patriot, Stinger, etc.) have `cluster_tier` `"medium"`; no base defenses with `"hard"`.
3. If a unit is missing or wrong tier, adjust the regexes/templates in `unit_matchup_archetypes.json` and re-run the script.

**Manual checks**:
- [ ] Excluded list (guide §1.2) does not appear as defenders (except Battle Chinook in hard).
- [ ] Easy/medium/hard tier assignments match your design (e.g. no overlords in easy).
- [ ] Demo Trap / Advanced Demo Trap never appear in defenders or base defense list.

---

### 1.3 Enemy general threat profiles (defense / objective strength)

**What**: Static strength values per general and difficulty for “can defend” and “can beat mission” logic.

**Where**: `Data/Archipelago/enemy_general_profiles.json`

**What to do**:
1. Open the file. For each of the 7 generals, check `threat_units` (unit types they send) and `difficulty.easy/medium/hard` with `defense_strength` and `objective_strength`.
2. Compare with in-game feel: if a general is too easy or too hard in logic, tweak the numbers (defense_strength for medium clusters, objective_strength for hard / mission win).
3. Ensure `threat_units` lists are accurate for that general (no missing or wrong units).

**Manual checks**:
- [ ] All 7 challenge generals present (no Demo/Infantry).
- [ ] threat_units match what that general actually fields.
- [ ] defense_strength and objective_strength values are in a sensible order (easy &lt; medium &lt; hard, objective ≥ defense).

---

### 1.4 Cluster definitions and selection

**What**: Where clusters are on the map and how many are selected per seed.

**Where**:
- Definitions: `Data/Archipelago/cluster_config.json` (and files from cluster editor in `cluster_definitions/`)
- Selection logic: `scripts/archipelago_cluster_selection.py`

**What to do**:
1. If you use the cluster editor: run
   `python scripts/archipelago_cluster_editor.py --bitmap <path_to_map_image> [--load existing.json] [--save out.json]`
   Place points, set tiers, save. Merge or copy the output into `cluster_config.json` under `maps.<MapName>`.
2. Run `python scripts/archipelago_cluster_selection.py` to print a sample of selected locations per map. Confirm count = `clusters_per_map × slots_per_cluster` and that tier/location_id look correct.
3. Adjust `defaults.clusters_per_map` and `defaults.slots_per_cluster` in `cluster_config.json` (and later YAML options) as needed.

**Manual checks**:
- [ ] Cluster positions (x, y) and waypoint names match your map/INI expectations.
- [ ] Selected locations have correct `tier` and `location_id` format.

---

### 1.5 Superweapon limit (1 vs 2)

**What**: Player can build 1 superweapon (2 if playing as Superweapon General). Enforced in challenge campaign when Archipelago is active.

**Where**: `GeneralsMD/.../GameLogic.cpp` (init, challenge branch); build limit comes from `GameInfo::getSuperweaponRestriction()` / `ThingTemplate::getMaxSimultaneousOfType()`.

**What to do**:
1. Start a **Generals Challenge** game with Archipelago enabled.
2. Pick **Superweapon General** → build a second Particle Cannon (or second superweapon) and confirm you can have 2.
3. Start another challenge with a **non-Superweapon** general → confirm you cannot build a second superweapon (only 1).
4. In the debug console (see below), search for **`[Archipelago] Superweapon limit`** and confirm the message says limit 2 when playing Superweapon General and 1 otherwise.

**Manual checks**:
- [ ] Superweapon General: limit 2, can build two superweapons.
- [ ] Other generals: limit 1, only one superweapon buildable.
- [ ] Debug log shows the correct limit at game start.

---

## 2. Step-by-Step Tests to Run

### Test 1: Matchup graph generation

1. Open a terminal in the repo root.
2. Run:
   `python scripts/archipelago_generate_matchup_graph.py`
3. Confirm no errors and that these files exist/updated:
   - `Data/Archipelago/generated_unit_matchup_graph.json`
   - `Data/Archipelago/generated_unit_matchup_graph.csv`
   - `Data/Archipelago/generated_unit_matchup_graph_readable.txt`
4. Run with scaling:
   `python scripts/archipelago_generate_matchup_graph.py --enemy-hp-multiplier 2 --enemy-dmg-multiplier 1.5`
   Open the JSON and check `notes.enemy_context` and a few edge weights to see the effect.

---

### Test 2: Archipelago plan automated tests

1. In repo root:
   `python scripts/tests/test_archipelago_data_pipeline.py`
2. All listed tests should **PASS**. If any FAIL, read the assertion message and fix the config or script indicated.
3. Tests cover: JSON configs, veterancy factors, base defense exclude (Demo/Advanced Demo), 7 enemy generals, graph structure, Chinook as hard defender only, excluded units not in defenders, no demo traps in defenders, base defenses medium-only, logic prereqs, cluster selection, cluster editor export.

---

### Test 3: Logic prereqs (can_defend / can_beat_mission)

1. Run:
   `python scripts/archipelago_logic_prerequisites.py`
2. You should see printed lines for each general’s medium difficulty defense/objective strength and two example calls (e.g. `can_defend(60, 'TankGeneral', 'medium'): True`).
3. Optionally edit `scripts/archipelago_logic_prerequisites.py` and call `can_defend` / `can_beat_mission` with different strengths to see thresholds.

---

### Test 4: Cluster selection

1. Run:
   `python scripts/archipelago_cluster_selection.py`
2. Check stdout: it should list at least one map and the number of locations and a few `location_id` and `tier` lines.
3. Confirm the number of locations = `clusters_per_map × slots_per_cluster` for that map (from `cluster_config.json` defaults).

---

### Test 5: Cluster editor export

1. Run:
   `python scripts/archipelago_cluster_editor.py --export Data/Archipelago/cluster_definitions/sample_coords.txt --save Data/Archipelago/cluster_definitions/export_test.json`
2. Open `export_test.json`: it should contain an array of cluster objects with `cluster_id`, `x`, `y`, `tier`, `waypoint_name`.
3. If you have Pillow and tkinter, you can test interactive mode with a bitmap:
   `python scripts/archipelago_cluster_editor.py --bitmap <path_to_image.png> [--save out.json]`

---

### Test 6: In-game spawner and checks (manual)

1. Build and run the game in **Debug**.
2. Enable the **Debug console / window** (see Section 3).
3. Start a **Generals Challenge** mission on a map that has a section in `UnlockableChecksDemo.ini` (e.g. the demo map you use).
4. Watch the debug console for:
   - **`[Archipelago] UnlockableCheckSpawner: runAfterMapLoad`** – confirms spawner ran for that map.
   - **`[Archipelago] Using UnlockableChecksDemo.ini fallback`** – confirms INI fallback (no slot data).
   - **`[Archipelago] Spawner running for map ... seed=...`** – map and seed.
   - **`[Archipelago] Spawned ... at ... -> check ...`** – each spawned unit and its check ID.
   - **`[Archipelago] Spawned unit ... vision range boosted to 400`** – vision anti-exploit applied (may appear multiple times).
5. Kill a spawned unit: you should see **`[Archipelago] Check complete: <id> (killed <template>) +$5000`** and an in-game unlock message.
6. Unlock all groups (e.g. via keybind if you have one): after the last required kill you should see **`[Archipelago] All groups unlocked bonus +$10,000`** and the in-game bonus message.

---

## 3. Debug Console and In-Game Console

### 3.1 Enabling the debug console

- **Visual Studio**: Run the game under the debugger (F5 or Start Debugging). Debug output typically goes to the **Output** window; select the show-all or “Debug” output.
- **Standalone**: If the build copies a `.exe` and you run it from a terminal, `DEBUG_LOG` may go to stdout/stderr or to a log file depending on your `DEBUG_LOG` implementation (see your codebase’s `Debug.h` or equivalent).
- **In-game**: Some builds have an in-game console (e.g. tilde `~` or a dedicated key). Check your bindings; messages shown with `TheInGameUI->messageNoFormat(...)` appear in-game (e.g. “Unlocked: …”, “All groups unlocked! +$10,000”, “No config for map …”).

### 3.2 Search terms for the debug console

Filter or search the debug log for these strings to find Archipelago-related messages:

| Search term | What it indicates |
|-------------|--------------------|
| **`[Archipelago]`** | Any Archipelago-tagged log (spawner, state, superweapon). Use this first for a broad filter. |
| **`[Archipelago] Superweapon limit`** | Superweapon cap set at game start (1 or 2). Confirms correct general detection. |
| **`[Archipelago] Using UnlockableChecksDemo.ini fallback`** | Spawner is using INI fallback, not slot data. Expected until slot data is wired. |
| **`[Archipelago] No config for map`** | Current map has no section in UnlockableChecksDemo.ini; spawner won’t run for that map. |
| **`[Archipelago] Spawner running for map`** | Spawner is active for this map and the seed. |
| **`[Archipelago] Spawned ... -> check`** | A unit was spawned and tied to a check ID. |
| **`[Archipelago] Spawned unit ... vision range boosted`** | Vision range was increased to 400 for that spawned unit (anti–Nuke Cannon exploit). |
| **`[Archipelago] Check complete`** | A kill was counted as completing a check (unlock + $5000). |
| **`[Archipelago] All groups unlocked bonus`** | All checks for the map are satisfied; $10,000 bonus granted. |
| **`[Archipelago] Granted check ... -> unlocked group`** | ArchipelagoState granted a group unlock for that check. |
| **`[Archipelago] State reset()`** | Archipelago state was reset/reloaded from file. |

### 3.3 Terms that might indicate problems

| Search term | Likely meaning |
|-------------|-----------------|
| **`no enemy team`** | Spawner couldn’t find the enemy team for the map; check INI `EnemyTeam` and map setup. |
| **`waypoint ... not found`** | A waypoint name in the INI doesn’t exist on the map. |
| **`template ... not found`** | A unit template in the INI is missing from the game data. |
| **`UnlockableChecksDemo.ini not found`** | INI not found in any of the search paths; check working directory and INI location. |

---

## 4. Quick reference: where things live

| What | File(s) / location |
|------|---------------------|
| Matchup overrides (manual edits) | `Data/Archipelago/unit_matchup_overrides.csv` |
| Archetype weights & defender rules | `Data/Archipelago/unit_matchup_archetypes.json` |
| Generated graph (readable) | `Data/Archipelago/generated_unit_matchup_graph_readable.txt` |
| Enemy general strengths | `Data/Archipelago/enemy_general_profiles.json` |
| Cluster definitions | `Data/Archipelago/cluster_config.json`, `cluster_definitions/*.json` |
| Fallback spawn config | `Data/INI/UnlockableChecksDemo.ini` |
| AP options (YAML) | `Data/Archipelago/options_schema.yaml` |
| Spawner + vision + fallback log | `GeneralsMD/.../UnlockableCheckSpawner.cpp` |
| Superweapon limit log | `GeneralsMD/.../GameLogic.cpp` |
| State / unlock logs | `GeneralsMD/.../ArchipelagoState.cpp` |
| Automated tests | `scripts/tests/test_archipelago_data_pipeline.py` |

---

*For implementation status and open TODOs, see [Archipelago-Implementation-Todo.md](Planning/Archipelago-Implementation-Todo.md).*
