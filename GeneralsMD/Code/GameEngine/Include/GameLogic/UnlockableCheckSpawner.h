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
#include "Common/DisabledTypes.h"
#include "Common/GameCommon.h"
#include "Common/GameType.h"
#include "Common/Geometry.h"
#include "GameLogic/Damage.h"

class File;
class Object;
class Team;
class SimpleObjectIterator;
struct ArchipelagoSlotMap;

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

	/** True if the spawned unit is in forced retreat back to guard position (exceeded MaxChaseRadius). */
	Bool isSpawnedUnitInForcedRetreat( const Object* obj ) const;

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

	/** Destroy and respawn the current map's spawned units using the same checks/rewards but a new deterministic seed. */
	Bool rerollCurrentMapSpawns( void );

	/** Resolve the assigned reward-group display label for a tracked check ID, or empty if none is assigned. */
	AsciiString getRewardLabelForCheckId( const AsciiString &checkId ) const;

	/** True if the target is a spawned cluster unit eligible for protection checks. */
	Bool isSpawnedUnitProtectionTarget( const Object* obj ) const;

	/** Apply protection rules to incoming damage for spawned cluster units. Returns TRUE if damage was fully blocked. */
	Bool applyProtectionToDamage( Object* target, DamageInfo* damageInfo );

	/** True if the target is immune to the requested protection action. */
	Bool isProtectionActionImmune(
		const Object* target,
		const char* actionTypeLabel,
		const Object* source = nullptr,
		const AsciiString* sourceWeaponName = nullptr,
		const AsciiString* sourceSpecialPowerName = nullptr,
		const char* disabledTypeLabel = nullptr,
		const char* damageTypeLabel = nullptr );

	/** True if the target is immune to the specified disabled type. */
	Bool isProtectionDisabledTypeImmune( const Object* target, DisabledType type );

	/** Mark a spawned unit as provoked so temporary anti-kite vision can be applied. */
	void markSpawnedUnitProvoked( const Object* obj, UnsignedInt durationFrames = 0u );

	/** Baseline (vanilla) max HP cached at spawn for a spawned unit, or 0 if not found. */
	Real getBaselineMaxHPForUnit( const Object* obj ) const;

	/** Build a human-readable producer chain summary for the given source object. */
	AsciiString buildProducerChainSummary( const Object* source ) const;

	/**
	 * Begin a pending damage trace for a spawned unit hit entering through Object::attemptDamage.
	 * Must be paired with finalizeSpawnedDamageTrace or cancelPendingTrace.
	 */
	void beginSpawnedDamageTrace( const Object* target, const Object* source, const DamageInfo* damageInfo );

	/** Record protection result into the pending trace after applyProtectionToDamage returns. */
	void recordPendingTraceProtectionResult( Bool matched, const AsciiString& matchedLabel, Real multiplier, Real damageAfterProtection );

	/** Finalize the pending trace with post-armor results and record to the ring buffer. */
	void finalizeSpawnedDamageTrace( Real actualDamageDealt, Real hpBefore, Real hpAfter, Real currentMaxHP );

	/** Record a bypassed-filter damage trace (hit that skipped Object::attemptDamage). */
	void recordBypassedSpawnedDamageTrace( const Object* target, const DamageInfo* damageInfo,
		Real actualDamageDealt, Real hpBefore, Real hpAfter, Real currentMaxHP );

	/** Cancel a pending trace without recording (e.g., if target turned out not to be spawned). */
	void cancelPendingTrace();

	/** True if a pending trace is active. */
	Bool isPendingTraceActive() const { return m_pendingTraceActive; }

	/** True if the spawner is currently issuing a command (CMD_FROM_SCRIPT) to one of its units.
	 *  Used by isAllowedToRespondToAiCommands to distinguish spawner commands from map scripts. */
	Bool isSpawnerCommandInProgress() const { return m_spawnerCommandInProgress; }

