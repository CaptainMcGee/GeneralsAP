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

#include "Lib/BaseType.h"
#include "Common/AsciiString.h"
#include "Common/STLTypedefs.h"
#include "Common/SubsystemInterface.h"

#include <map>
#include <set>
#include <vector>

class ThingTemplate;

class ArchipelagoState : public SubsystemInterface
{
public:
	enum GeneralIndex
	{
		GENERAL_USA_AIRFORCE = 0,
		GENERAL_USA_LASER = 1,
		GENERAL_USA_SUPERWEAPON = 2,
		GENERAL_CHINA_TANK = 3,
		GENERAL_CHINA_INFANTRY = 4,
		GENERAL_CHINA_NUKE = 5,
		GENERAL_GLA_TOXIN = 6,
		GENERAL_GLA_DEMOLITION = 7,
		GENERAL_GLA_STEALTH = 8,
		GENERAL_COUNT = 9
	};

public:
	enum UnlockItemApplyResult
	{
		UNLOCK_ITEM_INVALID = 0,
		UNLOCK_ITEM_UNLOCKED,
		UNLOCK_ITEM_ALREADY_UNLOCKED,
		UNLOCK_ITEM_POOL_EXHAUSTED
	};

	struct UnlockItemOutcome
	{
		UnlockItemApplyResult result;
		AsciiString groupId;
		AsciiString displayName;
		AsciiString sourceTag;
		Int cashAward;
		Bool changedState;

		UnlockItemOutcome() :
			result(UNLOCK_ITEM_INVALID),
			cashAward(0),
			changedState(FALSE)
		{
		}
	};

	ArchipelagoState( void );
	virtual ~ArchipelagoState( void );

	static ArchipelagoState *getInstance( void );

	virtual void init( void );
	virtual void reset( void );
	virtual void update( void );
	void wipeProgress( void );

	Bool isUnitUnlocked( const AsciiString &templateName ) const;
	Bool isBuildingUnlocked( const AsciiString &templateName ) const;
	Bool isGroupUnlocked( const AsciiString &groupId ) const;
	Bool isGeneralUnlocked( Int generalIndex ) const;
	Bool isTemplateUnlocked( const ThingTemplate *tmpl ) const;
	Bool isAlwaysUnlocked( const AsciiString &templateName ) const;
	Int getUnlockedGroupCount( void ) const;
	Int getUnlockedItemPoolGroupCount( void ) const;
	Int getTotalItemPoolGroupCount( void ) const;
	Int getLastAppliedReceivedItemSequence( void ) const;
	Int getStartingCashBonus( void ) const;
	Real getProductionMultiplier( void ) const;
	Bool isZoomLimitDisabled( void ) const;
	AsciiString getLastUnlockGroupId( void ) const;
	AsciiString getLastUnlockSource( void ) const;
	void armMissionStartOptions( Bool loadingSaveGame );

	void unlockUnit( const AsciiString &templateName );
	void unlockBuilding( const AsciiString &templateName );
	/** Unlock all templates in group at once (one save, one notify with group name).
	 *  @return TRUE if any templates were added, FALSE if all were already unlocked. */
	Bool unlockGroup( const struct UnlockGroup *group, const char* notifySuffix = nullptr );
	UnlockItemOutcome applyUnlockGroupById( const AsciiString &groupId, const AsciiString &sourceTag, Bool notifyPlayer, const char *notifySuffix = nullptr );
	UnlockItemOutcome applyConfiguredCheckReward( const AsciiString &checkId, const AsciiString &groupId, Bool notifyPlayer );
	UnlockItemOutcome consumeLocalFallbackUnlockItem( const AsciiString &sourceTag, Bool notifyPlayer );
	void unlockGeneral( Int generalIndex );
	void unlockAll( void );

	void markLocationComplete( Int locationId );
	Bool isLocationComplete( Int locationId ) const;

	/** Grant a kill check: records check completion only. Local fallback reward simulation is handled by UnlockableCheckSpawner. */
	Bool grantCheckForKill( const AsciiString& checkId, const AsciiString& victimTemplateName, Bool isSpawnedUnitKill = FALSE );
	Bool isCheckComplete( const AsciiString& checkId ) const;

	void saveToFile( void );
	void loadFromFile( void );
	void notifyUnlock( const AsciiString &itemName );
	void dumpDebugState( void ) const;
	AsciiString getSaveFilePath( void ) const;
	AsciiString getBridgeDirectoryPath( void ) const;
	AsciiString getBridgeInboundFilePath( void ) const;
	AsciiString getBridgeOutboundFilePath( void ) const;

private:
	void ensureDefaultStartingGenerals( void );
	void initializeBridgePaths( void );
	void importBridgeState( Bool logChanges );
	void exportBridgeState( void ) const;
	void refreshUnlockedTemplateCachesFromGroups( void );
	void syncUnlockedGroupsFromCurrentState( void );
	Bool isGroupSatisfied( const struct UnlockGroup *group ) const;
	void applyGroupMembers( const struct UnlockGroup *group );
	Int countRemainingItemPoolGroups( void ) const;
	AsciiString findNextAvailableItemPoolGroup( const std::set<AsciiString> &excludedGroupIds ) const;
	Bool mergeBridgeState(
		const std::set<AsciiString> &unlockedUnits,
		const std::set<AsciiString> &unlockedBuildings,
		const std::set<AsciiString> &unlockedGroupIds,
		const std::set<Int> &unlockedGenerals,
		const std::set<Int> &startingGenerals,
		const std::set<Int> &sessionStarterGenerals,
		const std::set<Int> &completedLocations,
		const std::set<AsciiString> &completedChecks,
		Int startingCashBonus,
		Real productionMultiplier,
		Bool disableZoomLimit );

private:
	std::set<AsciiString> m_unlockedUnits;
	std::set<AsciiString> m_unlockedBuildings;
	std::set<AsciiString> m_unlockedGroupIds;
	std::set<Int> m_unlockedGenerals;
	std::set<Int> m_startingGenerals;
	std::set<Int> m_completedLocations;
	std::set<AsciiString> m_completedChecks;
	Bool m_initialized;
	AsciiString m_saveFilePath;
	AsciiString m_bridgeDirectoryPath;
	AsciiString m_bridgeInboundFilePath;
	AsciiString m_bridgeOutboundFilePath;
	UnsignedInt m_bridgePollCountdown;
	UnsignedInt m_lastImportedBridgeHash;
	Int m_lastAppliedReceivedItemSequence;
	Int m_startingCashBonus;
	Real m_productionMultiplier;
	Bool m_disableZoomLimit;
	std::set<Int> m_sessionOptionStarterGenerals;
	Bool m_appliedMissionStartOptions;
	Bool m_pendingMissionStartOptions;
	UnsignedInt m_missionStartOptionsEarliestFrame;
	UnsignedInt m_localFallbackUnlockSeed;
	Int m_localFallbackConsumedCount;
	AsciiString m_lastUnlockGroupId;
	AsciiString m_lastUnlockSource;
};

extern ArchipelagoState *TheArchipelagoState;
