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

#include "GameLogic/ArchipelagoState.h"
#include "GameLogic/UnlockRegistry.h"
#include "Common/ThingTemplate.h"
#include "Common/ThingFactory.h"
#include "Common/KindOf.h"
#include "Common/GameState.h"
#include "Common/GlobalData.h"
#include "Common/FileSystem.h"
#include "Common/RandomValue.h"
#include "GameClient/Eva.h"
#include "GameClient/InGameUI.h"

#include <cctype>
#include <fstream>
#include <sstream>
#include <string>

ArchipelagoState *TheArchipelagoState = NULL;

static void escapeJsonString(std::ostream &out, const char *s)
{
	for (; *s; ++s)
	{
		if (*s == '\\')
			out << "\\\\";
		else if (*s == '"')
			out << "\\\"";
		else
			out << *s;
	}
}

static void parseStringArray(const std::string &content, const char *key, std::set<AsciiString> &out)
{
	size_t keyPos = content.find(key);
	if (keyPos == std::string::npos)
		return;
	size_t start = content.find('[', keyPos);
	size_t end = content.find(']', start);
	if (start == std::string::npos || end == std::string::npos || end <= start)
		return;

	size_t pos = start + 1;
	while (pos < end)
	{
		size_t open = content.find('\"', pos);
		if (open == std::string::npos || open >= end)
			break;
		size_t close = content.find('\"', open + 1);
		if (close == std::string::npos || close > end)
			break;
		std::string value = content.substr(open + 1, close - open - 1);
		if (!value.empty())
			out.insert(AsciiString(value.c_str()));
		pos = close + 1;
	}
}

static void parseIntArray(const std::string &content, const char *key, std::set<Int> &out)
{
	size_t keyPos = content.find(key);
	if (keyPos == std::string::npos)
		return;
	size_t start = content.find('[', keyPos);
	size_t end = content.find(']', start);
	if (start == std::string::npos || end == std::string::npos || end <= start)
		return;

	size_t pos = start + 1;
	while (pos < end)
	{
		while (pos < end && !std::isdigit(static_cast<unsigned char>(content[pos])) && content[pos] != '-')
			++pos;
		if (pos >= end)
			break;
		size_t numEnd = pos + 1;
		while (numEnd < end && std::isdigit(static_cast<unsigned char>(content[numEnd])))
			++numEnd;
		std::string numStr = content.substr(pos, numEnd - pos);
		out.insert(static_cast<Int>(std::atoi(numStr.c_str())));
		pos = numEnd + 1;
	}
}

static std::string toLowerString(const char *text)
{
	std::string out = text ? text : "";
	for (size_t i = 0; i < out.size(); ++i)
		out[i] = (char)std::tolower((unsigned char)out[i]);
	return out;
}

static Bool startsWithNoCase(const AsciiString &value, const char *prefix)
{
	std::string lhs = toLowerString(value.str());
	std::string rhs = toLowerString(prefix);
	if (lhs.size() < rhs.size())
		return FALSE;
	return lhs.compare(0, rhs.size(), rhs) == 0;
}

static Bool endsWithNoCase(const AsciiString &value, const char *suffix)
{
	std::string lhs = toLowerString(value.str());
	std::string rhs = toLowerString(suffix);
	if (lhs.size() < rhs.size())
		return FALSE;
	return lhs.compare(lhs.size() - rhs.size(), rhs.size(), rhs) == 0;
}

static Bool containsNoCase(const AsciiString &value, const char *needle)
{
	std::string lhs = toLowerString(value.str());
	std::string rhs = toLowerString(needle);
	return lhs.find(rhs) != std::string::npos;
}

