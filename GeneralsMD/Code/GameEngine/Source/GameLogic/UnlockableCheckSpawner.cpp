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
#include "Common/Player.h"
#include "Common/RandomValue.h"
#include "Common/PlayerList.h"
#include "Common/UnicodeString.h"
#include "Common/Team.h"
#include "Common/ThingFactory.h"
#include "Common/ThingTemplate.h"

#include "GameClient/CampaignManager.h"
#include "GameClient/InGameUI.h"

#include "Common/Radar.h"

#include "GameLogic/AI.h"
#include "GameLogic/AIPathfind.h"
#include "GameLogic/Module/AIUpdate.h"
#include "GameLogic/GameLogic.h"
#include "GameLogic/Object.h"
#include "GameLogic/Module/BehaviorModule.h"
#include "GameLogic/Module/CreateModule.h"
#include "GameLogic/PartitionManager.h"
#include "GameLogic/UnlockRegistry.h"
#include "GameLogic/UnlockableCheckSpawner.h"
#include "GameLogic/ArchipelagoState.h"
#include "GameLogic/TerrainLogic.h"
#include "GameLogic/Module/BodyModule.h"
#include "GameLogic/ExperienceTracker.h"

#include "GameClient/Drawable.h"

// ------------------------------------------------------------------------------------------------
UnlockableCheckSpawner* TheUnlockableCheckSpawner = nullptr;

// Spawned unit vision range: slightly above Nuke Cannon (360) to prevent range exploitation.
static const Real kSpawnedUnitMinVisionRange = 365.0f;

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
	currentConfig.defendRadius = 150.0f;
	currentConfig.maxChaseRadius = 550.0f;

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
			currentConfig.defendRadius = 150.0f;
			currentConfig.maxChaseRadius = 550.0f;
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
			m_currentMapCheckRewardGroups.erase( checkId );
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

		m_spawnedUnits.push_back( obj );
		m_spawnedUnitLastRevealPos.push_back( *pos );
		m_spawnedUnitGuardPos.push_back( *pos );
		m_spawnedUnitHasRevealed.push_back( FALSE );
	}

}

