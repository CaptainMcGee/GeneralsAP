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
#include "Common/Player.h"
#include "Common/PlayerList.h"
#include "Common/FileSystem.h"
#include "Common/RandomValue.h"
#include "GameLogic/GameLogic.h"
#include "GameClient/Eva.h"
#include "GameClient/InGameUI.h"
#include "GameClient/View.h"

#include <algorithm>
#include <cctype>
#include <cstdlib>
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

static void writeStringArray(std::ostream &out, const char *key, const std::set<AsciiString> &values, Bool trailingComma)
{
	out << "  \"" << key << "\": [";
	Bool first = TRUE;
	for (std::set<AsciiString>::const_iterator it = values.begin(); it != values.end(); ++it)
	{
		if (!first)
			out << ", ";
		out << '"';
		escapeJsonString(out, it->str());
		out << '"';
		first = FALSE;
	}
	out << "]";
	if (trailingComma)
		out << ",";
	out << "\n";
}

static void writeIntArray(std::ostream &out, const char *key, const std::set<Int> &values, Bool trailingComma)
{
	out << "  \"" << key << "\": [";
	Bool first = TRUE;
	for (std::set<Int>::const_iterator it = values.begin(); it != values.end(); ++it)
	{
		if (!first)
			out << ", ";
		out << *it;
		first = FALSE;
	}
	out << "]";
	if (trailingComma)
		out << ",";
	out << "\n";
}

struct BridgeReceivedItem
{
	Int sequence;
	AsciiString kind;
	AsciiString groupId;
};

struct BridgeSessionOptions
{
	Int startingCashBonus;
	Real productionMultiplier;
	Bool disableZoomLimit;
	std::set<Int> starterGenerals;

	BridgeSessionOptions() :
		startingCashBonus(0),
		productionMultiplier(1.0f),
		disableZoomLimit(FALSE)
	{
	}
};

