# Unit Matchup Weight Sources

This file tracks the external references used to seed matchup weights.

## Source IDs

- `INI-DPS`
  Source: actual game INI files (`Data/INI/Weapon.ini`, `Data/INI/Armor.ini`, `Data/INI/Object/FactionUnit.ini`)
  Method: DPS = PrimaryDamage / (DelayBetweenShots/1000). Effective DPS = DPS × ArmorModifier%.
  TTK = DefenderHP / EffectiveDPS. Weight derived from comparative TTK in 1v1 open field.
  Key armor interactions used:
  - SMALL_ARMS: 100% vs HumanArmor, 25% vs TankArmor, 50% vs TruckArmor, 120% vs AirplaneArmor
  - INFANTRY_MISSILE: 10% vs HumanArmor, 100% vs TankArmor, 50% vs TruckArmor, 120% vs AirplaneArmor
  - ARMOR_PIERCING: 10% vs HumanArmor, 100% vs TankArmor
  - FLAME: 150% vs HumanArmor, 25% vs TankArmor, 0% vs DragonTankArmor
  - GATTLING: 100% vs HumanArmor, 10% vs TankArmor, 120% vs AirplaneArmor
  - SNIPER: 200% vs HumanArmor, 1% vs TankArmor
  - FLESHY_SNIPER: 200% vs HumanArmor, 0% vs TankArmor
  - EXPLOSION: 100% vs HumanArmor, 100% vs TankArmor
  - JET_MISSILES: 25% vs BaseDefenseArmor, 25% vs AirplaneArmor, 30% vs AntiAirVehicle
  - STEALTHJET_MISSILES: 250% vs BaseDefenseArmor
  - COMANCHE_VULCAN: 100% vs HumanArmor, 25% vs TankArmor, 50% vs TruckArmor
  - KILL_PILOT: 0% vs HumanArmor, 100% vs TankArmor

- `GF-26006`
  URL: `https://gamefaqs.gamespot.com/pc/917865-command-and-conquer-generals-zero-hour/faqs/26006`
  Notes used:
  - "Battlemaster Tank > Crusader Tank > Scorpion Tank" (1v1: Crusader wins marginally; groups: BM wins with horde)
  - "Gattling Tanks > Quad Cannons > Avengers"
  - "Tomahawk Missile > Inferno Cannon > Rocket Buggy"
  - "1 fully upgraded Overlord can destroy 3-4 Paladins, and 3-5 Marauders (No Salvage)"
  - Helix with upgrades rated above Comanche in flexibility.
  - Marauder weapon range increased to 170 in Zero Hour, rated above Paladin.

- `CNCW-Terrorist`
  URL: `https://cnc.fandom.com/wiki/Terrorist_(Generals_1)`
  Notes used:
  - Terrorists can deal very high value trades versus vehicles.
  - One can destroy most vehicles and two can destroy an Overlord.
  - Strong splash potential, high volatility/risk profile.

- `CNCW-Overlord`
  URL: `https://cnc-central.fandom.com/wiki/Overlord_tank_(Generals_1)`
  Notes used:
  - Overlord is dominant in direct armored combat (80dmg AP every 300ms = 267 DPS).
  - Key weaknesses include aircraft, Jarmen Kell pilot-snipe, Hijacker capture, and Bomb Trucks.
  - Single rocket infantry loses 1v1 to Overlord (fast fire rate + crush); groups of 3+ overwhelm.

- `USER-REQ`
  URL: direct design input from the project owner (this chat)
  Notes used:
  - Toxin rebel variants are significantly stronger than base rebels versus vehicles.
  - Toxin rebels are extremely strong versus most infantry except Jarmen Kell and Pathfinders.
  - These rows are tagged separately so they can be reviewed independently from external citations.

## Important Caveat

These are seed values for generation-time balancing, not a claim of strict esports frame-perfect truth.
After each balance test pass, adjust:

- `unit_matchup_archetype_weights.csv` for broad system behavior
- `unit_matchup_overrides.csv` for specific unit-vs-unit corrections

Current override strategy is "citation-backed first": each explicit row in
`unit_matchup_overrides.csv` carries a `source` tag and rationale.
