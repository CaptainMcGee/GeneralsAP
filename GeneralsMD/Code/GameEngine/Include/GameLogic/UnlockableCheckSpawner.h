/*
**	Command & Conquer Generals Zero Hour(tm)
**	Copyright 2025 Electronic Arts Inc.
**
**	This program is free software: you can redistribute it and/or modify
**	it under the terms of the GNU General Public License as published by
**	the Free Software Foundation, either version 3 of the License, or
**	(at your option) any later version.
**
**	This program is distributed in the hope that it will be useful,
**	but WITHOUT ANY WARRANTY; without even the implied warranty of
**	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
**	GNU General Public License for more details.
**
**	You should have received a copy of the GNU General Public License
**	along with this program.  If not, see <http://www.gnu.org/licenses/>.
*/

#pragma once

#include <map>
#include <set>
#include <string>
#include <vector>

#include "Lib/BaseType.h"
#include "Common/AsciiString.h"
#include "Common/GameType.h"
#include "Common/Geometry.h"

class File;
class Object;
class Team;

/**
 * UnlockableCheckSpawner - Demo / foundation for unlockable kill checks.
 *
 * At map load, spawns units at waypoints and tags buildings with ArchipelagoCheckId
 * for a self-contained randomizer demo. Designed to expand to full Archipelago integration:
 * - Seed will come from ArchipelagoState when connected
 * - Check completion will hook into scoreTheKill
 * - Config can be extended with rewards, prerequisites, etc.
 */
class UnlockableCheckSpawner
{
public:
	UnlockableCheckSpawner();
	~UnlockableCheckSpawner();

	/** Initialize and load config. Call once at game startup. */
	void init();

	/** Run after map objects are loaded. Spawns units, tags buildings. Call from GameLogic::startNewGame. */
	void runAfterMapLoad( const AsciiString& mapName, Bool loadingSaveGame );

	/** Whether the demo spawner is enabled (config exists and was loaded). */
	Bool isEnabled() const { return m_enabled; }

	/** Damage output scalar for spawned units (1.0 = normal). Called from weapon damage path. */
	Real getDamageOutputScalar( const Object* source ) const;

	/** True if object is a spawned unit (should ignore script/mission commands). */
	Bool isSpawnedUnit( const Object* obj ) const;

	/** Guard position for spawned unit, or nullptr if not a spawned unit. Used to reject move commands that would take unit far from spawn. */
	const Coord3D* getGuardPositionForUnit( const Object* obj ) const;

	/** Max chase radius for current map (0 = no limit). Used to reject move-to-position when dest is outside radius. */
	Real getMaxChaseRadiusForCurrentMap() const { return m_currentMapMaxChaseRadius; }

	/** Defend radius for current map (0 = no limit). Spawned units must return inside before acquiring new targets. */
	Real getDefendRadiusForCurrentMap() const { return m_currentMapDefendRadius; }

	/** True if script action debug logging is enabled (for debugging triggers affecting spawned units). */
	Bool isDebugScriptActionsEnabled() const { return m_debugScriptActions; }

	/** Called each frame from GameLogic::update. Plays periodic marker FX on spawned units. */
	void update();

	/** Called from Object::scoreTheKill when local player completes a tracked Archipelago check on the current map. */
	void onArchipelagoCheckKilled( const Object* victim, Bool isNewCheck );

	/** Emit concise spawned-unit status messages for in-game debug/demo checks. */
	void reportDebugStatus( void ) const;

	/** Write detailed spawned-unit runtime state into UserData for AI/debug inspection. */
	void dumpDebugState( void ) const;

