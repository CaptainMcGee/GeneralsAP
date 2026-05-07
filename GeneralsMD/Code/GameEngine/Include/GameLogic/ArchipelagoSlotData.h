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
**	MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
**	GNU General Public License for more details.
**
**	You should have received a copy of the GNU General Public License
**	along with this program.  If not, see <http://www.gnu.org/licenses/>.
*/
#pragma once

#include "Lib/BaseType.h"
#include "Common/AsciiString.h"
#include "Common/Geometry.h"

#include <set>
#include <vector>

struct ArchipelagoSlotUnit
{
	AsciiString unitKey;
	AsciiString runtimeKey;
	Int apLocationId;
	AsciiString defenderTemplate;
	AsciiString displayName;

	ArchipelagoSlotUnit() : apLocationId( 0 ) {}
};

struct ArchipelagoSlotCluster
{
	AsciiString clusterKey;
	AsciiString tier;
	AsciiString clusterClass;
	AsciiString primaryRequirement;
	AsciiString requiredMissionGate;
	Coord3D center;
	Real radius;
	std::vector<ArchipelagoSlotUnit> units;

	ArchipelagoSlotCluster() : radius( 0.0f )
	{
		center.zero();
	}
};

struct ArchipelagoSlotCapturedBuilding
{
	AsciiString buildingKey;
	AsciiString runtimeKey;
	Int apLocationId;
	AsciiString label;
	AsciiString templateName;
	AsciiString authorStatus;

	ArchipelagoSlotCapturedBuilding() : apLocationId( 0 ) {}
};

struct ArchipelagoSlotSupplyPileThreshold
{
	AsciiString pileKey;
	AsciiString thresholdKey;
	AsciiString runtimeKey;
	Int apLocationId;
	AsciiString label;
	AsciiString templateName;
	AsciiString authorStatus;
	Int startingAmount;
	Int amountCollected;
	Real fractionCollected;
	Bool hasStartingAmount;
	Bool hasAmountCollected;
	Bool hasFractionCollected;

	ArchipelagoSlotSupplyPileThreshold()
		: apLocationId( 0 )
		, startingAmount( 0 )
		, amountCollected( 0 )
		, fractionCollected( 0.0f )
		, hasStartingAmount( FALSE )
		, hasAmountCollected( FALSE )
		, hasFractionCollected( FALSE )
	{
	}
};

struct ArchipelagoSlotMap
{
	AsciiString mapKey;
	AsciiString mapLeafName;
	Int mapSlot;
	AsciiString missionRuntimeKey;
	Int missionApLocationId;
	std::vector<ArchipelagoSlotCluster> clusters;
	std::vector<ArchipelagoSlotCapturedBuilding> capturedBuildings;
	std::vector<ArchipelagoSlotSupplyPileThreshold> supplyPileThresholds;

	ArchipelagoSlotMap() : mapSlot( -1 ), missionApLocationId( 0 ) {}
};

class ArchipelagoSlotData
{
public:
	ArchipelagoSlotData();

	void reset();
	Bool loadFromFile(
		const AsciiString& filePath,
		const AsciiString& expectedHash,
		Int expectedVersion,
		const AsciiString& inboundSeedId,
		const AsciiString& inboundSlotName,
		const AsciiString& inboundSessionNonce,
		AsciiString& errorMessage );

	Bool isLoaded() const { return m_loaded; }
	const AsciiString& getSeedId() const { return m_seedId; }
	const AsciiString& getSlotName() const { return m_slotName; }
	const AsciiString& getSessionNonce() const { return m_sessionNonce; }
	const AsciiString& getSlotDataPath() const { return m_slotDataPath; }
	const AsciiString& getSlotDataHash() const { return m_slotDataHash; }
	Int getVersion() const { return m_version; }
	Int getMapCount() const { return static_cast<Int>( m_maps.size() ); }
	Int getRuntimeCheckCount() const { return static_cast<Int>( m_runtimeKeys.size() ); }
	Int getFutureLocationCount() const;

	const ArchipelagoSlotMap* findMapByKey( const AsciiString& mapKey ) const;
	const ArchipelagoSlotMap* findMapByLeafName( const AsciiString& mapLeafName ) const;
	AsciiString getMissionRuntimeKeyForGeneralIndex( Int generalIndex ) const;
	Bool isSelectedRuntimeKey( const AsciiString& runtimeKey ) const;
	Bool isMissionRuntimeKey( const AsciiString& runtimeKey ) const;

	static AsciiString mapKeyForGeneralIndex( Int generalIndex );
	static AsciiString mapLeafNameForKey( const AsciiString& mapKey );
	static Bool computeFileSha256( const AsciiString& filePath, AsciiString& outHash );

private:
	Bool m_loaded;
	Int m_version;
	AsciiString m_logicModel;
	AsciiString m_seedId;
	AsciiString m_slotName;
	AsciiString m_sessionNonce;
	AsciiString m_slotDataPath;
	AsciiString m_slotDataHash;
	std::vector<ArchipelagoSlotMap> m_maps;
	std::set<AsciiString> m_runtimeKeys;
	std::set<AsciiString> m_missionRuntimeKeys;
};
