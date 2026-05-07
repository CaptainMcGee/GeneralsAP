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

#include "GameLogic/UnlockRegistry.h"
#include "Common/GlobalData.h"
#include "Common/FileSystem.h"
#include "Common/file.h"

#include <algorithm>
#include <ctype.h>
#include <stdlib.h>
#include <string.h>
#include <fstream>
#include <string>

UnlockRegistry *TheUnlockRegistry = NULL;

static std::string trimString(const std::string &in)
{
	size_t start = 0;
	while (start < in.size() && isspace(static_cast<unsigned char>(in[start])))
		++start;
	size_t end = in.size();
	while (end > start && isspace(static_cast<unsigned char>(in[end - 1])))
		--end;
	return in.substr(start, end - start);
}

static std::string stripComment(const std::string &in)
{
	size_t semicolon = in.find(';');
	if (semicolon == std::string::npos)
		return in;
	return in.substr(0, semicolon);
}

static void parseTemplateTokens(const std::string &value, std::vector<AsciiString> &out)
{
	std::string normalized = value;
	for (size_t i = 0; i < normalized.size(); ++i)
	{
		if (normalized[i] == ',')
			normalized[i] = ' ';
	}

	size_t pos = 0;
	while (pos < normalized.size())
	{
		while (pos < normalized.size() && isspace(static_cast<unsigned char>(normalized[pos])))
			++pos;
		size_t begin = pos;
		while (pos < normalized.size() && !isspace(static_cast<unsigned char>(normalized[pos])))
			++pos;
		if (pos > begin)
			out.push_back(AsciiString(normalized.substr(begin, pos - begin).c_str()));
	}
}

static Bool readNextLineFromContent(const std::string &content, size_t &pos, std::string &line)
{
	if (pos >= content.size())
		return FALSE;
	size_t end = content.find('\n', pos);
	if (end == std::string::npos)
	{
		line = content.substr(pos);
		pos = content.size();
	}
	else
	{
		line = content.substr(pos, end - pos);
		pos = end + 1;
	}
	if (!line.empty() && line[line.size() - 1] == '\r')
		line.resize(line.size() - 1);
	return TRUE;
}

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

UnlockRegistry::UnlockRegistry( void ) :
	m_startingGeneralUSA(-1),
	m_startingGeneralChina(-1),
	m_startingGeneralGLA(-1)
{
}

UnlockRegistry::~UnlockRegistry( void )
{
}

UnlockRegistry *UnlockRegistry::getInstance( void )
{
	if (TheUnlockRegistry == NULL)
	{
		TheUnlockRegistry = NEW UnlockRegistry();
	}
	return TheUnlockRegistry;
}

void UnlockRegistry::init( void )
{
	m_unlockGroups.clear();
	m_templateToGroupIndex.clear();
	m_groupNameToIndex.clear();
	m_itemPoolGroupIndices.clear();
	m_buildingTemplates.clear();
	m_unitTemplates.clear();
	m_upgradeTemplates.clear();
	m_commandTemplates.clear();
	m_alwaysUnlockedUnits.clear();
	m_alwaysUnlockedBuildings.clear();
	m_startingGeneralUSA = -1;
	m_startingGeneralChina = -1;
	m_startingGeneralGLA = -1;

	// Prefer TheFileSystem so paths resolve correctly regardless of working directory.
	if (TheFileSystem != NULL)
	{
		File *fp = TheFileSystem->openFile("Data\\INI\\Archipelago.ini", File::READ | File::TEXT);
		if (fp != NULL)
		{
			loadFromFile(fp);
			if (!m_unlockGroups.empty())
				DEBUG_LOG(("UnlockRegistry: loaded %d groups from Data\\INI\\Archipelago.ini (via FileSystem)", (Int)m_unlockGroups.size()));
		}
	}

	if (m_unlockGroups.empty() && TheGlobalData != NULL)
	{
		AsciiString userIni = TheGlobalData->getPath_UserData();
		userIni.concat("INI\\Archipelago.ini");
		loadFromIni(userIni);
		if (!m_unlockGroups.empty())
			DEBUG_LOG(("UnlockRegistry: loaded %d groups from %s", (Int)m_unlockGroups.size(), userIni.str()));
	}

	if (m_unlockGroups.empty())
	{
		static const char *kCandidates[] = {
			"Data/INI/Archipelago.ini",
			".\\Data\\INI\\Archipelago.ini",
			"..\\Data\\INI\\Archipelago.ini",
			"..\\..\\Data\\INI\\Archipelago.ini",
			"..\\..\\..\\Data\\INI\\Archipelago.ini",
			NULL
		};
		for (Int i = 0; kCandidates[i] != NULL && m_unlockGroups.empty(); ++i)
		{
			loadFromIni(kCandidates[i]);
			if (!m_unlockGroups.empty())
				DEBUG_LOG(("UnlockRegistry: loaded %d groups from %s", (Int)m_unlockGroups.size(), kCandidates[i]));
		}
	}

	if (m_unlockGroups.empty())
	{
		DEBUG_LOG(("UnlockRegistry: Archipelago.ini not found/parsed; using fallback defaults"));
	}

	initDefaultsIfEmpty();
	sortGroupsByImportance();
}