static AsciiString resolveLegacyTemplateName(const AsciiString &templateName)
{
	if (templateName.isEmpty())
		return templateName;

	if (TheThingFactory != NULL)
	{
		const ThingTemplate *exact = TheThingFactory->findTemplate(templateName, FALSE);
		if (exact != NULL)
			return exact->getName();
	}

	struct AliasPair
	{
		const char *legacy;
		const char *modern;
	};

	static const AliasPair kAliases[] =
	{
		{ "AmericaPathfinder", "AmericaInfantryPathfinder" },
		{ "AmericaColonelBurton", "AmericaInfantryColonelBurton" },
		{ "AmericaHumvee", "AmericaVehicleHumvee" },
		{ "AmericaTOWMissileHumvee", "AmericaVehicleHumvee" },
		{ "AmericaCrusaderTank", "AmericaTankCrusader" },
		{ "AmericaLaserTank", "AmericaTankCrusader" },
		{ "AmericaPaladinTank", "AmericaTankPaladin" },
		{ "AmericaTomahawk", "AmericaVehicleTomahawk" },
		{ "AmericaAmbulance", "AmericaVehicleMedic" },
		{ "AmericaSentryDroneRobot", "AmericaVehicleBattleDrone" },
		{ "AmericaComanche", "AmericaVehicleComanche" },
		{ "AmericaJetAuroraAlpha", "AmericaJetAurora" },

		{ "ChinaHacker", "ChinaInfantryHacker" },
		{ "ChinaSuperHacker", "ChinaInfantryHacker" },
		{ "ChinaBlackLotus", "ChinaInfantryBlackLotus" },
		{ "ChinaBattlemaster", "ChinaTankBattleMaster" },
		{ "ChinaEmperorBattlemaster", "ChinaTankBattleMaster" },
		{ "ChinaDragonTank", "ChinaTankDragon" },
		{ "ChinaGatlingTank", "ChinaTankGattling" },
		{ "ChinaInfernoCannon", "ChinaVehicleInfernoCannon" },
		{ "ChinaOverlord", "ChinaTankOverlord" },
		{ "ChinaEmperorOverlord", "ChinaTankOverlord" },
		{ "ChinaTroopCrawler", "ChinaVehicleTroopCrawler" },
		{ "ChinaNukeCannon", "ChinaVehicleNukeLauncher" },

		{ "GLARebel", "GLAInfantryRebel" },
		{ "GLAToxinRebel", "GLAInfantryRebel" },
		{ "GLATerrorist", "GLAInfantryTerrorist" },
		{ "GLAHijacker", "GLAInfantryHijacker" },
		{ "GLASaboteur", "GLAInfantryHijacker" },
		{ "GLAJarmenKell", "GLAInfantryJarmenKell" },
		{ "GLAAngryMob", "GLAInfantryAngryMobNexus" },
		{ "GLATechnical", "GLAVehicleTechnical" },
		{ "GLAScorpionTank", "GLATankScorpion" },
		{ "GLAMarauderTank", "GLATankMarauder" },
		{ "GLAQuadCannon", "GLAVehicleQuadCannon" },
		{ "GLARocketBuggy", "GLAVehicleRocketBuggy" },
		{ "GLAToxinTractor", "GLAVehicleToxinTruck" },
		{ "GLABombTruck", "GLAVehicleBombTruck" },
		{ "GLAScudLauncher", "GLAVehicleScudLauncher" },
		{ "GLABattleBus", "GLAVehicleTechnical" },
		{ NULL, NULL }
	};

	for (const AliasPair *it = kAliases; it->legacy != NULL; ++it)
	{
		if (templateName.compareNoCase(it->legacy) == 0)
		{
			AsciiString mapped(it->modern);
			if (TheThingFactory != NULL)
			{
				const ThingTemplate *tmpl = TheThingFactory->findTemplate(mapped, FALSE);
				if (tmpl != NULL)
					return tmpl->getName();
			}
			return mapped;
		}
	}

	return templateName;
}

enum ArchFaction
{
	ARCH_FACTION_UNKNOWN = 0,
	ARCH_FACTION_USA,
	ARCH_FACTION_CHINA,
	ARCH_FACTION_GLA
};

