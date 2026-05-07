# Command & Conquer Generals: Zero Hour Setup Guide

This Archipelago world is an early GeneralsAP skeleton targeting Archipelago 0.6.7.

This setup page is intentionally stale as player-facing documentation. Use the repo docs for current release validation truth: `TESTING.md`, `Docs/Archipelago/Operations/Player-Release-Architecture.md`, and `Docs/Archipelago/Planning/Item-Location-Framework-Branch-Readiness.md`.

Current checkpoint scope:

- stable mission-victory locations
- one shuffled victory medal item per main challenge general
- Boss General access gated by all seven victory medals
- canonical location IDs
- canonical runtime keys
- slot-data v2 shell
- packaged bridge file mode
- packaged AP websocket network mode
- received-item to runtime unlock/session option mapping
- selected mission/cluster `LocationChecks`
- Boss victory `StatusUpdate`
- real local Archipelago 0.6.7 server smoke
- clean-runtime guarded completion smoke for selected mission/cluster keys
- optional spawned cluster materialization smoke
- APSkeleton-style module layout adapted to GeneralsAP's challenge-map progression model

Not implemented yet:

- cluster weakness logic
- mission `Hold` / `Win` logic
- player-facing connect/launcher UI
- tracker UI
- hosted-room public release proof
- natural score-screen victory and spawned-kill playthrough proof
- clean-machine package proof outside the developer environment
- captured-building and supply-pile gameplay

Developer notes live in `Docs/Archipelago/Planning/AP-World-Skeleton-Notes.md`.