private:
	enum ProtectionMatchKind
	{
		PROTECTION_MATCH_SPECIAL_POWER = 0,
		PROTECTION_MATCH_WEAPON,
		PROTECTION_MATCH_OBJECT,
		PROTECTION_MATCH_DAMAGE_TYPE,
		PROTECTION_MATCH_DISABLED_TYPE,
		PROTECTION_MATCH_ACTION_TYPE,
		PROTECTION_MATCH_COUNT
	};

	enum ProtectionEffectKind
	{
		PROTECTION_EFFECT_DAMAGE_MULTIPLIER = 0,
		PROTECTION_EFFECT_IMMUNITY
	};

	struct ProtectionRule
	{
		AsciiString bucket;
		AsciiString playerName;
		AsciiString playerCategory;
		AsciiString notes;
		std::vector<AsciiString> internalLabels;
		ProtectionMatchKind matchKind;
		ProtectionEffectKind effectKind;
		Real damageMultiplier;

		ProtectionRule()
			: matchKind( PROTECTION_MATCH_OBJECT )
			, effectKind( PROTECTION_EFFECT_DAMAGE_MULTIPLIER )
			, damageMultiplier( 1.0f )
		{
		}
	};

	struct ProtectionEvent
	{
		UnsignedInt frame;
		UnsignedInt targetId;
		AsciiString targetTemplate;
		AsciiString sourceTemplate;
		AsciiString sourceWeaponName;
		AsciiString sourceSpecialPowerName;
		AsciiString damageTypeLabel;
		AsciiString playerName;
		AsciiString matchedLabel;
		AsciiString effectLabel;
		Real damageMultiplier;
		Real incomingDamageAmount;
		Real appliedDamageAmount;

		ProtectionEvent()
			: frame( 0u )
			, targetId( 0u )
			, damageMultiplier( 1.0f )
			, incomingDamageAmount( 0.0f )
			, appliedDamageAmount( 0.0f )
		{
		}
	};

	struct SpawnedDamageTraceEvent
	{
		UnsignedInt frame;
		ObjectID targetId;
		AsciiString targetTemplate;
		AsciiString targetCheckId;
		AsciiString targetClusterId;
		AsciiString sourceTemplate;
		AsciiString sourceWeaponName;
		AsciiString sourceSpecialPowerName;
		AsciiString producerChainSummary;
		AsciiString damageTypeLabel;
		Real incomingDamageBeforeProtection;
		Real damageAfterProtectionScaling;
		Real actualDamageDealt;
		Real hpBefore;
		Real hpAfter;
		Real currentMaxHP;
		Real baselineMaxHP;
		Bool enteredThroughObjectAttemptDamage;
		Bool protectionRuleMatched;
		AsciiString protectionMatchedLabel;
		Real protectionMultiplierApplied;
		Bool bypassedObjectFilter;

		SpawnedDamageTraceEvent()
			: frame( 0u )
			, targetId( INVALID_ID )
			, incomingDamageBeforeProtection( 0.0f )
			, damageAfterProtectionScaling( 0.0f )
			, actualDamageDealt( 0.0f )
			, hpBefore( 0.0f )
			, hpAfter( 0.0f )
			, currentMaxHP( 0.0f )
			, baselineMaxHP( 0.0f )
			, enteredThroughObjectAttemptDamage( FALSE )
			, protectionRuleMatched( FALSE )
			, protectionMultiplierApplied( 1.0f )
			, bypassedObjectFilter( FALSE )
		{
		}
	};

	struct MapConfig
	{
		UnsignedInt configSeed;
		std::vector<AsciiString> unitWaypoints;
		std::vector<AsciiString> unitTemplates;
		std::vector<AsciiString> unitCheckIds;
		std::vector<AsciiString> unitRewardGroupIds;
		std::vector<AsciiString> unitClusterIds;
		std::vector<AsciiString> clusterIds;
		std::vector<AsciiString> clusterTiers;
		std::vector<AsciiString> clusterWaypoints;
		std::vector<Real> clusterAngles;
		std::vector<Real> clusterRadii;
		std::vector<Real> clusterSpreads;
		std::vector<Real> clusterCenterReservedRadii;
		std::vector<Coord3D> clusterCenters;
		std::vector<Bool> clusterHasAbsoluteCenters;
		std::vector<AsciiString> easyUnitTemplates;
		std::vector<AsciiString> mediumUnitTemplates;
		std::vector<AsciiString> hardUnitTemplates;
		std::vector<Real> easyUnitWeights;
		std::vector<Real> mediumUnitWeights;
		std::vector<Real> hardUnitWeights;
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
		Bool usesSlotData;  ///< TRUE when map config came from verified Seed-Slot-Data.json.

		MapConfig() :
			configSeed( 0u ),
			spawnOffset( 0.0f ),
			spawnOffsetSpread( 0.0f ),
			spawnCount( 0 ),
			damageOutputScalar( 1.0f ),
			defendRadius( 0.0f ),
			maxChaseRadius( 0.0f ),
			repeatLocalRewardsForCompletedChecks( FALSE ),
			usesSlotData( FALSE )
		{
		}
	};

	void loadConfig();
	Bool loadConfigFromContent( const std::string& content );
	Bool buildSlotDataConfigForMap( const AsciiString& mapLeafName, MapConfig& outConfig ) const;
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
	void loadProtectionConfig();
	Bool loadProtectionConfigFromContent( const std::string& content );
	Bool resolveProtectionRule( const ProtectionRule& rule, std::vector<AsciiString>& unresolved ) const;
	Bool resolveProtectionInternalLabel( ProtectionMatchKind matchKind, const AsciiString& label ) const;
	void resetProtectionRegistry();
	void appendDerivedSpecialPowerLabels( const AsciiString& label, std::vector<AsciiString>& labels ) const;
	void appendDerivedSourceLabels( const Object* source, std::vector<AsciiString>& objectLabels, std::vector<AsciiString>& specialPowerLabels ) const;
	AsciiString getDamageTypeLabel( DamageType type ) const;
	AsciiString getDisabledTypeLabel( DisabledType type ) const;
	Bool evaluateProtectionRuleMatch(
		const ProtectionRule& rule,
		const std::vector<AsciiString>& objectLabels,
		const std::vector<AsciiString>& weaponLabels,
		const std::vector<AsciiString>& specialPowerLabels,
		const AsciiString& damageTypeLabel,
		const AsciiString& disabledTypeLabel,
		const AsciiString& actionTypeLabel,
		AsciiString& matchedLabel ) const;
	void recordProtectionEvent(
		const Object* target,
		const Object* source,
		const ProtectionRule& rule,
		const AsciiString& matchedLabel,
		const char* effectLabel,
		Real damageMultiplier,
		const AsciiString& damageTypeLabel,
		Real incomingDamageAmount,
		Real appliedDamageAmount,
		const AsciiString& sourceWeaponName,
		const AsciiString& sourceSpecialPowerName );
	void recordUnmatchedProtectionEvent(
		const Object* target,
		const Object* source,
		const AsciiString& damageTypeLabel,
		Real incomingDamageAmount,
		const AsciiString& sourceWeaponName,
		const AsciiString& sourceSpecialPowerName );
	void recordSpawnedDamageEvent( const SpawnedDamageTraceEvent& evt );
	void trimSpawnedDamageEvents();
	void trimProtectionEvents();
	AsciiString pickWeightedClusterTemplate( const MapConfig& config, const AsciiString& clusterTier, UnsignedInt hashVal ) const;
	Int findConfiguredClusterIndex( const MapConfig& config, const AsciiString& clusterId ) const;
	Int findSpawnedUnitIndex( const Object* obj ) const;
	Bool isSpawnedUnitTemporarilyAlerted( const Object* obj ) const;
	Bool isClusterTemporarilyAlerted( const AsciiString& clusterId ) const;
	void updateClusterAlertState( UnsignedInt frame );
	void applyRetreatSpeedBoost( Object* obj, size_t index );
	void restoreRetreatSpeedBoost( Object* obj, size_t index );
	void applyRetreatRepair( Object* obj ) const;
	void triggerClusterRetreat( const AsciiString& clusterId );
	Bool canSpawnedUnitFireAtTarget( const Object* obj, const Object* target ) const;
	GuardMode getGuardModeForUnit( const Object* obj ) const;
	Bool isSafeSupportAttackTarget( const Object* source, const Object* target, const AsciiString& canonicalTemplateName ) const;
	Object* findNearestEnemyInfantryForCrusher( Object* obj, Real maxRange ) const;
	Object* findNearestEnemyCombatTarget( Object* obj, Real maxRange, Bool allowStructures ) const;
	AsciiString getCanonicalSpawnTemplateName( const AsciiString& templateName ) const;
	Bool isCrusherChaseTemplate( const AsciiString& canonicalTemplateName ) const;
	Bool isSupportAttackTemplate( const AsciiString& canonicalTemplateName ) const;
	Bool isArtillerySupportTemplate( const AsciiString& canonicalTemplateName ) const;
	Team* getOrCreateClusterTeam( const AsciiString& clusterId, Team* fallbackTeam );
	Bool resolveTrackableSpawnPosition( Object* obj,
		const Coord3D& anchorPos,
		const Coord3D& desiredPos,
		Real minSeparation,
		Real minAnchorDistance,
		Real maxAnchorDistance,
		Coord3D* resolvedPos,
		const std::vector<Coord3D>* additionalOccupiedPositions = NULL ) const;
	void clearSpawnedUnitsOnly( void );

	Bool m_enabled;
	Bool m_initialized;
	Bool m_debugScriptActions;  ///< When true, log team-related script actions to debug window
	Bool m_protectionRegistryLoaded;
	Bool m_protectionRegistryValid;
	std::map<AsciiString, MapConfig> m_mapConfigs;
	std::vector<ProtectionRule> m_protectionRules;
	std::vector<AsciiString> m_protectionUnresolvedLabels;
	std::vector<ProtectionEvent> m_recentProtectionEvents;
	std::vector<SpawnedDamageTraceEvent> m_recentSpawnedDamageEvents;
	SpawnedDamageTraceEvent m_pendingTraceEvent;  ///< Staging area populated by Object::attemptDamage, finalized by ActiveBody.
	Bool m_pendingTraceActive;  ///< TRUE between beginSpawnedDamageTrace and finalize/cancel.
	Bool m_spawnerCommandInProgress;  ///< TRUE while the spawner is issuing its own CMD_FROM_SCRIPT commands.
	std::vector<Object*> m_spawnedUnits;
	std::vector<Coord3D> m_spawnedUnitLastRevealPos;
	std::vector<Coord3D> m_spawnedUnitGuardPos;  ///< Spawn position for re-issuing guard (keeps units defending area)
	std::vector<AsciiString> m_spawnedUnitClusterIds;  ///< Cluster assignment for designer-facing grouping/debug.
	std::vector<Bool> m_spawnedUnitHasRevealed;  ///< True after first reveal (needed so we don't undo before we've revealed)
	std::vector<Real> m_spawnedUnitBaseVisionRanges;  ///< Original unit vision range before temporary anti-kite adjustments.
	std::vector<Real> m_spawnedUnitBaselineMaxHP;  ///< Vanilla baseline max HP cached at spawn finalization for trace reporting.
	std::vector<UnsignedInt> m_spawnedUnitLastObservedDamageFrames;  ///< Last observed body-damage timestamp so alerts only react to new hits.
	std::vector<UnsignedInt> m_spawnedUnitAlertUntilFrames;  ///< Absolute frame until temporary anti-kite alert remains active for this unit.
	std::vector<Bool> m_spawnedUnitRetreatActive;  ///< True while unit is in forced retreat back to guard position.
	std::vector<UnsignedInt> m_spawnedUnitRetreatCooldownUntil;  ///< Absolute frame until post-retreat cooldown expires (blocks cluster target propagation).
	std::vector<UnsignedInt> m_spawnedUnitLastAggroCommandFrames;  ///< Last frame a scripted aggro command was issued for this spawned unit.
	std::vector<ObjectID> m_spawnedUnitLastAggroTargetIds;  ///< Last target object ID used for scripted aggro command throttling.
	std::vector<ObjectID> m_spawnedUnitRetaliationTargetIds;  ///< Per-unit retaliation target (INVALID_ID = not retaliating).
	Real m_currentMapDamageOutputScalar;  ///< Damage output scalar for current map's spawned units
	Real m_currentMapDefendRadius;  ///< Defend radius for current map (0 = no pull-back when idle)
	Real m_currentMapMaxChaseRadius;  ///< Max chase radius - always pull back when outside (0 = no limit)
	AsciiString m_currentMapUnitMarkerFX;
	Bool m_repeatLocalRewardsForCompletedChecks;
	Bool m_currentMapUsesSlotData;
	std::vector<AsciiString> m_currentMapUnitTemplates;  ///< All tracked templates configured for current map (units + tagged buildings).
	std::set<AsciiString> m_unlockedCheckIds;  ///< Check IDs unlocked this session (by killing spawned units)
	std::vector<AsciiString> m_currentMapAllCheckIds;  ///< All check IDs for current map (unit + building checks; used for completion bonus)
	std::map<AsciiString, AsciiString> m_currentMapCheckRewardGroups;  ///< checkId -> assigned Archipelago unlock group
	std::map<AsciiString, UnsignedInt> m_clusterAlertUntilFrames;  ///< clusterId -> alert expiration frame
	std::map<AsciiString, Coord3D> m_clusterAlertThreatPositions;  ///< clusterId -> last observed threat position
	std::map<AsciiString, ObjectID> m_clusterRetaliationTargetIds;  ///< clusterId -> ObjectID of attacker being retaliated against by entire cluster
	std::map<AsciiString, TeamID> m_clusterTeamIds;  ///< clusterId -> dedicated spawned-cluster team
	AsciiString m_currentMapLeafName;
	MapConfig m_currentMapConfig;
	Bool m_hasCurrentMapConfig;
	UnsignedInt m_currentMapRerollCount;
	MapConfig m_pendingRerollConfig;
	Bool m_hasPendingReroll;
	UnsignedInt m_pendingRerollSpawnFrame;
};

extern UnlockableCheckSpawner* TheUnlockableCheckSpawner;