static std::string stripKnownGeneralPrefix(const std::string &name, std::string *outPrefix = NULL)
{
	size_t pos = name.find('_');
	if (pos != std::string::npos)
	{
		std::string prefix = toLowerString(name.substr(0, pos).c_str());
		if (prefix == "airf" || prefix == "lazr" || prefix == "supw" ||
			prefix == "tank" || prefix == "infa" || prefix == "nuke" ||
			prefix == "demo" || prefix == "slth" || prefix == "toxin" || prefix == "chem")
		{
			if (outPrefix != NULL)
				*outPrefix = prefix;
			return name.substr(pos + 1);
		}
	}

	if (outPrefix != NULL)
		outPrefix->clear();
	return name;
}

static ArchFaction detectFactionFromCoreName(const std::string &coreName)
{
	AsciiString name(coreName.c_str());
	if (startsWithNoCase(name, "America"))
		return ARCH_FACTION_USA;
	if (startsWithNoCase(name, "China"))
		return ARCH_FACTION_CHINA;
	if (startsWithNoCase(name, "GLA"))
		return ARCH_FACTION_GLA;
	return ARCH_FACTION_UNKNOWN;
}

static Bool isAllowedGeneralPrefixForFaction(const std::string &prefix, ArchFaction faction)
{
	if (prefix.empty())
		return TRUE;

	if (faction == ARCH_FACTION_USA)
		return prefix == "airf" || prefix == "lazr" || prefix == "supw";
	if (faction == ARCH_FACTION_CHINA)
		return prefix == "tank" || prefix == "infa" || prefix == "nuke";
	if (faction == ARCH_FACTION_GLA)
		return prefix == "demo" || prefix == "slth" || prefix == "toxin" || prefix == "chem";
	return FALSE;
}

static void expandUnlockAcrossFactionGenerals(const AsciiString &templateName, Bool isBuilding, std::set<AsciiString> &targetSet)
{
	const AsciiString resolved = resolveLegacyTemplateName(templateName);
	std::string sourceName = resolved.str();
	if (sourceName.empty())
		return;

	std::string sourcePrefix;
	std::string sourceCore = stripKnownGeneralPrefix(sourceName, &sourcePrefix);
	ArchFaction sourceFaction = detectFactionFromCoreName(sourceCore);
	if (sourceFaction == ARCH_FACTION_UNKNOWN || !isAllowedGeneralPrefixForFaction(sourcePrefix, sourceFaction))
	{
		targetSet.insert(resolved);
		return;
	}

	const std::string sourceCoreLower = toLowerString(sourceCore.c_str());
	Bool insertedAny = FALSE;

	if (TheThingFactory != NULL)
	{
		for (const ThingTemplate *tmpl = TheThingFactory->firstTemplate(); tmpl != NULL; tmpl = tmpl->friend_getNextTemplate())
		{
			const AsciiString &candidate = tmpl->getName();
			if (candidate.isEmpty())
				continue;
			if (startsWithNoCase(candidate, "GC_") || startsWithNoCase(candidate, "CINE_") || startsWithNoCase(candidate, "Boss_"))
				continue;
			if (tmpl->isKindOf(KINDOF_STRUCTURE) != isBuilding)
				continue;

			std::string candidateName = candidate.str();
			std::string candidatePrefix;
			std::string candidateCore = stripKnownGeneralPrefix(candidateName, &candidatePrefix);

			ArchFaction candidateFaction = detectFactionFromCoreName(candidateCore);
			if (candidateFaction != sourceFaction)
				continue;
			if (!isAllowedGeneralPrefixForFaction(candidatePrefix, candidateFaction))
				continue;
			if (toLowerString(candidateCore.c_str()) != sourceCoreLower)
				continue;

			targetSet.insert(candidate);
			insertedAny = TRUE;
		}
	}

	if (!insertedAny)
		targetSet.insert(resolved);
}

ArchipelagoState::ArchipelagoState( void ) :
	m_initialized(FALSE)
{
}

ArchipelagoState::~ArchipelagoState( void )
{
}