	/** Resolve the assigned reward-group display label for a tracked check ID, or empty if none is assigned. */
	AsciiString getRewardLabelForCheckId( const AsciiString &checkId ) const;

private:
	struct MapConfig
	{
		UnsignedInt configSeed;
		std::vector<AsciiString> unitWaypoints;
		std::vector<AsciiString> unitTemplates;
		std::vector<AsciiString> unitCheckIds;
		std::vector<AsciiString> unitRewardGroupIds;
		std::vector<AsciiString> buildingTemplates;
		std::vector<AsciiString> buildingCheckIds;
		std::vector<AsciiString> buildingRewardGroupIds;
		AsciiString enemyTeamName;
		Real spawnOffset;  ///< Inner ring radius from waypoint for radial placement
		Real spawnOffsetSpread;  ///< Outer ring delta for alternating wide radial placement
		Int spawnCount;  ///< Number of units to spawn (cycles through UnitCheckIds if > count)
		Real damageOutputScalar;  ///< Damage dealt multiplier for spawned units (1.0 = normal, 0.5 = half damage)
		Real defendRadius;  ///< World units - pull back when outside this radius and not attacking (0 = no limit)
		Real maxChaseRadius;  ///< World units - always pull back when outside this radius, even when attacking (0 = no limit)
		AsciiString unitMarkerFX;  ///< Optional FXList name for visual distinction (plays periodically if set)
		Bool repeatLocalRewardsForCompletedChecks;  ///< Demo-only: duplicate completed checks still replay local reward/cash without resending AP completion.

		MapConfig() :
			configSeed( 0u ),
			spawnOffset( 0.0f ),
			spawnOffsetSpread( 0.0f ),
			spawnCount( 0 ),
			damageOutputScalar( 1.0f ),
			defendRadius( 0.0f ),
			maxChaseRadius( 0.0f ),
			repeatLocalRewardsForCompletedChecks( FALSE )
		{
		}
	};

	void loadConfig();
	Bool loadConfigFromContent( const std::string& content );
	UnsignedInt hashIndex( UnsignedInt seedVal, UnsignedInt index ) const;
	void spawnUnitsForMap( const AsciiString& mapName, const MapConfig& config );
	void tagBuildingsForMap( const AsciiString& mapName, const MapConfig& config );
	Team* getEnemyTeam( const MapConfig& config ) const;
	void initializeCurrentMapTracking( const MapConfig& config );
	void syncCompletedChecksFromArchipelagoState();
	void remapCurrentMapRewardGroupsForUnlockedState();
	Bool areTrackedTemplatesUnlocked() const;
	void rebuildRuntimeStateFromLoadedObjects( const MapConfig& config );
	AsciiString getAssignedRewardGroupIdForCheck( const AsciiString &checkId ) const;

	Bool m_enabled;
	Bool m_initialized;
	Bool m_debugScriptActions;  ///< When true, log team-related script actions to debug window
	std::map<AsciiString, MapConfig> m_mapConfigs;
	std::vector<Object*> m_spawnedUnits;
	std::vector<Coord3D> m_spawnedUnitLastRevealPos;
	std::vector<Coord3D> m_spawnedUnitGuardPos;  ///< Spawn position for re-issuing guard (keeps units defending area)
	std::vector<Bool> m_spawnedUnitHasRevealed;  ///< True after first reveal (needed so we don't undo before we've revealed)
	Real m_currentMapDamageOutputScalar;  ///< Damage output scalar for current map's spawned units
	Real m_currentMapDefendRadius;  ///< Defend radius for current map (0 = no pull-back when idle)
	Real m_currentMapMaxChaseRadius;  ///< Max chase radius - always pull back when outside (0 = no limit)
	AsciiString m_currentMapUnitMarkerFX;
	Bool m_repeatLocalRewardsForCompletedChecks;
	std::vector<AsciiString> m_currentMapUnitTemplates;  ///< All tracked templates configured for current map (units + tagged buildings).
	std::set<AsciiString> m_unlockedCheckIds;  ///< Check IDs unlocked this session (by killing spawned units)
	std::vector<AsciiString> m_currentMapAllCheckIds;  ///< All check IDs for current map (unit + building checks; used for completion bonus)
	std::map<AsciiString, AsciiString> m_currentMapCheckRewardGroups;  ///< checkId -> assigned Archipelago unlock group
};

extern UnlockableCheckSpawner* TheUnlockableCheckSpawner;