// ------------------------------------------------------------------------------------------------
void UnlockableCheckSpawner::runAfterMapLoad( const AsciiString& mapName, Bool loadingSaveGame )
{
	m_spawnedUnits.clear();
	m_spawnedUnitLastRevealPos.clear();
	m_spawnedUnitGuardPos.clear();
	m_spawnedUnitHasRevealed.clear();
	m_currentMapDamageOutputScalar = 1.0f;
	m_currentMapDefendRadius = 0.0f;
	m_currentMapMaxChaseRadius = 0.0f;
	m_currentMapUnitMarkerFX.clear();
	m_currentMapUnitTemplates.clear();
	m_unlockedCheckIds.clear();
	m_currentMapAllCheckIds.clear();
	m_currentMapCheckRewardGroups.clear();

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

	m_currentMapDamageOutputScalar = config.damageOutputScalar > 0.0f ? config.damageOutputScalar : 1.0f;
	m_currentMapDefendRadius = config.defendRadius > 0.0f ? config.defendRadius : 0.0f;
	m_currentMapMaxChaseRadius = config.maxChaseRadius > 0.0f ? config.maxChaseRadius : 0.0f;
	m_currentMapUnitMarkerFX = config.unitMarkerFX;
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

	// Prefer checks not already completed: kills should progress through random not-yet-unlocked groups first.
	std::vector<AsciiString> checkIdsToAssign;
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
	// If all groups are already unlocked, still spawn with random IDs from full list.
	if ( checkIdsToAssign.empty() )
		checkIdsToAssign = config.unitCheckIds;
	DEBUG_LOG( ( "UnlockableCheckSpawner: check assignment pool size=%d (total map checks=%d)", (Int)checkIdsToAssign.size(), (Int)config.unitCheckIds.size() ) );
	std::vector<AsciiString> templatesToAssign = config.unitTemplates;
	DEBUG_LOG( ( "UnlockableCheckSpawner: template assignment pool size=%d (total map templates=%d)", (Int)templatesToAssign.size(), (Int)config.unitTemplates.size() ) );

	for ( Int i = 0; i < numToSpawn; ++i )
	{
		UnsignedInt h = hashIndex( config.configSeed, (UnsignedInt)i );
		Int wpIndex = (Int)( (UnsignedInt)i % (UnsignedInt)config.unitWaypoints.size() );
		Int tmplIndex = i % (Int)templatesToAssign.size();
		Int checkIdx = i % (Int)checkIdsToAssign.size();
		const AsciiString& checkId = checkIdsToAssign[checkIdx];
		AsciiString rewardLabel = getRewardLabelForCheckId( checkId );

		const AsciiString& waypointName = config.unitWaypoints[wpIndex];
		const AsciiString& templateName = templatesToAssign[tmplIndex];

		Waypoint* way = TheTerrainLogic->getWaypointByName( waypointName );
		if ( !way )
		{
			// Fallback: campaign maps may be single-player with only Player_1_Start
			way = TheTerrainLogic->getWaypointByName( AsciiString( "Player_1_Start" ) );
		}
		if ( !way )
		{
			DEBUG_LOG( ( "UnlockableCheckSpawner: waypoint %s and Player_1_Start not found for map %s", waypointName.str(), mapName.str() ) );
			continue;
		}

		const ThingTemplate* tmpl = TheThingFactory->findTemplate( templateName );
		if ( !tmpl )
		{
			DEBUG_LOG( ( "UnlockableCheckSpawner: template %s not found", templateName.str() ) );
			continue;
		}

		Object* obj = TheThingFactory->newObject( tmpl, team );
		if ( !obj )
			continue;

		Coord3D pos = *way->getLocation();
		// Deterministic wide placement in the top-right quadrant of the player base.
		// Alternate between inner and outer radii while walking across a fixed arc so
		// all spawned check units stay on-map and visible from the base.
		const Real baseRadius = config.spawnOffset > 0.0f ? config.spawnOffset : 650.0f;
		const Real outerDelta = config.spawnOffsetSpread > 0.0f ? config.spawnOffsetSpread : 200.0f;
		const Real radius = baseRadius + ( ( i & 1 ) ? outerDelta : 0.0f );
		const Real arcStart = 0.20f;
		const Real arcSpan = 0.95f;
		const Real t = numToSpawn > 1 ? (Real)i / (Real)( numToSpawn - 1 ) : 0.5f;
		const Real jitter = ( (Real)( h % 1000u ) / 1000.0f ) * 0.08f;
		const Real angle = arcStart + arcSpan * t + jitter;
		pos.x += (Real)cos( angle ) * radius;
		pos.y += (Real)sin( angle ) * radius;
		pos.z = TheTerrainLogic->getGroundHeight( pos.x, pos.y );
		obj->setPosition( &pos );
		obj->setArchipelagoCheckId( checkId );
		if ( rewardLabel.isNotEmpty() )
			obj->setName( rewardLabel );
		// Ensure spawned units detect from beyond Nuke Cannon range (350) to avoid exploitation.
		if ( obj->getVisionRange() < kSpawnedUnitMinVisionRange )
		{
			obj->setVisionRange( kSpawnedUnitMinVisionRange );
			DEBUG_LOG( ( "[Archipelago] Spawned unit %s vision range boosted to %.0f (min for anti-exploit)", templateName.str(), (double)kSpawnedUnitMinVisionRange ) );
		}

		m_spawnedUnits.push_back( obj );
		m_spawnedUnitLastRevealPos.push_back( pos );
		m_spawnedUnitGuardPos.push_back( pos );
		m_spawnedUnitHasRevealed.push_back( FALSE );

		// Add to pathfinder
		team->setActive();
		TheAI->pathfinder()->addObjectToPathfindMap( obj );

		// onBuildComplete for created objects
		for ( BehaviorModule** m = obj->getBehaviorModules(); *m; ++m )
		{
			CreateModuleInterface* create = (*m)->getCreate();
			if ( create )
				create->onBuildComplete();
		}

		// No initial guard - units can chase freely within DefendRadius

		// Max HP = 25% of original, current = full of new max. Veterancy 3.
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

		DEBUG_LOG( ( "[Archipelago] Spawned %s at %s -> check %s reward=%s", templateName.str(), waypointName.str(), checkId.str(), getAssignedRewardGroupIdForCheck( checkId ).str() ) );
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
Bool UnlockableCheckSpawner::isSpawnedUnit( const Object* obj ) const
{
	if ( !obj || !m_enabled || m_spawnedUnits.empty() )
		return FALSE;
	for ( size_t i = 0; i < m_spawnedUnits.size(); ++i )
	{
		if ( m_spawnedUnits[i] == obj )
			return TRUE;
	}
	return FALSE;
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
	if ( !m_enabled || m_spawnedUnits.empty() || !TheGameLogic )
		return;

	PlayerMaskType localMask = 0;
	if ( ThePartitionManager && ThePlayerList )
	{
		Player* localPlayer = ThePlayerList->getLocalPlayer();
		if ( localPlayer )
			localMask = localPlayer->getPlayerMask();
	}

	UnsignedInt frame = TheGameLogic->getFrame();

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

	for ( size_t i = 0; i < m_spawnedUnits.size(); )
	{
		Object* obj = m_spawnedUnits[i];
		if ( !obj || obj->isEffectivelyDead() )
		{
			// Undo our reveal before removing (must do or spawn spot stays revealed)
			if ( localMask && ThePartitionManager && i < m_spawnedUnitLastRevealPos.size() && i < m_spawnedUnitHasRevealed.size() && m_spawnedUnitHasRevealed[i] )
			{
				const Coord3D& last = m_spawnedUnitLastRevealPos[i];
				ThePartitionManager->undoShroudReveal( last.x, last.y, 50.0f, localMask );
			}
			m_spawnedUnits.erase( m_spawnedUnits.begin() + (Int)i );
			m_spawnedUnitLastRevealPos.erase( m_spawnedUnitLastRevealPos.begin() + (Int)i );
			m_spawnedUnitGuardPos.erase( m_spawnedUnitGuardPos.begin() + (Int)i );
			m_spawnedUnitHasRevealed.erase( m_spawnedUnitHasRevealed.begin() + (Int)i );
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

				Bool shouldPull = FALSE;
				if ( distSqr > maxChaseSqr )
					shouldPull = TRUE;
				else if ( defendSqr > 0.0f && distSqr > defendSqr )
				{
					Object* victim = ai->getCurrentVictim();
					if ( !victim || victim->isEffectivelyDead() )
						shouldPull = TRUE;
				}
				if ( shouldPull )
					ai->aiMoveToPosition( &spawnPos, CMD_FROM_SCRIPT );
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
		DEBUG_LOG( ( "[Archipelago] Ignored duplicate check completion for %s", checkId.str() ) );
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
			L"[ARCHIPELAGO] %hs -> %hs [%hs] anchor=(%.0f, %.0f)",
			checkId.str(),
			rewardLabel.isNotEmpty() ? rewardLabel.str() : "<unassigned>",
			stateLabel,
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
AsciiString UnlockableCheckSpawner::getRewardLabelForCheckId( const AsciiString& checkId ) const
{
	AsciiString groupId = getAssignedRewardGroupIdForCheck( checkId );
	if ( groupId.isEmpty() || TheUnlockRegistry == NULL )
		return AsciiString::TheEmptyString;

	const UnlockGroup* group = TheUnlockRegistry->findGroupByName( groupId );
	if ( group == NULL )
		return groupId;
	return group->displayName.isNotEmpty() ? group->displayName : group->groupName;
}