ArchipelagoState *ArchipelagoState::getInstance( void )
{
	if (TheArchipelagoState == NULL)
	{
		TheArchipelagoState = NEW ArchipelagoState();
	}
	return TheArchipelagoState;
}

void ArchipelagoState::init( void )
{
	if (m_initialized)
		return;

	AsciiString saveDir;
	if (TheGameState != NULL)
	{
		saveDir = TheGameState->getSaveDirectory();
		m_saveFilePath = TheGameState->getFilePathInSaveDirectory("ArchipelagoState.json");
	}
	else if (TheGlobalData != NULL)
	{
		saveDir = TheGlobalData->getPath_UserData();
		saveDir.concat("Save\\");
		m_saveFilePath = saveDir;
		m_saveFilePath.concat("ArchipelagoState.json");
	}
	else
	{
		m_saveFilePath = "ArchipelagoState.json";
	}

	loadFromFile();
	ensureDefaultStartingGenerals();

	if (TheFileSystem && !saveDir.isEmpty())
		TheFileSystem->createDirectory(saveDir);

	if (TheFileSystem && !TheFileSystem->doesFileExist(m_saveFilePath.str()))
		saveToFile();
	m_initialized = TRUE;
}

void ArchipelagoState::reset( void )
{
	// NOTE: this function is also called by engine lifecycle resets.
	// Do not wipe persistent Archipelago progress here.
	loadFromFile();
	ensureDefaultStartingGenerals();
	DEBUG_LOG(("[Archipelago] State reset() reloaded from %s", m_saveFilePath.str()));
}

void ArchipelagoState::wipeProgress( void )
{
	m_unlockedUnits.clear();
	m_unlockedBuildings.clear();
	m_unlockedGenerals.clear();
	m_startingGenerals.clear();
	m_completedLocations.clear();
	ensureDefaultStartingGenerals();
	saveToFile();
}

void ArchipelagoState::update( void )
{
}

Bool ArchipelagoState::isUnitUnlocked( const AsciiString &templateName ) const
{
	const AsciiString resolved = resolveLegacyTemplateName(templateName);
	if (isAlwaysUnlocked(resolved))
		return TRUE;
	if (m_unlockedUnits.find(resolved) != m_unlockedUnits.end())
		return TRUE;
	return m_unlockedUnits.find(templateName) != m_unlockedUnits.end();
}

Bool ArchipelagoState::isBuildingUnlocked( const AsciiString &templateName ) const
{
	const AsciiString resolved = resolveLegacyTemplateName(templateName);
	if (isAlwaysUnlocked(resolved))
		return TRUE;
	if (m_unlockedBuildings.find(resolved) != m_unlockedBuildings.end())
		return TRUE;
	return m_unlockedBuildings.find(templateName) != m_unlockedBuildings.end();
}

Bool ArchipelagoState::isGeneralUnlocked( Int generalIndex ) const
{
	return m_unlockedGenerals.find(generalIndex) != m_unlockedGenerals.end();
}

Bool ArchipelagoState::isTemplateUnlocked( const ThingTemplate *tmpl ) const
{
	if (tmpl == NULL)
		return TRUE;

	const AsciiString &name = tmpl->getName();
	if (isAlwaysUnlocked(name))
		return TRUE;

	if (tmpl->isKindOf(KINDOF_STRUCTURE))
		return isBuildingUnlocked(name);

	return isUnitUnlocked(name);
}

