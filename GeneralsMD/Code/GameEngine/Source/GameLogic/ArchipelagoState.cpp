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
#include "Common/Team.h"
#include "GameLogic/UnlockableCheckSpawner.h"
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
#include "GameNetwork/GameInfo.h"
#include "Common/Money.h"

#include <algorithm>
#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <fstream>
#include <string>

ArchipelagoState *TheArchipelagoState = NULL;

static std::string readTextFile(std::ifstream &file)
{
	std::string content;
	char buffer[4096];
	while (file.read(buffer, sizeof(buffer)))
		content.append(buffer, static_cast<size_t>(file.gcount()));
	if (file.gcount() > 0)
		content.append(buffer, static_cast<size_t>(file.gcount()));
	return content;
}

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

static std::string parseRawArrayField(const std::string &content, const char *key)
{
	size_t keyPos = content.find(key);
	if (keyPos == std::string::npos)
		return "[]";
	size_t start = content.find('[', keyPos);
	if (start == std::string::npos)
		return "[]";

	Int depth = 0;
	Bool inString = FALSE;
	Bool escaped = FALSE;
	for (size_t pos = start; pos < content.size(); ++pos)
	{
		const char ch = content[pos];
		if (inString)
		{
			if (escaped)
				escaped = FALSE;
			else if (ch == '\\')
				escaped = TRUE;
			else if (ch == '"')
				inString = FALSE;
			continue;
		}

		if (ch == '"')
		{
			inString = TRUE;
		}
		else if (ch == '[')
		{
			++depth;
		}
		else if (ch == ']')
		{
			--depth;
			if (depth == 0)
				return content.substr(start, pos - start + 1);
			if (depth < 0)
				return "[]";
		}
	}

	return "[]";
}

static void writeRawJsonArray(std::ostream &out, const char *key, const std::string &rawArray, Bool trailingComma)
{
	out << "  \"" << key << "\": ";
	if (!rawArray.empty() && rawArray[0] == '[')
		out << rawArray;
	else
		out << "[]";
	if (trailingComma)
		out << ",";
	out << "\n";
}

