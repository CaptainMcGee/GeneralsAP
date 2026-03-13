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

#include "PreRTS.h"

#include <algorithm>
#include <cmath>
#include <fstream>
#include <sstream>

#include "Common/FileSystem.h"
#include "Common/GlobalData.h"
#include "Common/GameMemory.h"
#include "Common/Player.h"
#include "Common/RandomValue.h"
#include "Common/PlayerList.h"
#include "Common/UnicodeString.h"
#include "Common/Team.h"
#include "Common/ThingFactory.h"
#include "Common/ThingTemplate.h"
#include "Common/Upgrade.h"

#include "GameClient/CampaignManager.h"
#include "GameClient/InGameUI.h"

#include "Common/Radar.h"

#include "GameLogic/AI.h"
#include "GameLogic/AIPathfind.h"
#include "GameLogic/Module/AIUpdate.h"
#include "GameLogic/Locomotor.h"
#include "GameLogic/GameLogic.h"
#include "GameLogic/Object.h"
#include "GameLogic/Module/BehaviorModule.h"
#include "GameLogic/Module/CreateModule.h"
#include "GameLogic/Module/PhysicsUpdate.h"
#include "GameLogic/PartitionManager.h"
#include "GameLogic/UnlockRegistry.h"
#include "GameLogic/UnlockableCheckSpawner.h"
#include "GameLogic/ArchipelagoState.h"
#include "GameLogic/TerrainLogic.h"
#include "GameLogic/Module/BodyModule.h"
#include "GameLogic/ExperienceTracker.h"
#include "GameLogic/Weapon.h"

#include "GameClient/Drawable.h"

// ------------------------------------------------------------------------------------------------
UnlockableCheckSpawner* TheUnlockableCheckSpawner = nullptr;

// Spawned unit sight/leash tuning for demo validation. Units keep a short default response range,
// but briefly get a larger acquisition window after taking damage so long-range potshots still
// provoke a reaction without letting the unit wander indefinitely.
static const Real kSpawnedUnitMinVisionRange = 200.0f;
static const Real kSpawnedUnitThreatResponseVisionRange = 500.0f;
static const UnsignedInt kSpawnedUnitThreatResponseFrames = LOGICFRAMES_PER_SECOND;
static const Real kSpawnedUnitRetreatSpeedScalar = 2.0f;
static const Real kSpawnedUnitRetreatRepairPercentPerSecond = 0.05f;
static const Real kSpawnedUnitRetreatAssistScalar = 1.05f;
static const Real kSpawnedUnitRetreatAssistMinSpeed = 20.0f;
static const UnsignedInt kSpawnedUnitRetreatDragDelayFrames = LOGICFRAMES_PER_SECOND;
static const Real kSpawnedUnitRetreatFacingDotThreshold = 0.80f;
static const Real kSpawnedUnitRetreatCompletionRadius = 150.0f;
static const char* kNoUpgradeRewardGroupId = "__no_upgrade__";
static const Real kSpawnedUnitSpawnSearchStep = 35.0f;
static const Int kSpawnedUnitSpawnSearchRings = 14;
static const Int kSpawnedUnitSpawnSearchSamples = 20;
static const Real kSpawnedClusterLocalMinRadiusScalar = 0.12f;
static const Real kSpawnedClusterLocalMaxRadiusScalar = 0.70f;
static const Real kSpawnedClusterLocalAngleJitter = 0.22f;
static const Real kSpawnedClusterGoldenAngle = 2.39996322973f;
static const Real kSpawnedUnitPlacementZBias = 1.50f;
static const Real kSpawnedUnitPlacementTerrainDeltaTolerance = 6.0f;
static const Real kClusterCenterSearchStep = 18.0f;
static const Int kClusterCenterSearchRings = 5;
static const Int kClusterCenterSearchSamples = 12;
static const Real kClusterFallbackMinSeparationScalar = 0.75f;
static const Real kClusterCenterTerrainFlatnessTolerance = 10.0f;
static const Real kClusterCenterSampleRadiusScalar = 0.55f;
static const UnsignedInt kSpawnedUnitRerollRespawnDelayFrames = LOGICFRAMES_PER_SECOND / 2;
static const UnsignedInt kSpawnedUnitAggroCommandThrottleFrames = LOGICFRAMES_PER_SECOND * 3;

// Spawned unit AI (future): Reduce exploitable behavior (pathing, idle, kiting). Use
// TheUnlockableCheckSpawner->isSpawnedUnit(obj) in AIUpdate or behavior modules to apply
// dedicated rules (e.g. defend radius, chase limits already exist here; consider tighter
// leash, no idle wander, or attack-move toward last known threat).

static void appendUniqueAsciiStrings( std::vector<AsciiString>& out, const std::vector<AsciiString>& in )
{
	for ( size_t i = 0; i < in.size(); ++i )
	{
		if ( std::find( out.begin(), out.end(), in[i] ) == out.end() )
			out.push_back( in[i] );
	}
}

static AsciiString getMapLeafName( const AsciiString& mapName )
{
	AsciiString leafName = mapName;
	const char* lastBack = strrchr( mapName.str(), '\\' );
	const char* lastFwd = strrchr( mapName.str(), '/' );
	const char* lastSep = lastBack;
	if ( !lastSep || ( lastFwd && lastFwd > lastSep ) )
		lastSep = lastFwd;
	if ( lastSep && lastSep[1] )
		leafName = lastSep + 1;

	Int len = leafName.getLength();
	if ( len > 4 && strcmp( leafName.str() + len - 4, ".map" ) == 0 )
	{
		char buf[256];
		strncpy( buf, leafName.str(), (size_t)( len - 4 ) );
		buf[len - 4] = '\0';
		leafName = buf;
	}
	return leafName;
}

static void writeEscapedJsonString( std::ofstream& file, const char* text )
{
	if ( text == NULL )
		return;

	for ( const char* cur = text; *cur != '\0'; ++cur )
	{
		switch ( *cur )
		{
			case '\\':
				file << "\\\\";
				break;
			case '"':
				file << "\\\"";
				break;
			case '\n':
				file << "\\n";
				break;
			case '\r':
				file << "\\r";
				break;
			case '\t':
				file << "\\t";
				break;
			default:
				file << *cur;
				break;
		}
	}
}

// ------------------------------------------------------------------------------------------------
UnlockableCheckSpawner::UnlockableCheckSpawner()
	: m_enabled( FALSE )
	, m_initialized( FALSE )
	, m_debugScriptActions( FALSE )
	, m_repeatLocalRewardsForCompletedChecks( FALSE )
	, m_hasCurrentMapConfig( FALSE )
	, m_currentMapRerollCount( 0u )
	, m_hasPendingReroll( FALSE )
	, m_pendingRerollSpawnFrame( 0u )
{
}

// ------------------------------------------------------------------------------------------------
UnlockableCheckSpawner::~UnlockableCheckSpawner()
{
}

// ------------------------------------------------------------------------------------------------
void UnlockableCheckSpawner::init()
{
	if ( m_initialized )
		return;
	m_initialized = TRUE;
	loadConfig();
}

// ------------------------------------------------------------------------------------------------
static void trimString( std::string& s )
{
	size_t start = s.find_first_not_of( " \t\r\n" );
	if ( start == std::string::npos )
	{
		s.clear();
		return;
	}
	size_t end = s.find_last_not_of( " \t\r\n" );
	s = s.substr( start, end - start + 1 );
}

static void parseCommaList( const std::string& value, std::vector<AsciiString>& out )
{
	out.clear();
	std::string s = value;
	size_t pos = 0;
	while ( pos < s.length() )
	{
		size_t comma = s.find( ',', pos );
		std::string token = ( comma == std::string::npos ) ? s.substr( pos ) : s.substr( pos, comma - pos );
		trimString( token );
		if ( !token.empty() )
			out.push_back( AsciiString( token.c_str() ) );
		if ( comma == std::string::npos )
			break;
		pos = comma + 1;
	}
}

static void parseCommaRealList( const std::string& value, std::vector<Real>& out )
{
	out.clear();
	std::string s = value;
	size_t pos = 0;
	while ( pos < s.length() )
	{
		size_t comma = s.find( ',', pos );
		std::string token = ( comma == std::string::npos ) ? s.substr( pos ) : s.substr( pos, comma - pos );
		trimString( token );
		if ( !token.empty() )
			out.push_back( (Real)atof( token.c_str() ) );
		if ( comma == std::string::npos )
			break;
		pos = comma + 1;
	}
}

// ------------------------------------------------------------------------------------------------
Bool UnlockableCheckSpawner::loadConfigFromContent( const std::string& content )
{
	AsciiString currentMap;
	MapConfig currentConfig;
	currentConfig.configSeed = 42;
	currentConfig.enemyTeamName = "teamplayer1";
	currentConfig.spawnOffset = 600.0f;
	currentConfig.spawnOffsetSpread = 200.0f;
	currentConfig.spawnCount = 0;  // 0 = use unitCheckIds.size()
	currentConfig.damageOutputScalar = 1.0f;
	currentConfig.defendRadius = 350.0f;
	currentConfig.maxChaseRadius = 500.0f;

	std::istringstream ss( content );
	std::string line;
	while ( std::getline( ss, line ) )
	{
		size_t hashPos = line.find( '#' );
		if ( hashPos != std::string::npos )
			line = line.substr( 0, hashPos );
		trimString( line );
		if ( line.empty() )
			continue;

		if ( line.length() >= 2 && line[0] == '[' && line[line.length() - 1] == ']' )
		{
			if ( !currentMap.isEmpty() && ( !currentConfig.unitWaypoints.empty() || !currentConfig.buildingTemplates.empty() ) )
				m_mapConfigs[currentMap] = currentConfig;
			std::string mapNameStr = line.substr( 1, line.length() - 2 );
			trimString( mapNameStr );
			currentMap = AsciiString( mapNameStr.c_str() );
			currentConfig = MapConfig();
			if ( currentMap == AsciiString( "Debug" ) )
				currentMap = AsciiString( "_debug" );  // Don't add as real map
			currentConfig.configSeed = 42;
			currentConfig.enemyTeamName = "teamplayer1";
			currentConfig.spawnOffset = 600.0f;
			currentConfig.spawnOffsetSpread = 200.0f;
			currentConfig.spawnCount = 0;
			currentConfig.damageOutputScalar = 1.0f;
	currentConfig.defendRadius = 350.0f;
	currentConfig.maxChaseRadius = 500.0f;
			continue;
		}

		size_t eq = line.find( '=' );
		if ( eq == std::string::npos )
			continue;

		std::string key = line.substr( 0, eq );
		std::string value = line.substr( eq + 1 );
		trimString( key );
		trimString( value );

		if ( key == "Seed" )
		{
			currentConfig.configSeed = (UnsignedInt)atoi( value.c_str() );
			if ( currentConfig.configSeed == 0 && value != "0" )
				currentConfig.configSeed = 42;
		}
		else if ( key == "UnitWaypoints" )
			parseCommaList( value, currentConfig.unitWaypoints );
		else if ( key == "UnitTemplates" )
			parseCommaList( value, currentConfig.unitTemplates );
		else if ( key == "UnitCheckIds" )
			parseCommaList( value, currentConfig.unitCheckIds );
		else if ( key == "UnitRewardGroups" )
			parseCommaList( value, currentConfig.unitRewardGroupIds );
		else if ( key == "UnitClusterIds" )
			parseCommaList( value, currentConfig.unitClusterIds );
		else if ( key == "ClusterIds" )
			parseCommaList( value, currentConfig.clusterIds );
		else if ( key == "ClusterTiers" )
			parseCommaList( value, currentConfig.clusterTiers );
		else if ( key == "ClusterWaypoints" )
			parseCommaList( value, currentConfig.clusterWaypoints );
		else if ( key == "ClusterAngles" )
			parseCommaRealList( value, currentConfig.clusterAngles );
		else if ( key == "ClusterRadii" )
			parseCommaRealList( value, currentConfig.clusterRadii );
		else if ( key == "ClusterSpreads" )
			parseCommaRealList( value, currentConfig.clusterSpreads );
		else if ( key == "ClusterCenterReservedRadii" )
			parseCommaRealList( value, currentConfig.clusterCenterReservedRadii );
		else if ( key == "EasyUnitTemplates" )
			parseCommaList( value, currentConfig.easyUnitTemplates );
		else if ( key == "MediumUnitTemplates" )
			parseCommaList( value, currentConfig.mediumUnitTemplates );
		else if ( key == "HardUnitTemplates" )
			parseCommaList( value, currentConfig.hardUnitTemplates );
		else if ( key == "EasyUnitWeights" )
			parseCommaRealList( value, currentConfig.easyUnitWeights );
		else if ( key == "MediumUnitWeights" )
			parseCommaRealList( value, currentConfig.mediumUnitWeights );
		else if ( key == "HardUnitWeights" )
			parseCommaRealList( value, currentConfig.hardUnitWeights );
		else if ( key == "BuildingTemplates" )
			parseCommaList( value, currentConfig.buildingTemplates );
		else if ( key == "BuildingCheckIds" )
			parseCommaList( value, currentConfig.buildingCheckIds );
		else if ( key == "BuildingRewardGroups" )
			parseCommaList( value, currentConfig.buildingRewardGroupIds );
		else if ( key == "EnemyTeam" )
			currentConfig.enemyTeamName = AsciiString( value.c_str() );
		else if ( key == "SpawnOffset" )
			currentConfig.spawnOffset = (Real)atof( value.c_str() );
		else if ( key == "SpawnOffsetSpread" )
			currentConfig.spawnOffsetSpread = (Real)atof( value.c_str() );
		else if ( key == "SpawnCount" )
			currentConfig.spawnCount = (Int)atoi( value.c_str() );
		else if ( key == "DamageOutputScalar" )
			currentConfig.damageOutputScalar = (Real)atof( value.c_str() );
		else if ( key == "DefendRadius" )
			currentConfig.defendRadius = (Real)atof( value.c_str() );
		else if ( key == "MaxChaseRadius" )
			currentConfig.maxChaseRadius = (Real)atof( value.c_str() );
		else if ( key == "UnitMarkerFX" )
			currentConfig.unitMarkerFX = AsciiString( value.c_str() );
		else if ( key == "RepeatLocalRewardsForCompletedChecks" )
			currentConfig.repeatLocalRewardsForCompletedChecks = ( value == "Yes" || value == "yes" || value == "1" || value == "true" );
		else if ( currentMap == AsciiString( "_debug" ) && key == "DebugScriptActions" )
			m_debugScriptActions = ( value == "Yes" || value == "yes" || value == "1" || value == "true" );
	}

	if ( !currentMap.isEmpty() && ( !currentConfig.unitWaypoints.empty() || !currentConfig.buildingTemplates.empty() ) )
		m_mapConfigs[currentMap] = currentConfig;

	return !m_mapConfigs.empty();
}