Bool ArchipelagoState::isAlwaysUnlocked( const AsciiString &templateName ) const
{
	if (TheUnlockRegistry != NULL && TheUnlockRegistry->isAlwaysUnlockedTemplate(templateName))
		return TRUE;

	static const char *usaAlways[] = {
		"AmericaDozer",
		"AmericaVehicleDozer",
		"AmericaChinook",
		"AmericaVehicleChinook",
		"AmericaRanger",
		"AmericaInfantryRanger",
		"AmericaCommandCenter",
		"AmericaSupplyCenter",
		"AmericaPowerPlant",
		"AmericaBarracks",
		NULL
	};
	static const char *chinaAlways[] = {
		"ChinaDozer",
		"ChinaVehicleDozer",
		"ChinaSupplyTruck",
		"ChinaVehicleSupplyTruck",
		"ChinaRedguard",
		"ChinaInfantryRedguard",
		"Infa_ChinaInfantryMiniGunner",
		"ChinaCommandCenter",
		"ChinaSupplyCenter",
		"ChinaPowerPlant",
		"ChinaBarracks",
		NULL
	};
	static const char *glaAlways[] = {
		"GLAWorker",
		"GLAInfantryWorker",
		"GLARebel",
		"GLAInfantryRebel",
		"GLACommandCenter",
		"GLASupplyStash",
		"GLABarracks",
		"Upgrade_GLABombTruckBioBomb",
		"Upgrade_GLABombTruckHighExplosiveBomb",
		NULL
	};

	for (const char **p = usaAlways; *p; ++p)
	{
		if (templateName.compareNoCase(*p) == 0)
			return TRUE;
	}
	for (const char **p = chinaAlways; *p; ++p)
	{
		if (templateName.compareNoCase(*p) == 0)
			return TRUE;
	}
	for (const char **p = glaAlways; *p; ++p)
	{
		if (templateName.compareNoCase(*p) == 0)
			return TRUE;
	}

	// Robust fallback for general-variant template names:
	// keep core economy/opening units and starter structures always available.
	if (endsWithNoCase(templateName, "Dozer") || containsNoCase(templateName, "Dozer"))
	{
		return TRUE;
	}
	if (endsWithNoCase(templateName, "Worker") || containsNoCase(templateName, "Worker"))
	{
		return TRUE;
	}
	if (endsWithNoCase(templateName, "SupplyTruck"))
	{
		return TRUE;
	}
	// Supply Chinooks (transport) always unlocked; exclude battle/combat Chinooks
	if ((endsWithNoCase(templateName, "Chinook") || containsNoCase(templateName, "Chinook")) && !containsNoCase(templateName, "Battle"))
	{
		return TRUE;
	}
	if (endsWithNoCase(templateName, "Ranger") ||
		endsWithNoCase(templateName, "Redguard") ||
		endsWithNoCase(templateName, "Rebel"))
	{
		return TRUE;
	}
	if (endsWithNoCase(templateName, "CommandCenter") ||
		endsWithNoCase(templateName, "PowerPlant") ||
		endsWithNoCase(templateName, "NuclearReactor") ||
		endsWithNoCase(templateName, "ColdFusionReactor") ||
		endsWithNoCase(templateName, "SupplyCenter") ||
		endsWithNoCase(templateName, "SupplyStash") ||
		endsWithNoCase(templateName, "Barracks"))
	{
		return TRUE;
	}

	return FALSE;
}

void ArchipelagoState::unlockUnit( const AsciiString &templateName )
{
	const AsciiString resolved = resolveLegacyTemplateName(templateName);
	if (isAlwaysUnlocked(resolved))
		return;

	if (TheUnlockRegistry != NULL)
	{
		std::vector<AsciiString> group = TheUnlockRegistry->getGroupTemplates(templateName);
		if (group.empty() && resolved.compareNoCase(templateName) != 0)
			group = TheUnlockRegistry->getGroupTemplates(resolved);
		if (!group.empty())
		{
			for (std::vector<AsciiString>::const_iterator it = group.begin(); it != group.end(); ++it)
			{
				// Mixed groups can contain both Units and Buildings; unlock each entry by its declared type.
				if (TheUnlockRegistry->isBuildingTemplate(*it))
					expandUnlockAcrossFactionGenerals(*it, TRUE, m_unlockedBuildings);
				else
					expandUnlockAcrossFactionGenerals(*it, FALSE, m_unlockedUnits);
			}
			saveToFile();
			notifyUnlock(resolved);
			return;
		}
	}

	expandUnlockAcrossFactionGenerals(resolved, FALSE, m_unlockedUnits);
	saveToFile();
	notifyUnlock(resolved);
}