static UnsignedInt hashBridgeContent(const std::string &content)
{
	UnsignedInt hash = 2166136261u;
	for (std::string::const_iterator it = content.begin(); it != content.end(); ++it)
	{
		hash ^= static_cast<unsigned char>(*it);
		hash *= 16777619u;
	}
	return hash;
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

static Int parseSingleIntField(const std::string &content, const char *key, Int defaultValue)
{
	size_t keyPos = content.find(key);
	if (keyPos == std::string::npos)
		return defaultValue;
	size_t colon = content.find(':', keyPos);
	if (colon == std::string::npos)
		return defaultValue;

	size_t pos = colon + 1;
	while (pos < content.size() && !std::isdigit(static_cast<unsigned char>(content[pos])) && content[pos] != '-')
		++pos;
	if (pos >= content.size())
		return defaultValue;

	size_t numEnd = pos + 1;
	while (numEnd < content.size() && std::isdigit(static_cast<unsigned char>(content[numEnd])))
		++numEnd;
	return static_cast<Int>(std::atoi(content.substr(pos, numEnd - pos).c_str()));
}

static UnsignedInt parseSingleUnsignedField(const std::string &content, const char *key, UnsignedInt defaultValue)
{
	Int parsed = parseSingleIntField(content, key, static_cast<Int>(defaultValue));
	return parsed < 0 ? defaultValue : static_cast<UnsignedInt>(parsed);
}

static AsciiString parseSingleStringField(const std::string &content, const char *key)
{
	size_t keyPos = content.find(key);
	if (keyPos == std::string::npos)
		return AsciiString::TheEmptyString;
	size_t colon = content.find(':', keyPos);
	if (colon == std::string::npos)
		return AsciiString::TheEmptyString;
	size_t open = content.find('\"', colon + 1);
	if (open == std::string::npos)
		return AsciiString::TheEmptyString;
	size_t close = content.find('\"', open + 1);
	if (close == std::string::npos)
		return AsciiString::TheEmptyString;
	return AsciiString(content.substr(open + 1, close - open - 1).c_str());
}

static Bool parseSingleBoolField(const std::string &content, const char *key, Bool defaultValue)
{
	size_t keyPos = content.find(key);
	if (keyPos == std::string::npos)
		return defaultValue;
	size_t colon = content.find(':', keyPos);
	if (colon == std::string::npos)
		return defaultValue;

	size_t pos = colon + 1;
	while (pos < content.size() && std::isspace(static_cast<unsigned char>(content[pos])))
		++pos;
	if (pos >= content.size())
		return defaultValue;

	if (content.compare(pos, 4, "true") == 0)
		return TRUE;
	if (content.compare(pos, 5, "false") == 0)
		return FALSE;
	return defaultValue;
}

static Real parseSingleRealField(const std::string &content, const char *key, Real defaultValue)
{
	size_t keyPos = content.find(key);
	if (keyPos == std::string::npos)
		return defaultValue;
	size_t colon = content.find(':', keyPos);
	if (colon == std::string::npos)
		return defaultValue;

	size_t pos = colon + 1;
	while (pos < content.size() &&
		!std::isdigit(static_cast<unsigned char>(content[pos])) &&
		content[pos] != '-' && content[pos] != '+')
	{
		++pos;
	}
	if (pos >= content.size())
		return defaultValue;

	size_t valueEnd = pos + 1;
	while (valueEnd < content.size() &&
		(std::isdigit(static_cast<unsigned char>(content[valueEnd])) || content[valueEnd] == '.'))
	{
		++valueEnd;
	}
	return (Real)std::atof(content.substr(pos, valueEnd - pos).c_str());
}

static void parseSessionOptions(const std::string &content, BridgeSessionOptions &out)
{
	size_t keyPos = content.find("\"sessionOptions\"");
	if (keyPos == std::string::npos)
		return;
	size_t objectStart = content.find('{', keyPos);
	size_t objectEnd = content.find('}', objectStart);
	if (objectStart == std::string::npos || objectEnd == std::string::npos || objectEnd <= objectStart)
		return;

	std::string objectText = content.substr(objectStart, objectEnd - objectStart + 1);
	out.startingCashBonus = parseSingleIntField(objectText, "\"startingCashBonus\"", 0);
	out.productionMultiplier = parseSingleRealField(objectText, "\"productionMultiplier\"", 1.0f);
	if (out.productionMultiplier <= 0.0f)
		out.productionMultiplier = 1.0f;
	out.disableZoomLimit = parseSingleBoolField(objectText, "\"disableZoomLimit\"", FALSE);
	parseIntArray(objectText, "\"starterGenerals\"", out.starterGenerals);
}

static void parseReceivedItems(const std::string &content, std::vector<BridgeReceivedItem> &out)
{
	size_t keyPos = content.find("\"receivedItems\"");
	if (keyPos == std::string::npos)
		return;
	size_t start = content.find('[', keyPos);
	size_t end = content.find(']', start);
	if (start == std::string::npos || end == std::string::npos || end <= start)
		return;

	size_t pos = start + 1;
	while (pos < end)
	{
		size_t objectStart = content.find('{', pos);
		if (objectStart == std::string::npos || objectStart >= end)
			break;
		size_t objectEnd = content.find('}', objectStart);
		if (objectEnd == std::string::npos || objectEnd > end)
			break;

		std::string objectText = content.substr(objectStart, objectEnd - objectStart + 1);
		BridgeReceivedItem item;
		item.sequence = parseSingleIntField(objectText, "\"sequence\"", -1);
		item.kind = parseSingleStringField(objectText, "\"kind\"");
		item.groupId = parseSingleStringField(objectText, "\"groupId\"");

		if (item.sequence >= 0 && item.kind.isNotEmpty() && item.groupId.isNotEmpty())
			out.push_back(item);

		pos = objectEnd + 1;
	}

	std::sort(out.begin(), out.end(), [](const BridgeReceivedItem &lhs, const BridgeReceivedItem &rhs) {
		return lhs.sequence < rhs.sequence;
	});
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
	m_initialized(FALSE),
	m_bridgePollCountdown(0),
	m_lastImportedBridgeHash(0),
	m_lastAppliedReceivedItemSequence(-1),
	m_startingCashBonus(0),
	m_productionMultiplier(1.0f),
	m_disableZoomLimit(FALSE),
	m_appliedMissionStartOptions(FALSE),
	m_pendingMissionStartOptions(FALSE),
	m_missionStartOptionsEarliestFrame(0),
	m_localFallbackUnlockSeed(0x41A7C3u),
	m_localFallbackConsumedCount(0)
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

	initializeBridgePaths();
	loadFromFile();
	importBridgeState(FALSE);
	syncUnlockedGroupsFromCurrentState();
	refreshUnlockedTemplateCachesFromGroups();
	ensureDefaultStartingGenerals();

	if (TheFileSystem && !saveDir.isEmpty())
		TheFileSystem->createDirectory(saveDir);

	if (TheFileSystem && !TheFileSystem->doesFileExist(m_saveFilePath.str()))
		saveToFile();
	else
		exportBridgeState();

	m_bridgePollCountdown = 0;
	m_initialized = TRUE;
	DEBUG_LOG(("[Archipelago] State initialized: save=%s inbound=%s outbound=%s",
		m_saveFilePath.str(),
		m_bridgeInboundFilePath.str(),
		m_bridgeOutboundFilePath.str()));
}

void ArchipelagoState::reset( void )
{
	// NOTE: this function is also called by engine lifecycle resets.
	// Do not wipe persistent Archipelago progress here.
	initializeBridgePaths();
	loadFromFile();
	importBridgeState(FALSE);
	syncUnlockedGroupsFromCurrentState();
	refreshUnlockedTemplateCachesFromGroups();
	ensureDefaultStartingGenerals();
	exportBridgeState();
	m_bridgePollCountdown = 0;
	DEBUG_LOG(("[Archipelago] State reset() reloaded from %s", m_saveFilePath.str()));
}

void ArchipelagoState::wipeProgress( void )
{
	m_unlockedUnits.clear();
	m_unlockedBuildings.clear();
	m_unlockedGenerals.clear();
	m_startingGenerals.clear();
	m_completedLocations.clear();
	m_completedChecks.clear();
	m_unlockedGroupIds.clear();
	m_lastImportedBridgeHash = 0;
	m_lastAppliedReceivedItemSequence = -1;
	m_appliedMissionStartOptions = FALSE;
	m_pendingMissionStartOptions = FALSE;
	m_missionStartOptionsEarliestFrame = 0;
	m_localFallbackUnlockSeed = 0x41A7C3u;
	m_localFallbackConsumedCount = 0;
	m_lastUnlockGroupId.clear();
	m_lastUnlockSource.clear();
	ensureDefaultStartingGenerals();
	saveToFile();
}

void ArchipelagoState::update( void )
{
	if (!m_initialized || m_bridgeInboundFilePath.isEmpty())
		return;

	if (m_disableZoomLimit)
	{
		if (TheTacticalView != NULL && TheTacticalView->isZoomLimited())
			TheTacticalView->setZoomLimited(FALSE);
	}

	if (m_pendingMissionStartOptions && !m_appliedMissionStartOptions && ThePlayerList != NULL && TheGameLogic != NULL)
	{
		Player *localPlayer = ThePlayerList->getLocalPlayer();
		if (localPlayer != NULL
			&& localPlayer->isPlayerActive()
			&& TheGameLogic->getFrame() >= m_missionStartOptionsEarliestFrame)
		{
			if (m_startingCashBonus > 0)
				localPlayer->getMoney()->deposit(m_startingCashBonus, FALSE, FALSE);
			m_appliedMissionStartOptions = TRUE;
			m_pendingMissionStartOptions = FALSE;
			saveToFile();
		}
	}

	if (m_bridgePollCountdown > 0)
	{
		--m_bridgePollCountdown;
		return;
	}

	m_bridgePollCountdown = 30;
	importBridgeState(TRUE);
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

Bool ArchipelagoState::isGroupSatisfied( const UnlockGroup *group ) const
{
	if (group == NULL)
		return FALSE;

	for (std::vector<AsciiString>::const_iterator it = group->templates.begin(); it != group->templates.end(); ++it)
	{
		if (isAlwaysUnlocked(*it))
			continue;

		if (TheUnlockRegistry != NULL && TheUnlockRegistry->isBuildingTemplate(*it))
		{
			if (!isBuildingUnlocked(*it))
				return FALSE;
		}
		else if (!isUnitUnlocked(*it))
		{
			return FALSE;
		}
	}

	return TRUE;
}

Bool ArchipelagoState::isGroupUnlocked( const AsciiString &groupId ) const
{
	if (m_unlockedGroupIds.find(groupId) != m_unlockedGroupIds.end())
		return TRUE;
	if (TheUnlockRegistry == NULL)
		return FALSE;
	return isGroupSatisfied(TheUnlockRegistry->findGroupByName(groupId));
}

Bool ArchipelagoState::isGeneralUnlocked( Int generalIndex ) const
{
	return m_unlockedGenerals.find(generalIndex) != m_unlockedGenerals.end();
}

Int ArchipelagoState::getUnlockedGroupCount( void ) const
{
	if (TheUnlockRegistry == NULL)
		return static_cast<Int>(m_unlockedGroupIds.size());

	Int count = 0;
	for (Int i = 0; i < TheUnlockRegistry->getGroupCount(); ++i)
	{
		const UnlockGroup *group = TheUnlockRegistry->getGroupAt(i);
		if (group != NULL && isGroupUnlocked(group->groupName))
			++count;
	}
	return count;
}

Int ArchipelagoState::getUnlockedItemPoolGroupCount( void ) const
{
	if (TheUnlockRegistry == NULL)
		return 0;

	Int count = 0;
	for (Int i = 0; i < TheUnlockRegistry->getItemPoolGroupCount(); ++i)
	{
		const UnlockGroup *group = TheUnlockRegistry->getItemPoolGroupAt(i);
		if (group != NULL && isGroupUnlocked(group->groupName))
			++count;
	}
	return count;
}

Int ArchipelagoState::getTotalItemPoolGroupCount( void ) const
{
	return TheUnlockRegistry ? TheUnlockRegistry->getItemPoolGroupCount() : 0;
}

Int ArchipelagoState::getLastAppliedReceivedItemSequence( void ) const
{
	return m_lastAppliedReceivedItemSequence;
}

Int ArchipelagoState::getStartingCashBonus( void ) const
{
	return m_startingCashBonus;
}

Real ArchipelagoState::getProductionMultiplier( void ) const
{
	return m_productionMultiplier > 0.0f ? m_productionMultiplier : 1.0f;
}

Bool ArchipelagoState::isZoomLimitDisabled( void ) const
{
	return m_disableZoomLimit;
}

AsciiString ArchipelagoState::getLastUnlockGroupId( void ) const
{
	return m_lastUnlockGroupId;
}

AsciiString ArchipelagoState::getLastUnlockSource( void ) const
{
	return m_lastUnlockSource;
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

void ArchipelagoState::applyGroupMembers( const UnlockGroup *group )
{
	if (group == NULL)
		return;

	for (std::vector<AsciiString>::const_iterator it = group->templates.begin(); it != group->templates.end(); ++it)
	{
		if (isAlwaysUnlocked(*it))
			continue;

		Bool isBuilding = TheUnlockRegistry != NULL && TheUnlockRegistry->isBuildingTemplate(*it);
		const AsciiString resolved = resolveLegacyTemplateName(*it);
		if (isBuilding)
		{
			expandUnlockAcrossFactionGenerals(resolved, TRUE, m_unlockedBuildings);
			m_unlockedBuildings.insert(*it);
			m_unlockedBuildings.insert(resolved);
		}
		else
		{
			expandUnlockAcrossFactionGenerals(resolved, FALSE, m_unlockedUnits);
			m_unlockedUnits.insert(*it);
			m_unlockedUnits.insert(resolved);
		}
	}
}

void ArchipelagoState::refreshUnlockedTemplateCachesFromGroups( void )
{
	if (TheUnlockRegistry == NULL)
		return;

	for (std::set<AsciiString>::const_iterator it = m_unlockedGroupIds.begin(); it != m_unlockedGroupIds.end(); ++it)
		applyGroupMembers(TheUnlockRegistry->findGroupByName(*it));
}

void ArchipelagoState::syncUnlockedGroupsFromCurrentState( void )
{
	if (TheUnlockRegistry == NULL)
		return;

	for (Int i = 0; i < TheUnlockRegistry->getGroupCount(); ++i)
	{
		const UnlockGroup *group = TheUnlockRegistry->getGroupAt(i);
		if (group != NULL && isGroupSatisfied(group))
			m_unlockedGroupIds.insert(group->groupName);
	}
}

Int ArchipelagoState::countRemainingItemPoolGroups( void ) const
{
	if (TheUnlockRegistry == NULL)
		return 0;

	Int remaining = 0;
	for (Int i = 0; i < TheUnlockRegistry->getItemPoolGroupCount(); ++i)
	{
		const UnlockGroup *group = TheUnlockRegistry->getItemPoolGroupAt(i);
		if (group != NULL && !isGroupUnlocked(group->groupName))
			++remaining;
	}
	return remaining;
}

AsciiString ArchipelagoState::findNextAvailableItemPoolGroup( const std::set<AsciiString> &excludedGroupIds ) const
{
	if (TheUnlockRegistry == NULL)
		return AsciiString::TheEmptyString;

	for (Int i = 0; i < TheUnlockRegistry->getItemPoolGroupCount(); ++i)
	{
		const UnlockGroup *group = TheUnlockRegistry->getItemPoolGroupAt(i);
		if (group == NULL)
			continue;
		if (excludedGroupIds.find(group->groupName) != excludedGroupIds.end())
			continue;
		if (isGroupUnlocked(group->groupName))
			continue;
		return group->groupName;
	}

	return AsciiString::TheEmptyString;
}

void ArchipelagoState::armMissionStartOptions( Bool loadingSaveGame )
{
	if (loadingSaveGame)
	{
		m_pendingMissionStartOptions = FALSE;
		m_missionStartOptionsEarliestFrame = 0;
		return;
	}

	m_appliedMissionStartOptions = FALSE;
	m_pendingMissionStartOptions = TRUE;
	if (TheGameLogic != NULL)
		m_missionStartOptionsEarliestFrame = TheGameLogic->getFrame() + (UnsignedInt)(LOGICFRAMES_PER_SECOND * 3);
	else
		m_missionStartOptionsEarliestFrame = (UnsignedInt)(LOGICFRAMES_PER_SECOND * 3);
}

void ArchipelagoState::unlockUnit( const AsciiString &templateName )
{
	const AsciiString resolved = resolveLegacyTemplateName(templateName);
	if (isAlwaysUnlocked(resolved))
		return;

	if (TheUnlockRegistry != NULL)
	{
		const UnlockGroup *group = TheUnlockRegistry->findGroupForTemplate(templateName);
		if (group == NULL && resolved.compareNoCase(templateName) != 0)
			group = TheUnlockRegistry->findGroupForTemplate(resolved);
		if (group != NULL)
		{
			applyUnlockGroupById(group->groupName, "legacy-template-unlock", TRUE);
			return;
		}
	}

	size_t before = m_unlockedUnits.size();
	expandUnlockAcrossFactionGenerals(resolved, FALSE, m_unlockedUnits);
	if (m_unlockedUnits.size() != before)
	{
		syncUnlockedGroupsFromCurrentState();
		saveToFile();
		notifyUnlock(resolved);
	}
}

void ArchipelagoState::unlockBuilding( const AsciiString &templateName )
{
	const AsciiString resolved = resolveLegacyTemplateName(templateName);
	if (isAlwaysUnlocked(resolved))
		return;

	if (TheUnlockRegistry != NULL)
	{
		const UnlockGroup *group = TheUnlockRegistry->findGroupForTemplate(templateName);
		if (group == NULL && resolved.compareNoCase(templateName) != 0)
			group = TheUnlockRegistry->findGroupForTemplate(resolved);
		if (group != NULL)
		{
			applyUnlockGroupById(group->groupName, "legacy-building-unlock", TRUE);
			return;
		}
	}

	size_t before = m_unlockedBuildings.size();
	expandUnlockAcrossFactionGenerals(resolved, TRUE, m_unlockedBuildings);
	if (m_unlockedBuildings.size() != before)
	{
		syncUnlockedGroupsFromCurrentState();
		saveToFile();
		notifyUnlock(resolved);
	}
}

Bool ArchipelagoState::unlockGroup( const UnlockGroup *group, const char* notifySuffix )
{
	if (group == NULL)
		return FALSE;
	UnlockItemOutcome outcome = applyUnlockGroupById(group->groupName, "legacy-group-unlock", TRUE, notifySuffix);
	return outcome.result == UNLOCK_ITEM_UNLOCKED || outcome.changedState;
}

ArchipelagoState::UnlockItemOutcome ArchipelagoState::applyUnlockGroupById( const AsciiString &groupId, const AsciiString &sourceTag, Bool notifyPlayer, const char *notifySuffix )
{
	UnlockItemOutcome outcome;
	outcome.groupId = groupId;
	outcome.sourceTag = sourceTag;

	if (TheUnlockRegistry == NULL)
		return outcome;

	const UnlockGroup *group = TheUnlockRegistry->findGroupByName(groupId);
	if (group == NULL)
	{
		DEBUG_LOG(("[Archipelago] Invalid unlock group id from %s: %s", sourceTag.str(), groupId.str()));
		return outcome;
	}

	outcome.groupId = group->groupName;
	outcome.displayName = group->displayName.isEmpty() ? group->groupName : group->displayName;

	Bool satisfied = isGroupSatisfied(group);
	if (m_unlockedGroupIds.insert(group->groupName).second)
		outcome.changedState = TRUE;

	if (!satisfied)
	{
		applyGroupMembers(group);
		syncUnlockedGroupsFromCurrentState();
		outcome.result = UNLOCK_ITEM_UNLOCKED;
		outcome.changedState = TRUE;
	}
	else
	{
		outcome.result = UNLOCK_ITEM_ALREADY_UNLOCKED;
	}

	m_lastUnlockGroupId = group->groupName;
	m_lastUnlockSource = sourceTag;

	if (outcome.changedState)
		saveToFile();

	if (notifyPlayer && (outcome.result == UNLOCK_ITEM_UNLOCKED || (notifySuffix != NULL && notifySuffix[0] != '\0')))
	{
		AsciiString msg = outcome.displayName;
		if (notifySuffix != NULL && notifySuffix[0] != '\0')
		{
			AsciiString withSuffix;
			withSuffix.format("%s%s", msg.str(), notifySuffix);
			msg = withSuffix;
		}
		notifyUnlock(msg);
	}

	DEBUG_LOG(("[Archipelago] Applied unlock group %s via %s result=%d changed=%d",
		group->groupName.str(),
		sourceTag.str(),
		(Int)outcome.result,
		(Int)outcome.changedState));
	return outcome;
}

ArchipelagoState::UnlockItemOutcome ArchipelagoState::consumeLocalFallbackUnlockItem( const AsciiString &sourceTag, Bool notifyPlayer )
{
	UnlockItemOutcome outcome;
	outcome.sourceTag = sourceTag;

	if (TheUnlockRegistry == NULL)
		return outcome;

	std::vector<const UnlockGroup*> remainingGroups;
	for (Int i = 0; i < TheUnlockRegistry->getItemPoolGroupCount(); ++i)
	{
		const UnlockGroup *group = TheUnlockRegistry->getItemPoolGroupAt(i);
		if (group != NULL && !isGroupUnlocked(group->groupName))
			remainingGroups.push_back(group);
	}

	++m_localFallbackConsumedCount;

	if (remainingGroups.empty())
	{
		m_lastUnlockGroupId.clear();
		m_lastUnlockSource = sourceTag;
		outcome.result = UNLOCK_ITEM_POOL_EXHAUSTED;
		outcome.cashAward = 10000;
		outcome.changedState = TRUE;
		saveToFile();
		if (notifyPlayer)
			notifyUnlock("All Archipelago items already unlocked (+$10000)");
		DEBUG_LOG(("[Archipelago] Local fallback unlock exhausted item pool via %s (+$10000)", sourceTag.str()));
		return outcome;
	}

	UnsignedInt selector = (m_localFallbackUnlockSeed ^ static_cast<UnsignedInt>(m_localFallbackConsumedCount * 2654435761u));
	Int index = static_cast<Int>(selector % static_cast<UnsignedInt>(remainingGroups.size()));
	const UnlockGroup *selectedGroup = remainingGroups[index];
	outcome = applyUnlockGroupById(selectedGroup->groupName, sourceTag, notifyPlayer, " (+$2000)");
	outcome.cashAward = outcome.result == UNLOCK_ITEM_UNLOCKED ? 2000 : 0;
	if (!outcome.changedState)
		saveToFile();
	return outcome;
}

ArchipelagoState::UnlockItemOutcome ArchipelagoState::applyConfiguredCheckReward( const AsciiString &checkId, const AsciiString &groupId, Bool notifyPlayer )
{
	std::set<AsciiString> excludedGroups;
	if (groupId.isNotEmpty())
		excludedGroups.insert(groupId);

	AsciiString resolvedGroupId = groupId;
	if (resolvedGroupId.isEmpty() || isGroupUnlocked(resolvedGroupId))
	{
		AsciiString replacementGroupId = findNextAvailableItemPoolGroup(excludedGroups);
		if (replacementGroupId.isNotEmpty())
			resolvedGroupId = replacementGroupId;
	}

	if (resolvedGroupId.isEmpty())
		return consumeLocalFallbackUnlockItem(checkId, notifyPlayer);

	UnlockItemOutcome outcome = applyUnlockGroupById(resolvedGroupId, checkId, notifyPlayer, " (+$2000)");
	outcome.cashAward = outcome.result == UNLOCK_ITEM_UNLOCKED ? 2000 : 0;
	if (!outcome.changedState)
		saveToFile();
	return outcome;
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
		for (Int i = 0; i < TheUnlockRegistry->getGroupCount(); ++i)
		{
			const UnlockGroup *group = TheUnlockRegistry->getGroupAt(i);
			if (group == NULL)
				continue;
			m_unlockedGroupIds.insert(group->groupName);
			applyGroupMembers(group);
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
	syncUnlockedGroupsFromCurrentState();

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

Bool ArchipelagoState::grantCheckForKill( const AsciiString& checkId, const AsciiString& victimTemplateName, Bool isSpawnedUnitKill )
{
	if ( checkId.isEmpty() )
		return FALSE;
	if ( m_completedChecks.find( checkId ) != m_completedChecks.end() )
		return FALSE;

	m_completedChecks.insert( checkId );
	saveToFile();
	DEBUG_LOG( ( "[Archipelago] Check complete: %s (killed %s, spawned=%d)", checkId.str(), victimTemplateName.str(), (Int)isSpawnedUnitKill ) );
	return TRUE;
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
	file << "  \"version\": 3,\n";
	writeStringArray(file, "unlockedUnits", m_unlockedUnits, TRUE);
	writeStringArray(file, "unlockedBuildings", m_unlockedBuildings, TRUE);
	writeStringArray(file, "unlockedGroupIds", m_unlockedGroupIds, TRUE);
	writeIntArray(file, "unlockedGenerals", m_unlockedGenerals, TRUE);
	writeIntArray(file, "startingGenerals", m_startingGenerals, TRUE);
	writeIntArray(file, "completedLocations", m_completedLocations, TRUE);
	writeStringArray(file, "completedChecks", m_completedChecks, TRUE);
	file << "  \"sessionOptions\": {\n";
	file << "    \"startingCashBonus\": " << m_startingCashBonus << ",\n";
	file << "    \"productionMultiplier\": " << m_productionMultiplier << ",\n";
	file << "    \"disableZoomLimit\": " << (m_disableZoomLimit ? "true" : "false") << ",\n";
	writeIntArray(file, "starterGenerals", m_sessionOptionStarterGenerals, FALSE);
	file << "  },\n";
	file << "  \"missionStartOptionsApplied\": " << (m_appliedMissionStartOptions ? "true" : "false") << ",\n";
	file << "  \"lastAppliedReceivedItemSequence\": " << m_lastAppliedReceivedItemSequence << ",\n";
	file << "  \"localFallbackUnlockSeed\": " << m_localFallbackUnlockSeed << ",\n";
	file << "  \"localFallbackConsumedCount\": " << m_localFallbackConsumedCount << "\n";
	file << "}\n";
	file.close();

	exportBridgeState();
	DEBUG_LOG(("[Archipelago] Saved state to %s", m_saveFilePath.str()));
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
	m_unlockedGroupIds.clear();
	m_unlockedGenerals.clear();
	m_startingGenerals.clear();
	m_sessionOptionStarterGenerals.clear();
	m_completedLocations.clear();
	m_completedChecks.clear();

	parseStringArray(content, "\"unlockedUnits\"", m_unlockedUnits);
	parseStringArray(content, "\"unlockedBuildings\"", m_unlockedBuildings);
	parseStringArray(content, "\"unlockedGroupIds\"", m_unlockedGroupIds);
	parseIntArray(content, "\"unlockedGenerals\"", m_unlockedGenerals);
	parseIntArray(content, "\"startingGenerals\"", m_startingGenerals);
	parseIntArray(content, "\"completedLocations\"", m_completedLocations);
	parseStringArray(content, "\"completedChecks\"", m_completedChecks);
	m_lastAppliedReceivedItemSequence = parseSingleIntField(content, "\"lastAppliedReceivedItemSequence\"", -1);
	m_localFallbackUnlockSeed = parseSingleUnsignedField(content, "\"localFallbackUnlockSeed\"", 0x41A7C3u);
	m_localFallbackConsumedCount = parseSingleIntField(content, "\"localFallbackConsumedCount\"", 0);
	BridgeSessionOptions sessionOptions;
	parseSessionOptions(content, sessionOptions);
	m_startingCashBonus = sessionOptions.startingCashBonus;
	m_productionMultiplier = sessionOptions.productionMultiplier;
	m_disableZoomLimit = sessionOptions.disableZoomLimit;
	m_sessionOptionStarterGenerals = sessionOptions.starterGenerals;
	m_appliedMissionStartOptions = parseSingleBoolField(content, "\"missionStartOptionsApplied\"", FALSE);
	m_pendingMissionStartOptions = FALSE;
	m_missionStartOptionsEarliestFrame = 0;
	syncUnlockedGroupsFromCurrentState();
	refreshUnlockedTemplateCachesFromGroups();
	DEBUG_LOG(("[Archipelago] Loaded state from %s", m_saveFilePath.str()));
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

void ArchipelagoState::dumpDebugState( void ) const
{
	AsciiString debugPath = m_bridgeDirectoryPath;
	if (debugPath.isEmpty() && TheGlobalData != NULL)
	{
		debugPath = TheGlobalData->getPath_UserData();
		debugPath.concat("Archipelago\\");
	}
	if (debugPath.isEmpty())
		debugPath = ".\\";

	if (TheFileSystem != NULL)
		TheFileSystem->createDirectory(debugPath);

	debugPath.concat("ArchipelagoUnlockState.json");
	std::ofstream file(debugPath.str());
	if (!file.is_open())
		return;

	file << "{\n";
	file << "  \"saveFilePath\": \"";
	escapeJsonString(file, m_saveFilePath.str());
	file << "\",\n";
	file << "  \"lastAppliedReceivedItemSequence\": " << m_lastAppliedReceivedItemSequence << ",\n";
	file << "  \"localFallbackUnlockSeed\": " << m_localFallbackUnlockSeed << ",\n";
	file << "  \"localFallbackConsumedCount\": " << m_localFallbackConsumedCount << ",\n";
	file << "  \"lastUnlockGroupId\": \"";
	escapeJsonString(file, m_lastUnlockGroupId.str());
	file << "\",\n";
	file << "  \"lastUnlockSource\": \"";
	escapeJsonString(file, m_lastUnlockSource.str());
	file << "\",\n";
	writeStringArray(file, "unlockedGroupIds", m_unlockedGroupIds, TRUE);
	writeStringArray(file, "unlockedUnits", m_unlockedUnits, TRUE);
	writeStringArray(file, "unlockedBuildings", m_unlockedBuildings, TRUE);
	writeStringArray(file, "completedChecks", m_completedChecks, TRUE);
	writeIntArray(file, "completedLocations", m_completedLocations, TRUE);
	file << "  \"remainingItemPoolGroups\": " << countRemainingItemPoolGroups() << ",\n";
	file << "  \"groups\": [\n";
	if (TheUnlockRegistry != NULL)
	{
		for (Int i = 0; i < TheUnlockRegistry->getGroupCount(); ++i)
		{
			const UnlockGroup *group = TheUnlockRegistry->getGroupAt(i);
			if (group == NULL)
				continue;
			file << "    {\n";
			file << "      \"groupId\": \"";
			escapeJsonString(file, group->groupName.str());
			file << "\",\n";
			file << "      \"displayName\": \"";
			escapeJsonString(file, (group->displayName.isEmpty() ? group->groupName : group->displayName).str());
			file << "\",\n";
			file << "      \"itemPool\": " << (group->itemPool ? "true" : "false") << ",\n";
			file << "      \"unlocked\": " << (isGroupUnlocked(group->groupName) ? "true" : "false") << ",\n";
			file << "      \"memberCount\": " << static_cast<Int>(group->templates.size()) << "\n";
			file << "    }";
			if (i + 1 < TheUnlockRegistry->getGroupCount())
				file << ",";
			file << "\n";
		}
	}
	file << "  ]\n";
	file << "}\n";
	file.close();
	DEBUG_LOG(("[Archipelago] Wrote debug state dump to %s", debugPath.str()));
}

AsciiString ArchipelagoState::getSaveFilePath( void ) const
{
	return m_saveFilePath;
}

AsciiString ArchipelagoState::getBridgeDirectoryPath( void ) const
{
	return m_bridgeDirectoryPath;
}

AsciiString ArchipelagoState::getBridgeInboundFilePath( void ) const
{
	return m_bridgeInboundFilePath;
}

AsciiString ArchipelagoState::getBridgeOutboundFilePath( void ) const
{
	return m_bridgeOutboundFilePath;
}

void ArchipelagoState::initializeBridgePaths( void )
{
	if (TheGlobalData != NULL)
	{
		m_bridgeDirectoryPath = TheGlobalData->getPath_UserData();
		m_bridgeDirectoryPath.concat("Archipelago\\");
		m_bridgeInboundFilePath = m_bridgeDirectoryPath;
		m_bridgeInboundFilePath.concat("Bridge-Inbound.json");
		m_bridgeOutboundFilePath = m_bridgeDirectoryPath;
		m_bridgeOutboundFilePath.concat("Bridge-Outbound.json");

		if (TheFileSystem != NULL)
			TheFileSystem->createDirectory(m_bridgeDirectoryPath);
	}
	else
	{
		m_bridgeDirectoryPath = AsciiString::TheEmptyString;
		m_bridgeInboundFilePath = "Bridge-Inbound.json";
		m_bridgeOutboundFilePath = "Bridge-Outbound.json";
	}

	DEBUG_LOG(("[Archipelago] Bridge paths: dir=%s inbound=%s outbound=%s",
		m_bridgeDirectoryPath.str(),
		m_bridgeInboundFilePath.str(),
		m_bridgeOutboundFilePath.str()));
}

Bool ArchipelagoState::mergeBridgeState(
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
	Bool disableZoomLimit )
{
	Bool changed = FALSE;

	for (std::set<AsciiString>::const_iterator it = unlockedUnits.begin(); it != unlockedUnits.end(); ++it)
	{
		const AsciiString resolved = resolveLegacyTemplateName(*it);
		if (isAlwaysUnlocked(resolved))
			continue;

		size_t before = m_unlockedUnits.size();
		expandUnlockAcrossFactionGenerals(resolved, FALSE, m_unlockedUnits);
		m_unlockedUnits.insert(*it);
		m_unlockedUnits.insert(resolved);
		if (m_unlockedUnits.size() != before)
			changed = TRUE;
	}

	for (std::set<AsciiString>::const_iterator it = unlockedBuildings.begin(); it != unlockedBuildings.end(); ++it)
	{
		const AsciiString resolved = resolveLegacyTemplateName(*it);
		if (isAlwaysUnlocked(resolved))
			continue;

		size_t before = m_unlockedBuildings.size();
		expandUnlockAcrossFactionGenerals(resolved, TRUE, m_unlockedBuildings);
		m_unlockedBuildings.insert(*it);
		m_unlockedBuildings.insert(resolved);
		if (m_unlockedBuildings.size() != before)
			changed = TRUE;
	}

	for (std::set<AsciiString>::const_iterator it = unlockedGroupIds.begin(); it != unlockedGroupIds.end(); ++it)
	{
		const UnlockGroup *group = TheUnlockRegistry ? TheUnlockRegistry->findGroupByName(*it) : NULL;
		if (group == NULL)
			continue;
		size_t beforeGroups = m_unlockedGroupIds.size();
		m_unlockedGroupIds.insert(group->groupName);
		applyGroupMembers(group);
		if (m_unlockedGroupIds.size() != beforeGroups)
			changed = TRUE;
	}

	for (std::set<Int>::const_iterator it = unlockedGenerals.begin(); it != unlockedGenerals.end(); ++it)
	{
		if (m_unlockedGenerals.insert(*it).second)
			changed = TRUE;
	}

	for (std::set<Int>::const_iterator it = startingGenerals.begin(); it != startingGenerals.end(); ++it)
	{
		if (m_startingGenerals.insert(*it).second)
			changed = TRUE;
		if (m_unlockedGenerals.insert(*it).second)
			changed = TRUE;
	}

	if (m_sessionOptionStarterGenerals != sessionStarterGenerals)
	{
		m_sessionOptionStarterGenerals = sessionStarterGenerals;
		changed = TRUE;
	}

	for (std::set<Int>::const_iterator it = m_sessionOptionStarterGenerals.begin(); it != m_sessionOptionStarterGenerals.end(); ++it)
	{
		if (m_startingGenerals.insert(*it).second)
			changed = TRUE;
		if (m_unlockedGenerals.insert(*it).second)
			changed = TRUE;
	}

	for (std::set<Int>::const_iterator it = completedLocations.begin(); it != completedLocations.end(); ++it)
	{
		if (m_completedLocations.insert(*it).second)
			changed = TRUE;
	}

	for (std::set<AsciiString>::const_iterator it = completedChecks.begin(); it != completedChecks.end(); ++it)
	{
		if (m_completedChecks.insert(*it).second)
			changed = TRUE;
	}

	size_t groupsBeforeSync = m_unlockedGroupIds.size();
	syncUnlockedGroupsFromCurrentState();
	if (m_unlockedGroupIds.size() != groupsBeforeSync)
		changed = TRUE;

	if (m_startingCashBonus != startingCashBonus)
	{
		m_startingCashBonus = startingCashBonus;
		m_appliedMissionStartOptions = FALSE;
		m_pendingMissionStartOptions = TRUE;
		m_missionStartOptionsEarliestFrame = TheGameLogic != NULL
			? TheGameLogic->getFrame() + (UnsignedInt)LOGICFRAMES_PER_SECOND
			: (UnsignedInt)LOGICFRAMES_PER_SECOND;
		changed = TRUE;
	}

	Real normalizedProductionMultiplier = productionMultiplier > 0.0f ? productionMultiplier : 1.0f;
	if (m_productionMultiplier != normalizedProductionMultiplier)
	{
		m_productionMultiplier = normalizedProductionMultiplier;
		changed = TRUE;
	}

	if (m_disableZoomLimit != disableZoomLimit)
	{
		m_disableZoomLimit = disableZoomLimit;
		changed = TRUE;
	}

	return changed;
}

void ArchipelagoState::importBridgeState( Bool logChanges )
{
	if (m_bridgeInboundFilePath.isEmpty())
		return;
	if (TheFileSystem != NULL && !TheFileSystem->doesFileExist(m_bridgeInboundFilePath.str()))
		return;

	std::ifstream file(m_bridgeInboundFilePath.str());
	if (!file.is_open())
		return;

	std::stringstream buffer;
	buffer << file.rdbuf();
	std::string content = buffer.str();
	if (content.empty())
		return;

	UnsignedInt hash = hashBridgeContent(content);
	if (hash == m_lastImportedBridgeHash)
		return;

	std::set<AsciiString> unlockedUnits;
	std::set<AsciiString> unlockedBuildings;
	std::set<AsciiString> unlockedGroupIds;
	std::set<Int> unlockedGenerals;
	std::set<Int> startingGenerals;
	BridgeSessionOptions sessionOptions;
	std::set<Int> completedLocations;
	std::set<AsciiString> completedChecks;
	std::vector<BridgeReceivedItem> receivedItems;

	parseStringArray(content, "\"unlockedUnits\"", unlockedUnits);
	parseStringArray(content, "\"unlockedBuildings\"", unlockedBuildings);
	parseStringArray(content, "\"unlockedGroupIds\"", unlockedGroupIds);
	parseIntArray(content, "\"unlockedGenerals\"", unlockedGenerals);
	parseIntArray(content, "\"startingGenerals\"", startingGenerals);
	parseSessionOptions(content, sessionOptions);
	parseIntArray(content, "\"completedLocations\"", completedLocations);
	parseStringArray(content, "\"completedChecks\"", completedChecks);
	parseReceivedItems(content, receivedItems);

	Bool changed = mergeBridgeState(
		unlockedUnits,
		unlockedBuildings,
		unlockedGroupIds,
		unlockedGenerals,
		startingGenerals,
		sessionOptions.starterGenerals,
		completedLocations,
		completedChecks,
		sessionOptions.startingCashBonus,
		sessionOptions.productionMultiplier,
		sessionOptions.disableZoomLimit );

	for (std::vector<BridgeReceivedItem>::const_iterator it = receivedItems.begin(); it != receivedItems.end(); ++it)
	{
		if (it->sequence <= m_lastAppliedReceivedItemSequence)
			continue;

		if (it->kind.compareNoCase("unlock_group") == 0)
		{
			UnlockItemOutcome outcome = applyUnlockGroupById(it->groupId, "bridge-received-item", FALSE);
			if (outcome.result == UNLOCK_ITEM_INVALID)
				DEBUG_LOG(("[Archipelago] Ignoring invalid inbound unlock group %s at sequence %d", it->groupId.str(), it->sequence));
		}
		else
		{
			DEBUG_LOG(("[Archipelago] Unsupported inbound received item kind %s at sequence %d", it->kind.str(), it->sequence));
		}

		m_lastAppliedReceivedItemSequence = it->sequence;
		changed = TRUE;
	}

	m_lastImportedBridgeHash = hash;
	if (changed)
	{
		saveToFile();
		if (logChanges)
			DEBUG_LOG(("[Archipelago] Imported bridge state from %s", m_bridgeInboundFilePath.str()));
	}
}

void ArchipelagoState::exportBridgeState( void ) const
{
	if (m_bridgeOutboundFilePath.isEmpty())
		return;

	std::ofstream file(m_bridgeOutboundFilePath.str());
	if (!file.is_open())
		return;

	file << "{\n";
	file << "  \"bridgeVersion\": 1,\n";
	file << "  \"stateVersion\": 3,\n";
	file << "  \"syncMode\": \"merge-only\",\n";
	file << "  \"runtimeSpawnSource\": \"UnlockableChecksDemo.ini fallback\",\n";
	file << "  \"saveFilePath\": \"";
	escapeJsonString(file, m_saveFilePath.str());
	file << "\",\n";
	writeStringArray(file, "unlockedUnits", m_unlockedUnits, TRUE);
	writeStringArray(file, "unlockedBuildings", m_unlockedBuildings, TRUE);
	writeStringArray(file, "unlockedGroupIds", m_unlockedGroupIds, TRUE);
	writeIntArray(file, "unlockedGenerals", m_unlockedGenerals, TRUE);
	writeIntArray(file, "startingGenerals", m_startingGenerals, TRUE);
	writeIntArray(file, "completedLocations", m_completedLocations, TRUE);
	writeStringArray(file, "completedChecks", m_completedChecks, TRUE);
	file << "  \"sessionOptions\": {\n";
	file << "    \"startingCashBonus\": " << m_startingCashBonus << ",\n";
	file << "    \"productionMultiplier\": " << m_productionMultiplier << ",\n";
	file << "    \"disableZoomLimit\": " << (m_disableZoomLimit ? "true" : "false") << ",\n";
	writeIntArray(file, "starterGenerals", m_sessionOptionStarterGenerals, FALSE);
	file << "  },\n";
	file << "  \"lastAppliedReceivedItemSequence\": " << m_lastAppliedReceivedItemSequence << "\n";
	file << "}\n";
	file.close();
	DEBUG_LOG(("[Archipelago] Exported bridge state to %s", m_bridgeOutboundFilePath.str()));
}

void ArchipelagoState::ensureDefaultStartingGenerals( void )
{
	if (!m_startingGenerals.empty())
	{
		for (std::set<Int>::const_iterator it = m_startingGenerals.begin(); it != m_startingGenerals.end(); ++it)
			m_unlockedGenerals.insert(*it);
		return;
	}

	if (!m_sessionOptionStarterGenerals.empty())
	{
		for (std::set<Int>::const_iterator it = m_sessionOptionStarterGenerals.begin(); it != m_sessionOptionStarterGenerals.end(); ++it)
		{
			m_startingGenerals.insert(*it);
			m_unlockedGenerals.insert(*it);
		}
	}
	else
	{
		m_startingGenerals.insert(GENERAL_USA_SUPERWEAPON);
		m_unlockedGenerals.insert(GENERAL_USA_SUPERWEAPON);
	}

	saveToFile();
}