// ------------------------------------------------------------------------------------------------
void UnlockableCheckSpawner::loadConfig()
{
	m_mapConfigs.clear();
	m_enabled = FALSE;

	// Try FileSystem first (resolves via game data root / BIG files)
	if ( TheFileSystem )
	{
		File* fp = TheFileSystem->openFile( "Data\\INI\\UnlockableChecksDemo.ini", File::READ | File::TEXT );
		if ( fp )
		{
			Int fileSize = static_cast<Int>( fp->size() );
			if ( fileSize > 0 )
			{
				char* buf = fp->readEntireAndClose();
				if ( buf )
				{
					std::string content( buf, static_cast<size_t>( fileSize ) );
					delete[] buf;
					if ( loadConfigFromContent( content ) )
					{
						m_enabled = TRUE;
						DEBUG_LOG( ( "UnlockableCheckSpawner: loaded config for %d maps (via FileSystem)", (Int)m_mapConfigs.size() ) );
						return;
					}
				}
			}
		}
	}

	// Fallback: try UserData and paths relative to working directory (like UnlockRegistry)
	if ( !m_enabled && TheGlobalData )
	{
		AsciiString userIni = TheGlobalData->getPath_UserData();
		userIni.concat( "INI\\UnlockableChecksDemo.ini" );
		std::ifstream file( userIni.str() );
		if ( file.is_open() )
		{
			std::string content( (std::istreambuf_iterator<char>( file )), std::istreambuf_iterator<char>() );
			file.close();
			if ( !content.empty() && loadConfigFromContent( content ) )
			{
				m_enabled = TRUE;
				DEBUG_LOG( ( "UnlockableCheckSpawner: loaded config from %s", userIni.str() ) );
				return;
			}
		}
	}

	static const char* kCandidates[] = {
		"Data\\INI\\UnlockableChecksDemo.ini",
		"Data/INI/UnlockableChecksDemo.ini",
		".\\Data\\INI\\UnlockableChecksDemo.ini",
		"..\\Data\\INI\\UnlockableChecksDemo.ini",
		"..\\..\\Data\\INI\\UnlockableChecksDemo.ini",
		"..\\..\\..\\Data\\INI\\UnlockableChecksDemo.ini",
		"Debug\\Data\\INI\\UnlockableChecksDemo.ini",
		".\\Debug\\Data\\INI\\UnlockableChecksDemo.ini",
		nullptr
	};
	for ( Int i = 0; kCandidates[i] != nullptr && !m_enabled; ++i )
	{
		std::ifstream file( kCandidates[i] );
		if ( file.is_open() )
		{
			std::string content( (std::istreambuf_iterator<char>( file )), std::istreambuf_iterator<char>() );
			file.close();
			if ( !content.empty() && loadConfigFromContent( content ) )
			{
				m_enabled = TRUE;
				DEBUG_LOG( ( "UnlockableCheckSpawner: loaded config for %d maps from %s", (Int)m_mapConfigs.size(), kCandidates[i] ) );
				return;
			}
		}
	}

	DEBUG_LOG( ( "UnlockableCheckSpawner: UnlockableChecksDemo.ini not found" ) );
}

// ------------------------------------------------------------------------------------------------
UnsignedInt UnlockableCheckSpawner::hashIndex( UnsignedInt seedVal, UnsignedInt index ) const
{
	return ( seedVal * 31u + index ) * 2654435761u;
}

// ------------------------------------------------------------------------------------------------
Bool UnlockableCheckSpawner::resolveTrackableSpawnPosition(
	Object* obj,
	const Coord3D& anchorPos,
	const Coord3D& desiredPos,
	Real minSeparation,
	Real minAnchorDistance,
	Real maxAnchorDistance,
	Coord3D* resolvedPos,
	const std::vector<Coord3D>* additionalOccupiedPositions ) const
{
	if ( obj == NULL || resolvedPos == NULL || TheTerrainLogic == NULL )
		return FALSE;

	Coord3D groundedAnchor = anchorPos;
	groundedAnchor.z = TheTerrainLogic->getGroundHeight( groundedAnchor.x, groundedAnchor.y );

	AIUpdateInterface* ai = obj->getAIUpdateInterface();
	if ( ai == NULL || TheAI == NULL || TheAI->pathfinder() == NULL )
	{
		*resolvedPos = desiredPos;
		resolvedPos->z = TheTerrainLogic->getGroundHeight( resolvedPos->x, resolvedPos->y );
		return TRUE;
	}

	obj->setPosition( &groundedAnchor );
	const LocomotorSet& locomotorSet = ai->getLocomotorSet();
	Pathfinder* pathfinder = TheAI->pathfinder();
	const Bool isCrusher = obj->getCrusherLevel() > 0;
	const Real minSeparationSq = minSeparation > 0.0f ? minSeparation * minSeparation : 0.0f;
	const GeometryInfo& geom = obj->getGeometryInfo();
	const Real footprintRadius = std::max( 28.0f, std::max( geom.getBoundingCircleRadius() * 0.75f, std::max( geom.getMajorRadius(), geom.getMinorRadius() ) * 0.90f ) );
	const Real footprintSampleRadius = std::max( 20.0f, footprintRadius * 0.85f );
	const Real minAnchorDistanceSq = std::max( 0.0f, minAnchorDistance ) * std::max( 0.0f, minAnchorDistance );
	const Real maxAnchorDistanceSq = maxAnchorDistance > 0.0f ? maxAnchorDistance * maxAnchorDistance : 0.0f;

	Coord3D groundedDesired = desiredPos;
	groundedDesired.z = TheTerrainLogic->getGroundHeight( groundedDesired.x, groundedDesired.y );

	auto isCandidateSeparated = [&]( const Coord3D& candidate ) -> Bool
	{
		if ( minSeparationSq <= 0.0f )
			return TRUE;

		for ( size_t i = 0; i < m_spawnedUnitGuardPos.size(); ++i )
		{
			const Coord3D& existing = m_spawnedUnitGuardPos[i];
			const Real dx = candidate.x - existing.x;
			const Real dy = candidate.y - existing.y;
			if ( dx * dx + dy * dy < minSeparationSq )
				return FALSE;
		}
		if ( additionalOccupiedPositions != NULL )
		{
			for ( size_t i = 0; i < additionalOccupiedPositions->size(); ++i )
			{
				const Coord3D& existing = (*additionalOccupiedPositions)[i];
				const Real dx = candidate.x - existing.x;
				const Real dy = candidate.y - existing.y;
				if ( dx * dx + dy * dy < minSeparationSq )
					return FALSE;
			}
		}
		return TRUE;
	};

	auto isCandidateClearOfObjects = [&]( const Coord3D& candidate ) -> Bool
	{
		if ( ThePartitionManager == NULL )
			return TRUE;

		SimpleObjectIterator* iter = ThePartitionManager->iteratePotentialCollisions( &candidate, obj->getGeometryInfo(), 0.0f, TRUE );
		MemoryPoolObjectHolder hold( iter );
		if ( iter == NULL )
			return TRUE;

		for ( Object* them = iter->first(); them; them = iter->next() )
		{
			if ( them == obj || them->isEffectivelyDead() )
				continue;
			return FALSE;
		}

		return TRUE;
	};

	auto isCandidateTerrainStable = [&]( Coord3D candidate ) -> Bool
	{
		candidate.z = TheTerrainLogic->getGroundHeight( candidate.x, candidate.y );
		const Real centerZ = candidate.z;

		if ( TheTerrainLogic->isUnderwater( candidate.x, candidate.y, NULL, NULL ) )
			return FALSE;
		if ( TheTerrainLogic->isCliffCell( candidate.x, candidate.y ) )
			return FALSE;

		static const Real kSampleAngles[] = {
			0.0f,
			0.78539816339f,
			1.57079632679f,
			2.35619449019f,
			3.14159265359f,
			3.92699071699f,
			4.71238898038f,
			5.49778714378f
		};
		for ( Int sampleIndex = 0; sampleIndex < (Int)ARRAY_SIZE( kSampleAngles ); ++sampleIndex )
		{
			Coord3D samplePos = candidate;
			samplePos.x += cosf( kSampleAngles[sampleIndex] ) * footprintSampleRadius;
			samplePos.y += sinf( kSampleAngles[sampleIndex] ) * footprintSampleRadius;
			samplePos.z = TheTerrainLogic->getGroundHeight( samplePos.x, samplePos.y );

			if ( TheTerrainLogic->isUnderwater( samplePos.x, samplePos.y, NULL, NULL ) )
				return FALSE;
			if ( TheTerrainLogic->isCliffCell( samplePos.x, samplePos.y ) )
				return FALSE;
			if ( fabs( samplePos.z - centerZ ) > kSpawnedUnitPlacementTerrainDeltaTolerance )
				return FALSE;

			PathfindLayerEnum sampleLayer = TheTerrainLogic->getLayerForDestination( &samplePos );
			if ( !pathfinder->validMovementPosition( isCrusher, sampleLayer, locomotorSet, &samplePos ) )
				return FALSE;
		}

		return TRUE;
	};

	auto finalizeCandidate = [&]( const Coord3D& candidate, Coord3D* out ) -> void
	{
		*out = candidate;
		const Real dynamicZBias = std::max( kSpawnedUnitPlacementZBias, std::min( 6.0f, footprintRadius * 0.10f ) );
		out->z = TheTerrainLogic->getGroundHeight( out->x, out->y ) + dynamicZBias;
	};

	auto isCandidateTrackable = [&]( Coord3D candidate ) -> Bool
	{
		candidate.z = TheTerrainLogic->getGroundHeight( candidate.x, candidate.y );
		const Real anchorDx = candidate.x - anchorPos.x;
		const Real anchorDy = candidate.y - anchorPos.y;
		const Real anchorDistSq = anchorDx * anchorDx + anchorDy * anchorDy;
		if ( anchorDistSq < minAnchorDistanceSq )
			return FALSE;
		if ( maxAnchorDistanceSq > 0.0f && anchorDistSq > maxAnchorDistanceSq )
			return FALSE;
		if ( TheTerrainLogic->isUnderwater( candidate.x, candidate.y, NULL, NULL ) )
			return FALSE;
		if ( TheTerrainLogic->isCliffCell( candidate.x, candidate.y ) )
			return FALSE;

		PathfindLayerEnum layer = TheTerrainLogic->getLayerForDestination( &candidate );
		if ( !pathfinder->validMovementPosition( isCrusher, layer, locomotorSet, &candidate ) )
			return FALSE;
		if ( !pathfinder->clientSafeQuickDoesPathExist( locomotorSet, &groundedAnchor, &candidate ) )
			return FALSE;
		if ( !isCandidateSeparated( candidate ) )
			return FALSE;
		if ( !isCandidateClearOfObjects( candidate ) )
			return FALSE;
		if ( !isCandidateTerrainStable( candidate ) )
			return FALSE;
		return TRUE;
	};

	if ( isCandidateTrackable( groundedDesired ) )
	{
		finalizeCandidate( groundedDesired, resolvedPos );
		return TRUE;
	}

	FindPositionOptions findOptions;
	findOptions.flags = FPF_CLEAR_CELLS_ONLY;
	findOptions.minRadius = 0.0f;
	findOptions.maxRadius = kSpawnedUnitSpawnSearchStep * (Real)kSpawnedUnitSpawnSearchRings;
	findOptions.maxZDelta = 25.0f;
	findOptions.ignoreObject = obj;
	findOptions.sourceToPathToDest = obj;

	Coord3D partitionCandidate = groundedDesired;
	if ( ThePartitionManager && ThePartitionManager->findPositionAround( &groundedDesired, &findOptions, &partitionCandidate )
		&& isCandidateTrackable( partitionCandidate ) )
	{
		finalizeCandidate( partitionCandidate, resolvedPos );
		return TRUE;
	}

	Coord3D adjustedPos = groundedDesired;
	if ( pathfinder->adjustToPossibleDestination( obj, locomotorSet, &adjustedPos ) && isCandidateTrackable( adjustedPos ) )
	{
		finalizeCandidate( adjustedPos, resolvedPos );
		return TRUE;
	}

	for ( Int ring = 1; ring <= kSpawnedUnitSpawnSearchRings; ++ring )
	{
		Real radius = kSpawnedUnitSpawnSearchStep * ring;
		for ( Int sample = 0; sample < kSpawnedUnitSpawnSearchSamples; ++sample )
		{
			Real angle = ( 2.0f * 3.14159265359f * sample ) / (Real)kSpawnedUnitSpawnSearchSamples;
			Coord3D candidate = groundedDesired;
			candidate.x += cosf( angle ) * radius;
			candidate.y += sinf( angle ) * radius;
			if ( isCandidateTrackable( candidate ) )
			{
				finalizeCandidate( candidate, resolvedPos );
				return TRUE;
			}
		}
	}

	Coord3D anchorCandidate = groundedAnchor;
	if ( ThePartitionManager && ThePartitionManager->findPositionAround( &groundedAnchor, &findOptions, &anchorCandidate )
		&& isCandidateTrackable( anchorCandidate ) )
	{
		finalizeCandidate( anchorCandidate, resolvedPos );
		return TRUE;
	}

	if ( isCandidateTrackable( groundedAnchor ) )
	{
		finalizeCandidate( groundedAnchor, resolvedPos );
		return TRUE;
	}

	return FALSE;
}

// ------------------------------------------------------------------------------------------------
Team* UnlockableCheckSpawner::getEnemyTeam( const MapConfig& config ) const
{
	if ( !ThePlayerList )
	{
		DEBUG_LOG( ( "UnlockableCheckSpawner::getEnemyTeam: ThePlayerList is null" ) );
		return nullptr;
	}
	// Generals Challenge: map uses "ThePlayer" (placeholder) with enemies from SidesList.
	// ThePlayer's enemies are set at newGame from the map; use them directly.
	if ( TheCampaignManager )
	{
		Campaign* campaign = TheCampaignManager->getCurrentCampaign();
		if ( campaign && campaign->m_isChallengeCampaign )
		{
			Player* thePlayer = ThePlayerList->findPlayerWithNameKey( NAMEKEY( "ThePlayer" ) );
			if ( thePlayer )
			{
				PlayerMaskType enemyMask = ThePlayerList->getPlayersWithRelationship(
					thePlayer->getPlayerIndex(), ALLOW_ENEMIES );
				if ( enemyMask )
				{
					Player* enemyPlayer = ThePlayerList->getEachPlayerFromMask( enemyMask );
					if ( enemyPlayer )
					{
						Team* team = enemyPlayer->getDefaultTeam();
						if ( team )
						{
							DEBUG_LOG( ( "UnlockableCheckSpawner::getEnemyTeam: using ThePlayer enemy (Challenge)" ) );
							return team;
						}
					}
				}
			}
			DEBUG_LOG( ( "UnlockableCheckSpawner::getEnemyTeam: Challenge but no ThePlayer enemy" ) );
		}
	}
	// Skirmish: human is slot 0 (player0), AI is slot 1 (player1). Team names are
	// "team" + playerName, e.g. "teamplayer1" for the AI.
	Player* enemyPlayer = ThePlayerList->findPlayerWithNameKey( NAMEKEY( "player1" ) );
	DEBUG_LOG( ( "UnlockableCheckSpawner::getEnemyTeam: player1=%p type=%d", (void*)enemyPlayer, enemyPlayer ? (Int)enemyPlayer->getPlayerType() : -1 ) );
	if ( enemyPlayer && enemyPlayer->getPlayerType() == PLAYER_COMPUTER )
	{
		Team* team = enemyPlayer->getDefaultTeam();
		if ( team )
		{
			DEBUG_LOG( ( "UnlockableCheckSpawner::getEnemyTeam: using player1 team" ) );
			return team;
		}
	}
	// Fallback: iterate for any PLAYER_COMPUTER that is ENEMIES with local
	Player* localPlayer = ThePlayerList->getLocalPlayer();
	if ( localPlayer )
	{
		for ( Int i = 0; i < ThePlayerList->getPlayerCount(); ++i )
		{
			Player* p = ThePlayerList->getNthPlayer( i );
			if ( !p || !p->isPlayerActive() || p->getPlayerType() != PLAYER_COMPUTER )
				continue;
			if ( localPlayer->getRelationship( p->getDefaultTeam() ) != ENEMIES )
				continue;
			Team* team = p->getDefaultTeam();
			if ( team )
			{
				DEBUG_LOG( ( "UnlockableCheckSpawner::getEnemyTeam: using enemy from iteration i=%d", i ) );
				return team;
			}
		}
	}
	// Last resort: team by name (e.g. "teamplayer1" for Generals Challenge AI)
	Team* team = TheTeamFactory->findTeam( config.enemyTeamName );
	DEBUG_LOG( ( "UnlockableCheckSpawner::getEnemyTeam: findTeam(%s)=%p", config.enemyTeamName.str(), (void*)team ) );
	return team;
}