void ArchipelagoState::unlockBuilding( const AsciiString &templateName )
{
	const AsciiString resolved = resolveLegacyTemplateName(templateName);
	if (isAlwaysUnlocked(resolved))
		return;

	if (TheUnlockRegistry != NULL)
	{
		std::vector<AsciiString> group = TheUnlockRegistry->getGroupTemplates(templateName);
		if (group.empty() && resolved.compareNoCase(templateName) != 0)
			group = TheUnlockRegistry->getGroupTemplates(resolved);
		if (!group.empty())
		{
			for (std::vector<AsciiString>::const_iterator it = group.begin(); it != group.end(); ++it)
			{
				// Mixed groups can contain both Units and Buildings; unlock each entry by its declared type.
				if (TheUnlockRegistry->isBuildingTemplate(*it))
					expandUnlockAcrossFactionGenerals(*it, TRUE, m_unlockedBuildings);
				else
					expandUnlockAcrossFactionGenerals(*it, FALSE, m_unlockedUnits);
			}
			saveToFile();
			notifyUnlock(resolved);
			return;
		}
	}

	expandUnlockAcrossFactionGenerals(resolved, TRUE, m_unlockedBuildings);
	saveToFile();
	notifyUnlock(resolved);
}

Bool ArchipelagoState::unlockGroup( const UnlockGroup *group, const char* notifySuffix )
{
	if (group == NULL || TheUnlockRegistry == NULL)
		return FALSE;

	size_t unitsBefore = m_unlockedUnits.size();
	size_t buildingsBefore = m_unlockedBuildings.size();

	for (std::vector<AsciiString>::const_iterator it = group->templates.begin(); it != group->templates.end(); ++it)
	{
		if (isAlwaysUnlocked(*it))
			continue;

		Bool isBuilding = TheUnlockRegistry->isBuildingTemplate(*it);
		const AsciiString resolved = resolveLegacyTemplateName(*it);
		if (isBuilding)
		{
			m_unlockedBuildings.insert(resolved);
			m_unlockedBuildings.insert(*it);
		}
		else
		{
			m_unlockedUnits.insert(resolved);
			m_unlockedUnits.insert(*it);
		}
	}

	Bool addedAny = (m_unlockedUnits.size() > unitsBefore) || (m_unlockedBuildings.size() > buildingsBefore);
	saveToFile();
	// Always notify for spawned-unit kills (notifySuffix set) so player sees feedback; otherwise only when we added content
	if (addedAny || (notifySuffix && notifySuffix[0]))
	{
		AsciiString displayName = group->displayName.isEmpty() ? group->groupName : group->displayName;
		if (notifySuffix && notifySuffix[0])
		{
			AsciiString msg;
			msg.format( "%s%s", displayName.str(), notifySuffix );
			notifyUnlock( msg );
		}
		else
			notifyUnlock( displayName );
	}
	return addedAny;
}

void ArchipelagoState::unlockGeneral( Int generalIndex )
{
	if (m_unlockedGenerals.insert(generalIndex).second)
	{
		saveToFile();
		static const char *kGeneralNames[] = {
			"USA Airforce",
			"USA Laser",
			"USA Superweapon",
			"China Tank",
			"China Infantry",
			"China Nuke",
			"GLA Toxin",
			"GLA Demolition",
			"GLA Stealth"
		};
		AsciiString msg;
		if (generalIndex >= 0 && generalIndex < GENERAL_COUNT)
			msg.format("%s General", kGeneralNames[generalIndex]);
		else
			msg.format("General %d", generalIndex);
		notifyUnlock(msg);
	}
}

