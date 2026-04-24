# Demo Video Script — Archipelago Mod Technical Showcase

## Recording Setup

- **Map**: GC_TankGeneral (Generals Challenge vs. China Tank General)
- **Player General**: USA Superweapon General
- **Fixture**: minimal_progression (nearly empty roster at start)
- **Launch**: `windows_demo_run.ps1 -Fixture minimal_progression -StarterGeneral Superweapon`
- **Flags**: `-win` (windowed), `-userDataDir ./UserData/` (isolated profile)
- **Runtime profile**: demo-playable
- **Duration target**: 3:30–4:15

## Pre-Recording Checklist

- [ ] Bridge sidecar running with minimal_progression fixture
- [ ] Second terminal ready for manual unlock triggers
- [ ] Unlock-all keybind confirmed working
- [ ] Screen recorder capturing game window + any in-game notifications
- [ ] Test that spawned clusters are visible on this map at expected positions

---

## Segment 1: Loading Screen (0:00–1:00)

**What's on screen**: Game loading screen / splash / map loading bar.

**Purpose**: Use the dead loading time to set context. The viewer has nothing else to look at, so they'll read.

**Recording cue**: Start recording as soon as the game window opens.

| Time | Caption | Notes |
|------|---------|-------|
| 0:02–0:08 | C&C Generals: Zero Hour — Archipelago Mod | Title card. Let it breathe. |
| 0:10–0:18 | Archipelago is a multiworld randomizer framework. Items found in one game can unlock progress in another. | Core Archipelago concept. |
| 0:20–0:28 | This mod integrates Zero Hour into that network. Units, buildings, and upgrades become randomized items. | What the mod does. |
| 0:30–0:38 | Enemy unit clusters are spawned at map locations. Defeating them sends "checks" back to the network. | The check concept. |
| 0:40–0:48 | This is an engine-level mod — 4,400 lines of C++ built on a modernized source port. Not a map hack. | Technical credibility. |
| 0:50–0:58 | Everything you're about to see is running in real-time in the game engine. | Transition to gameplay. |

---

## Segment 2: Mission Start — The Locked Roster (1:00–1:30)

**What's on screen**: Mission begins. Player base is visible. Build menu shows mostly locked/grayed-out options.

**Recording cue**: Slowly mouse over the build menu to show locked items. Select the Barracks and War Factory (if available) to show what's grayed out. Build a few Rangers and a Dozer.

**Player action**: Build initial economy (Supply Center, Power Plant, Rangers). Show the limited options.

| Time | Caption | Notes |
|------|---------|-------|
| 1:02–1:10 | You start with almost nothing. Basic infantry, dozers, and supply buildings. | Show the sparse menu. |
| 1:12–1:20 | Everything else is locked until the Archipelago network delivers it. Every seed is different. | Mouse over locked items. |
| 1:22–1:28 | Unlocks are cross-faction — receiving one item unlocks the equivalent for USA, China, and GLA. | Key design concept. |

---

## Segment 3: First Unlock Arrives (1:30–1:50)

**What's on screen**: Build menu. Player is building base.

**Recording cue**: Trigger a manual unlock from the second terminal. The in-game feedback should be visible. Then mouse over the build menu to show newly available units.

**Player action**: Trigger 1-2 manual unlocks. Start building the newly available units.

| Time | Caption | Notes |
|------|---------|-------|
| 1:32–1:40 | Items arrive from the Archipelago network. New unit categories appear in the build menu. | Trigger unlock just before this caption. |
| 1:42–1:49 | 29 unlock groups cover the full roster — infantry, vehicles, tanks, aircraft, upgrades, and buildings. | Build something new while this shows. |

---

## Segment 4: Discovering the Clusters (1:50–2:20)

**What's on screen**: Player scrolls/pans to a spawned enemy cluster on the map. Enemy units are idle at their guard positions.

**Recording cue**: Pan the camera to the nearest spawned cluster. Hover over individual units to show check ID tooltips. Let the viewer see the cluster formation before engaging.

**Player action**: Don't attack yet. Just observe.

| Time | Caption | Notes |
|------|---------|-------|
| 1:52–2:00 | Enemy unit clusters are spawned at fixed map positions. These are the Archipelago checks. | Pan to cluster. |
| 2:02–2:10 | Each cluster is a coordinated group. They guard a position and fight as a team. | Show the idle formation. |
| 2:12–2:19 | Hover over a unit to see its check ID. Destroying the cluster completes the check. | Hover to show tooltip. |

---

## Segment 5: Cluster AI in Action (2:20–2:55)

**What's on screen**: Player engages a cluster. Shows retaliation, leashing, and retreat.

**Recording cue**: Send a small force to attack one unit in the cluster. Watch the coordinated response. Then try to kite a unit away — watch it hit the leash and snap back.