// ------------------------------------------------------------------------------------------------
void UnlockableCheckSpawner::initializeCurrentMapTracking( const MapConfig& config )
{
	m_currentMapAllCheckIds.clear();
	appendUniqueAsciiStrings( m_currentMapAllCheckIds, config.unitCheckIds );
	appendUniqueAsciiStrings( m_currentMapAllCheckIds, config.buildingCheckIds );

	m_currentMapUnitTemplates.clear();
	appendUniqueAsciiStrings( m_currentMapUnitTemplates, config.unitTemplates );
	appendUniqueAsciiStrings( m_currentMapUnitTemplates, config.easyUnitTemplates );
	appendUniqueAsciiStrings( m_currentMapUnitTemplates, config.mediumUnitTemplates );
	appendUniqueAsciiStrings( m_currentMapUnitTemplates, config.hardUnitTemplates );
	appendUniqueAsciiStrings( m_currentMapUnitTemplates, config.buildingTemplates );

	m_currentMapCheckRewardGroups.clear();
	for ( size_t i = 0; i < config.unitCheckIds.size() && i < config.unitRewardGroupIds.size(); ++i )
	{
		if ( config.unitCheckIds[i].isNotEmpty() && config.unitRewardGroupIds[i].isNotEmpty() )
			m_currentMapCheckRewardGroups[config.unitCheckIds[i]] = config.unitRewardGroupIds[i];
	}
	for ( size_t i = 0; i < config.buildingCheckIds.size() && i < config.buildingRewardGroupIds.size(); ++i )
	{
		if ( config.buildingCheckIds[i].isNotEmpty() && config.buildingRewardGroupIds[i].isNotEmpty() )
			m_currentMapCheckRewardGroups[config.buildingCheckIds[i]] = config.buildingRewardGroupIds[i];
	}
}

// ------------------------------------------------------------------------------------------------
Bool UnlockableCheckSpawner::areTrackedTemplatesUnlocked() const
{
	if ( !TheArchipelagoState || m_currentMapUnitTemplates.empty() )
		return FALSE;

	for ( size_t i = 0; i < m_currentMapUnitTemplates.size(); ++i )
	{
		const AsciiString& templateName = m_currentMapUnitTemplates[i];
		if ( !TheArchipelagoState->isUnitUnlocked( templateName ) && !TheArchipelagoState->isBuildingUnlocked( templateName ) )
			return FALSE;
	}
	return TRUE;
}

// ------------------------------------------------------------------------------------------------
void UnlockableCheckSpawner::syncCompletedChecksFromArchipelagoState()
{
	if ( !TheArchipelagoState || m_currentMapAllCheckIds.empty() )
		return;

	for ( size_t i = 0; i < m_currentMapAllCheckIds.size(); ++i )
	{
		if ( TheArchipelagoState->isCheckComplete( m_currentMapAllCheckIds[i] ) )
			m_unlockedCheckIds.insert( m_currentMapAllCheckIds[i] );
	}
}

// ------------------------------------------------------------------------------------------------
void UnlockableCheckSpawner::remapCurrentMapRewardGroupsForUnlockedState()
{
	if ( !TheArchipelagoState || TheUnlockRegistry == NULL || m_currentMapAllCheckIds.empty() )
		return;

	std::set<AsciiString> reservedGroupIds;
	for ( size_t i = 0; i < m_currentMapAllCheckIds.size(); ++i )
	{
		const AsciiString &checkId = m_currentMapAllCheckIds[i];
		if ( m_unlockedCheckIds.find( checkId ) != m_unlockedCheckIds.end() )
			continue;

		AsciiString configuredGroupId;
		std::map<AsciiString, AsciiString>::const_iterator existing = m_currentMapCheckRewardGroups.find( checkId );
		if ( existing != m_currentMapCheckRewardGroups.end() )
			configuredGroupId = existing->second;

		AsciiString assignedGroupId = configuredGroupId;
		if ( assignedGroupId.isNotEmpty() )
		{
			if ( reservedGroupIds.find( assignedGroupId ) != reservedGroupIds.end()
				|| TheArchipelagoState->isGroupUnlocked( assignedGroupId ) )
			{
				assignedGroupId.clear();
			}
		}

		if ( assignedGroupId.isEmpty() )
		{
			for ( Int groupIndex = 0; groupIndex < TheUnlockRegistry->getItemPoolGroupCount(); ++groupIndex )
			{
				const UnlockGroup *group = TheUnlockRegistry->getItemPoolGroupAt( groupIndex );
				if ( group == NULL )
					continue;
				if ( reservedGroupIds.find( group->groupName ) != reservedGroupIds.end() )
					continue;
				if ( TheArchipelagoState->isGroupUnlocked( group->groupName ) )
					continue;
				assignedGroupId = group->groupName;
				break;
			}
		}

		if ( assignedGroupId.isEmpty() )
			m_currentMapCheckRewardGroups[checkId] = AsciiString( kNoUpgradeRewardGroupId );
		else
			m_currentMapCheckRewardGroups[checkId] = assignedGroupId;

		if ( assignedGroupId.isNotEmpty() )
			reservedGroupIds.insert( assignedGroupId );
	}
}

// ------------------------------------------------------------------------------------------------
void UnlockableCheckSpawner::rebuildRuntimeStateFromLoadedObjects( const MapConfig& config )
{
	if ( !TheGameLogic )
		return;

	std::set<AsciiString> spawnedUnitCheckIds( config.unitCheckIds.begin(), config.unitCheckIds.end() );
	for ( Object* obj = TheGameLogic->getFirstObject(); obj; obj = obj->getNextObject() )
	{
		if ( !obj || obj->isEffectivelyDead() )
			continue;

		const AsciiString& checkId = obj->getArchipelagoCheckId();
		if ( checkId.isEmpty() || spawnedUnitCheckIds.find( checkId ) == spawnedUnitCheckIds.end() )
			continue;

		const Coord3D* pos = obj->getPosition();
		if ( !pos )
			continue;

		AsciiString clusterId;
		for ( size_t i = 0; i < config.unitCheckIds.size() && i < config.unitClusterIds.size(); ++i )
		{
			if ( config.unitCheckIds[i] == checkId )
			{
				clusterId = config.unitClusterIds[i];
				break;
			}
		}

		m_spawnedUnits.push_back( obj );
		m_spawnedUnitLastRevealPos.push_back( *pos );
		m_spawnedUnitGuardPos.push_back( *pos );
		m_spawnedUnitClusterIds.push_back( clusterId );
		m_spawnedUnitHasRevealed.push_back( FALSE );
		m_spawnedUnitBaseVisionRanges.push_back( obj->getVisionRange() );
		m_spawnedUnitLastObservedDamageFrames.push_back( 0u );
		m_spawnedUnitRetreatBoostActive.push_back( FALSE );
		m_spawnedUnitRetreatActive.push_back( FALSE );
		m_spawnedUnitRetreatHardPull.push_back( FALSE );
		m_spawnedUnitRetreatStartFrames.push_back( 0u );
		m_spawnedUnitBaseRetreatSpeeds.push_back( 0.0f );
		m_spawnedUnitBaseRetreatAccelerations.push_back( 0.0f );
		m_spawnedUnitBaseRetreatBraking.push_back( 0.0f );
		m_spawnedUnitBaseRetreatNoSlowdown.push_back( FALSE );
		m_spawnedUnitBaseRetreatUltraAccurate.push_back( FALSE );
		m_spawnedUnitLastAggroCommandFrames.push_back( 0u );
		m_spawnedUnitLastAggroTargetIds.push_back( INVALID_ID );
	}

}

// ------------------------------------------------------------------------------------------------
void UnlockableCheckSpawner::runAfterMapLoad( const AsciiString& mapName, Bool loadingSaveGame )
{
	clearSpawnedUnitsOnly();
	m_currentMapDamageOutputScalar = 1.0f;
	m_currentMapDefendRadius = 0.0f;
	m_currentMapMaxChaseRadius = 0.0f;
	m_currentMapUnitMarkerFX.clear();
	m_repeatLocalRewardsForCompletedChecks = FALSE;
	m_currentMapUnitTemplates.clear();
	m_unlockedCheckIds.clear();
	m_currentMapAllCheckIds.clear();
	m_currentMapCheckRewardGroups.clear();
	m_clusterAlertUntilFrames.clear();
	m_clusterAlertThreatPositions.clear();
	m_hasPendingReroll = FALSE;
	m_pendingRerollSpawnFrame = 0u;

	DEBUG_LOG( ( "[Archipelago] UnlockableCheckSpawner: runAfterMapLoad map=%s loadingSave=%d enabled=%d", mapName.str(), (Int)loadingSaveGame, (Int)m_enabled ) );

	// Retry config load if not enabled - working directory may differ when entering a game
	if ( !m_enabled )
	{
		loadConfig();
		DEBUG_LOG( ( "[Archipelago] After loadConfig enabled=%d configs=%d", (Int)m_enabled, (Int)m_mapConfigs.size() ) );
		if ( !m_enabled )
			return;
	}

	AsciiString leafName = getMapLeafName( mapName );
	DEBUG_LOG( ( "UnlockableCheckSpawner: leafName=%s", leafName.str() ) );

	// Case-insensitive lookup (map names may vary)
	std::map<AsciiString, MapConfig>::const_iterator it = m_mapConfigs.end();
	for ( std::map<AsciiString, MapConfig>::const_iterator i = m_mapConfigs.begin(); i != m_mapConfigs.end(); ++i )
	{
		if ( i->first.compareNoCase( leafName ) == 0 )
		{
			it = i;
			break;
		}
	}
	if ( it == m_mapConfigs.end() )
	{
		DEBUG_LOG( ( "[Archipelago] No config for map %s (add section to UnlockableChecksDemo.ini)", leafName.str() ) );
		if ( TheInGameUI )
		{
			AsciiString msg;
			msg.format( "Unlockable Check Demo: no config for map %s. Add [%s] to UnlockableChecksDemo.ini", leafName.str(), leafName.str() );
			UnicodeString msgUnicode;
			msgUnicode.translate( msg );
			TheInGameUI->messageNoFormat( msgUnicode );
		}
		return;
	}

	const MapConfig& config = it->second;
	DEBUG_LOG( ( "[Archipelago] Spawner running for map %s seed=%u", leafName.str(), config.configSeed ) );
	m_currentMapLeafName = leafName;
	m_currentMapConfig = config;
	m_hasCurrentMapConfig = TRUE;
	m_currentMapRerollCount = 0u;

	m_currentMapDamageOutputScalar = config.damageOutputScalar > 0.0f ? config.damageOutputScalar : 1.0f;
	m_currentMapDefendRadius = config.defendRadius > 0.0f ? config.defendRadius : 0.0f;
	m_currentMapMaxChaseRadius = config.maxChaseRadius > 0.0f ? config.maxChaseRadius : 0.0f;
	m_currentMapUnitMarkerFX = config.unitMarkerFX;
	m_repeatLocalRewardsForCompletedChecks = config.repeatLocalRewardsForCompletedChecks;
	initializeCurrentMapTracking( config );
	syncCompletedChecksFromArchipelagoState();
	remapCurrentMapRewardGroupsForUnlockedState();
	if ( TheArchipelagoState )
		TheArchipelagoState->armMissionStartOptions( loadingSaveGame );
	DEBUG_LOG( ( "[Archipelago] Pre-spawn sync: %d completed checks from ArchipelagoState", (Int)m_unlockedCheckIds.size() ) );

	if ( loadingSaveGame )
	{
		rebuildRuntimeStateFromLoadedObjects( config );
		DEBUG_LOG( ( "[Archipelago] Rebuilt save-game runtime state: %d spawned units tracked, %d completed checks cached",
			(Int)m_spawnedUnits.size(), (Int)m_unlockedCheckIds.size() ) );
		return;
	}

	spawnUnitsForMap( leafName, config );
	tagBuildingsForMap( leafName, config );

	// Brief in-game message so user knows demo is active (easy to verify)
	if ( TheInGameUI && ( !config.unitCheckIds.empty() || !config.buildingCheckIds.empty() ) )
	{
		AsciiString msg;
		msg.format( "Unlockable Checks Demo: %d units, %d buildings tagged. Hover units to see unlock groups.", (Int)config.unitCheckIds.size(), (Int)config.buildingCheckIds.size() );
		UnicodeString msgUnicode;
		msgUnicode.translate( msg );
		TheInGameUI->messageNoFormat( msgUnicode );
	}

	if ( TheInGameUI && TheArchipelagoState && TheUnlockRegistry )
	{
		std::vector<AsciiString> unlockedLabels;
		for ( Int groupIndex = 0; groupIndex < TheUnlockRegistry->getGroupCount(); ++groupIndex )
		{
			const UnlockGroup* group = TheUnlockRegistry->getGroupAt( groupIndex );
			if ( group == NULL || !TheArchipelagoState->isGroupUnlocked( group->groupName ) )
				continue;
			unlockedLabels.push_back( group->displayName.isEmpty() ? group->groupName : group->displayName );
		}

		if ( unlockedLabels.empty() )
		{
			UnicodeString noneMsg;
			noneMsg.translate( "[ARCHIPELAGO] Unlocked items on mission load: <none>" );
			TheInGameUI->messageNoFormat( noneMsg );
		}
		else
		{
			AsciiString summary;
			summary.format( "[ARCHIPELAGO] Unlocked items on mission load (%d):", (Int)unlockedLabels.size() );
			UnicodeString summaryUnicode;
			summaryUnicode.translate( summary );
			TheInGameUI->messageNoFormat( summaryUnicode );

			for ( size_t start = 0; start < unlockedLabels.size(); start += 4 )
			{
				AsciiString line;
				for ( size_t i = start; i < unlockedLabels.size() && i < start + 4; ++i )
				{
					if ( i > start )
						line.concat( ", " );
					line.concat( unlockedLabels[i] );
				}
				UnicodeString lineUnicode;
				lineUnicode.translate( line );
				TheInGameUI->messageNoFormat( lineUnicode );
			}
		}
	}
}