void ArchipelagoState::unlockAll( void )
{
	for (Int i = 0; i < GENERAL_COUNT; ++i)
		m_unlockedGenerals.insert(i);

	if (TheUnlockRegistry != NULL)
	{
		std::vector<AsciiString> templates = TheUnlockRegistry->getAllTemplates();
		for (std::vector<AsciiString>::const_iterator it = templates.begin(); it != templates.end(); ++it)
		{
			if (TheUnlockRegistry->isBuildingTemplate(*it))
				m_unlockedBuildings.insert(*it);
			else
				m_unlockedUnits.insert(*it);
		}
	}

	// Safety net: ensure every currently loaded unit/structure template is unlocked.
	// This makes debug unlock-all robust even if Archipelago.ini has stale template names.
	if (TheThingFactory != NULL)
	{
		for (const ThingTemplate *tmpl = TheThingFactory->firstTemplate(); tmpl != NULL; tmpl = tmpl->friend_getNextTemplate())
		{
			const AsciiString &name = tmpl->getName();
			if (name.isEmpty() || isAlwaysUnlocked(name))
				continue;

			if (tmpl->isKindOf(KINDOF_STRUCTURE))
				m_unlockedBuildings.insert(name);
			else
				m_unlockedUnits.insert(name);
		}
	}

	// Also unlock command/upgrade-style toggles that are not ThingTemplates.
	m_unlockedUnits.insert("Upgrade_InfantryCaptureBuilding");
	m_unlockedUnits.insert("Command_CombatDrop");

	saveToFile();
	notifyUnlock("All Items");
}

void ArchipelagoState::markLocationComplete( Int locationId )
{
	if (m_completedLocations.insert(locationId).second)
		saveToFile();
}

Bool ArchipelagoState::isLocationComplete( Int locationId ) const
{
	return m_completedLocations.find(locationId) != m_completedLocations.end();
}

void ArchipelagoState::grantCheckForKill( const AsciiString& checkId, const AsciiString& victimTemplateName, Bool isSpawnedUnitKill )
{
	if ( checkId.isEmpty() )
		return;
	if ( m_completedChecks.find( checkId ) != m_completedChecks.end() )
		return;

	m_completedChecks.insert( checkId );

	if ( TheUnlockRegistry )
	{
		const UnlockGroup* group = TheUnlockRegistry->findGroupForTemplate( victimTemplateName );
		if ( group )
		{
			unlockGroup( group, isSpawnedUnitKill ? " (+$5000)" : nullptr );
			DEBUG_LOG( ( "[Archipelago] Granted check %s (killed %s) -> unlocked group %s", checkId.str(), victimTemplateName.str(), group->displayName.isEmpty() ? group->groupName.str() : group->displayName.str() ) );
		}
		else
		{
			// No group mapping: unlock the template directly (unlockUnit/Building already notify)
			if ( TheUnlockRegistry->isBuildingTemplate( victimTemplateName ) )
				unlockBuilding( victimTemplateName );
			else
				unlockUnit( victimTemplateName );
			DEBUG_LOG( ( "[Archipelago] Granted check %s (killed %s) -> direct unlock", checkId.str(), victimTemplateName.str() ) );
		}
	}
}

Bool ArchipelagoState::isCheckComplete( const AsciiString& checkId ) const
{
	return m_completedChecks.find( checkId ) != m_completedChecks.end();
}

void ArchipelagoState::saveToFile( void )
{
	if (m_saveFilePath.isEmpty())
		return;

	std::ofstream file(m_saveFilePath.str());
	if (!file.is_open())
		return;

	file << "{\n";
	file << "  \"version\": 1,\n";

	file << "  \"unlockedUnits\": [";
	Bool first = TRUE;
	for (std::set<AsciiString>::const_iterator it = m_unlockedUnits.begin(); it != m_unlockedUnits.end(); ++it)
	{
		if (!first)
			file << ", ";
		file << "\"";
		escapeJsonString(file, it->str());
		file << "\"";
		first = FALSE;
	}
	file << "],\n";

	file << "  \"unlockedBuildings\": [";
	first = TRUE;
	for (std::set<AsciiString>::const_iterator it = m_unlockedBuildings.begin(); it != m_unlockedBuildings.end(); ++it)
	{
		if (!first)
			file << ", ";
		file << "\"";
		escapeJsonString(file, it->str());
		file << "\"";
		first = FALSE;
	}
	file << "],\n";

	file << "  \"unlockedGenerals\": [";
	first = TRUE;
	for (std::set<Int>::const_iterator it = m_unlockedGenerals.begin(); it != m_unlockedGenerals.end(); ++it)
	{
		if (!first)
			file << ", ";
		file << *it;
		first = FALSE;
	}
	file << "],\n";

	file << "  \"startingGenerals\": [";
	first = TRUE;
	for (std::set<Int>::const_iterator it = m_startingGenerals.begin(); it != m_startingGenerals.end(); ++it)
	{
		if (!first)
			file << ", ";
		file << *it;
		first = FALSE;
	}
	file << "],\n";

	file << "  \"completedLocations\": [";
	first = TRUE;
	for (std::set<Int>::const_iterator it = m_completedLocations.begin(); it != m_completedLocations.end(); ++it)
	{
		if (!first)
			file << ", ";
		file << *it;
		first = FALSE;
	}
	file << "]\n";
	file << "}\n";
	file.close();
}

