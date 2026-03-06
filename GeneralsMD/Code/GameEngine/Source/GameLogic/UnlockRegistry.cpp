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
#include <cctype>
#include <cstring>
#include <fstream>
#include <sstream>
#include <string>

UnlockRegistry *TheUnlockRegistry = NULL;

static std::string trimString(const std::string &in)
{
	size_t start = 0;
	while (start < in.size() && std::isspace(static_cast<unsigned char>(in[start])))
		++start;
	size_t end = in.size();
	while (end > start && std::isspace(static_cast<unsigned char>(in[end - 1])))
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

	std::stringstream ss(normalized);
	std::string token;
	while (ss >> token)
		out.push_back(AsciiString(token.c_str()));
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
	m_buildingTemplates.clear();
	m_unitTemplates.clear();
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
	for (std::set<AsciiString>::const_iterator it = m_unitTemplates.begin(); it != m_unitTemplates.end(); ++it)
		result.push_back(*it);
	for (std::set<AsciiString>::const_iterator it = m_buildingTemplates.begin(); it != m_buildingTemplates.end(); ++it)
		result.push_back(*it);
	return result;
}

std::vector<AsciiString> UnlockRegistry::getAllTemplatesInGroupOrder( void ) const
{
	std::vector<AsciiString> result;
	result.reserve(m_unlockGroups.size());
	for (std::vector<UnlockGroup>::const_iterator it = m_unlockGroups.begin(); it != m_unlockGroups.end(); ++it)
	{
		if (!it->templates.empty())
			result.push_back(it->templates.front());
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

Bool UnlockRegistry::isBuildingTemplate( const AsciiString &templateName ) const
{
	return m_buildingTemplates.find(templateName) != m_buildingTemplates.end();
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
		lower[i] = (char)std::tolower((unsigned char)lower[i]);
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

void UnlockRegistry::addGroup( const UnlockGroup &group )
{
	UnlockGroup g = group;
	if (g.importance < 0)
		g.importance = defaultImportance(g);

	Int idx = static_cast<Int>(m_unlockGroups.size());
	m_unlockGroups.push_back(g);

	for (std::vector<AsciiString>::const_iterator it = g.templates.begin(); it != g.templates.end(); ++it)
	{
		m_templateToGroupIndex[*it] = idx;
		Bool isBuilding = !g.buildingTemplateNames.empty()
			? (g.buildingTemplateNames.find(*it) != g.buildingTemplateNames.end())
			: g.isBuildingGroup;
		if (isBuilding)
			m_buildingTemplates.insert(*it);
		else
			m_unitTemplates.insert(*it);
	}
}

void UnlockRegistry::sortGroupsByImportance()
{
	// Set default importance for any unset
	for (std::vector<UnlockGroup>::iterator it = m_unlockGroups.begin(); it != m_unlockGroups.end(); ++it)
	{
		if (it->importance < 0)
			it->importance = defaultImportance(*it);
	}

	// Stable sort: buildings (0) first, units (1), misc (2) last
	std::stable_sort(m_unlockGroups.begin(), m_unlockGroups.end(),
		[](const UnlockGroup &a, const UnlockGroup &b) { return a.importance < b.importance; });

	// Rebuild indices after reorder
	m_templateToGroupIndex.clear();
	m_buildingTemplates.clear();
	m_unitTemplates.clear();
	for (Int idx = 0; idx < static_cast<Int>(m_unlockGroups.size()); ++idx)
	{
		const UnlockGroup &g = m_unlockGroups[idx];
		for (std::vector<AsciiString>::const_iterator it = g.templates.begin(); it != g.templates.end(); ++it)
		{
			m_templateToGroupIndex[*it] = idx;
			Bool isBuilding = !g.buildingTemplateNames.empty()
				? (g.buildingTemplateNames.find(*it) != g.buildingTemplateNames.end())
				: g.isBuildingGroup;
			if (isBuilding)
				m_buildingTemplates.insert(*it);
			else
				m_unitTemplates.insert(*it);
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

	std::istringstream ss(content);
	loadFromStream(ss);
}

void UnlockRegistry::loadFromIni( const AsciiString &filePath )
{
	std::ifstream file(filePath.str());
	if (!file.is_open())
		return;
	loadFromStream(file);
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
		v[i] = (char)std::tolower((unsigned char)v[i]);
	if (v == "random" || v.empty())
		return -1;
	Int idx = static_cast<Int>(std::atoi(value.c_str()));
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

void UnlockRegistry::loadFromStream( std::istream &in )
{
	UnlockGroup current;
	Bool inGroup = FALSE;
	Bool inAlwaysUnlocked = FALSE;
	Bool inArchipelagoSettings = FALSE;

	std::string line;
	while (std::getline(in, line))
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
					for (std::vector<AsciiString>::const_iterator it = tokens.begin(); it != tokens.end(); ++it)
						m_alwaysUnlockedUnits.insert(*it);
				}
				else if (key == "Buildings")
				{
					for (std::vector<AsciiString>::const_iterator it = tokens.begin(); it != tokens.end(); ++it)
						m_alwaysUnlockedBuildings.insert(*it);
				}
			}
			continue;
		}

		if (line.rfind("UnlockGroup", 0) == 0)
		{
			current = UnlockGroup();
			current.isBuildingGroup = FALSE;
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
			if (!value.empty() && value.front() == '\"' && value.back() == '\"')
				value = value.substr(1, value.size() - 2);
			current.displayName = AsciiString(value.c_str());
		}
		else if (key == "Units")
		{
			current.isBuildingGroup = FALSE;
			std::vector<AsciiString> tokens;
			parseTemplateTokens(value, tokens);
			for (std::vector<AsciiString>::const_iterator it = tokens.begin(); it != tokens.end(); ++it)
				current.templates.push_back(*it);
		}
		else if (key == "Buildings")
		{
			current.isBuildingGroup = TRUE;
			std::vector<AsciiString> tokens;
			parseTemplateTokens(value, tokens);
			for (std::vector<AsciiString>::const_iterator it = tokens.begin(); it != tokens.end(); ++it)
			{
				current.templates.push_back(*it);
				current.buildingTemplateNames.insert(*it);
			}
		}
		else if (key == "Importance")
		{
			current.importance = static_cast<Int>(std::atoi(value.c_str()));
		}
	}
}