// ------------------------------------------------------------------------------------------------
void UnlockableCheckSpawner::spawnUnitsForMap( const AsciiString& mapName, const MapConfig& config )
{
	// When slot data from Archipelago is not in use, we fall back to INI config.
	DEBUG_LOG( ( "[Archipelago] Using UnlockableChecksDemo.ini fallback—no slot data" ) );

	m_currentMapDamageOutputScalar = config.damageOutputScalar > 0.0f ? config.damageOutputScalar : 1.0f;
	m_currentMapDefendRadius = config.defendRadius > 0.0f ? config.defendRadius : 0.0f;
	m_currentMapMaxChaseRadius = config.maxChaseRadius > 0.0f ? config.maxChaseRadius : 0.0f;
	m_currentMapUnitMarkerFX = config.unitMarkerFX;

	Int numToSpawn = config.spawnCount > 0 ? config.spawnCount : (Int)config.unitCheckIds.size();
	DEBUG_LOG( ( "UnlockableCheckSpawner::spawnUnitsForMap: waypoints=%d templates=%d checkIds=%d numToSpawn=%d",
		(Int)config.unitWaypoints.size(), (Int)config.unitTemplates.size(), (Int)config.unitCheckIds.size(), numToSpawn ) );
	if ( config.unitWaypoints.empty() || config.unitTemplates.empty() || config.unitCheckIds.empty() || numToSpawn <= 0 )
		return;

	Team* team = getEnemyTeam( config );
	if ( !team )
	{
		DEBUG_LOG( ( "UnlockableCheckSpawner: no enemy team for map %s", mapName.str() ) );
		if ( TheInGameUI )
		{
			AsciiString msg;
			msg.format( "Unlockable Check Demo: no enemy team for %s. Check DEBUG_LOG.", mapName.str() );
			UnicodeString msgUnicode;
			msgUnicode.translate( msg );
			TheInGameUI->messageNoFormat( msgUnicode );
		}
		return;
	}

	// In demo-repeat mode, keep the full configured check slice so cluster composition stays stable across mission restarts.
	// Outside that mode, prefer checks not already completed.
	std::vector<AsciiString> checkIdsToAssign;
	if ( m_repeatLocalRewardsForCompletedChecks )
	{
		checkIdsToAssign = config.unitCheckIds;
	}
	else
	{
		checkIdsToAssign.reserve( config.unitCheckIds.size() );
		for ( size_t i = 0; i < config.unitCheckIds.size(); ++i )
		{
			const AsciiString& id = config.unitCheckIds[i];
			Bool alreadyUnlocked = ( m_unlockedCheckIds.find( id ) != m_unlockedCheckIds.end() );
			if ( !alreadyUnlocked && TheArchipelagoState )
				alreadyUnlocked = TheArchipelagoState->isCheckComplete( id );
			if ( !alreadyUnlocked )
				checkIdsToAssign.push_back( id );
		}
	}
	// If all groups are already unlocked, still spawn with random IDs from full list.
	if ( checkIdsToAssign.empty() )
		checkIdsToAssign = config.unitCheckIds;
	DEBUG_LOG( ( "UnlockableCheckSpawner: check assignment pool size=%d (total map checks=%d)", (Int)checkIdsToAssign.size(), (Int)config.unitCheckIds.size() ) );
	std::vector<AsciiString> templatesToAssign = config.unitTemplates;
	DEBUG_LOG( ( "UnlockableCheckSpawner: template assignment pool size=%d (total map templates=%d)", (Int)templatesToAssign.size(), (Int)config.unitTemplates.size() ) );
	std::map<AsciiString, Int> clusterAssignedCounts;
	std::map<AsciiString, Int> clusterSpawnSuccesses;
	std::map<AsciiString, Int> clusterSpawnSkips;
	std::map<AsciiString, std::vector<AsciiString> > clusterCheckIds;
	std::map<AsciiString, Int> configuredIndexByCheckId;
	for ( size_t i = 0; i < checkIdsToAssign.size(); ++i )
	{
		for ( size_t j = 0; j < config.unitCheckIds.size() && j < config.unitClusterIds.size(); ++j )
		{
			if ( config.unitCheckIds[j] == checkIdsToAssign[i] && config.unitClusterIds[j].isNotEmpty() )
			{
				clusterAssignedCounts[config.unitClusterIds[j]] += 1;
				clusterCheckIds[config.unitClusterIds[j]].push_back( checkIdsToAssign[i] );
				configuredIndexByCheckId[checkIdsToAssign[i]] = (Int)j;
				break;
			}
		}
	}

	struct PlannedClusterSpawn
	{
		Object* object;
		AsciiString clusterId;
		AsciiString clusterTier;
		AsciiString waypointName;
		AsciiString templateName;
		AsciiString upgradeName;
		AsciiString checkId;
		AsciiString rewardLabel;
		Coord3D resolvedPos;
		Coord3D clusterCenter;
	};
	for ( size_t clusterListIndex = 0; clusterListIndex < config.clusterIds.size(); ++clusterListIndex )
	{
		const AsciiString& clusterId = config.clusterIds[clusterListIndex];
		const Int plannedCount = clusterAssignedCounts.find( clusterId ) != clusterAssignedCounts.end()
			? clusterAssignedCounts[clusterId]
			: 0;
		if ( plannedCount <= 0 )
			continue;

		const std::vector<AsciiString>& clusterChecks = clusterCheckIds[clusterId];
		if ( clusterChecks.empty() )
			continue;

		const Int configuredClusterIndex = findConfiguredClusterIndex( config, clusterId );
		AsciiString clusterTier;
		if ( configuredClusterIndex >= 0 && (size_t)configuredClusterIndex < config.clusterTiers.size() )
			clusterTier = config.clusterTiers[(size_t)configuredClusterIndex];

		AsciiString waypointName = !config.unitWaypoints.empty() ? config.unitWaypoints[0] : AsciiString( "Player_1_Start" );
		if ( configuredClusterIndex >= 0
			&& (size_t)configuredClusterIndex < config.clusterWaypoints.size()
			&& config.clusterWaypoints[(size_t)configuredClusterIndex].isNotEmpty() )
			waypointName = config.clusterWaypoints[(size_t)configuredClusterIndex];

		Waypoint* way = TheTerrainLogic->getWaypointByName( waypointName );
		if ( !way )
			way = TheTerrainLogic->getWaypointByName( AsciiString( "Player_1_Start" ) );
		if ( !way )
		{
			DEBUG_LOG( ( "UnlockableCheckSpawner: waypoint %s and Player_1_Start not found for map %s", waypointName.str(), mapName.str() ) );
			continue;
		}

		Coord3D anchorPos = *way->getLocation();
		anchorPos.z = TheTerrainLogic->getGroundHeight( anchorPos.x, anchorPos.y );
		Coord3D desiredCenter = anchorPos;
		Real clusterSpread = std::max( 72.0f, config.spawnOffsetSpread > 0.0f ? config.spawnOffsetSpread : 96.0f );
		Real clusterMinRadius = 0.0f;
		Real clusterAngle = 0.0f;
		if ( configuredClusterIndex >= 0 )
		{
			if ( (size_t)configuredClusterIndex < config.clusterAngles.size() && (size_t)configuredClusterIndex < config.clusterRadii.size() )
			{
				clusterAngle = config.clusterAngles[(size_t)configuredClusterIndex];
				const Real clusterRadius = config.clusterRadii[(size_t)configuredClusterIndex];
				desiredCenter.x += cosf( clusterAngle ) * clusterRadius;
				desiredCenter.y += sinf( clusterAngle ) * clusterRadius;
			}
			if ( (size_t)configuredClusterIndex < config.clusterSpreads.size() )
				clusterSpread = std::max( 90.0f, config.clusterSpreads[(size_t)configuredClusterIndex] );
			if ( (size_t)configuredClusterIndex < config.clusterCenterReservedRadii.size() )
				clusterMinRadius = std::max( 0.0f, config.clusterCenterReservedRadii[(size_t)configuredClusterIndex] );
		}
		desiredCenter.z = TheTerrainLogic->getGroundHeight( desiredCenter.x, desiredCenter.y );

		Real clusterMinSeparation = std::max( 54.0f, clusterSpread * 0.20f );
		auto destroyPlannedObjects = [&]( std::vector<PlannedClusterSpawn>& planned ) -> void
		{
			for ( size_t destroyIndex = 0; destroyIndex < planned.size(); ++destroyIndex )
			{
				if ( planned[destroyIndex].object && TheGameLogic )
					TheGameLogic->destroyObject( planned[destroyIndex].object );
			}
			planned.clear();
		};

		auto tryPlanClusterAtCenter = [&]( const Coord3D& candidateCenter, Real clusterOuterRadius, Real minSeparation, std::vector<PlannedClusterSpawn>& plannedOut ) -> Bool
		{
			std::vector<Coord3D> localOccupiedPositions;
			plannedOut.clear();
			localOccupiedPositions.reserve( clusterChecks.size() );

			for ( size_t slotOrdinal = 0; slotOrdinal < clusterChecks.size(); ++slotOrdinal )
			{
				const AsciiString& checkId = clusterChecks[slotOrdinal];
				const Int configuredIndex = configuredIndexByCheckId.find( checkId ) != configuredIndexByCheckId.end()
					? configuredIndexByCheckId[checkId]
					: -1;
				UnsignedInt slotHash = hashIndex( config.configSeed ^ 0x9E3779B9u, (UnsignedInt)( configuredClusterIndex + 1 ) * 1024u + (UnsignedInt)slotOrdinal );
				AsciiString templateName;
				AsciiString upgradeName;
				if ( clusterTier.compareNoCase( "hard" ) == 0 )
				{
					// Hard pockets are fully weighted-random now. Overlord variants remain strongly weighted
					// in data, but we still resolve the visual variants by applying upgrades to the base hull
					// after spawn so the planner fits the stock Overlord footprint reliably.
					AsciiString weightedTemplate = pickWeightedClusterTemplate( config, clusterTier, slotHash );
					if ( weightedTemplate.compareNoCase( "ChinaTankOverlordGattlingCannon" ) == 0
						|| weightedTemplate.compareNoCase( "Tank_ChinaTankOverlordGattlingCannon" ) == 0 )
					{
						templateName = AsciiString( "ChinaTankOverlord" );
						upgradeName = AsciiString( "Upgrade_ChinaOverlordGattlingCannon" );
					}
					else if ( weightedTemplate.compareNoCase( "ChinaTankOverlordPropagandaTower" ) == 0
						|| weightedTemplate.compareNoCase( "Tank_ChinaTankOverlordPropagandaTower" ) == 0 )
					{
						templateName = AsciiString( "ChinaTankOverlord" );
						upgradeName = AsciiString( "Upgrade_ChinaOverlordPropagandaTower" );
					}
					else if ( weightedTemplate.compareNoCase( "ChinaTankOverlordBattleBunker" ) == 0
						|| weightedTemplate.compareNoCase( "Tank_ChinaTankOverlordBattleBunker" ) == 0 )
					{
						templateName = AsciiString( "ChinaTankOverlord" );
						upgradeName = AsciiString( "Upgrade_ChinaOverlordBattleBunker" );
					}
					else
					{
						templateName = weightedTemplate;
					}
				}
				else
				{
					templateName = pickWeightedClusterTemplate( config, clusterTier, slotHash );
				}
				if ( templateName.isEmpty() && configuredIndex >= 0 && (size_t)configuredIndex < config.unitTemplates.size() )
					templateName = config.unitTemplates[(size_t)configuredIndex];
				if ( templateName.isEmpty() )
					templateName = templatesToAssign[(Int)( slotOrdinal % templatesToAssign.size() )];

				const ThingTemplate* tmpl = TheThingFactory->findTemplate( templateName );
				if ( tmpl == NULL )
				{
					const char* underscore = strchr( templateName.str(), '_' );
					if ( underscore != NULL && underscore[1] != '\0' )
					{
						AsciiString fallbackTemplate = underscore + 1;
						tmpl = TheThingFactory->findTemplate( fallbackTemplate );
						if ( tmpl != NULL )
						{
							DEBUG_LOG( ( "[Archipelago] Spawn template alias %s resolved to stock template %s", templateName.str(), fallbackTemplate.str() ) );
							templateName = fallbackTemplate;
						}
					}
				}
				if ( tmpl == NULL )
				{
					destroyPlannedObjects( plannedOut );
					return FALSE;
				}

				Object* obj = TheThingFactory->newObject( tmpl, team );
				if ( obj == NULL )
				{
					destroyPlannedObjects( plannedOut );
					return FALSE;
				}

				const Real clusterSeedAngle = ( configuredClusterIndex >= 0 && (size_t)configuredClusterIndex < config.clusterAngles.size() )
					? config.clusterAngles[(size_t)configuredClusterIndex] + 0.35f * (Real)( configuredClusterIndex + 1 )
					: 0.35f;
				const Real angleJitter = ( ( (Real)( slotHash % 1000u ) / 1000.0f ) - 0.5f ) * ( 2.0f * kSpawnedClusterLocalAngleJitter );
				const Real slotAngle = clusterSeedAngle + kSpawnedClusterGoldenAngle * (Real)slotOrdinal + angleJitter;
				const Real ordinalAlpha = clusterChecks.size() > 0 ? ( (Real)slotOrdinal + 0.5f ) / (Real)clusterChecks.size() : 0.5f;
				const Real radialAlpha = (Real)sqrt( ordinalAlpha );
				const Real localOuterRadius = std::max( clusterOuterRadius, clusterMinRadius + 1.0f );
				const Real localRadius = clusterMinRadius
					+ ( localOuterRadius - clusterMinRadius )
					* ( kSpawnedClusterLocalMinRadiusScalar
						+ ( kSpawnedClusterLocalMaxRadiusScalar - kSpawnedClusterLocalMinRadiusScalar ) * radialAlpha );

				Coord3D desiredPos = candidateCenter;
				desiredPos.x += cosf( slotAngle ) * localRadius;
				desiredPos.y += sinf( slotAngle ) * localRadius;
				desiredPos.z = TheTerrainLogic->getGroundHeight( desiredPos.x, desiredPos.y );

				Coord3D resolvedPos = desiredPos;
				if ( !resolveTrackableSpawnPosition( obj, candidateCenter, desiredPos, minSeparation, clusterMinRadius, clusterOuterRadius, &resolvedPos, &localOccupiedPositions ) )
				{
					if ( TheGameLogic )
						TheGameLogic->destroyObject( obj );
					destroyPlannedObjects( plannedOut );
					return FALSE;
				}

				localOccupiedPositions.push_back( resolvedPos );
				PlannedClusterSpawn planned;
				planned.object = obj;
				planned.clusterId = clusterId;
				planned.clusterTier = clusterTier;
				planned.waypointName = waypointName;
				planned.templateName = templateName;
				planned.upgradeName = upgradeName;
				planned.checkId = checkId;
				planned.rewardLabel = getRewardLabelForCheckId( checkId );
				planned.resolvedPos = resolvedPos;
				planned.clusterCenter = candidateCenter;
				plannedOut.push_back( planned );
			}

			return ( plannedOut.size() == clusterChecks.size() );
		};

		auto isClusterCenterTerrainUsable = [&]( Coord3D candidateCenter, Real clusterOuterRadius ) -> Bool
		{
			candidateCenter.z = TheTerrainLogic->getGroundHeight( candidateCenter.x, candidateCenter.y );
			if ( TheTerrainLogic->isUnderwater( candidateCenter.x, candidateCenter.y, NULL, NULL ) )
				return FALSE;
			if ( TheTerrainLogic->isCliffCell( candidateCenter.x, candidateCenter.y ) )
				return FALSE;

			const Real centerZ = candidateCenter.z;
			const Real sampleRadius = std::max( 55.0f, clusterOuterRadius * kClusterCenterSampleRadiusScalar );
			static const Real kCenterSampleAngles[] = {
				0.0f,
				0.78539816339f,
				1.57079632679f,
				2.35619449019f,
				3.14159265359f,
				3.92699071699f,
				4.71238898038f,
				5.49778714378f
			};

			for ( Int sampleIndex = 0; sampleIndex < (Int)ARRAY_SIZE( kCenterSampleAngles ); ++sampleIndex )
			{
				Coord3D samplePos = candidateCenter;
				samplePos.x += cosf( kCenterSampleAngles[sampleIndex] ) * sampleRadius;
				samplePos.y += sinf( kCenterSampleAngles[sampleIndex] ) * sampleRadius;
				samplePos.z = TheTerrainLogic->getGroundHeight( samplePos.x, samplePos.y );
				if ( TheTerrainLogic->isUnderwater( samplePos.x, samplePos.y, NULL, NULL ) )
					return FALSE;
				if ( TheTerrainLogic->isCliffCell( samplePos.x, samplePos.y ) )
					return FALSE;
				if ( fabs( samplePos.z - centerZ ) > kClusterCenterTerrainFlatnessTolerance )
					return FALSE;
			}

			return TRUE;
		};

		std::vector<PlannedClusterSpawn> clusterPlan;
		Bool clusterFitFound = FALSE;
		Coord3D selectedCenter = desiredCenter;
		std::vector<Coord3D> preferredCenters;
		if ( mapName.compareNoCase( "GC_TankGeneral" ) == 0 && clusterId.compareNoCase( "TG_Hard" ) == 0 )
		{
			static const Real kAuthoredHardCenters[][2] = {
				{ 860.0f, 1735.0f },
				{ 920.0f, 1700.0f },
				{ 790.0f, 1775.0f },
				{ 975.0f, 1665.0f },
				{ 835.0f, 1685.0f },
				{ 905.0f, 1795.0f }
			};
			for ( Int preferredIndex = 0; preferredIndex < (Int)ARRAY_SIZE( kAuthoredHardCenters ); ++preferredIndex )
			{
				Coord3D preferredCenter;
				preferredCenter.x = kAuthoredHardCenters[preferredIndex][0];
				preferredCenter.y = kAuthoredHardCenters[preferredIndex][1];
				preferredCenter.z = TheTerrainLogic->getGroundHeight( preferredCenter.x, preferredCenter.y );
				preferredCenters.push_back( preferredCenter );
			}
		}
		const Real inwardDirX = desiredCenter.x - anchorPos.x;
		const Real inwardDirY = desiredCenter.y - anchorPos.y;
		const Real inwardDirLen = (Real)sqrt( inwardDirX * inwardDirX + inwardDirY * inwardDirY );
		const Real inwardNormX = inwardDirLen > 0.1f ? inwardDirX / inwardDirLen : cosf( clusterAngle );
		const Real inwardNormY = inwardDirLen > 0.1f ? inwardDirY / inwardDirLen : sinf( clusterAngle );
		const Real lateralNormX = -inwardNormY;
		const Real lateralNormY = inwardNormX;
		for ( Int searchPhase = 0; searchPhase < 4 && !clusterFitFound; ++searchPhase )
		{
			const Real minSeparation = searchPhase == 0
				? clusterMinSeparation
					: std::max( searchPhase == 3 ? 42.0f : 48.0f,
						clusterMinSeparation * ( searchPhase == 1 ? kClusterFallbackMinSeparationScalar : ( searchPhase == 2 ? 0.60f : 0.52f ) ) );
			const Bool hardCluster = clusterTier.compareNoCase( "hard" ) == 0;
			Real clusterOuterRadius = clusterSpread * ( searchPhase == 0 ? 1.0f : ( searchPhase == 1 ? 1.15f : ( searchPhase == 2 ? 1.30f : 1.45f ) ) );
			if ( hardCluster )
				clusterOuterRadius *= ( searchPhase == 0 ? 1.30f : ( searchPhase == 1 ? 1.45f : ( searchPhase == 2 ? 1.65f : 1.85f ) ) );
			for ( size_t preferredIndex = 0; preferredIndex < preferredCenters.size() && !clusterFitFound; ++preferredIndex )
			{
				const Coord3D& preferredCenter = preferredCenters[preferredIndex];
				if ( !isClusterCenterTerrainUsable( preferredCenter, clusterOuterRadius ) )
					continue;
				if ( tryPlanClusterAtCenter( preferredCenter, clusterOuterRadius, minSeparation, clusterPlan ) )
				{
					selectedCenter = preferredCenter;
					clusterFitFound = TRUE;
				}
			}
			if ( clusterFitFound )
				break;
			const Real desiredDistanceToAnchor = inwardDirLen;
			const Real maxInwardDistance = hardCluster
				? std::max( 220.0f, desiredDistanceToAnchor * ( searchPhase == 0 ? 0.55f : ( searchPhase == 1 ? 0.68f : ( searchPhase == 2 ? 0.80f : 0.88f ) ) ) )
				: std::max( 45.0f, clusterOuterRadius * 0.28f ) * ( searchPhase == 0 ? 4.0f : 6.0f );
			const Int inwardSamples = hardCluster
				? ( searchPhase == 0 ? 6 : 8 )
				: ( searchPhase == 0 ? 4 : 6 );
			for ( Int inwardIndex = 0; inwardIndex <= inwardSamples && !clusterFitFound; ++inwardIndex )
			{
				const Real inwardDistance = inwardSamples > 0
					? ( maxInwardDistance * (Real)inwardIndex ) / (Real)inwardSamples
					: 0.0f;
				const Real lateralStep = hardCluster
					? std::max( 65.0f, clusterOuterRadius * 0.42f )
					: std::max( 55.0f, clusterOuterRadius * 0.35f );
				const Int lateralSamples = hardCluster ? 4 : 0;
				for ( Int lateralIndex = -lateralSamples; lateralIndex <= lateralSamples && !clusterFitFound; ++lateralIndex )
				{
					Coord3D inwardCenter = desiredCenter;
					if ( inwardDistance > 0.0f )
					{
						inwardCenter.x -= inwardNormX * inwardDistance;
						inwardCenter.y -= inwardNormY * inwardDistance;
					}
					if ( lateralIndex != 0 )
					{
						inwardCenter.x += lateralNormX * lateralStep * (Real)lateralIndex;
						inwardCenter.y += lateralNormY * lateralStep * (Real)lateralIndex;
					}
					inwardCenter.z = TheTerrainLogic->getGroundHeight( inwardCenter.x, inwardCenter.y );
					if ( !isClusterCenterTerrainUsable( inwardCenter, clusterOuterRadius ) )
						continue;
					if ( tryPlanClusterAtCenter( inwardCenter, clusterOuterRadius, minSeparation, clusterPlan ) )
					{
						selectedCenter = inwardCenter;
						clusterFitFound = TRUE;
					}
				}
			}
			if ( clusterFitFound )
				break;
			const Real searchStep = kClusterCenterSearchStep + (Real)searchPhase * 8.0f;
			const Int searchRings = kClusterCenterSearchRings + searchPhase * ( hardCluster ? 4 : 2 );
			const Int searchSamples = kClusterCenterSearchSamples + searchPhase * ( hardCluster ? 4 : 2 );
			for ( Int ring = 0; ring <= searchRings && !clusterFitFound; ++ring )
			{
				const Int samplesThisRing = ring == 0 ? 1 : searchSamples;
				for ( Int sample = 0; sample < samplesThisRing; ++sample )
				{
					Coord3D candidateCenter = desiredCenter;
					if ( ring > 0 )
					{
						const Real sampleAngle = ( (Real)sample / (Real)samplesThisRing ) * 6.28318530718f;
						const Real sampleRadius = searchStep * (Real)ring;
						candidateCenter.x += cosf( sampleAngle ) * sampleRadius;
						candidateCenter.y += sinf( sampleAngle ) * sampleRadius;
					}
					candidateCenter.z = TheTerrainLogic->getGroundHeight( candidateCenter.x, candidateCenter.y );
					if ( !isClusterCenterTerrainUsable( candidateCenter, clusterOuterRadius ) )
						continue;
					if ( tryPlanClusterAtCenter( candidateCenter, clusterOuterRadius, minSeparation, clusterPlan ) )
					{
						selectedCenter = candidateCenter;
						clusterFitFound = TRUE;
						break;
					}
				}
			}
		}

		if ( !clusterFitFound )
		{
			clusterSpawnSkips[clusterId] = plannedCount;
			DEBUG_LOG( ( "[Archipelago] Failed to fit full cluster %s planned=%d near desired center (%.1f, %.1f); no units spawned for this cluster",
				clusterId.str(), plannedCount, desiredCenter.x, desiredCenter.y ) );
			continue;
		}

		DEBUG_LOG( ( "[Archipelago] Cluster %s fitted full slice at center (%.1f, %.1f) planned=%d spread=%.1f",
			clusterId.str(), selectedCenter.x, selectedCenter.y, plannedCount, clusterSpread ) );

			for ( size_t plannedIndex = 0; plannedIndex < clusterPlan.size(); ++plannedIndex )
			{
				PlannedClusterSpawn& planned = clusterPlan[plannedIndex];
				Object* obj = planned.object;
				obj->setPosition( &planned.resolvedPos );
			obj->setArchipelagoCheckId( planned.checkId );
			if ( planned.rewardLabel.isNotEmpty() )
				obj->setName( planned.rewardLabel );
			Real baseVisionRange = obj->getVisionRange();
			if ( baseVisionRange < kSpawnedUnitMinVisionRange )
			{
				obj->setVisionRange( kSpawnedUnitMinVisionRange );
				DEBUG_LOG( ( "[Archipelago] Spawned unit %s vision range boosted to %.0f (min for anti-exploit)", planned.templateName.str(), (double)kSpawnedUnitMinVisionRange ) );
			}

			m_spawnedUnits.push_back( obj );
			m_spawnedUnitLastRevealPos.push_back( planned.resolvedPos );
			m_spawnedUnitGuardPos.push_back( planned.resolvedPos );
			m_spawnedUnitClusterIds.push_back( planned.clusterId );
			m_spawnedUnitHasRevealed.push_back( FALSE );
			m_spawnedUnitBaseVisionRanges.push_back( baseVisionRange );
			m_spawnedUnitLastObservedDamageFrames.push_back( 0u );
			m_spawnedUnitRetreatBoostActive.push_back( FALSE );
			m_spawnedUnitRetreatActive.push_back( FALSE );
			m_spawnedUnitRetreatHardPull.push_back( FALSE );
			m_spawnedUnitRetreatStartFrames.push_back( 0u );
			m_spawnedUnitBaseRetreatSpeeds.push_back( 0.0f );
			m_spawnedUnitBaseRetreatAccelerations.push_back( 0.0f );
			m_spawnedUnitBaseRetreatBraking.push_back( 0.0f );
			m_spawnedUnitBaseRetreatNoSlowdown.push_back( FALSE );
			m_spawnedUnitBaseRetreatUltraAccurate.push_back( FALSE );
			m_spawnedUnitLastAggroCommandFrames.push_back( 0u );
			m_spawnedUnitLastAggroTargetIds.push_back( INVALID_ID );

			team->setActive();
			TheAI->pathfinder()->addObjectToPathfindMap( obj );

			for ( BehaviorModule** m = obj->getBehaviorModules(); *m; ++m )
			{
				CreateModuleInterface* create = (*m)->getCreate();
				if ( create )
					create->onBuildComplete();
			}

			if ( planned.upgradeName.isNotEmpty() && TheUpgradeCenter != NULL )
			{
				const UpgradeTemplate* upgradeTemplate = TheUpgradeCenter->findUpgrade( planned.upgradeName );
				if ( upgradeTemplate != NULL && obj->affectedByUpgrade( upgradeTemplate ) && !obj->hasUpgrade( upgradeTemplate ) )
					obj->giveUpgrade( upgradeTemplate );
			}

			BodyModuleInterface* body = obj->getBodyModule();
			if ( body )
			{
				Real originalMax = body->getMaxHealth();
				Real newMax = originalMax * 0.25f;
				body->setMaxHealth( newMax, FULLY_HEAL );
			}
			ExperienceTracker* xp = obj->getExperienceTracker();
			if ( xp )
				xp->setVeterancyLevel( LEVEL_HEROIC, FALSE );

			clusterSpawnSuccesses[planned.clusterId] += 1;
			DEBUG_LOG( ( "[Archipelago] Spawned %s at cluster=%s center=(%.1f, %.1f) -> check %s reward=%s",
				planned.templateName.str(),
				planned.clusterId.str(),
				planned.clusterCenter.x,
				planned.clusterCenter.y,
				planned.checkId.str(),
				getAssignedRewardGroupIdForCheck( planned.checkId ).str() ) );
		}
	}

	for ( std::map<AsciiString, Int>::const_iterator it = clusterAssignedCounts.begin(); it != clusterAssignedCounts.end(); ++it )
	{
		const AsciiString& clusterId = it->first;
		const Int plannedCount = it->second;
		const Int spawnedCount = clusterSpawnSuccesses.find( clusterId ) != clusterSpawnSuccesses.end()
			? clusterSpawnSuccesses.find( clusterId )->second
			: 0;
		const Int skippedCount = clusterSpawnSkips.find( clusterId ) != clusterSpawnSkips.end()
			? clusterSpawnSkips.find( clusterId )->second
			: 0;
		DEBUG_LOG( ( "[Archipelago] Cluster spawn summary: cluster=%s planned=%d spawned=%d skipped=%d",
			clusterId.str(), plannedCount, spawnedCount, skippedCount ) );
	}
}