void ArchipelagoState::loadFromFile( void )
{
	if (m_saveFilePath.isEmpty())
		return;

	std::ifstream file(m_saveFilePath.str());
	if (!file.is_open())
		return;

	std::stringstream buffer;
	buffer << file.rdbuf();
	std::string content = buffer.str();

	m_unlockedUnits.clear();
	m_unlockedBuildings.clear();
	m_unlockedGenerals.clear();
	m_startingGenerals.clear();
	m_completedLocations.clear();

	parseStringArray(content, "\"unlockedUnits\"", m_unlockedUnits);
	parseStringArray(content, "\"unlockedBuildings\"", m_unlockedBuildings);
	parseIntArray(content, "\"unlockedGenerals\"", m_unlockedGenerals);
	parseIntArray(content, "\"startingGenerals\"", m_startingGenerals);
	parseIntArray(content, "\"completedLocations\"", m_completedLocations);
}

void ArchipelagoState::notifyUnlock( const AsciiString &itemName )
{
	if (TheInGameUI)
	{
		UnicodeString msg;
		msg.format(L"[UNLOCKED] %hs", itemName.str());
		RGBColor green = { 0, 255, 100 };
		TheInGameUI->messageColor(&green, msg);
	}
	if (TheEva)
	{
		TheEva->setShouldPlay(EVA_UpgradeComplete);
	}
}

AsciiString ArchipelagoState::getSaveFilePath( void ) const
{
	return m_saveFilePath;
}

void ArchipelagoState::ensureDefaultStartingGenerals( void )
{
	if (!m_startingGenerals.empty())
	{
		for (std::set<Int>::const_iterator it = m_startingGenerals.begin(); it != m_startingGenerals.end(); ++it)
			m_unlockedGenerals.insert(*it);
		return;
	}

	Int usa, china, gla;
	if (TheUnlockRegistry != NULL)
	{
		Int regUsa = TheUnlockRegistry->getStartingGeneralUSA();
		Int regChina = TheUnlockRegistry->getStartingGeneralChina();
		Int regGla = TheUnlockRegistry->getStartingGeneralGLA();
		usa = (regUsa >= 0 && regUsa <= 2) ? regUsa : GameLogicRandomValue(0, 2);
		china = (regChina >= 3 && regChina <= 5) ? regChina : 3 + GameLogicRandomValue(0, 2);
		gla = (regGla >= 6 && regGla <= 8) ? regGla : 6 + GameLogicRandomValue(0, 2);
	}
	else
	{
		usa = GameLogicRandomValue(0, 2);
		china = 3 + GameLogicRandomValue(0, 2);
		gla = 6 + GameLogicRandomValue(0, 2);
	}

	m_startingGenerals.insert(usa);
	m_startingGenerals.insert(china);
	m_startingGenerals.insert(gla);

	m_unlockedGenerals.insert(usa);
	m_unlockedGenerals.insert(china);
	m_unlockedGenerals.insert(gla);

	saveToFile();
}
