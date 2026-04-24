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

#include <istream>
#include <map>
#include <set>
#include <vector>

struct UnlockGroup
{
	AsciiString groupName;
	AsciiString displayName;
	AsciiString faction;
	std::vector<AsciiString> templates;
	Bool isBuildingGroup;
	Bool itemPool;
	Bool expandGenerals;  // if TRUE (default), unlocking auto-expands to all general variants
	std::set<AsciiString> buildingTemplateNames;  // when non-empty, per-template unit vs building
	std::set<AsciiString> upgradeTemplateNames;
	std::set<AsciiString> commandTemplateNames;
	Int importance;  // 0=buildings first, 1=units, 2=misc last. Used for sort order.
};

class UnlockRegistry
{
public:
	UnlockRegistry( void );
	~UnlockRegistry( void );

	static UnlockRegistry *getInstance( void );

	void init( void );

	const UnlockGroup *findGroupForTemplate( const AsciiString &templateName ) const;
	std::vector<AsciiString> getGroupTemplates( const AsciiString &templateName ) const;
	AsciiString getFactionForTemplate( const AsciiString &templateName ) const;

	std::vector<AsciiString> getAllTemplates( void ) const;
	/** Returns one representative template per group, in Archipelago.ini group order. Use for ap_unlock_next_group. */
	std::vector<AsciiString> getAllTemplatesInGroupOrder( void ) const;
	/** Returns number of UnlockGroups. Iterate 0..getGroupCount()-1 with getGroupAt for INI order. */
	Int getGroupCount( void ) const;
	/** Returns the UnlockGroup at index (0-based, in Archipelago.ini order). */
	const UnlockGroup *getGroupAt( Int index ) const;
	const UnlockGroup *findGroupByName( const AsciiString &groupName ) const;
	Int getItemPoolGroupCount( void ) const;
	const UnlockGroup *getItemPoolGroupAt( Int index ) const;
	Bool isBuildingTemplate( const AsciiString &templateName ) const;
	Bool isUpgradeTemplate( const AsciiString &templateName ) const;
	Bool isCommandTemplate( const AsciiString &templateName ) const;

	/** Returns TRUE if template is in AlwaysUnlocked block (unlocked from start). */
	Bool isAlwaysUnlockedTemplate( const AsciiString &templateName ) const;

	/** Starting general from ArchipelagoSettings. -1 = RANDOM, 0-8 = specific general index. */
	Int getStartingGeneralUSA( void ) const { return m_startingGeneralUSA; }
	Int getStartingGeneralChina( void ) const { return m_startingGeneralChina; }
	Int getStartingGeneralGLA( void ) const { return m_startingGeneralGLA; }

	Int calculateLocationId( Int enemyGeneralIndex, Int missionNumber ) const;

private:
	void addGroup( const UnlockGroup &group );
	void initDefaultsIfEmpty( void );
	void sortGroupsByImportance( void );
	void loadFromIni( const AsciiString &filePath );
	void loadFromFile( class File *fp );
	void loadFromStream( std::istream &in );

private:
	std::vector<UnlockGroup> m_unlockGroups;
	std::map<AsciiString, Int> m_templateToGroupIndex;
	std::map<AsciiString, Int> m_groupNameToIndex;
	std::vector<Int> m_itemPoolGroupIndices;
	std::set<AsciiString> m_buildingTemplates;
	std::set<AsciiString> m_unitTemplates;
	std::set<AsciiString> m_upgradeTemplates;
	std::set<AsciiString> m_commandTemplates;
	std::set<AsciiString> m_alwaysUnlockedUnits;
	std::set<AsciiString> m_alwaysUnlockedBuildings;
	Int m_startingGeneralUSA;   /* -1 = RANDOM, 0-2 = USA, 3-5 = China, 6-8 = GLA */
	Int m_startingGeneralChina;
	Int m_startingGeneralGLA;
};

extern UnlockRegistry *TheUnlockRegistry;