// ------------------------------------------------------------------------------------------------
Real UnlockableCheckSpawner::getDamageOutputScalar( const Object* source ) const
{
	if ( !source || !m_enabled || m_spawnedUnits.empty() )
		return 1.0f;
	for ( size_t i = 0; i < m_spawnedUnits.size(); ++i )
	{
		if ( m_spawnedUnits[i] == source )
			return m_currentMapDamageOutputScalar;
	}
	return 1.0f;
}

// ------------------------------------------------------------------------------------------------
Int UnlockableCheckSpawner::findSpawnedUnitIndex( const Object* obj ) const
{
	if ( obj == NULL )
		return -1;

	for ( size_t i = 0; i < m_spawnedUnits.size(); ++i )
	{
		if ( m_spawnedUnits[i] == obj )
			return (Int)i;
	}

	return -1;
}

// ------------------------------------------------------------------------------------------------
Int UnlockableCheckSpawner::findConfiguredClusterIndex( const MapConfig& config, const AsciiString& clusterId ) const
{
	if ( clusterId.isEmpty() )
		return -1;

	for ( size_t i = 0; i < config.clusterIds.size(); ++i )
	{
		if ( config.clusterIds[i].compareNoCase( clusterId ) == 0 )
			return (Int)i;
	}

	return -1;
}

// ------------------------------------------------------------------------------------------------
Bool UnlockableCheckSpawner::isClusterTemporarilyAlerted( const AsciiString& clusterId ) const
{
	if ( clusterId.isEmpty() || !TheGameLogic )
		return FALSE;

	std::map<AsciiString, UnsignedInt>::const_iterator it = m_clusterAlertUntilFrames.find( clusterId );
	if ( it == m_clusterAlertUntilFrames.end() )
		return FALSE;

	return TheGameLogic->getFrame() <= it->second;
}

// ------------------------------------------------------------------------------------------------
Bool UnlockableCheckSpawner::isSpawnedUnitTemporarilyAlerted( const Object* obj ) const
{
	if ( obj == NULL || !m_enabled || !TheGameLogic )
		return FALSE;

	Int index = findSpawnedUnitIndex( obj );
	if ( index < 0 )
		return FALSE;
	if ( (size_t)index < m_spawnedUnitRetreatActive.size() && m_spawnedUnitRetreatActive[(size_t)index] )
		return FALSE;

	UnsignedInt now = TheGameLogic->getFrame();
	BodyModuleInterface* body = obj->getBodyModule();
	if ( body != NULL )
	{
		UnsignedInt lastDamageFrame = body->getLastDamageTimestamp();
		if ( lastDamageFrame != 0 && now >= lastDamageFrame && ( now - lastDamageFrame ) <= kSpawnedUnitThreatResponseFrames )
			return TRUE;
	}

	if ( (size_t)index < m_spawnedUnitClusterIds.size() )
		return isClusterTemporarilyAlerted( m_spawnedUnitClusterIds[(size_t)index] );

	return FALSE;
}

// ------------------------------------------------------------------------------------------------
void UnlockableCheckSpawner::updateClusterAlertState( UnsignedInt frame )
{
	for ( size_t i = 0; i < m_spawnedUnits.size(); ++i )
	{
		Object* obj = m_spawnedUnits[i];
		if ( obj == NULL || obj->isEffectivelyDead() || i >= m_spawnedUnitLastObservedDamageFrames.size() )
			continue;

		BodyModuleInterface* body = obj->getBodyModule();
		if ( body == NULL )
			continue;

		UnsignedInt lastDamageFrame = body->getLastDamageTimestamp();
		if ( lastDamageFrame == 0 || lastDamageFrame == m_spawnedUnitLastObservedDamageFrames[i] )
			continue;

		m_spawnedUnitLastObservedDamageFrames[i] = lastDamageFrame;
		if ( lastDamageFrame > frame )
			continue;

		if ( i >= m_spawnedUnitClusterIds.size() || m_spawnedUnitClusterIds[i].isEmpty() )
			continue;

		if ( i >= m_spawnedUnitGuardPos.size() || m_currentMapDefendRadius <= 0.0f )
			continue;

		const Coord3D* pos = obj->getPosition();
		const Coord3D& guardPos = m_spawnedUnitGuardPos[i];
		Real dx = pos->x - guardPos.x;
		Real dy = pos->y - guardPos.y;
		Real distSqr = dx * dx + dy * dy;
		Real defendSqr = m_currentMapDefendRadius * m_currentMapDefendRadius;
		if ( distSqr > defendSqr )
			continue;

		UnsignedInt alertUntil = lastDamageFrame + kSpawnedUnitThreatResponseFrames;
		AsciiString clusterId = m_spawnedUnitClusterIds[i];
		std::map<AsciiString, UnsignedInt>::iterator it = m_clusterAlertUntilFrames.find( clusterId );
		if ( it == m_clusterAlertUntilFrames.end() || alertUntil > it->second )
			m_clusterAlertUntilFrames[clusterId] = alertUntil;
		m_clusterAlertThreatPositions[clusterId] = *pos;
	}

	for ( std::map<AsciiString, UnsignedInt>::iterator it = m_clusterAlertUntilFrames.begin(); it != m_clusterAlertUntilFrames.end(); )
	{
		if ( frame > it->second )
		{
			m_clusterAlertThreatPositions.erase( it->first );
			it = m_clusterAlertUntilFrames.erase( it );
		}
		else
		{
			++it;
		}
	}
}

// ------------------------------------------------------------------------------------------------
Real UnlockableCheckSpawner::getEffectiveAcquireRadiusForUnit( const Object* obj ) const
{
	Real baseRadius = m_currentMapDefendRadius > 0.0f ? m_currentMapDefendRadius : m_currentMapMaxChaseRadius;
	if ( obj == NULL || baseRadius <= 0.0f )
		return baseRadius;

	if ( isSpawnedUnitTemporarilyAlerted( obj ) )
		return std::max( baseRadius, kSpawnedUnitThreatResponseVisionRange );

	return baseRadius;
}