const UnlockGroup *UnlockRegistry::findGroupForTemplate( const AsciiString &templateName ) const
{
	std::map<AsciiString, Int>::const_iterator it = m_templateToGroupIndex.find(templateName);
	if (it == m_templateToGroupIndex.end())
		return NULL;
	Int idx = it->second;
	if (idx < 0 || idx >= static_cast<Int>(m_unlockGroups.size()))
		return NULL;
	return &m_unlockGroups[idx];
}

std::vector<AsciiString> UnlockRegistry::getGroupTemplates( const AsciiString &templateName ) const
{
	const UnlockGroup *group = findGroupForTemplate(templateName);
	if (group == NULL)
		return std::vector<AsciiString>();
	return group->templates;
}

AsciiString UnlockRegistry::getFactionForTemplate( const AsciiString &templateName ) const
{
	const UnlockGroup *group = findGroupForTemplate(templateName);
	if (group == NULL)
		return AsciiString::TheEmptyString;
	return group->faction;
}

std::vector<AsciiString> UnlockRegistry::getAllTemplates( void ) const
{
	std::vector<AsciiString> result;
	result.reserve(m_unitTemplates.size() + m_buildingTemplates.size());
	for (std::set<AsciiString>::const_iterator unitTemplateIt = m_unitTemplates.begin(); unitTemplateIt != m_unitTemplates.end(); ++unitTemplateIt)
		result.push_back(*unitTemplateIt);
	for (std::set<AsciiString>::const_iterator buildingTemplateIt = m_buildingTemplates.begin(); buildingTemplateIt != m_buildingTemplates.end(); ++buildingTemplateIt)
		result.push_back(*buildingTemplateIt);
	return result;
}

std::vector<AsciiString> UnlockRegistry::getAllTemplatesInGroupOrder( void ) const
{
	std::vector<AsciiString> result;
	result.reserve(m_unlockGroups.size());
	for (std::vector<UnlockGroup>::const_iterator orderedGroupIt = m_unlockGroups.begin(); orderedGroupIt != m_unlockGroups.end(); ++orderedGroupIt)
	{
		if (!orderedGroupIt->templates.empty())
			result.push_back(orderedGroupIt->templates[0]);
	}
	return result;
}

Int UnlockRegistry::getGroupCount( void ) const
{
	return static_cast<Int>(m_unlockGroups.size());
}

const UnlockGroup *UnlockRegistry::getGroupAt( Int index ) const
{
	if (index < 0 || index >= static_cast<Int>(m_unlockGroups.size()))
		return NULL;
	return &m_unlockGroups[index];
}

const UnlockGroup *UnlockRegistry::findGroupByName( const AsciiString &groupName ) const
{
	std::map<AsciiString, Int>::const_iterator it = m_groupNameToIndex.find(groupName);
	if (it == m_groupNameToIndex.end())
		return NULL;
	return getGroupAt(it->second);
}

Int UnlockRegistry::getItemPoolGroupCount( void ) const
{
	return static_cast<Int>(m_itemPoolGroupIndices.size());
}

const UnlockGroup *UnlockRegistry::getItemPoolGroupAt( Int index ) const
{
	if (index < 0 || index >= static_cast<Int>(m_itemPoolGroupIndices.size()))
		return NULL;
	return getGroupAt(m_itemPoolGroupIndices[index]);
}

Bool UnlockRegistry::isBuildingTemplate( const AsciiString &templateName ) const
{
	return m_buildingTemplates.find(templateName) != m_buildingTemplates.end();
}

Bool UnlockRegistry::isUpgradeTemplate( const AsciiString &templateName ) const
{
	return m_upgradeTemplates.find(templateName) != m_upgradeTemplates.end();
}

Bool UnlockRegistry::isCommandTemplate( const AsciiString &templateName ) const
{
	return m_commandTemplates.find(templateName) != m_commandTemplates.end();
}