static void writeFutureLocationStateArrays(
	std::ostream &out,
	const std::string &capturedBuildingStateJson,
	const std::string &supplyPileStateJson,
	Bool trailingComma )
{
	writeRawJsonArray(out, "capturedBuildingState", capturedBuildingStateJson, TRUE);
	writeRawJsonArray(out, "supplyPileState", supplyPileStateJson, trailingComma);
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

struct BridgeSessionMetadata
{
	AsciiString seedId;
	AsciiString slotName;
	AsciiString sessionNonce;
	Int slotDataVersion;
	AsciiString slotDataPath;
	AsciiString slotDataHash;

	BridgeSessionMetadata() :
		slotDataVersion(0)
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
		while (pos < end && !isdigit(static_cast<unsigned char>(content[pos])) && content[pos] != '-')
			++pos;
		if (pos >= end)
			break;
		size_t numEnd = pos + 1;
		while (numEnd < end && isdigit(static_cast<unsigned char>(content[numEnd])))
			++numEnd;
		std::string numStr = content.substr(pos, numEnd - pos);
		out.insert(static_cast<Int>(atoi(numStr.c_str())));
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
	while (pos < content.size() && !isdigit(static_cast<unsigned char>(content[pos])) && content[pos] != '-')
		++pos;
	if (pos >= content.size())
		return defaultValue;

	size_t numEnd = pos + 1;
	while (numEnd < content.size() && isdigit(static_cast<unsigned char>(content[numEnd])))
		++numEnd;
	return static_cast<Int>(atoi(content.substr(pos, numEnd - pos).c_str()));
}

static UnsignedInt parseSingleUnsignedField(const std::string &content, const char *key, UnsignedInt defaultValue)
{
	Int parsed = parseSingleIntField(content, key, static_cast<Int>(defaultValue));
	return parsed < 0 ? defaultValue : static_cast<UnsignedInt>(parsed);
}

static Bool compareBridgeReceivedItemsBySequence(const BridgeReceivedItem &lhs, const BridgeReceivedItem &rhs);

static Int hexDigitValue(char ch)
{
	if (ch >= '0' && ch <= '9')
		return ch - '0';
	if (ch >= 'a' && ch <= 'f')
		return ch - 'a' + 10;
	if (ch >= 'A' && ch <= 'F')
		return ch - 'A' + 10;
	return -1;
}

static std::string decodeJsonStringLiteral(const std::string &value)
{
	std::string out;
	out.reserve(value.size());
	for (size_t i = 0; i < value.size(); ++i)
	{
		if (value[i] != '\\' || i + 1 >= value.size())
		{
			out.push_back(value[i]);
			continue;
		}

		const char escaped = value[++i];
		switch (escaped)
		{
			case '"': out.push_back('"'); break;
			case '\\': out.push_back('\\'); break;
			case '/': out.push_back('/'); break;
			case 'b': out.push_back('\b'); break;
			case 'f': out.push_back('\f'); break;
			case 'n': out.push_back('\n'); break;
			case 'r': out.push_back('\r'); break;
			case 't': out.push_back('\t'); break;
			case 'u':
			{
				if (i + 4 >= value.size())
				{
					out.append("\\u");
					break;
				}
				Int codepoint = 0;
				Bool valid = TRUE;
				for (Int digit = 0; digit < 4; ++digit)
				{
					const Int hex = hexDigitValue(value[i + 1 + digit]);
					if (hex < 0)
					{
						valid = FALSE;
						break;
					}
					codepoint = (codepoint << 4) | hex;
				}
				if (!valid)
				{
					out.append("\\u");
					break;
				}
				i += 4;
				if (codepoint <= 0x7f)
				{
					out.push_back(static_cast<char>(codepoint));
				}
				else if (codepoint <= 0x7ff)
				{
					out.push_back(static_cast<char>(0xc0 | ((codepoint >> 6) & 0x1f)));
					out.push_back(static_cast<char>(0x80 | (codepoint & 0x3f)));
				}
				else
				{
					out.push_back(static_cast<char>(0xe0 | ((codepoint >> 12) & 0x0f)));
					out.push_back(static_cast<char>(0x80 | ((codepoint >> 6) & 0x3f)));
					out.push_back(static_cast<char>(0x80 | (codepoint & 0x3f)));
				}
				break;
			}
			default:
				out.push_back(escaped);
				break;
		}
	}
	return out;
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
	return AsciiString(decodeJsonStringLiteral(content.substr(open + 1, close - open - 1)).c_str());
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
	while (pos < content.size() && isspace(static_cast<unsigned char>(content[pos])))
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
		!isdigit(static_cast<unsigned char>(content[pos])) &&
		content[pos] != '-' && content[pos] != '+')
	{
		++pos;
	}
	if (pos >= content.size())
		return defaultValue;

	size_t valueEnd = pos + 1;
	while (valueEnd < content.size() &&
		(isdigit(static_cast<unsigned char>(content[valueEnd])) || content[valueEnd] == '.'))
	{
		++valueEnd;
	}
	return (Real)atof(content.substr(pos, valueEnd - pos).c_str());
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

static void parseSessionMetadata(const std::string &content, BridgeSessionMetadata &out)
{
	out.seedId = parseSingleStringField(content, "\"seedId\"");
	out.slotName = parseSingleStringField(content, "\"slotName\"");
	out.sessionNonce = parseSingleStringField(content, "\"sessionNonce\"");
	out.slotDataVersion = parseSingleIntField(content, "\"slotDataVersion\"", 0);
	out.slotDataPath = parseSingleStringField(content, "\"slotDataPath\"");
	out.slotDataHash = parseSingleStringField(content, "\"slotDataHash\"");
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

	std::sort(out.begin(), out.end(), compareBridgeReceivedItemsBySequence);
}

static Bool compareBridgeReceivedItemsBySequence(const BridgeReceivedItem &lhs, const BridgeReceivedItem &rhs)
{
	return lhs.sequence < rhs.sequence;
}

static std::string toLowerString(const char *text)
{
	std::string out = text ? text : "";
	for (size_t i = 0; i < out.size(); ++i)
		out[i] = (char)tolower((unsigned char)out[i]);
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
	m_lastImportedSessionNonce(AsciiString::TheEmptyString),
	m_slotDataReferencePresent(FALSE),
	m_slotDataLoadFailed(FALSE),
	m_lastAppliedReceivedItemSequence(-1),
	m_startingCashBonus(0),
	m_productionMultiplier(1.0f),
	m_disableZoomLimit(FALSE),
	m_capturedBuildingStateJson("[]"),
	m_supplyPileStateJson("[]"),
	m_appliedMissionStartOptions(FALSE),
	m_pendingMissionStartOptions(FALSE),
	m_missionStartCashTarget(0u),
	m_missionStartOptionsEarliestFrame(0),
	m_missionStartOptionsLatestFrame(0),
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
	processRuntimeSmokeCompletionFile();
	processRuntimeSmokeDumpFile();
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
	processRuntimeSmokeCompletionFile();
	processRuntimeSmokeDumpFile();
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
	m_lastImportedSessionNonce.clear();
	m_slotData.reset();
	m_slotDataReferencePresent = FALSE;
	m_slotDataLoadFailed = FALSE;
	m_lastSlotDataHash.clear();
	m_lastSlotDataSessionNonce.clear();
	m_lastSlotDataError.clear();
	m_missionStartCashTarget = 0u;
	m_missionStartOptionsEarliestFrame = 0;
	m_missionStartOptionsLatestFrame = 0;
	m_localFallbackUnlockSeed = 0x41A7C3u;
	m_localFallbackConsumedCount = 0;
	m_capturedBuildingStateJson = "[]";
	m_supplyPileStateJson = "[]";
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
			&& TheGameLogic->getFrame() >= m_missionStartOptionsEarliestFrame)
		{
			if (m_startingCashBonus > 0)
			{
				const UnsignedInt targetCash = (UnsignedInt)m_startingCashBonus;
				Money *money = localPlayer->getMoney();
				if (TheGameInfo != NULL)
				{
					Money gameStartingCash = TheGameInfo->getStartingCash();
					if (gameStartingCash.countMoney() != targetCash)
						gameStartingCash.setStartingCash(targetCash);
					TheGameInfo->setStartingCash(gameStartingCash);
				}

				const UnsignedInt currentCash = money->countMoney();
				if (currentCash < targetCash)
				{
					money->deposit(targetCash - currentCash, FALSE, FALSE);
					DEBUG_LOG(("[Archipelago] Applied mission-start cash top-up: current=%u target=%u", currentCash, targetCash));
				}
			}
			if (TheGameLogic->getFrame() >= m_missionStartOptionsLatestFrame)
			{
				m_appliedMissionStartOptions = TRUE;
				m_pendingMissionStartOptions = FALSE;
				saveToFile();
			}
		}
	}

	if (m_bridgePollCountdown > 0)
	{
		--m_bridgePollCountdown;
		return;
	}

	m_bridgePollCountdown = 30;
	importBridgeState(TRUE);
	processRuntimeSmokeCompletionFile();
	processRuntimeSmokeDumpFile();
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

	for (std::vector<AsciiString>::const_iterator groupTemplateIt = group->templates.begin(); groupTemplateIt != group->templates.end(); ++groupTemplateIt)
	{
		if (isAlwaysUnlocked(*groupTemplateIt))
			continue;

		if (TheUnlockRegistry != NULL && TheUnlockRegistry->isBuildingTemplate(*groupTemplateIt))
		{
			if (!isBuildingUnlocked(*groupTemplateIt))
				return FALSE;
		}
		else if (!isUnitUnlocked(*groupTemplateIt))
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

	for (const char **usaAlwaysIt = usaAlways; *usaAlwaysIt; ++usaAlwaysIt)
	{
		if (templateName.compareNoCase(*usaAlwaysIt) == 0)
			return TRUE;
	}
	for (const char **chinaAlwaysIt = chinaAlways; *chinaAlwaysIt; ++chinaAlwaysIt)
	{
		if (templateName.compareNoCase(*chinaAlwaysIt) == 0)
			return TRUE;
	}
	for (const char **glaAlwaysIt = glaAlways; *glaAlwaysIt; ++glaAlwaysIt)
	{
		if (templateName.compareNoCase(*glaAlwaysIt) == 0)
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

	for (std::vector<AsciiString>::const_iterator memberTemplateIt = group->templates.begin(); memberTemplateIt != group->templates.end(); ++memberTemplateIt)
	{
		if (isAlwaysUnlocked(*memberTemplateIt))
			continue;

		Bool isBuilding = TheUnlockRegistry != NULL && TheUnlockRegistry->isBuildingTemplate(*memberTemplateIt);
		const AsciiString resolved = resolveLegacyTemplateName(*memberTemplateIt);

		if (group->expandGenerals)
		{
			if (isBuilding)
				expandUnlockAcrossFactionGenerals(resolved, TRUE, m_unlockedBuildings);
			else
				expandUnlockAcrossFactionGenerals(resolved, FALSE, m_unlockedUnits);
		}

		if (isBuilding)
		{
			m_unlockedBuildings.insert(*memberTemplateIt);
			m_unlockedBuildings.insert(resolved);
		}
		else
		{
			m_unlockedUnits.insert(*memberTemplateIt);
			m_unlockedUnits.insert(resolved);
		}
	}
}

void ArchipelagoState::refreshUnlockedTemplateCachesFromGroups( void )
{
	if (TheUnlockRegistry == NULL)
		return;

	for (std::set<AsciiString>::const_iterator unlockedGroupIt = m_unlockedGroupIds.begin(); unlockedGroupIt != m_unlockedGroupIds.end(); ++unlockedGroupIt)
		applyGroupMembers(TheUnlockRegistry->findGroupByName(*unlockedGroupIt));
}

void ArchipelagoState::syncUnlockedGroupsFromCurrentState( void )
{
	if (TheUnlockRegistry == NULL)
		return;

	for (Int groupIndex = 0; groupIndex < TheUnlockRegistry->getGroupCount(); ++groupIndex)
	{
		const UnlockGroup *group = TheUnlockRegistry->getGroupAt(groupIndex);
		if (group != NULL && isGroupSatisfied(group))
			m_unlockedGroupIds.insert(group->groupName);
	}
}

Int ArchipelagoState::countRemainingItemPoolGroups( void ) const
{
	if (TheUnlockRegistry == NULL)
		return 0;

	Int remaining = 0;
	for (Int remainingGroupIndex = 0; remainingGroupIndex < TheUnlockRegistry->getItemPoolGroupCount(); ++remainingGroupIndex)
	{
		const UnlockGroup *group = TheUnlockRegistry->getItemPoolGroupAt(remainingGroupIndex);
		if (group != NULL && !isGroupUnlocked(group->groupName))
			++remaining;
	}
	return remaining;
}

AsciiString ArchipelagoState::findNextAvailableItemPoolGroup( const std::set<AsciiString> &excludedGroupIds ) const
{
	if (TheUnlockRegistry == NULL)
		return AsciiString::TheEmptyString;

	for (Int candidateGroupIndex = 0; candidateGroupIndex < TheUnlockRegistry->getItemPoolGroupCount(); ++candidateGroupIndex)
	{
		const UnlockGroup *group = TheUnlockRegistry->getItemPoolGroupAt(candidateGroupIndex);
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
		m_missionStartCashTarget = 0u;
		m_missionStartOptionsEarliestFrame = 0;
		m_missionStartOptionsLatestFrame = 0;
		return;
	}

	m_appliedMissionStartOptions = FALSE;
	m_pendingMissionStartOptions = TRUE;
	m_missionStartCashTarget = 0u;
	if (TheGameInfo != NULL && m_startingCashBonus > 0)
	{
		const UnsignedInt targetCash = (UnsignedInt)m_startingCashBonus;
		Money gameStartingCash = TheGameInfo->getStartingCash();
		if (gameStartingCash.countMoney() != targetCash)
		{
			gameStartingCash.setStartingCash(targetCash);
			TheGameInfo->setStartingCash(gameStartingCash);
		}
	}
	if (TheGameLogic != NULL)
	{
		m_missionStartOptionsEarliestFrame = TheGameLogic->getFrame();
		m_missionStartOptionsLatestFrame = m_missionStartOptionsEarliestFrame + (UnsignedInt)(LOGICFRAMES_PER_SECOND * 90);
	}
	else
	{
		m_missionStartOptionsEarliestFrame = 0u;
		m_missionStartOptionsLatestFrame = (UnsignedInt)(LOGICFRAMES_PER_SECOND * 90);
	}
}

UnsignedInt ArchipelagoState::adjustMissionStartMoneyForPlayer( const Player *player, UnsignedInt requestedMoney ) const
{
	if (player == NULL || m_startingCashBonus <= 0 || !m_pendingMissionStartOptions || TheGameLogic == NULL || ThePlayerList == NULL)
		return requestedMoney;

	const UnsignedInt frame = TheGameLogic->getFrame();
	if (frame < m_missionStartOptionsEarliestFrame || frame > m_missionStartOptionsLatestFrame)
		return requestedMoney;

	const Player *localPlayer = ThePlayerList->getLocalPlayer();
	if (localPlayer == NULL || player != localPlayer)
		return requestedMoney;

	const UnsignedInt targetMoney = (UnsignedInt)m_startingCashBonus;
	return requestedMoney < targetMoney ? targetMoney : requestedMoney;
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
	for (Int fallbackGroupIndex = 0; fallbackGroupIndex < TheUnlockRegistry->getItemPoolGroupCount(); ++fallbackGroupIndex)
	{
		const UnlockGroup *group = TheUnlockRegistry->getItemPoolGroupAt(fallbackGroupIndex);
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
	outcome = applyUnlockGroupById(selectedGroup->groupName, sourceTag, notifyPlayer, " (+$1000)");
	outcome.cashAward = outcome.result == UNLOCK_ITEM_UNLOCKED ? 1000 : 0;
	if (!outcome.changedState)
		saveToFile();
	return outcome;
}

ArchipelagoState::UnlockItemOutcome ArchipelagoState::applyConfiguredCheckReward( const AsciiString &checkId, const AsciiString &groupId, Bool notifyPlayer )
{
	if (groupId.isEmpty())
		return consumeLocalFallbackUnlockItem(checkId, notifyPlayer);
	if (groupId.compareNoCase("__no_upgrade__") == 0)
	{
		UnlockItemOutcome outcome;
		outcome.result = UNLOCK_ITEM_ALREADY_UNLOCKED;
		outcome.groupId = groupId;
		outcome.displayName = "No upgrade";
		outcome.sourceTag = checkId;
		outcome.cashAward = 1000;
		m_lastUnlockGroupId.clear();
		m_lastUnlockSource = checkId;
		if (notifyPlayer)
			notifyUnlock("No upgrade (+$1000)");
		return outcome;
	}

	// If the configured reward group doesn't exist (e.g. granularity changed the group names),
	// fall back to a random item from the pool instead of silently failing.
	if (TheUnlockRegistry != NULL && TheUnlockRegistry->findGroupByName(groupId) == NULL)
	{
		DEBUG_LOG(("[Archipelago] Configured reward group %s not found for check %s, using fallback", groupId.str(), checkId.str()));
		return consumeLocalFallbackUnlockItem(checkId, notifyPlayer);
	}

	UnlockItemOutcome outcome = applyUnlockGroupById(groupId, checkId, notifyPlayer, " (+$1000)");
	outcome.cashAward = outcome.result == UNLOCK_ITEM_UNLOCKED ? 1000 : 0;
	if (!outcome.changedState)
		saveToFile();
	return outcome;
}

ArchipelagoState::UnlockItemOutcome ArchipelagoState::replayConfiguredCheckReward( const AsciiString &checkId, const AsciiString &groupId, Bool notifyPlayer )
{
	UnlockItemOutcome outcome;
	outcome.sourceTag = checkId;
	outcome.cashAward = 1000;

	if (groupId.compareNoCase("__no_upgrade__") == 0)
	{
		outcome.result = UNLOCK_ITEM_ALREADY_UNLOCKED;
		outcome.displayName = "No upgrade";
		m_lastUnlockGroupId.clear();
		m_lastUnlockSource = checkId;
		if (notifyPlayer)
			notifyUnlock("No upgrade (+$1000)");
		DEBUG_LOG(("[Archipelago] Replayed no-upgrade reward for %s (+$1000)", checkId.str()));
		return outcome;
	}

	if (groupId.isEmpty() || TheUnlockRegistry == NULL)
	{
		outcome.result = UNLOCK_ITEM_ALREADY_UNLOCKED;
		outcome.displayName = "Cleared";
		m_lastUnlockGroupId.clear();
		m_lastUnlockSource = checkId;
		if (notifyPlayer)
			notifyUnlock("Cleared (+$1000)");
		DEBUG_LOG(("[Archipelago] Replayed generic configured check reward for %s (+$1000)", checkId.str()));
		return outcome;
	}

	const UnlockGroup *group = TheUnlockRegistry->findGroupByName(groupId);
	if (group == NULL)
	{
		// Configured group doesn't exist (e.g. granularity changed the group names).
		// Fall back to a random item from the pool instead of returning "Cleared".
		DEBUG_LOG(("[Archipelago] Replay: configured group %s not found for check %s, using fallback", groupId.str(), checkId.str()));
		return consumeLocalFallbackUnlockItem(checkId, notifyPlayer);
	}

	if (!isGroupUnlocked(group->groupName))
	{
		outcome = applyUnlockGroupById(group->groupName, checkId, notifyPlayer, " (+$1000)");
		outcome.cashAward = 1000;
		return outcome;
	}

	outcome.result = UNLOCK_ITEM_ALREADY_UNLOCKED;
	outcome.groupId = group->groupName;
	outcome.displayName = group->displayName.isEmpty() ? group->groupName : group->displayName;
	m_lastUnlockGroupId = group->groupName;
	m_lastUnlockSource = checkId;
	if (notifyPlayer)
	{
		AsciiString msg;
		msg.format("%s (+$1000)", outcome.displayName.str());
		notifyUnlock(msg);
	}
	DEBUG_LOG(("[Archipelago] Replayed configured check reward %s for duplicate check %s (+$1000)", group->groupName.str(), checkId.str()));
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
	for (Int generalIndex = 0; generalIndex < GENERAL_COUNT; ++generalIndex)
		m_unlockedGenerals.insert(generalIndex);

	if (TheUnlockRegistry != NULL)
	{
		for (Int unlockAllGroupIndex = 0; unlockAllGroupIndex < TheUnlockRegistry->getGroupCount(); ++unlockAllGroupIndex)
		{
			const UnlockGroup *group = TheUnlockRegistry->getGroupAt(unlockAllGroupIndex);
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

	Bool changed = markRuntimeCheckComplete( checkId, isSpawnedUnitKill ? AsciiString( "spawned-kill" ) : AsciiString( "kill" ) );
	if ( changed )
		DEBUG_LOG( ( "[Archipelago] Check complete: %s (killed %s, spawned=%d)", checkId.str(), victimTemplateName.str(), (Int)isSpawnedUnitKill ) );
	return changed;
}

Bool ArchipelagoState::isCheckComplete( const AsciiString& checkId ) const
{
	return m_completedChecks.find( checkId ) != m_completedChecks.end();
}

Bool ArchipelagoState::markRuntimeCheckComplete( const AsciiString& checkId, const AsciiString& sourceTag )
{
	if ( checkId.isEmpty() )
		return FALSE;

	if ( m_slotDataReferencePresent && !hasVerifiedSlotData() )
	{
		DEBUG_LOG( ( "[Archipelago] Ignoring runtime check %s from %s because slot-data reference is not verified", checkId.str(), sourceTag.str() ) );
		return FALSE;
	}

	if ( hasVerifiedSlotData() && !m_slotData.isSelectedRuntimeKey( checkId ) )
	{
		DEBUG_LOG( ( "[Archipelago] Ignoring unselected runtime check %s from %s", checkId.str(), sourceTag.str() ) );
		return FALSE;
	}

	if ( m_completedChecks.find( checkId ) != m_completedChecks.end() )
		return FALSE;

	m_completedChecks.insert( checkId );
	saveToFile();
	DEBUG_LOG( ( "[Archipelago] Runtime check complete: %s source=%s", checkId.str(), sourceTag.str() ) );
	return TRUE;
}

void ArchipelagoState::processRuntimeSmokeCompletionFile( void )
{
	if ( m_bridgeDirectoryPath.isEmpty() )
		return;

	AsciiString flagPath = m_bridgeDirectoryPath;
	flagPath.concat( "Enable-Runtime-Smoke.flag" );
	std::ifstream flagFile( flagPath.str() );
	if ( !flagFile.is_open() )
		return;
	flagFile.close();

	AsciiString commandPath = m_bridgeDirectoryPath;
	commandPath.concat( "Runtime-Smoke-Complete.json" );
	std::ifstream commandFile( commandPath.str() );
	if ( !commandFile.is_open() )
		return;

	std::string content = readTextFile(commandFile);
	commandFile.close();

	std::set<AsciiString> requestedChecks;
	parseStringArray( content, "\"completedChecks\"", requestedChecks );
	if ( requestedChecks.empty() )
	{
		remove( commandPath.str() );
		DEBUG_LOG( ( "[Archipelago] Runtime smoke completion file had no completedChecks" ) );
		return;
	}

	Int acceptedCount = 0;
	for ( std::set<AsciiString>::const_iterator requestedCheckIt = requestedChecks.begin(); requestedCheckIt != requestedChecks.end(); ++requestedCheckIt )
	{
		if ( markRuntimeCheckComplete( *requestedCheckIt, AsciiString( "runtime-smoke" ) ) )
			++acceptedCount;
	}

	remove( commandPath.str() );
	DEBUG_LOG( ( "[Archipelago] Runtime smoke completion file processed: requested=%d accepted=%d", (Int)requestedChecks.size(), acceptedCount ) );
}

void ArchipelagoState::processRuntimeSmokeDumpFile( void ) const
{
	if ( m_bridgeDirectoryPath.isEmpty() )
		return;

	AsciiString flagPath = m_bridgeDirectoryPath;
	flagPath.concat( "Enable-Runtime-Smoke.flag" );
	std::ifstream flagFile( flagPath.str() );
	if ( !flagFile.is_open() )
		return;
	flagFile.close();

	AsciiString dumpPath = m_bridgeDirectoryPath;
	dumpPath.concat( "Runtime-Smoke-DumpSpawned.flag" );
	std::ifstream dumpFile( dumpPath.str() );
	if ( !dumpFile.is_open() )
		return;
	dumpFile.close();

	if ( TheUnlockableCheckSpawner != NULL )
	{
		TheUnlockableCheckSpawner->dumpDebugState();
		DEBUG_LOG( ( "[Archipelago] Runtime smoke spawned-unit dump requested" ) );
	}
}

void ArchipelagoState::saveToFile( void )
{
	if (m_saveFilePath.isEmpty())
		return;

	std::ofstream file(m_saveFilePath.str());
	if (!file.is_open())
		return;

	file << "{\n";
	file << "  \"version\": 4,\n";
	writeStringArray(file, "unlockedUnits", m_unlockedUnits, TRUE);
	writeStringArray(file, "unlockedBuildings", m_unlockedBuildings, TRUE);
	writeStringArray(file, "unlockedGroupIds", m_unlockedGroupIds, TRUE);
	writeIntArray(file, "unlockedGenerals", m_unlockedGenerals, TRUE);
	writeIntArray(file, "startingGenerals", m_startingGenerals, TRUE);
	writeIntArray(file, "completedLocations", m_completedLocations, TRUE);
	writeStringArray(file, "completedChecks", m_completedChecks, TRUE);
	writeFutureLocationStateArrays(file, m_capturedBuildingStateJson, m_supplyPileStateJson, TRUE);
	file << "  \"sessionOptions\": {\n";
	file << "    \"startingCashBonus\": " << m_startingCashBonus << ",\n";
	file << "    \"productionMultiplier\": " << m_productionMultiplier << ",\n";
	file << "    \"disableZoomLimit\": " << (m_disableZoomLimit ? "true" : "false") << ",\n";
	writeIntArray(file, "starterGenerals", m_sessionOptionStarterGenerals, FALSE);
	file << "  },\n";
	file << "  \"missionStartOptionsApplied\": " << (m_appliedMissionStartOptions ? "true" : "false") << ",\n";
	file << "  \"lastImportedSessionNonce\": \"";
	escapeJsonString(file, m_lastImportedSessionNonce.str());
	file << "\",\n";
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

	std::string content = readTextFile(file);

	m_unlockedUnits.clear();
	m_unlockedBuildings.clear();
	m_unlockedGroupIds.clear();
	m_unlockedGenerals.clear();
	m_startingGenerals.clear();
	m_sessionOptionStarterGenerals.clear();
	m_completedLocations.clear();
	m_completedChecks.clear();
	m_capturedBuildingStateJson = "[]";
	m_supplyPileStateJson = "[]";

	parseStringArray(content, "\"unlockedUnits\"", m_unlockedUnits);
	parseStringArray(content, "\"unlockedBuildings\"", m_unlockedBuildings);
	parseStringArray(content, "\"unlockedGroupIds\"", m_unlockedGroupIds);
	parseIntArray(content, "\"unlockedGenerals\"", m_unlockedGenerals);
	parseIntArray(content, "\"startingGenerals\"", m_startingGenerals);
	parseIntArray(content, "\"completedLocations\"", m_completedLocations);
	parseStringArray(content, "\"completedChecks\"", m_completedChecks);
	m_capturedBuildingStateJson = parseRawArrayField(content, "\"capturedBuildingState\"");
	m_supplyPileStateJson = parseRawArrayField(content, "\"supplyPileState\"");
	m_lastImportedSessionNonce = parseSingleStringField(content, "\"lastImportedSessionNonce\"");
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
	m_missionStartCashTarget = 0u;
	m_missionStartOptionsEarliestFrame = 0;
	m_missionStartOptionsLatestFrame = 0;
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
	writeFutureLocationStateArrays(file, m_capturedBuildingStateJson, m_supplyPileStateJson, TRUE);
	file << "  \"remainingItemPoolGroups\": " << countRemainingItemPoolGroups() << ",\n";
	file << "  \"groups\": [\n";
	if (TheUnlockRegistry != NULL)
	{
		for (Int debugGroupIndex = 0; debugGroupIndex < TheUnlockRegistry->getGroupCount(); ++debugGroupIndex)
		{
			const UnlockGroup *group = TheUnlockRegistry->getGroupAt(debugGroupIndex);
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
			if (debugGroupIndex + 1 < TheUnlockRegistry->getGroupCount())
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

AsciiString ArchipelagoState::getRuntimeSpawnSource( void ) const
{
	if ( m_slotData.isLoaded() )
	{
		AsciiString source( "Seed-Slot-Data.json " );
		source.concat( m_slotData.getSlotDataHash() );
		return source;
	}
	if ( m_slotDataReferencePresent && m_slotDataLoadFailed )
	{
		AsciiString source( "slot-data rejected: " );
		source.concat( m_lastSlotDataError );
		return source;
	}
	return AsciiString( "UnlockableChecksDemo.ini fallback" );
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

AsciiString ArchipelagoState::resolveSlotDataPath( const AsciiString &slotDataPath ) const
{
	if ( slotDataPath.isEmpty() )
		return AsciiString::TheEmptyString;

	std::string raw = slotDataPath.str();
	if ( raw.find( ':' ) != std::string::npos || raw.find( ".." ) != std::string::npos )
		return AsciiString::TheEmptyString;
	if ( raw != "Seed-Slot-Data.json" )
		return AsciiString::TheEmptyString;

	AsciiString resolved = m_bridgeDirectoryPath;
	if ( resolved.isEmpty() )
		return slotDataPath;
	resolved.concat( slotDataPath );
	return resolved;
}

void ArchipelagoState::refreshSlotDataFromInbound(
	const AsciiString &seedId,
	const AsciiString &slotName,
	const AsciiString &sessionNonce,
	Int slotDataVersion,
	const AsciiString &slotDataPath,
	const AsciiString &slotDataHash,
	Bool logChanges )
{
	const Bool hasReference = slotDataPath.isNotEmpty() || slotDataHash.isNotEmpty() || slotDataVersion != 0;
	if ( !hasReference )
	{
		if ( m_slotDataReferencePresent || m_slotData.isLoaded() )
			DEBUG_LOG( ( "[Archipelago] No slot-data reference in inbound; using demo fallback" ) );
		m_slotData.reset();
		m_slotDataReferencePresent = FALSE;
		m_slotDataLoadFailed = FALSE;
		m_lastSlotDataHash.clear();
		m_lastSlotDataSessionNonce.clear();
		m_lastSlotDataError.clear();
		return;
	}

	m_slotDataReferencePresent = TRUE;
	if ( m_slotData.isLoaded()
		&& m_lastSlotDataHash.compare( slotDataHash ) == 0
		&& m_lastSlotDataSessionNonce.compare( sessionNonce ) == 0 )
	{
		return;
	}

	const AsciiString resolvedPath = resolveSlotDataPath( slotDataPath );
	if ( resolvedPath.isEmpty() )
	{
		m_slotData.reset();
		m_slotDataLoadFailed = TRUE;
		m_lastSlotDataError = "invalid slotDataPath";
		DEBUG_LOG( ( "[Archipelago] Slot data rejected: invalid slotDataPath %s", slotDataPath.str() ) );
		return;
	}

	AsciiString error;
	ArchipelagoSlotData loaded;
	if ( !loaded.loadFromFile( resolvedPath, slotDataHash, slotDataVersion, seedId, slotName, sessionNonce, error ) )
	{
		m_slotData.reset();
		m_slotDataLoadFailed = TRUE;
		m_lastSlotDataHash = slotDataHash;
		m_lastSlotDataSessionNonce = sessionNonce;
		m_lastSlotDataError = error;
		DEBUG_LOG( ( "[Archipelago] Slot data rejected: %s", error.str() ) );
		return;
	}

	m_slotData = loaded;
	m_slotDataLoadFailed = FALSE;
	m_lastSlotDataHash = slotDataHash;
	m_lastSlotDataSessionNonce = sessionNonce;
	m_lastSlotDataError.clear();
	if ( logChanges )
	{
		DEBUG_LOG( ( "[Archipelago] Loaded verified slot data: seed=%s slot=%s maps=%d checks=%d hash=%s",
			m_slotData.getSeedId().str(),
			m_slotData.getSlotName().str(),
			m_slotData.getMapCount(),
			m_slotData.getRuntimeCheckCount(),
			m_slotData.getSlotDataHash().str() ) );
	}
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
	Bool disableZoomLimit,
	const AsciiString &sessionNonce )
{
	Bool changed = FALSE;
	Bool sessionNonceChanged = FALSE;

	for (std::set<AsciiString>::const_iterator unlockedUnitIt = unlockedUnits.begin(); unlockedUnitIt != unlockedUnits.end(); ++unlockedUnitIt)
	{
		const AsciiString resolved = resolveLegacyTemplateName(*unlockedUnitIt);
		if (isAlwaysUnlocked(resolved))
			continue;

		size_t before = m_unlockedUnits.size();
		expandUnlockAcrossFactionGenerals(resolved, FALSE, m_unlockedUnits);
		m_unlockedUnits.insert(*unlockedUnitIt);
		m_unlockedUnits.insert(resolved);
		if (m_unlockedUnits.size() != before)
			changed = TRUE;
	}

	for (std::set<AsciiString>::const_iterator unlockedBuildingIt = unlockedBuildings.begin(); unlockedBuildingIt != unlockedBuildings.end(); ++unlockedBuildingIt)
	{
		const AsciiString resolved = resolveLegacyTemplateName(*unlockedBuildingIt);
		if (isAlwaysUnlocked(resolved))
			continue;

		size_t before = m_unlockedBuildings.size();
		expandUnlockAcrossFactionGenerals(resolved, TRUE, m_unlockedBuildings);
		m_unlockedBuildings.insert(*unlockedBuildingIt);
		m_unlockedBuildings.insert(resolved);
		if (m_unlockedBuildings.size() != before)
			changed = TRUE;
	}

	for (std::set<AsciiString>::const_iterator unlockedGroupIdIt = unlockedGroupIds.begin(); unlockedGroupIdIt != unlockedGroupIds.end(); ++unlockedGroupIdIt)
	{
		const UnlockGroup *group = TheUnlockRegistry ? TheUnlockRegistry->findGroupByName(*unlockedGroupIdIt) : NULL;
		if (group == NULL)
			continue;
		size_t beforeGroups = m_unlockedGroupIds.size();
		m_unlockedGroupIds.insert(group->groupName);
		applyGroupMembers(group);
		if (m_unlockedGroupIds.size() != beforeGroups)
			changed = TRUE;
	}

	for (std::set<Int>::const_iterator unlockedGeneralIt = unlockedGenerals.begin(); unlockedGeneralIt != unlockedGenerals.end(); ++unlockedGeneralIt)
	{
		if (m_unlockedGenerals.insert(*unlockedGeneralIt).second)
			changed = TRUE;
	}

	for (std::set<Int>::const_iterator startingGeneralIt = startingGenerals.begin(); startingGeneralIt != startingGenerals.end(); ++startingGeneralIt)
	{
		if (m_startingGenerals.insert(*startingGeneralIt).second)
			changed = TRUE;
		if (m_unlockedGenerals.insert(*startingGeneralIt).second)
			changed = TRUE;
	}

	if (m_sessionOptionStarterGenerals != sessionStarterGenerals)
	{
		m_sessionOptionStarterGenerals = sessionStarterGenerals;
		changed = TRUE;
	}

	for (std::set<Int>::const_iterator starterGeneralIt = m_sessionOptionStarterGenerals.begin(); starterGeneralIt != m_sessionOptionStarterGenerals.end(); ++starterGeneralIt)
	{
		if (m_startingGenerals.insert(*starterGeneralIt).second)
			changed = TRUE;
		if (m_unlockedGenerals.insert(*starterGeneralIt).second)
			changed = TRUE;
	}

	for (std::set<Int>::const_iterator completedLocationIt = completedLocations.begin(); completedLocationIt != completedLocations.end(); ++completedLocationIt)
	{
		if (m_completedLocations.insert(*completedLocationIt).second)
			changed = TRUE;
	}

	for (std::set<AsciiString>::const_iterator completedCheckIt = completedChecks.begin(); completedCheckIt != completedChecks.end(); ++completedCheckIt)
	{
		if (m_completedChecks.insert(*completedCheckIt).second)
			changed = TRUE;
	}

	size_t groupsBeforeSync = m_unlockedGroupIds.size();
	syncUnlockedGroupsFromCurrentState();
	if (m_unlockedGroupIds.size() != groupsBeforeSync)
		changed = TRUE;

	if (sessionNonce.isNotEmpty() && m_lastImportedSessionNonce.compare(sessionNonce) != 0)
	{
		m_lastImportedSessionNonce = sessionNonce;
		sessionNonceChanged = TRUE;
		changed = TRUE;
	}

	Bool shouldRearmMissionStartOptions = FALSE;
	if (m_startingCashBonus != startingCashBonus)
	{
		m_startingCashBonus = startingCashBonus;
		changed = TRUE;
		shouldRearmMissionStartOptions = (startingCashBonus > 0);
	}
	else if (sessionNonceChanged && startingCashBonus > 0)
	{
		shouldRearmMissionStartOptions = TRUE;
	}

	if (shouldRearmMissionStartOptions)
	{
		m_appliedMissionStartOptions = FALSE;
		m_pendingMissionStartOptions = TRUE;
		m_missionStartCashTarget = 0u;
		m_missionStartOptionsEarliestFrame = TheGameLogic != NULL
			? TheGameLogic->getFrame()
			: 0u;
		m_missionStartOptionsLatestFrame = m_missionStartOptionsEarliestFrame + (UnsignedInt)(LOGICFRAMES_PER_SECOND * 90);
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

	std::string content = readTextFile(file);
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
	BridgeSessionMetadata sessionMetadata;
	std::set<Int> completedLocations;
	std::set<AsciiString> completedChecks;
	std::vector<BridgeReceivedItem> receivedItems;

	parseStringArray(content, "\"unlockedUnits\"", unlockedUnits);
	parseStringArray(content, "\"unlockedBuildings\"", unlockedBuildings);
	parseStringArray(content, "\"unlockedGroupIds\"", unlockedGroupIds);
	parseIntArray(content, "\"unlockedGenerals\"", unlockedGenerals);
	parseIntArray(content, "\"startingGenerals\"", startingGenerals);
	parseSessionOptions(content, sessionOptions);
	parseSessionMetadata(content, sessionMetadata);
	parseIntArray(content, "\"completedLocations\"", completedLocations);
	parseStringArray(content, "\"completedChecks\"", completedChecks);
	parseReceivedItems(content, receivedItems);

	refreshSlotDataFromInbound(
		sessionMetadata.seedId,
		sessionMetadata.slotName,
		sessionMetadata.sessionNonce,
		sessionMetadata.slotDataVersion,
		sessionMetadata.slotDataPath,
		sessionMetadata.slotDataHash,
		logChanges );

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
		sessionOptions.disableZoomLimit,
		sessionMetadata.sessionNonce );

	for (std::vector<BridgeReceivedItem>::const_iterator receivedItemIt = receivedItems.begin(); receivedItemIt != receivedItems.end(); ++receivedItemIt)
	{
		if (receivedItemIt->sequence <= m_lastAppliedReceivedItemSequence)
			continue;

		if (receivedItemIt->kind.compareNoCase("unlock_group") == 0)
		{
			UnlockItemOutcome outcome = applyUnlockGroupById(receivedItemIt->groupId, "bridge-received-item", FALSE);
			if (outcome.result == UNLOCK_ITEM_INVALID)
				DEBUG_LOG(("[Archipelago] Ignoring invalid inbound unlock group %s at sequence %d", receivedItemIt->groupId.str(), receivedItemIt->sequence));
		}
		else
		{
			DEBUG_LOG(("[Archipelago] Unsupported inbound received item kind %s at sequence %d", receivedItemIt->kind.str(), receivedItemIt->sequence));
		}

		m_lastAppliedReceivedItemSequence = receivedItemIt->sequence;
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
	file << "  \"stateVersion\": 4,\n";
	file << "  \"syncMode\": \"merge-only\",\n";
	file << "  \"runtimeSpawnSource\": \"";
	escapeJsonString(file, getRuntimeSpawnSource().str());
	file << "\",\n";
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
	writeFutureLocationStateArrays(file, m_capturedBuildingStateJson, m_supplyPileStateJson, TRUE);
	file << "  \"sessionOptions\": {\n";
	file << "    \"startingCashBonus\": " << m_startingCashBonus << ",\n";
	file << "    \"productionMultiplier\": " << m_productionMultiplier << ",\n";
	file << "    \"disableZoomLimit\": " << (m_disableZoomLimit ? "true" : "false") << ",\n";
	writeIntArray(file, "starterGenerals", m_sessionOptionStarterGenerals, FALSE);
	file << "  },\n";
	file << "  \"sessionNonce\": \"";
	escapeJsonString(file, m_lastImportedSessionNonce.str());
	file << "\",\n";
	file << "  \"lastAppliedReceivedItemSequence\": " << m_lastAppliedReceivedItemSequence << "\n";
	file << "}\n";
	file.close();
	DEBUG_LOG(("[Archipelago] Exported bridge state to %s", m_bridgeOutboundFilePath.str()));
}

void ArchipelagoState::ensureDefaultStartingGenerals( void )
{
	if (!m_startingGenerals.empty())
	{
		for (std::set<Int>::const_iterator startingGeneralIt = m_startingGenerals.begin(); startingGeneralIt != m_startingGenerals.end(); ++startingGeneralIt)
			m_unlockedGenerals.insert(*startingGeneralIt);
		return;
	}

	if (!m_sessionOptionStarterGenerals.empty())
	{
		for (std::set<Int>::const_iterator sessionStarterGeneralIt = m_sessionOptionStarterGenerals.begin(); sessionStarterGeneralIt != m_sessionOptionStarterGenerals.end(); ++sessionStarterGeneralIt)
		{
			m_startingGenerals.insert(*sessionStarterGeneralIt);
			m_unlockedGenerals.insert(*sessionStarterGeneralIt);
		}
	}
	else
	{
		m_startingGenerals.insert(GENERAL_USA_SUPERWEAPON);
		m_unlockedGenerals.insert(GENERAL_USA_SUPERWEAPON);
	}

	saveToFile();
}