// ------------------------------------------------------------------------------------------------
Real UnlockableCheckSpawner::getEffectiveVisionRangeForUnit( const Object* obj ) const
{
	Int index = findSpawnedUnitIndex( obj );
	Real baseVisionRange = kSpawnedUnitMinVisionRange;
	if ( index >= 0 && (size_t)index < m_spawnedUnitBaseVisionRanges.size() )
		baseVisionRange = m_spawnedUnitBaseVisionRanges[(size_t)index];
	if ( index >= 0 && (size_t)index < m_spawnedUnitRetreatActive.size() && m_spawnedUnitRetreatActive[(size_t)index] )
		return std::max( baseVisionRange, kSpawnedUnitMinVisionRange );

	Real targetFloor = kSpawnedUnitMinVisionRange;
	if ( isSpawnedUnitTemporarilyAlerted( obj ) )
		targetFloor = kSpawnedUnitThreatResponseVisionRange;

	return std::max( baseVisionRange, targetFloor );
}

// ------------------------------------------------------------------------------------------------
void UnlockableCheckSpawner::applyRetreatSpeedBoost( Object* obj, size_t index )
{
	if ( obj == NULL || index >= m_spawnedUnitRetreatBoostActive.size() )
		return;

	AIUpdateInterface* ai = obj->getAIUpdateInterface();
	if ( ai == NULL )
		return;

	Locomotor* locomotor = ai->getCurLocomotor();
	if ( locomotor == NULL )
		return;

	BodyModuleInterface* body = obj->getBodyModule();
	if ( body == NULL )
		return;

	if ( !m_spawnedUnitRetreatBoostActive[index] )
	{
		m_spawnedUnitBaseRetreatSpeeds[index] = locomotor->getMaxSpeedForCondition( body->getDamageState() );
		m_spawnedUnitBaseRetreatAccelerations[index] = locomotor->getMaxAcceleration( body->getDamageState() );
		m_spawnedUnitBaseRetreatBraking[index] = locomotor->getBraking();
		m_spawnedUnitBaseRetreatUltraAccurate[index] = locomotor->isUltraAccurate();
		m_spawnedUnitRetreatBoostActive[index] = TRUE;
	}

	if ( m_spawnedUnitBaseRetreatSpeeds[index] > 0.0f )
		locomotor->setMaxSpeed( m_spawnedUnitBaseRetreatSpeeds[index] * kSpawnedUnitRetreatSpeedScalar );
	if ( m_spawnedUnitBaseRetreatAccelerations[index] > 0.0f )
		locomotor->setMaxAcceleration( m_spawnedUnitBaseRetreatAccelerations[index] * kSpawnedUnitRetreatSpeedScalar );
	if ( m_spawnedUnitBaseRetreatBraking[index] > 0.0f )
		locomotor->setMaxBraking( m_spawnedUnitBaseRetreatBraking[index] * kSpawnedUnitRetreatSpeedScalar );
	locomotor->setNoSlowDownAsApproachingDest( TRUE );
	locomotor->setUltraAccurate( TRUE );
	locomotor->startMove();
}

// ------------------------------------------------------------------------------------------------
void UnlockableCheckSpawner::restoreRetreatSpeedBoost( Object* obj, size_t index )
{
	if ( obj == NULL || index >= m_spawnedUnitRetreatBoostActive.size() || !m_spawnedUnitRetreatBoostActive[index] )
		return;

	AIUpdateInterface* ai = obj->getAIUpdateInterface();
	if ( ai == NULL )
		return;

	Locomotor* locomotor = ai->getCurLocomotor();
	if ( locomotor == NULL )
		return;

	if ( m_spawnedUnitBaseRetreatSpeeds[index] > 0.0f )
		locomotor->setMaxSpeed( m_spawnedUnitBaseRetreatSpeeds[index] );
	if ( m_spawnedUnitBaseRetreatAccelerations[index] > 0.0f )
		locomotor->setMaxAcceleration( m_spawnedUnitBaseRetreatAccelerations[index] );
	if ( m_spawnedUnitBaseRetreatBraking[index] > 0.0f )
		locomotor->setMaxBraking( m_spawnedUnitBaseRetreatBraking[index] );
	locomotor->setNoSlowDownAsApproachingDest( FALSE );
	locomotor->setUltraAccurate( m_spawnedUnitBaseRetreatUltraAccurate[index] );

	m_spawnedUnitRetreatBoostActive[index] = FALSE;
	m_spawnedUnitBaseRetreatSpeeds[index] = 0.0f;
	m_spawnedUnitBaseRetreatAccelerations[index] = 0.0f;
	m_spawnedUnitBaseRetreatBraking[index] = 0.0f;
	m_spawnedUnitBaseRetreatNoSlowdown[index] = FALSE;
	m_spawnedUnitBaseRetreatUltraAccurate[index] = FALSE;
}

// ------------------------------------------------------------------------------------------------
void UnlockableCheckSpawner::applyRetreatRepair( Object* obj ) const
{
	if ( obj == NULL || obj->isEffectivelyDead() )
		return;

	BodyModuleInterface* body = obj->getBodyModule();
	if ( body == NULL )
		return;

	const Real maxHealth = body->getMaxHealth();
	const Real currentHealth = body->getHealth();
	if ( maxHealth <= 0.0f || currentHealth >= maxHealth )
		return;

	const Real healAmount = ( maxHealth * kSpawnedUnitRetreatRepairPercentPerSecond ) / (Real)LOGICFRAMES_PER_SECOND;
	if ( healAmount <= 0.0f )
		return;

	obj->attemptHealing( healAmount, obj );
}

// ------------------------------------------------------------------------------------------------
void UnlockableCheckSpawner::applyRetreatMovementAssist( Object* obj, const Coord3D& guardPos, size_t index ) const
{
	if ( obj == NULL || obj->isEffectivelyDead() || index >= m_spawnedUnitBaseRetreatSpeeds.size() )
		return;

	if ( obj->isKindOf( KINDOF_AIRCRAFT ) || obj->isKindOf( KINDOF_STRUCTURE ) )
		return;

	const Coord3D* curPos = obj->getPosition();
	Real dx = guardPos.x - curPos->x;
	Real dy = guardPos.y - curPos->y;
	Real dist = (Real)sqrt( dx * dx + dy * dy );
	if ( dist <= 1.0f )
		return;

	PhysicsBehavior* physics = obj->getPhysics();
	if ( physics == NULL )
		return;

	Real assistedSpeed = 0.0f;
	Real assistedAccel = 0.0f;
	AIUpdateInterface* ai = obj->getAIUpdateInterface();
	BodyModuleInterface* body = obj->getBodyModule();
	if ( ai != NULL && body != NULL && ai->getCurLocomotor() != NULL )
	{
		Locomotor* locomotor = ai->getCurLocomotor();
		assistedSpeed = locomotor->getMaxSpeedForCondition( body->getDamageState() );
		assistedAccel = locomotor->getMaxAcceleration( body->getDamageState() );
	}

	if ( assistedSpeed <= 0.0f )
	{
		assistedSpeed = m_spawnedUnitBaseRetreatSpeeds[index];
		if ( assistedSpeed <= 0.0f )
			assistedSpeed = 45.0f;
	}
	if ( assistedAccel <= 0.0f )
	{
		assistedAccel = m_spawnedUnitBaseRetreatAccelerations[index];
		if ( assistedAccel <= 0.0f )
			assistedAccel = 30.0f;
	}

	assistedSpeed *= kSpawnedUnitRetreatAssistScalar;
	assistedAccel *= kSpawnedUnitRetreatAssistScalar;
	if ( assistedSpeed < kSpawnedUnitRetreatAssistMinSpeed )
		assistedSpeed = kSpawnedUnitRetreatAssistMinSpeed;

	Coord3D dir;
	dir.x = dx / dist;
	dir.y = dy / dist;
	dir.z = 0.0f;

	const Coord3D* velocity = physics->getVelocity();
	Real currentSpeedAlongDir = 0.0f;
	if ( velocity != NULL )
		currentSpeedAlongDir = velocity->x * dir.x + velocity->y * dir.y;
	if ( currentSpeedAlongDir < 0.0f )
		currentSpeedAlongDir = 0.0f;

	Real desiredSpeed = assistedSpeed;
	if ( desiredSpeed > dist )
		desiredSpeed = dist;

	Real speedDelta = desiredSpeed - currentSpeedAlongDir;
	if ( speedDelta <= 0.0f )
		return;

	Real mass = physics->getMass();
	Real accelForce = mass * assistedAccel;
	Real maxForceNeeded = mass * speedDelta;
	if ( fabs( accelForce ) > fabs( maxForceNeeded ) )
		accelForce = maxForceNeeded;

	Coord3D force;
	force.x = accelForce * dir.x;
	force.y = accelForce * dir.y;
	force.z = 0.0f;
	physics->applyMotiveForce( &force );
}

// ------------------------------------------------------------------------------------------------
Object* UnlockableCheckSpawner::findNearestEnemyInfantryForCrusher( Object* obj, Real maxRange ) const
{
	if ( obj == NULL || ThePartitionManager == NULL || maxRange <= 0.0f )
		return NULL;

	Player* owner = obj->getControllingPlayer();
	if ( owner == NULL )
		return NULL;

	PartitionFilterPlayerAffiliation enemyFilter( owner, ALLOW_ENEMIES, TRUE );
	PartitionFilter* filters[2] = { &enemyFilter, NULL };
	SimpleObjectIterator* iter = ThePartitionManager->iterateObjectsInRange(
		obj,
		maxRange,
		FROM_CENTER_2D,
		filters,
		ITER_SORTED_NEAR_TO_FAR );
	if ( iter == NULL )
		return NULL;

	Object* bestTarget = NULL;
	for ( Object* other = iter->first(); other != NULL; other = iter->next() )
	{
		if ( other == obj || other->isEffectivelyDead() || other->isDestroyed() )
			continue;
		if ( !other->isKindOf( KINDOF_INFANTRY ) )
			continue;
		if ( other->isKindOf( KINDOF_AIRCRAFT ) || other->isKindOf( KINDOF_STRUCTURE ) )
			continue;
		bestTarget = other;
		break;
	}

	deleteInstance( iter );
	return bestTarget;
}

// ------------------------------------------------------------------------------------------------
Object* UnlockableCheckSpawner::findNearestEnemyCombatTarget( Object* obj, Real maxRange, Bool allowStructures ) const
{
	if ( obj == NULL || ThePartitionManager == NULL || maxRange <= 0.0f )
		return NULL;

	Player* owner = obj->getControllingPlayer();
	if ( owner == NULL )
		return NULL;

	PartitionFilterPlayerAffiliation enemyFilter( owner, ALLOW_ENEMIES, TRUE );
	PartitionFilter* filters[2] = { &enemyFilter, NULL };
	SimpleObjectIterator* iter = ThePartitionManager->iterateObjectsInRange(
		obj,
		maxRange,
		FROM_CENTER_2D,
		filters,
		ITER_SORTED_NEAR_TO_FAR );
	if ( iter == NULL )
		return NULL;

	Object* bestTarget = NULL;
	for ( Object* other = iter->first(); other != NULL; other = iter->next() )
	{
		if ( other == obj || other->isEffectivelyDead() || other->isDestroyed() )
			continue;
		if ( other->isKindOf( KINDOF_AIRCRAFT ) )
			continue;
		if ( other->isKindOf( KINDOF_INERT ) || other->isKindOf( KINDOF_PROJECTILE ) )
			continue;
		if ( !allowStructures && other->isKindOf( KINDOF_STRUCTURE ) )
			continue;
		bestTarget = other;
		break;
	}

	deleteInstance( iter );
	return bestTarget;
}

// ------------------------------------------------------------------------------------------------
AsciiString UnlockableCheckSpawner::getCanonicalSpawnTemplateName( const AsciiString& templateName ) const
{
	if ( templateName.isEmpty() )
		return AsciiString::TheEmptyString;

	const char* underscore = strchr( templateName.str(), '_' );
	if ( underscore != NULL && underscore[1] != '\0' )
		return AsciiString( underscore + 1 );

	return templateName;
}

// ------------------------------------------------------------------------------------------------
Bool UnlockableCheckSpawner::isCrusherChaseTemplate( const AsciiString& canonicalTemplateName ) const
{
	return canonicalTemplateName.compareNoCase( "ChinaVehicleDozer" ) == 0
		|| canonicalTemplateName.compareNoCase( "ChinaVehicleSupplyTruck" ) == 0;
}

// ------------------------------------------------------------------------------------------------
Bool UnlockableCheckSpawner::isSupportAttackTemplate( const AsciiString& canonicalTemplateName ) const
{
	return canonicalTemplateName.compareNoCase( "ChinaTankECM" ) == 0
		|| canonicalTemplateName.compareNoCase( "ChinaVehicleNukeLauncher" ) == 0
		|| canonicalTemplateName.compareNoCase( "ChinaVehicleInfernoCannon" ) == 0
		|| canonicalTemplateName.compareNoCase( "ChinaVehicleTroopCrawler" ) == 0;
}

// ------------------------------------------------------------------------------------------------
Bool UnlockableCheckSpawner::isSpawnedUnit( const Object* obj ) const
{
	return ( obj != NULL && m_enabled && findSpawnedUnitIndex( obj ) >= 0 ) ? TRUE : FALSE;
}

// ------------------------------------------------------------------------------------------------
const Coord3D* UnlockableCheckSpawner::getGuardPositionForUnit( const Object* obj ) const
{
	if ( !obj || !m_enabled || m_spawnedUnits.empty() || m_spawnedUnitGuardPos.size() != m_spawnedUnits.size() )
		return nullptr;
	for ( size_t i = 0; i < m_spawnedUnits.size(); ++i )
	{
		if ( m_spawnedUnits[i] == obj )
			return &m_spawnedUnitGuardPos[i];
	}
	return nullptr;
}