Int UnlockRegistry::calculateLocationId( Int enemyGeneralIndex, Int missionNumber ) const
{
	return (enemyGeneralIndex * 10) + missionNumber;
}

static Bool containsMisc(const AsciiString &s)
{
	if (s.isEmpty())
		return FALSE;
	std::string lower = s.str();
	for (size_t i = 0; i < lower.size(); ++i)
		lower[i] = (char)tolower((unsigned char)lower[i]);
	return lower.find("misc") != std::string::npos;
}

static Int defaultImportance(const UnlockGroup &g)
{
	if (containsMisc(g.groupName) || containsMisc(g.displayName))
		return 2;  // misc last
	if (!g.buildingTemplateNames.empty())
		return 0;  // buildings first
	return 1;  // units
}

static Bool compareUnlockGroupImportance(const UnlockGroup &a, const UnlockGroup &b)
{
	return a.importance < b.importance;
}

void UnlockRegistry::addGroup( const UnlockGroup &group )
{
	UnlockGroup g = group;
	if (g.importance < 0)
		g.importance = defaultImportance(g);

	Int idx = static_cast<Int>(m_unlockGroups.size());
	m_unlockGroups.push_back(g);
	m_groupNameToIndex[g.groupName] = idx;

	for (std::vector<AsciiString>::const_iterator templateIt = g.templates.begin(); templateIt != g.templates.end(); ++templateIt)
	{
		m_templateToGroupIndex[*templateIt] = idx;
		Bool isBuilding = !g.buildingTemplateNames.empty()
			? (g.buildingTemplateNames.find(*templateIt) != g.buildingTemplateNames.end())
			: g.isBuildingGroup;
		if (isBuilding)
			m_buildingTemplates.insert(*templateIt);
		else
			m_unitTemplates.insert(*templateIt);
		if (g.upgradeTemplateNames.find(*templateIt) != g.upgradeTemplateNames.end())
			m_upgradeTemplates.insert(*templateIt);
		if (g.commandTemplateNames.find(*templateIt) != g.commandTemplateNames.end())
			m_commandTemplates.insert(*templateIt);
	}
}

void UnlockRegistry::sortGroupsByImportance()
{
	// Set default importance for any unset
	for (std::vector<UnlockGroup>::iterator groupIt = m_unlockGroups.begin(); groupIt != m_unlockGroups.end(); ++groupIt)
	{
		if (groupIt->importance < 0)
			groupIt->importance = defaultImportance(*groupIt);
	}

	// Stable sort: buildings (0) first, units (1), misc (2) last
	std::stable_sort(m_unlockGroups.begin(), m_unlockGroups.end(), compareUnlockGroupImportance);

	// Rebuild indices after reorder
	m_templateToGroupIndex.clear();
	m_groupNameToIndex.clear();
	m_itemPoolGroupIndices.clear();
	m_buildingTemplates.clear();
	m_unitTemplates.clear();
	m_upgradeTemplates.clear();
	m_commandTemplates.clear();
	for (Int idx = 0; idx < static_cast<Int>(m_unlockGroups.size()); ++idx)
	{
		const UnlockGroup &g = m_unlockGroups[idx];
		m_groupNameToIndex[g.groupName] = idx;
		if (g.itemPool)
			m_itemPoolGroupIndices.push_back(idx);
		for (std::vector<AsciiString>::const_iterator sortedTemplateIt = g.templates.begin(); sortedTemplateIt != g.templates.end(); ++sortedTemplateIt)
		{
			m_templateToGroupIndex[*sortedTemplateIt] = idx;
			Bool isBuilding = !g.buildingTemplateNames.empty()
				? (g.buildingTemplateNames.find(*sortedTemplateIt) != g.buildingTemplateNames.end())
				: g.isBuildingGroup;
			if (isBuilding)
				m_buildingTemplates.insert(*sortedTemplateIt);
			else
				m_unitTemplates.insert(*sortedTemplateIt);
			if (g.upgradeTemplateNames.find(*sortedTemplateIt) != g.upgradeTemplateNames.end())
				m_upgradeTemplates.insert(*sortedTemplateIt);
			if (g.commandTemplateNames.find(*sortedTemplateIt) != g.commandTemplateNames.end())
				m_commandTemplates.insert(*sortedTemplateIt);
		}
	}
}