**Player action**:
1. Attack one cluster unit → watch full cluster respond
2. Pull back your units → watch spawned units pursue to the leash boundary then retreat
3. Let them retreat — observe the speed boost and healing

| Time | Caption | Notes |
|------|---------|-------|
| 2:22–2:29 | Attack one unit and the entire cluster retaliates. They coordinate as a group. | Send units in. |
| 2:30–2:37 | Each unit has a two-tier leash — a soft defend radius and a hard max chase limit. | Show a unit chasing. |
| 2:38–2:45 | Beyond the chase limit, units always retreat — faster movement, healing, and damage reduction. | Unit should be retreating now. |
| 2:47–2:54 | After retreating, a 5-second cooldown prevents them from immediately re-engaging. | Unit arrives back at guard position. |

---

## Segment 6: Unlock All — Full Arsenal (2:55–3:10)

**What's on screen**: Build menu transitions from partial to fully populated.

**Recording cue**: Press the unlock-all keybind. The in-game feedback fires. Mouse over the now-full build menu.

**Player action**: Hit unlock-all. Queue up superweapon construction and advanced units.

| Time | Caption | Notes |
|------|---------|-------|
| 2:57–3:04 | With all items received, the full roster unlocks — over 300 unit and building templates. | Hit unlock-all just before this. |
| 3:05–3:10 | Time to test the limits of the spawned unit protection system. | Transition to protection demo. |

---

## Segment 7: Protection System Demo (3:10–3:40)

**What's on screen**: Player fires superweapons and uses special abilities against spawned clusters.

**Recording cue**: Build and fire the Particle Cannon at a cluster. Use EMP if available. Show the cluster surviving.

**Player action**:
1. Fire Particle Cannon at a cluster → units survive with 0 damage
2. If possible, show EMP not disabling them
3. Show units still fighting at 4x health with 140% weapon range

| Time | Caption | Notes |
|------|---------|-------|
| 3:12–3:19 | Spawned clusters are protected by a 91-rule damage matrix. Superweapons deal zero damage. | Fire superweapon at cluster. |
| 3:20–3:27 | They're immune to EMP, hijack, hacker disable, and sniper vehicle kills. | Show EMP or other ability. |
| 3:28–3:36 | 4x health, 140% weapon range, and built-in stealth detection. These are not easy targets. | Show them fighting back. |

---

## Segment 8: Cluster Kill — Check Complete (3:37–3:55)

**What's on screen**: Player destroys a cluster with conventional forces. Check completion feedback appears.

**Recording cue**: Send a large conventional force to overwhelm and destroy a cluster. Show the completion notification.

**Player action**: Destroy a full cluster. Let the check completion register.

| Time | Caption | Notes |
|------|---------|-------|
| 3:38–3:45 | To complete a check, defeat the cluster with conventional firepower — no shortcuts. | Attack the cluster. |
| 3:46–3:53 | Each completed check sends an item into the Archipelago network — for you or another player. | Show completion feedback. |

---

## Segment 9: Closing (3:55–4:12)

**What's on screen**: Gameplay continues in background. Can show remaining clusters, base overview, or just combat.

**Recording cue**: Let gameplay run. These are closing title cards.

| Time | Caption | Notes |
|------|---------|-------|
| 3:56–4:03 | Work in progress. The Archipelago network connection is next — this demo uses local test fixtures. | Honest status. |
| 4:04–4:12 | Built on the open-source SuperHackers engine port. Follow the project for updates. | Closing. Let gameplay run a few more seconds, then cut. |

---

## Total Caption Count: 27 entries
## Estimated Video Length: ~4:15 (cut after last caption fades)

## Recording Tips

- **Caption breathing room**: Leave 1-2 seconds between captions so the viewer can watch gameplay.
- **Camera pacing**: Move the camera slowly and deliberately. Quick pans make captions hard to read.
- **Don't rush unlocks**: Give each unlock a beat before triggering the next one. The viewer needs time to register what changed.
- **Cluster engagement**: Let the AI behavior play out for a few seconds before moving to the next demonstration. The retaliation and retreat behaviors are the most visually interesting parts.
- **Superweapon timing**: The Particle Cannon has a visible beam. Time the caption to appear just as the beam fires so the viewer reads "zero damage" while watching the beam hit.
- **End clean**: Let 3-5 seconds of gameplay run after the final caption before cutting.

## FFmpeg Burn-In Command (Example)

```bash
ffmpeg -i recording.mp4 -vf "subtitles=demo-video-captions.srt:force_style='FontSize=22,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=2,MarginV=40'" -c:a copy output.mp4
```

Adjust `FontSize`, `MarginV` (vertical position), and colors to taste.