// ------------------------------------------------------------------------------------------------
void UnlockableCheckSpawner::update()
{
	if ( !m_enabled || !TheGameLogic )
		return;

	UnsignedInt frame = TheGameLogic->getFrame();

	if ( m_hasPendingReroll )
	{
		Bool hasLingeringSpawnedObjects = FALSE;
		for ( Object* obj = TheGameLogic->getFirstObject(); obj != NULL; obj = obj->getNextObject() )
		{
			if ( obj->isEffectivelyDead() || obj->isDestroyed() )
				continue;

			const AsciiString& checkId = obj->getArchipelagoCheckId();
			if ( checkId.isEmpty() )
				continue;

			if ( std::find( m_pendingRerollConfig.unitCheckIds.begin(), m_pendingRerollConfig.unitCheckIds.end(), checkId )
				!= m_pendingRerollConfig.unitCheckIds.end() )
			{
				hasLingeringSpawnedObjects = TRUE;
				break;
			}
		}

		if ( !hasLingeringSpawnedObjects && frame >= m_pendingRerollSpawnFrame )
		{
			MapConfig rerollConfig = m_pendingRerollConfig;
			m_hasPendingReroll = FALSE;
			m_pendingRerollSpawnFrame = 0u;
			spawnUnitsForMap( m_currentMapLeafName, rerollConfig );
		}
	}

	if ( m_spawnedUnits.empty() )
		return;

	PlayerMaskType localMask = 0;
	if ( ThePartitionManager && ThePlayerList )
	{
		Player* localPlayer = ThePlayerList->getLocalPlayer();
		if ( localPlayer )
			localMask = localPlayer->getPlayerMask();
	}

	updateClusterAlertState( frame );

	// Smooth sine-based rainbow - no segment boundaries, fluid flow. Tint is additive (-1..1 like FRENZY_COLOR).
	// Tint: subtle; Radar: stronger for visibility.
	static const UnsignedInt kRainbowCycleFrames = 240u;
	static const Real kTintStrength = 0.03f;  // Very subtle on model; minimap uses full saturation
	static const Real kTwoPi = 6.28318530717958647692f;
	static RGBColor s_rainbowColor;
	{
		Real hue = (Real)( frame % kRainbowCycleFrames ) / (Real)kRainbowCycleFrames;
		// Sine-based: smooth continuous transition, no HSV segment pauses
		Real r = 0.5f + 0.5f * (Real)sin( hue * kTwoPi );
		Real g = 0.5f + 0.5f * (Real)sin( hue * kTwoPi + kTwoPi / 3.0f );
		Real b = 0.5f + 0.5f * (Real)sin( hue * kTwoPi + 2.0f * kTwoPi / 3.0f );
		// Map 0..1 to ±kTintStrength for model tint
		s_rainbowColor.red   = ( r - 0.5f ) * ( kTintStrength * 2.0f );
		s_rainbowColor.green = ( g - 0.5f ) * ( kTintStrength * 2.0f );
		s_rainbowColor.blue  = ( b - 0.5f ) * ( kTintStrength * 2.0f );
	}

	auto shouldIssueAggroCommand = [&]( size_t index, Object* target ) -> Bool
	{
		if ( index >= m_spawnedUnitLastAggroCommandFrames.size() || index >= m_spawnedUnitLastAggroTargetIds.size() )
			return TRUE;

		const ObjectID targetId = target ? target->getID() : INVALID_ID;
		if ( m_spawnedUnitLastAggroTargetIds[index] != targetId )
			return TRUE;

		return ( frame - m_spawnedUnitLastAggroCommandFrames[index] ) >= kSpawnedUnitAggroCommandThrottleFrames;
	};

	auto markAggroCommandIssued = [&]( size_t index, Object* target ) -> void
	{
		if ( index >= m_spawnedUnitLastAggroCommandFrames.size() || index >= m_spawnedUnitLastAggroTargetIds.size() )
			return;
		m_spawnedUnitLastAggroCommandFrames[index] = frame;
		m_spawnedUnitLastAggroTargetIds[index] = target ? target->getID() : INVALID_ID;
	};

	for ( size_t i = 0; i < m_spawnedUnits.size(); )
	{
		Object* obj = m_spawnedUnits[i];
		if ( !obj || obj->isEffectivelyDead() )
		{
			if ( obj && i < m_spawnedUnitRetreatBoostActive.size() )
				restoreRetreatSpeedBoost( obj, i );

			// Undo our reveal before removing (must do or spawn spot stays revealed)
			if ( localMask && ThePartitionManager && i < m_spawnedUnitLastRevealPos.size() && i < m_spawnedUnitHasRevealed.size() && m_spawnedUnitHasRevealed[i] )
			{
				const Coord3D& last = m_spawnedUnitLastRevealPos[i];
				ThePartitionManager->undoShroudReveal( last.x, last.y, 50.0f, localMask );
			}
			m_spawnedUnits.erase( m_spawnedUnits.begin() + (Int)i );
			m_spawnedUnitLastRevealPos.erase( m_spawnedUnitLastRevealPos.begin() + (Int)i );
			m_spawnedUnitGuardPos.erase( m_spawnedUnitGuardPos.begin() + (Int)i );
			m_spawnedUnitClusterIds.erase( m_spawnedUnitClusterIds.begin() + (Int)i );
			m_spawnedUnitHasRevealed.erase( m_spawnedUnitHasRevealed.begin() + (Int)i );
			m_spawnedUnitBaseVisionRanges.erase( m_spawnedUnitBaseVisionRanges.begin() + (Int)i );
			m_spawnedUnitLastObservedDamageFrames.erase( m_spawnedUnitLastObservedDamageFrames.begin() + (Int)i );
			m_spawnedUnitRetreatBoostActive.erase( m_spawnedUnitRetreatBoostActive.begin() + (Int)i );
			m_spawnedUnitRetreatActive.erase( m_spawnedUnitRetreatActive.begin() + (Int)i );
			m_spawnedUnitRetreatHardPull.erase( m_spawnedUnitRetreatHardPull.begin() + (Int)i );
			m_spawnedUnitRetreatStartFrames.erase( m_spawnedUnitRetreatStartFrames.begin() + (Int)i );
			m_spawnedUnitBaseRetreatSpeeds.erase( m_spawnedUnitBaseRetreatSpeeds.begin() + (Int)i );
			m_spawnedUnitBaseRetreatAccelerations.erase( m_spawnedUnitBaseRetreatAccelerations.begin() + (Int)i );
			m_spawnedUnitBaseRetreatBraking.erase( m_spawnedUnitBaseRetreatBraking.begin() + (Int)i );
			m_spawnedUnitBaseRetreatNoSlowdown.erase( m_spawnedUnitBaseRetreatNoSlowdown.begin() + (Int)i );
			m_spawnedUnitBaseRetreatUltraAccurate.erase( m_spawnedUnitBaseRetreatUltraAccurate.begin() + (Int)i );
			m_spawnedUnitLastAggroCommandFrames.erase( m_spawnedUnitLastAggroCommandFrames.begin() + (Int)i );
			m_spawnedUnitLastAggroTargetIds.erase( m_spawnedUnitLastAggroTargetIds.begin() + (Int)i );
			continue;
		}

		// Shroud: always undo at last before revealing at current (prevents stacking, reveal follows unit)
		const Real kRevealRadius = 50.0f;
		if ( localMask && ThePartitionManager && i < m_spawnedUnitLastRevealPos.size() && i < m_spawnedUnitHasRevealed.size() )
		{
			const Coord3D* pos = obj->getPosition();
			Coord3D& last = m_spawnedUnitLastRevealPos[i];
			if ( m_spawnedUnitHasRevealed[i] )
				ThePartitionManager->undoShroudReveal( last.x, last.y, kRevealRadius, localMask );
			ThePartitionManager->doShroudReveal( pos->x, pos->y, kRevealRadius, localMask );
			last = *pos;
			m_spawnedUnitHasRevealed[i] = TRUE;
		}

		// Rainbow tint (re-apply every frame; Drawable update may clear it)
		Drawable* draw = obj->getDrawable();
		if ( draw )
			draw->colorTint( &s_rainbowColor );

		Real desiredVisionRange = getEffectiveVisionRangeForUnit( obj );
		if ( desiredVisionRange > 0.0f && fabs( obj->getVisionRange() - desiredVisionRange ) > 0.5f )
			obj->setVisionRange( desiredVisionRange );

		// Rainbow on minimap: full saturation for visibility (stronger than model tint)
		Real hue = (Real)( frame % kRainbowCycleFrames ) / (Real)kRainbowCycleFrames;
		Real mr = 0.5f + 0.5f * (Real)sin( hue * kTwoPi );
		Real mg = 0.5f + 0.5f * (Real)sin( hue * kTwoPi + kTwoPi / 3.0f );
		Real mb = 0.5f + 0.5f * (Real)sin( hue * kTwoPi + 2.0f * kTwoPi / 3.0f );
		Color mapColor = GameMakeColor(
			(UnsignedByte)( mr * 255.0f ),
			(UnsignedByte)( mg * 255.0f ),
			(UnsignedByte)( mb * 255.0f ),
			255 );
		obj->setCustomIndicatorColor( mapColor );
		if ( TheRadar )
		{
			RadarObject* ro = obj->friend_getRadarData();
			if ( ro )
				ro->setColor( mapColor );
		}

		// Pull back: outside MaxChaseRadius always; between DefendRadius and MaxChaseRadius only when idle.
		// If unit has a live target in range, let it attack in place until target dies, then force return.
		if ( m_currentMapMaxChaseRadius > 0.0f && i < m_spawnedUnitGuardPos.size() )
		{
			AIUpdateInterface* ai = obj->getAIUpdateInterface();
			if ( ai )
			{
				const Coord3D* curPos = obj->getPosition();
				const Coord3D& spawnPos = m_spawnedUnitGuardPos[i];
				Real dx = curPos->x - spawnPos.x;
				Real dy = curPos->y - spawnPos.y;
				Real distSqr = dx * dx + dy * dy;
				Real maxChaseSqr = m_currentMapMaxChaseRadius * m_currentMapMaxChaseRadius;
				Real defendSqr = m_currentMapDefendRadius > 0.0f
					? ( m_currentMapDefendRadius * m_currentMapDefendRadius )
					: 0.0f;

				Real retreatCompleteSqr = kSpawnedUnitRetreatCompletionRadius * kSpawnedUnitRetreatCompletionRadius;
				Bool shouldPull = FALSE;
				Bool hardPull = FALSE;
				if ( m_spawnedUnitRetreatActive[i] )
				{
					shouldPull = distSqr > retreatCompleteSqr;
					hardPull = m_spawnedUnitRetreatHardPull[i];
				}
				else if ( distSqr > maxChaseSqr )
				{
					shouldPull = TRUE;
					hardPull = TRUE;
				}
				else if ( defendSqr > 0.0f && distSqr > defendSqr )
				{
					Object* victim = ai->getCurrentVictim();
					if ( !victim || victim->isEffectivelyDead() )
						shouldPull = TRUE;
				}
				if ( shouldPull )
				{
					Bool enteringRetreat = !m_spawnedUnitRetreatActive[i];
					if ( enteringRetreat )
					{
						m_spawnedUnitRetreatActive[i] = TRUE;
						m_spawnedUnitRetreatHardPull[i] = hardPull;
						m_spawnedUnitRetreatStartFrames[i] = frame;
						if ( i < m_spawnedUnitLastAggroTargetIds.size() )
							m_spawnedUnitLastAggroTargetIds[i] = INVALID_ID;
						ai->setCurrentVictim( NULL );
						ai->clearWaypointQueue();
						ai->chooseLocomotorSet( LOCOMOTORSET_NORMAL );
						ai->aiMoveToPosition( &spawnPos, CMD_FROM_SCRIPT );
					}
					else if ( hardPull )
					{
						m_spawnedUnitRetreatHardPull[i] = TRUE;
					}

					applyRetreatSpeedBoost( obj, i );
					applyRetreatRepair( obj );
					if ( ai->getCurLocomotor() )
						ai->getCurLocomotor()->startMove();

					if ( m_spawnedUnitRetreatHardPull[i] )
					{
						Bool insideRetreatCompletionRadius = ( distSqr <= retreatCompleteSqr );
						if ( insideRetreatCompletionRadius )
						{
							m_spawnedUnitRetreatHardPull[i] = FALSE;
						}
						else
						{
							Bool facingGuard = FALSE;
							const Coord3D* unitDir = obj->getUnitDirectionVector2D();
							if ( unitDir != NULL && distSqr > 1.0f )
							{
								const Real distVal = (Real)sqrt( distSqr );
								const Real dirToGuardX = ( spawnPos.x - curPos->x ) / distVal;
								const Real dirToGuardY = ( spawnPos.y - curPos->y ) / distVal;
								const Real facingDot = unitDir->x * dirToGuardX + unitDir->y * dirToGuardY;
								facingGuard = ( facingDot >= kSpawnedUnitRetreatFacingDotThreshold );
							}

							Bool dragDelayElapsed = ( frame - m_spawnedUnitRetreatStartFrames[i] ) >= kSpawnedUnitRetreatDragDelayFrames;
							if ( facingGuard || dragDelayElapsed )
								applyRetreatMovementAssist( obj, spawnPos, i );
						}
					}
				}
				else
				{
					restoreRetreatSpeedBoost( obj, i );
					m_spawnedUnitRetreatActive[i] = FALSE;
					m_spawnedUnitRetreatHardPull[i] = FALSE;
					m_spawnedUnitRetreatStartFrames[i] = 0u;
					if ( i < m_spawnedUnitLastAggroTargetIds.size() )
						m_spawnedUnitLastAggroTargetIds[i] = INVALID_ID;

					const ThingTemplate* tmpl = obj->getTemplate();
					const AsciiString canonicalTemplateName = tmpl ? getCanonicalSpawnTemplateName( tmpl->getName() ) : AsciiString::TheEmptyString;
					if ( isCrusherChaseTemplate( canonicalTemplateName )
						|| ( obj->getCrusherLevel() > 0 && obj->getCurrentWeapon() == NULL ) )
					{
						const Real acquireRadius = getEffectiveAcquireRadiusForUnit( obj );
						Object* infantryTarget = findNearestEnemyInfantryForCrusher( obj, acquireRadius );
						if ( infantryTarget != NULL && shouldIssueAggroCommand( i, infantryTarget ) )
						{
							ai->clearWaypointQueue();
							ai->chooseLocomotorSet( LOCOMOTORSET_NORMAL );
							ai->setCurrentVictim( infantryTarget );
							const Coord3D* targetPos = infantryTarget->getPosition();
							if ( targetPos != NULL )
								ai->aiAttackMoveToPosition( targetPos, NO_MAX_SHOTS_LIMIT, CMD_FROM_SCRIPT );
							else
								ai->aiAttackObject( infantryTarget, NO_MAX_SHOTS_LIMIT, CMD_FROM_SCRIPT );
							markAggroCommandIssued( i, infantryTarget );
						}
					}
					else if ( isSupportAttackTemplate( canonicalTemplateName ) )
					{
						const Real acquireRadius = getEffectiveAcquireRadiusForUnit( obj );
						const Bool allowStructures =
							canonicalTemplateName.compareNoCase( "ChinaVehicleNukeLauncher" ) == 0
							|| canonicalTemplateName.compareNoCase( "ChinaVehicleInfernoCannon" ) == 0;
						Object* combatTarget = ai->getCurrentVictim();
						if ( combatTarget != NULL && ( combatTarget->isEffectivelyDead() || combatTarget->isDestroyed() ) )
							combatTarget = NULL;
						if ( combatTarget == NULL )
							combatTarget = findNearestEnemyCombatTarget( obj, acquireRadius, allowStructures );
						const Bool hasLivingVictim = ai->getCurrentVictim() != NULL
							&& !ai->getCurrentVictim()->isEffectivelyDead()
							&& !ai->getCurrentVictim()->isDestroyed();
						if ( combatTarget != NULL && !hasLivingVictim && shouldIssueAggroCommand( i, combatTarget ) )
						{
							ai->clearWaypointQueue();
							ai->chooseLocomotorSet( LOCOMOTORSET_NORMAL );
							ai->setCurrentVictim( combatTarget );
							if ( canonicalTemplateName.compareNoCase( "ChinaTankECM" ) == 0 )
							{
								const Coord3D* targetPos = combatTarget->getPosition();
								if ( targetPos != NULL )
									ai->aiMoveToPosition( targetPos, CMD_FROM_SCRIPT );
							}
							else if ( canonicalTemplateName.compareNoCase( "ChinaVehicleTroopCrawler" ) == 0 )
							{
								ai->aiAttackObject( combatTarget, NO_MAX_SHOTS_LIMIT, CMD_FROM_SCRIPT );
							}
							else if ( canonicalTemplateName.compareNoCase( "ChinaVehicleNukeLauncher" ) == 0
								|| canonicalTemplateName.compareNoCase( "ChinaVehicleInfernoCannon" ) == 0 )
							{
								ai->aiAttackObject( combatTarget, NO_MAX_SHOTS_LIMIT, CMD_FROM_SCRIPT );
							}
							else
							{
								ai->aiAttackObject( combatTarget, NO_MAX_SHOTS_LIMIT, CMD_FROM_SCRIPT );
							}
							markAggroCommandIssued( i, combatTarget );
						}
					}
				}
			}
		}

		++i;
	}
}

// ------------------------------------------------------------------------------------------------
void UnlockableCheckSpawner::onArchipelagoCheckKilled( const Object* victim, Bool isNewCheck )
{
	if ( !victim || !m_enabled || m_currentMapAllCheckIds.empty() )
		return;

	const AsciiString& checkId = victim->getArchipelagoCheckId();
	if ( checkId.isEmpty() )
		return;

	if ( std::find( m_currentMapAllCheckIds.begin(), m_currentMapAllCheckIds.end(), checkId ) == m_currentMapAllCheckIds.end() )
		return;

	if ( !isNewCheck )
	{
		m_unlockedCheckIds.insert( checkId );
		if ( m_repeatLocalRewardsForCompletedChecks && TheArchipelagoState )
		{
			AsciiString rewardGroupId = getAssignedRewardGroupIdForCheck( checkId );
			ArchipelagoState::UnlockItemOutcome replayOutcome = TheArchipelagoState->replayConfiguredCheckReward( checkId, rewardGroupId, TRUE );
			Player* localPlayer = ThePlayerList ? ThePlayerList->getLocalPlayer() : NULL;
			if ( localPlayer && replayOutcome.cashAward > 0 )
				localPlayer->getMoney()->deposit( replayOutcome.cashAward );
			DEBUG_LOG( ( "[Archipelago] Replayed duplicate check reward for %s cash=%d group=%s",
				checkId.str(),
				replayOutcome.cashAward,
				replayOutcome.groupId.str() ) );
		}
		else
		{
			DEBUG_LOG( ( "[Archipelago] Ignored duplicate check completion for %s", checkId.str() ) );
		}
		return;
	}

	m_unlockedCheckIds.insert( checkId );

	if ( !TheArchipelagoState )
		return;

	AsciiString rewardGroupId = getAssignedRewardGroupIdForCheck( checkId );
	ArchipelagoState::UnlockItemOutcome outcome;
	if ( rewardGroupId.isNotEmpty() )
		outcome = TheArchipelagoState->applyConfiguredCheckReward( checkId, rewardGroupId, TRUE );
	else
		outcome = TheArchipelagoState->consumeLocalFallbackUnlockItem( checkId, TRUE );
	Player* localPlayer = ThePlayerList ? ThePlayerList->getLocalPlayer() : nullptr;
	if ( localPlayer && outcome.cashAward > 0 )
		localPlayer->getMoney()->deposit( outcome.cashAward );

	DEBUG_LOG( ( "[Archipelago] Reward for check %s result=%d cash=%d group=%s configured=%d",
		checkId.str(),
		(Int)outcome.result,
		outcome.cashAward,
		outcome.groupId.str(),
		rewardGroupId.isNotEmpty() ? 1 : 0 ) );
}