void UnlockRegistry::initDefaultsIfEmpty( void )
{
	if (!m_unlockGroups.empty())
		return;

	// Fallback minimal groups when INI is missing.
	UnlockGroup rebelGroup;
	rebelGroup.groupName = "GLA_Rebel";
	rebelGroup.displayName = "Rebel Infantry";
	rebelGroup.faction = "GLA";
	rebelGroup.isBuildingGroup = FALSE;
	rebelGroup.itemPool = TRUE;
	rebelGroup.expandGenerals = TRUE;
	rebelGroup.importance = 1;
	rebelGroup.templates.push_back("GLARebel");
	rebelGroup.templates.push_back("GLAToxinRebel");
	addGroup(rebelGroup);
}

void UnlockRegistry::loadFromFile( File *fp )
{
	if (fp == NULL)
		return;
	Int fileSize = static_cast<Int>(fp->size());
	if (fileSize <= 0)
		return;
	char *buf = fp->readEntireAndClose();
	if (buf == NULL)
		return;
	std::string content(buf, static_cast<size_t>(fileSize));
	delete[] buf;

	loadFromContent(content);
}

void UnlockRegistry::loadFromIni( const AsciiString &filePath )
{
	std::ifstream file(filePath.str());
	if (!file.is_open())
		return;
	std::string content = readTextFile(file);
	loadFromContent(content);
}

Bool UnlockRegistry::isAlwaysUnlockedTemplate( const AsciiString &templateName ) const
{
	if (m_alwaysUnlockedUnits.find(templateName) != m_alwaysUnlockedUnits.end())
		return TRUE;
	if (m_alwaysUnlockedBuildings.find(templateName) != m_alwaysUnlockedBuildings.end())
		return TRUE;
	return FALSE;
}

static Int parseGeneralSetting(const std::string &value)
{
	std::string v = value;
	for (size_t i = 0; i < v.size(); ++i)
		v[i] = (char)tolower((unsigned char)v[i]);
	if (v == "random" || v.empty())
		return -1;
	Int idx = static_cast<Int>(atoi(value.c_str()));
	if (idx >= 0 && idx <= 8)
		return idx;
	/* Support general names for manual INI editing: USA 0-2, China 3-5, GLA 6-8 */
	if (v == "air force" || v == "airforce") return 0;
	if (v == "laser") return 1;
	if (v == "super weapon" || v == "superweapon") return 2;
	if (v == "infantry") return 3;
	if (v == "tank") return 4;
	if (v == "nuke" || v == "nuclear") return 5;
	if (v == "demo" || v == "demolition") return 6;
	if (v == "stealth") return 7;
	if (v == "toxin" || v == "chemical") return 8;
	return -1;
}

static Bool parseBoolSetting(const std::string &value, Bool defaultValue)
{
	if (value.empty())
		return defaultValue;

	std::string v = value;
	for (size_t i = 0; i < v.size(); ++i)
		v[i] = (char)tolower((unsigned char)v[i]);

	if (v == "yes" || v == "true" || v == "1" || v == "on")
		return TRUE;
	if (v == "no" || v == "false" || v == "0" || v == "off")
		return FALSE;
	return defaultValue;
}

