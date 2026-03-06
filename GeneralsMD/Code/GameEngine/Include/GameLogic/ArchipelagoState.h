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
	ArchipelagoState( void );
	virtual ~ArchipelagoState( void );

	static ArchipelagoState *getInstance( void );

	virtual void init( void );
	virtual void reset( void );
	virtual void update( void );
	void wipeProgress( void );

	Bool isUnitUnlocked( const AsciiString &templateName ) const;
	Bool isBuildingUnlocked( const AsciiString &templateName ) const;
	Bool isGeneralUnlocked( Int generalIndex ) const;
	Bool isTemplateUnlocked( const ThingTemplate *tmpl ) const;
	Bool isAlwaysUnlocked( const AsciiString &templateName ) const;

	void unlockUnit( const AsciiString &templateName );
	void unlockBuilding( const AsciiString &templateName );
	/** Unlock all templates in group at once (one save, one notify with group name).
	 *  @return TRUE if any templates were added, FALSE if all were already unlocked. */
	Bool unlockGroup( const struct UnlockGroup *group, const char* notifySuffix = nullptr );
	void unlockGeneral( Int generalIndex );
	void unlockAll( void );

	void markLocationComplete( Int locationId );
	Bool isLocationComplete( Int locationId ) const;

	/** Grant a kill check: unlock the victim template's group. Used when player destroys a unit with ArchipelagoCheckId.
	 *  isSpawnedUnitKill: when true, notify message includes " (+$5000)" and is the single source of the unlock message. */
	void grantCheckForKill( const AsciiString& checkId, const AsciiString& victimTemplateName, Bool isSpawnedUnitKill = FALSE );
	Bool isCheckComplete( const AsciiString& checkId ) const;

	void saveToFile( void );
	void loadFromFile( void );
	void notifyUnlock( const AsciiString &itemName );
	AsciiString getSaveFilePath( void ) const;

private:
	void ensureDefaultStartingGenerals( void );

private:
	std::set<AsciiString> m_unlockedUnits;
	std::set<AsciiString> m_unlockedBuildings;
	std::set<Int> m_unlockedGenerals;
	std::set<Int> m_startingGenerals;
	std::set<Int> m_completedLocations;
	std::set<AsciiString> m_completedChecks;
	Bool m_initialized;
	AsciiString m_saveFilePath;
};

extern ArchipelagoState *TheArchipelagoState;