// ------------------------------------------------------------------------------------------------
void UnlockableCheckSpawner::reportDebugStatus( void ) const
{
	if ( TheInGameUI == NULL )
		return;

	Int aliveCount = 0;
	Int deadCount = 0;
	Int inertCount = 0;
	for ( size_t i = 0; i < m_spawnedUnits.size(); ++i )
	{
		const Object* obj = m_spawnedUnits[i];
		if ( obj == NULL )
		{
			++deadCount;
			continue;
		}
		if ( obj->isEffectivelyDead() || obj->isDestroyed() )
		{
			++deadCount;
			continue;
		}
		if ( obj->isKindOf( KINDOF_INERT ) )
		{
			++inertCount;
			continue;
		}
		++aliveCount;
	}

	UnicodeString summary;
	summary.format(
		L"[ARCHIPELAGO] Spawned checks %d/%d complete, units alive=%d dead=%d inert=%d",
		(Int)m_unlockedCheckIds.size(),
		(Int)m_currentMapAllCheckIds.size(),
		aliveCount,
		deadCount,
		inertCount );
	TheInGameUI->messageNoFormat( summary );

	UnicodeString leash;
	leash.format(
		L"[ARCHIPELAGO] Spawn leash: defend %.0f, chase %.0f, tracked units=%d",
		m_currentMapDefendRadius,
		m_currentMapMaxChaseRadius,
		(Int)m_spawnedUnits.size() );
	TheInGameUI->messageNoFormat( leash );

	for ( size_t i = 0; i < m_spawnedUnits.size(); ++i )
	{
		const Object* obj = m_spawnedUnits[i];
		if ( obj == NULL )
			continue;
		AsciiString checkId = obj->getArchipelagoCheckId();
		AsciiString rewardLabel = getRewardLabelForCheckId( checkId );
		const char* stateLabel = ( obj->isEffectivelyDead() || obj->isDestroyed() ) ? "dead" : ( obj->isKindOf( KINDOF_INERT ) ? "inert" : "alive" );
		UnicodeString line;
		line.format(
			L"[ARCHIPELAGO] %hs -> %hs [%hs] cluster=%hs anchor=(%.0f, %.0f)",
			checkId.str(),
			rewardLabel.isNotEmpty() ? rewardLabel.str() : "<unassigned>",
			stateLabel,
			i < m_spawnedUnitClusterIds.size() && m_spawnedUnitClusterIds[i].isNotEmpty() ? m_spawnedUnitClusterIds[i].str() : "<none>",
			i < m_spawnedUnitGuardPos.size() ? m_spawnedUnitGuardPos[i].x : 0.0f,
			i < m_spawnedUnitGuardPos.size() ? m_spawnedUnitGuardPos[i].y : 0.0f );
		TheInGameUI->messageNoFormat( line );
	}
}

// ------------------------------------------------------------------------------------------------
void UnlockableCheckSpawner::dumpDebugState( void ) const
{
	AsciiString path;
	if ( TheGlobalData != NULL )
	{
		path = TheGlobalData->getPath_UserData();
		path.concat( "Archipelago\\" );
	}
	if ( path.isEmpty() )
		path = ".\\";

	if ( TheFileSystem != NULL )
		TheFileSystem->createDirectory( path );

	path.concat( "ArchipelagoSpawnedUnitState.json" );
	std::ofstream file( path.str() );
	if ( !file.is_open() )
		return;

	file << "{\n";
	file << "  \"trackedSpawnedUnits\": " << (Int)m_spawnedUnits.size() << ",\n";
	file << "  \"completedChecks\": " << (Int)m_unlockedCheckIds.size() << ",\n";
	file << "  \"totalChecks\": " << (Int)m_currentMapAllCheckIds.size() << ",\n";
	file << "  \"defendRadius\": " << m_currentMapDefendRadius << ",\n";
	file << "  \"maxChaseRadius\": " << m_currentMapMaxChaseRadius << ",\n";
	file << "  \"units\": [\n";

	for ( size_t i = 0; i < m_spawnedUnits.size(); ++i )
	{
		const Object* obj = m_spawnedUnits[i];
		file << "    {\n";
		file << "      \"index\": " << (Int)i << ",\n";
		file << "      \"objectId\": " << ( obj ? obj->getID() : 0 ) << ",\n";
		file << "      \"template\": \"";
		if ( obj != NULL && obj->getTemplate() != NULL )
			writeEscapedJsonString( file, obj->getTemplate()->getName().str() );
		file << "\",\n";
		file << "      \"checkId\": \"";
		if ( obj != NULL )
			writeEscapedJsonString( file, obj->getArchipelagoCheckId().str() );
		file << "\",\n";
		file << "      \"rewardGroupId\": \"";
		if ( obj != NULL )
			writeEscapedJsonString( file, getAssignedRewardGroupIdForCheck( obj->getArchipelagoCheckId() ).str() );
		file << "\",\n";
		file << "      \"rewardLabel\": \"";
		if ( obj != NULL )
			writeEscapedJsonString( file, getRewardLabelForCheckId( obj->getArchipelagoCheckId() ).str() );
		file << "\",\n";
		file << "      \"clusterId\": \"";
		if ( i < m_spawnedUnitClusterIds.size() )
			writeEscapedJsonString( file, m_spawnedUnitClusterIds[i].str() );
		file << "\",\n";
		file << "      \"alive\": " << ( obj != NULL && !obj->isEffectivelyDead() && !obj->isDestroyed() ? "true" : "false" ) << ",\n";
		file << "      \"inert\": " << ( obj != NULL && obj->isKindOf( KINDOF_INERT ) ? "true" : "false" ) << ",\n";
		file << "      \"spawnedCheckUnit\": " << ( obj != NULL && isSpawnedUnit( obj ) ? "true" : "false" ) << ",\n";
		file << "      \"defendRadius\": " << m_currentMapDefendRadius << ",\n";
		file << "      \"maxChaseRadius\": " << m_currentMapMaxChaseRadius << ",\n";
		file << "      \"currentPosition\": ";
		if ( obj != NULL && obj->getPosition() != NULL )
		{
			const Coord3D* pos = obj->getPosition();
			file << "{ \"x\": " << pos->x
				<< ", \"y\": " << pos->y
				<< ", \"z\": " << pos->z << " },\n";
		}
		else
		{
			file << "null,\n";
		}
		file << "      \"guardPosition\": ";
		if ( i < m_spawnedUnitGuardPos.size() )
		{
			file << "{ \"x\": " << m_spawnedUnitGuardPos[i].x
				<< ", \"y\": " << m_spawnedUnitGuardPos[i].y
				<< ", \"z\": " << m_spawnedUnitGuardPos[i].z << " }";
		}
		else
		{
			file << "null";
		}
		file << "\n";
		file << "    }";
		if ( i + 1 < m_spawnedUnits.size() )
			file << ",";
		file << "\n";
	}

	file << "  ]\n";
	file << "}\n";
	file.close();

	if ( TheInGameUI != NULL )
	{
		UnicodeString msg;
		msg.format( L"[ARCHIPELAGO] Wrote spawned-unit debug state to %hs", path.str() );
		TheInGameUI->messageNoFormat( msg );
	}
}

// ------------------------------------------------------------------------------------------------
void UnlockableCheckSpawner::clearSpawnedUnitsOnly( void )
{
	PlayerMaskType localMask = 0;
	if ( ThePlayerList )
	{
		Player* localPlayer = ThePlayerList->getLocalPlayer();
		if ( localPlayer )
			localMask = localPlayer->getPlayerMask();
	}

	for ( size_t i = 0; i < m_spawnedUnits.size(); ++i )
	{
		Object* obj = m_spawnedUnits[i];
		if ( obj != NULL )
		{
			if ( i < m_spawnedUnitRetreatBoostActive.size() )
				restoreRetreatSpeedBoost( obj, i );
			if ( localMask && ThePartitionManager && i < m_spawnedUnitLastRevealPos.size() && i < m_spawnedUnitHasRevealed.size() && m_spawnedUnitHasRevealed[i] )
			{
				const Coord3D& last = m_spawnedUnitLastRevealPos[i];
				ThePartitionManager->undoShroudReveal( last.x, last.y, 50.0f, localMask );
			}
			if ( TheGameLogic )
				TheGameLogic->destroyObject( obj );
		}
	}

	m_spawnedUnits.clear();
	m_spawnedUnitLastRevealPos.clear();
	m_spawnedUnitGuardPos.clear();
	m_spawnedUnitClusterIds.clear();
	m_spawnedUnitHasRevealed.clear();
	m_spawnedUnitBaseVisionRanges.clear();
	m_spawnedUnitLastObservedDamageFrames.clear();
	m_spawnedUnitRetreatBoostActive.clear();
	m_spawnedUnitRetreatActive.clear();
	m_spawnedUnitRetreatHardPull.clear();
	m_spawnedUnitRetreatStartFrames.clear();
	m_spawnedUnitBaseRetreatSpeeds.clear();
	m_spawnedUnitBaseRetreatAccelerations.clear();
	m_spawnedUnitBaseRetreatBraking.clear();
	m_spawnedUnitBaseRetreatNoSlowdown.clear();
	m_spawnedUnitBaseRetreatUltraAccurate.clear();
	m_spawnedUnitLastAggroCommandFrames.clear();
	m_spawnedUnitLastAggroTargetIds.clear();
	m_clusterAlertUntilFrames.clear();
	m_clusterAlertThreatPositions.clear();
}

// ------------------------------------------------------------------------------------------------
Bool UnlockableCheckSpawner::rerollCurrentMapSpawns( void )
{
	if ( !m_enabled || !m_hasCurrentMapConfig )
		return FALSE;

	clearSpawnedUnitsOnly();

	MapConfig rerollConfig = m_currentMapConfig;
	++m_currentMapRerollCount;
	rerollConfig.configSeed = m_currentMapConfig.configSeed + ( m_currentMapRerollCount * 7919u );
	DEBUG_LOG( ( "[Archipelago] Rerolling current map spawns for %s seed=%u reroll=%u",
		m_currentMapLeafName.str(), rerollConfig.configSeed, m_currentMapRerollCount ) );
	m_pendingRerollConfig = rerollConfig;
	m_hasPendingReroll = TRUE;
	m_pendingRerollSpawnFrame = TheGameLogic ? ( TheGameLogic->getFrame() + kSpawnedUnitRerollRespawnDelayFrames ) : 0u;
	return TRUE;
}

// ------------------------------------------------------------------------------------------------
void UnlockableCheckSpawner::tagBuildingsForMap( const AsciiString& mapName, const MapConfig& config )
{
	if ( config.buildingTemplates.empty() || config.buildingCheckIds.empty() )
		return;

	// Collect objects matching each template
	std::vector<std::vector<Object*>> byTemplate( config.buildingTemplates.size() );
	for ( Object* obj = TheGameLogic->getFirstObject(); obj; obj = obj->getNextObject() )
	{
		if ( obj->isEffectivelyDead() )
			continue;
		if ( !obj->getTemplate()->isKindOf( KINDOF_STRUCTURE ) )
			continue;

		const AsciiString& tmplName = obj->getTemplate()->getName();
		for ( size_t t = 0; t < config.buildingTemplates.size(); ++t )
		{
			if ( tmplName == config.buildingTemplates[t] )
			{
				byTemplate[t].push_back( obj );
				break;
			}
		}
	}

	// Tag one building per check
	for ( size_t i = 0; i < config.buildingCheckIds.size(); ++i )
	{
		const AsciiString& checkId = config.buildingCheckIds[i];
		// Use first template that has buildings (or round-robin)
		size_t t = i % config.buildingTemplates.size();
		if ( byTemplate[t].empty() )
			continue;

		UnsignedInt h = hashIndex( config.configSeed, (UnsignedInt)i + 1000u ); // offset to avoid collision with unit hash
		Int idx = (Int)( h % byTemplate[t].size() );
		Object* obj = byTemplate[t][idx];
		obj->setArchipelagoCheckId( checkId );
		DEBUG_LOG( ( "[Archipelago] Tagged building %s -> check %s reward=%s", obj->getTemplate()->getName().str(), checkId.str(), getAssignedRewardGroupIdForCheck( checkId ).str() ) );
	}
}

// ------------------------------------------------------------------------------------------------
AsciiString UnlockableCheckSpawner::getAssignedRewardGroupIdForCheck( const AsciiString& checkId ) const
{
	if ( checkId.isEmpty() )
		return AsciiString::TheEmptyString;

	std::map<AsciiString, AsciiString>::const_iterator it = m_currentMapCheckRewardGroups.find( checkId );
	if ( it == m_currentMapCheckRewardGroups.end() )
		return AsciiString::TheEmptyString;
	return it->second;
}

// ------------------------------------------------------------------------------------------------
AsciiString UnlockableCheckSpawner::pickWeightedClusterTemplate( const MapConfig& config, const AsciiString& clusterTier, UnsignedInt hashVal ) const
{
	const std::vector<AsciiString>* templates = NULL;
	const std::vector<Real>* weights = NULL;

	if ( clusterTier.compareNoCase( "easy" ) == 0 )
	{
		templates = &config.easyUnitTemplates;
		weights = &config.easyUnitWeights;
	}
	else if ( clusterTier.compareNoCase( "medium" ) == 0 )
	{
		templates = &config.mediumUnitTemplates;
		weights = &config.mediumUnitWeights;
	}
	else if ( clusterTier.compareNoCase( "hard" ) == 0 )
	{
		templates = &config.hardUnitTemplates;
		weights = &config.hardUnitWeights;
	}

	if ( templates == NULL || templates->empty() )
		return AsciiString::TheEmptyString;

	Real totalWeight = 0.0f;
	for ( size_t i = 0; i < templates->size(); ++i )
	{
		const Real weight = ( weights != NULL && i < weights->size() && (*weights)[i] > 0.0f ) ? (*weights)[i] : 1.0f;
		totalWeight += weight;
	}

	if ( totalWeight <= 0.0f )
		return (*templates)[hashVal % templates->size()];

	const Real target = ( (Real)( hashVal % 100000u ) / 100000.0f ) * totalWeight;
	Real cumulative = 0.0f;
	for ( size_t i = 0; i < templates->size(); ++i )
	{
		const Real weight = ( weights != NULL && i < weights->size() && (*weights)[i] > 0.0f ) ? (*weights)[i] : 1.0f;
		cumulative += weight;
		if ( target <= cumulative )
			return (*templates)[i];
	}

	return templates->back();
}

// ------------------------------------------------------------------------------------------------
AsciiString UnlockableCheckSpawner::getRewardLabelForCheckId( const AsciiString& checkId ) const
{
	AsciiString groupId = getAssignedRewardGroupIdForCheck( checkId );
	if ( groupId.isEmpty() )
		return AsciiString::TheEmptyString;
	if ( groupId.compareNoCase( kNoUpgradeRewardGroupId ) == 0 )
		return AsciiString( "No upgrade" );
	if ( TheUnlockRegistry == NULL )
		return groupId;

	const UnlockGroup* group = TheUnlockRegistry->findGroupByName( groupId );
	if ( group == NULL )
		return groupId;
	return group->displayName.isNotEmpty() ? group->displayName : group->groupName;
}