void UnlockRegistry::loadFromContent( const std::string &content )
{
	UnlockGroup current;
	Bool inGroup = FALSE;
	Bool inAlwaysUnlocked = FALSE;
	Bool inArchipelagoSettings = FALSE;

	std::string line;
	size_t linePos = 0;
	while (readNextLineFromContent(content, linePos, line))
	{
		line = stripComment(line);
		line = trimString(line);
		if (line.empty())
			continue;

		if (line == "ArchipelagoSettings")
		{
			inArchipelagoSettings = TRUE;
			inAlwaysUnlocked = FALSE;
			inGroup = FALSE;
			continue;
		}

		if (inArchipelagoSettings)
		{
			if (line == "End" || line == "END" || line == "end")
			{
				inArchipelagoSettings = FALSE;
				continue;
			}
			size_t eq = line.find('=');
			if (eq != std::string::npos)
			{
				std::string key = trimString(line.substr(0, eq));
				std::string value = trimString(line.substr(eq + 1));
				if (key == "StartingGeneralUSA")
					m_startingGeneralUSA = parseGeneralSetting(value);
				else if (key == "StartingGeneralChina")
					m_startingGeneralChina = parseGeneralSetting(value);
				else if (key == "StartingGeneralGLA")
					m_startingGeneralGLA = parseGeneralSetting(value);
			}
			continue;
		}

		if (line == "AlwaysUnlocked")
		{
			inAlwaysUnlocked = TRUE;
			inGroup = FALSE;
			continue;
		}

		if (inAlwaysUnlocked)
		{
			if (line == "End" || line == "END" || line == "end")
			{
				inAlwaysUnlocked = FALSE;
				continue;
			}
			size_t eq = line.find('=');
			if (eq != std::string::npos)
			{
				std::string key = trimString(line.substr(0, eq));
				std::string value = trimString(line.substr(eq + 1));
				std::vector<AsciiString> tokens;
				parseTemplateTokens(value, tokens);
				if (key == "Units")
				{
					for (std::vector<AsciiString>::const_iterator alwaysUnitTokenIt = tokens.begin(); alwaysUnitTokenIt != tokens.end(); ++alwaysUnitTokenIt)
						m_alwaysUnlockedUnits.insert(*alwaysUnitTokenIt);
				}
				else if (key == "Buildings")
				{
					for (std::vector<AsciiString>::const_iterator alwaysBuildingTokenIt = tokens.begin(); alwaysBuildingTokenIt != tokens.end(); ++alwaysBuildingTokenIt)
						m_alwaysUnlockedBuildings.insert(*alwaysBuildingTokenIt);
				}
			}
			continue;
		}

		if (line.compare(0, strlen("UnlockGroup"), "UnlockGroup") == 0)
		{
			current = UnlockGroup();
			current.isBuildingGroup = FALSE;
			current.itemPool = TRUE;
			current.expandGenerals = TRUE;
			current.importance = -1;  // unset, computed in addGroup
			inGroup = TRUE;

			std::string name = trimString(line.substr(strlen("UnlockGroup")));
			current.groupName = AsciiString(name.c_str());
			continue;
		}

		if (!inGroup)
			continue;

		if (line == "End" || line == "END" || line == "end")
		{
			if (!current.groupName.isEmpty() && !current.templates.empty())
				addGroup(current);
			inGroup = FALSE;
			continue;
		}

		size_t eq = line.find('=');
		if (eq == std::string::npos)
			continue;

		std::string key = trimString(line.substr(0, eq));
		std::string value = trimString(line.substr(eq + 1));

		if (key == "Faction")
		{
			current.faction = AsciiString(value.c_str());
		}
		else if (key == "DisplayName")
		{
			if (!value.empty() && value[0] == '\"' && value[value.size() - 1] == '\"')
				value = value.substr(1, value.size() - 2);
			current.displayName = AsciiString(value.c_str());
		}
		else if (key == "Units")
		{
			current.isBuildingGroup = FALSE;
			std::vector<AsciiString> tokens;
			parseTemplateTokens(value, tokens);
			for (std::vector<AsciiString>::const_iterator unitTokenIt = tokens.begin(); unitTokenIt != tokens.end(); ++unitTokenIt)
				current.templates.push_back(*unitTokenIt);
		}
		else if (key == "Upgrades")
		{
			current.isBuildingGroup = FALSE;
			std::vector<AsciiString> tokens;
			parseTemplateTokens(value, tokens);
			for (std::vector<AsciiString>::const_iterator upgradeTokenIt = tokens.begin(); upgradeTokenIt != tokens.end(); ++upgradeTokenIt)
			{
				current.templates.push_back(*upgradeTokenIt);
				current.upgradeTemplateNames.insert(*upgradeTokenIt);
			}
		}
		else if (key == "Commands")
		{
			current.isBuildingGroup = FALSE;
			std::vector<AsciiString> tokens;
			parseTemplateTokens(value, tokens);
			for (std::vector<AsciiString>::const_iterator commandTokenIt = tokens.begin(); commandTokenIt != tokens.end(); ++commandTokenIt)
			{
				current.templates.push_back(*commandTokenIt);
				current.commandTemplateNames.insert(*commandTokenIt);
			}
		}
		else if (key == "Buildings")
		{
			current.isBuildingGroup = TRUE;
			std::vector<AsciiString> tokens;
			parseTemplateTokens(value, tokens);
			for (std::vector<AsciiString>::const_iterator buildingTokenIt = tokens.begin(); buildingTokenIt != tokens.end(); ++buildingTokenIt)
			{
				current.templates.push_back(*buildingTokenIt);
				current.buildingTemplateNames.insert(*buildingTokenIt);
			}
		}
		else if (key == "Importance")
		{
			current.importance = static_cast<Int>(atoi(value.c_str()));
		}
		else if (key == "ItemPool")
		{
			current.itemPool = parseBoolSetting(value, TRUE);
		}
		else if (key == "ExpandGenerals")
		{
			current.expandGenerals = parseBoolSetting(value, TRUE);
		}
	}
}
