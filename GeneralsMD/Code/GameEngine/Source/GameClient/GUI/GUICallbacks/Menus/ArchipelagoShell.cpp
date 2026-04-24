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

#include "GameClient/WindowLayout.h"
#include "GameClient/Gadget.h"
#include "GameClient/GadgetComboBox.h"
#include "GameClient/GadgetListBox.h"
#include "GameClient/GadgetPushButton.h"
#include "GameClient/GadgetStaticText.h"
#include "GameClient/GadgetTextEntry.h"
#include "GameClient/Display.h"
#include "GameClient/Shell.h"
#include "GameClient/KeyDefs.h"
#include "GameClient/GameWindowManager.h"
#include "GameClient/GameText.h"
#include "GameClient/GameWindowTransitions.h"
#include "GameClient/Image.h"
#include "Common/NameKeyGenerator.h"

#include <cstdio>
#include <cstdlib>
#include <cctype>
#include <fstream>
#include <iterator>
#include <string>
#include <vector>

Image *getMapPreviewImage( AsciiString mapName );

namespace
{
	const char *const AP_FIXTURE_PATH = "Data\\Archipelago\\APShellReviewFixture.json";
	const char *const AP_REVIEW_FLAG_PATH = "UserData\\Archipelago\\APShellReviewOpen.txt";
	const Color AP_LIST_COLOR = GameMakeColor(255, 255, 255, 255);
	const Color AP_CHECKED_COLOR = GameMakeColor(186, 255, 12, 255);
	const Color AP_GREEN_COLOR = GameMakeColor(186, 255, 12, 255);
	const Color AP_YELLOW_COLOR = GameMakeColor(255, 214, 64, 255);
	const Color AP_RED_COLOR = GameMakeColor(255, 96, 96, 255);
	const Color AP_LOCKED_COLOR = GameMakeColor(176, 176, 176, 255);
	const Color AP_INFO_COLOR = GameMakeColor(180, 204, 255, 255);
	const Color AP_MUTED_COLOR = GameMakeColor(214, 214, 214, 255);
	const Int AP_MARKER_COUNT = 8;

	enum APScreenKind
	{
		AP_SCREEN_HUB = 0,
		AP_SCREEN_CONNECT,
		AP_SCREEN_MISSION_INTEL,
		AP_SCREEN_CHECK_TRACKER,
		AP_SCREEN_COUNT
	};

	struct APConnectionFixture
	{
		AsciiString state;
		AsciiString host;
		AsciiString port;
		AsciiString slot;
		AsciiString playerName;
		AsciiString lastError;
	};

	struct APDeckFixture
	{
		AsciiString hint;
		Int completedCheckCount;
		Int pendingCheckCount;
		AsciiString playerSlotLabel;

		APDeckFixture() : completedCheckCount(-1), pendingCheckCount(-1) {}
	};

	struct APMissionSelectorOption
	{
		AsciiString id;
		AsciiString label;
	};

	struct APMissionSelectorFixture
	{
		AsciiString currentId;
		std::vector<APMissionSelectorOption> options;
	};

	struct APClusterFixture
	{
		AsciiString id;
		AsciiString label;
		AsciiString status;
		std::vector<AsciiString> missingTypes;
		Int markerX;
		Int markerY;
		Bool selected;

		APClusterFixture() : markerX(0), markerY(0), selected(FALSE) {}
	};

	struct APMissionFixture
	{
		AsciiString id;
		AsciiString label;
		AsciiString status;
		std::vector<AsciiString> holdMissing;
		std::vector<AsciiString> winMissing;
		AsciiString minimapImage;
		AsciiString emblemImage;
		AsciiString emblemAbbrev;
		Bool selected;
		std::vector<APClusterFixture> clusters;
	};

	struct APCheckFixture
	{
		AsciiString id;
		AsciiString label;
		AsciiString source;
		Bool checked;
	};

	struct APFixtureData
	{
		APDeckFixture deck;
		APConnectionFixture connection;
		APMissionSelectorFixture missionSelector;
		std::vector<APMissionFixture> missions;
		std::vector<APCheckFixture> checks;
		Bool loaded;

		APFixtureData() : loaded(FALSE) {}
	};

	struct APScreenState
	{
		Bool buttonPushed;
		Bool isShuttingDown;
		Bool isPopulating;
		Int selectedMissionIndex;
		Int selectedClusterIndex;

		APScreenState() : buttonPushed(FALSE), isShuttingDown(FALSE), isPopulating(FALSE), selectedMissionIndex(-1), selectedClusterIndex(-1) {}
	};

	static APFixtureData s_fixture;
	static APScreenState s_screenStates[AP_SCREEN_COUNT];
	static Bool s_reviewCaptureDone = FALSE;

	static UnicodeString toUnicode(const AsciiString &value)
	{
		UnicodeString text;
		text.translate(value);
		return text;
	}

	static UnicodeString toUnicode(const std::string &value)
	{
		UnicodeString text;
		text.translate(AsciiString(value.c_str()));
		return text;
	}

	static std::string readTextFile(const char *path)
	{
		std::ifstream input(path, std::ios::binary);
		if (!input)
			return std::string();
		return std::string(std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>());
	}

	static AsciiString readReviewTarget()
	{
		std::string content = readTextFile(AP_REVIEW_FLAG_PATH);
		if (content.empty())
			return AsciiString::TheEmptyString;

		size_t newline = content.find_first_of("\r\n");
		if (newline != std::string::npos)
			content.resize(newline);

		size_t begin = 0;
		while (begin < content.size() && std::isspace(static_cast<unsigned char>(content[begin])))
			++begin;

		size_t end = content.size();
		while (end > begin && std::isspace(static_cast<unsigned char>(content[end - 1])))
			--end;

		if (begin >= end)
			return AsciiString::TheEmptyString;

		return AsciiString(content.substr(begin, end - begin).c_str());
	}

	static size_t skipWhitespace(const std::string &text, size_t pos)
	{
		while (pos < text.size() && std::isspace(static_cast<unsigned char>(text[pos])))
			++pos;
		return pos;
	}

	static size_t findKey(const std::string &text, const char *key, size_t from = 0)
	{
		std::string quoted("\"");
		quoted += key;
		quoted += "\"";
		return text.find(quoted, from);
	}

	static Bool extractDelimited(const std::string &text, size_t openPos, char openChar, char closeChar, std::string &out)
	{
		if (openPos == std::string::npos || openPos >= text.size() || text[openPos] != openChar)
			return FALSE;

		Int depth = 0;
		Bool inString = FALSE;
		Bool escaped = FALSE;
		for (size_t index = openPos; index < text.size(); ++index)
		{
			char current = text[index];
			if (inString)
			{
				if (escaped)
				{
					escaped = FALSE;
				}
				else if (current == '\\')
				{
					escaped = TRUE;
				}
				else if (current == '"')
				{
					inString = FALSE;
				}
				continue;
			}

			if (current == '"')
			{
				inString = TRUE;
				continue;
			}

			if (current == openChar)
				++depth;
			else if (current == closeChar)
			{
				--depth;
				if (depth == 0)
				{
					out = text.substr(openPos, index - openPos + 1);
					return TRUE;
				}
			}
		}

		return FALSE;
	}

	static Bool extractValue(const std::string &text, const char *key, std::string &out)
	{
		size_t keyPos = findKey(text, key);
		if (keyPos == std::string::npos)
			return FALSE;
		size_t colon = text.find(':', keyPos);
		if (colon == std::string::npos)
			return FALSE;
		size_t valuePos = skipWhitespace(text, colon + 1);
		if (valuePos >= text.size())
			return FALSE;
		if (text[valuePos] == '{')
			return extractDelimited(text, valuePos, '{', '}', out);
		if (text[valuePos] == '[')
			return extractDelimited(text, valuePos, '[', ']', out);

		size_t end = valuePos;
		while (end < text.size() && text[end] != ',' && text[end] != '\n' && text[end] != '\r' && text[end] != '}')
			++end;
		out = text.substr(valuePos, end - valuePos);
		return TRUE;
	}

	static std::string parseStringValue(const std::string &value)
	{
		size_t open = value.find('"');
		if (open == std::string::npos)
			return std::string();
		std::string result;
		Bool escaped = FALSE;
		for (size_t index = open + 1; index < value.size(); ++index)
		{
			char current = value[index];
			if (escaped)
			{
				result.push_back(current);
				escaped = FALSE;
			}
			else if (current == '\\')
			{
				escaped = TRUE;
			}
			else if (current == '"')
			{
				break;
			}
			else
			{
				result.push_back(current);
			}
		}
		return result;
	}

	static AsciiString readStringField(const std::string &text, const char *key)
	{
		std::string value;
		if (!extractValue(text, key, value))
			return AsciiString::TheEmptyString;
		return AsciiString(parseStringValue(value).c_str());
	}

	static Bool readBoolField(const std::string &text, const char *key, Bool defaultValue)
	{
		std::string value;
		if (!extractValue(text, key, value))
			return defaultValue;
		value = value.substr(skipWhitespace(value, 0));
		if (value.find("true") == 0)
			return TRUE;
		if (value.find("false") == 0)
			return FALSE;
		return defaultValue;
	}

	static Int readIntField(const std::string &text, const char *key, Int defaultValue)
	{
		std::string value;
		if (!extractValue(text, key, value))
			return defaultValue;

		const char *begin = value.c_str();
		char *end = nullptr;
		long parsed = std::strtol(begin, &end, 10);
		if (begin == end)
			return defaultValue;
		return static_cast<Int>(parsed);
	}

	static std::vector<AsciiString> readStringArrayField(const std::string &text, const char *key)
	{
		std::vector<AsciiString> items;
		std::string arrayText;
		if (!extractValue(text, key, arrayText))
			return items;

		size_t pos = 0;
		while (TRUE)
		{
			size_t open = arrayText.find('"', pos);
			if (open == std::string::npos)
				break;
			size_t close = open + 1;
			Bool escaped = FALSE;
			for (; close < arrayText.size(); ++close)
			{
				char current = arrayText[close];
				if (escaped)
				{
					escaped = FALSE;
				}
				else if (current == '\\')
				{
					escaped = TRUE;
				}
				else if (current == '"')
				{
					break;
				}
			}
			if (close >= arrayText.size())
				break;
			items.push_back(AsciiString(arrayText.substr(open + 1, close - open - 1).c_str()));
			pos = close + 1;
		}

		return items;
	}

	static std::vector<std::string> splitObjectArray(const std::string &arrayText)
	{
		std::vector<std::string> objects;
		size_t pos = 0;
		while (TRUE)
		{
			size_t open = arrayText.find('{', pos);
			if (open == std::string::npos)
				break;
			std::string objectText;
			if (!extractDelimited(arrayText, open, '{', '}', objectText))
				break;
			objects.push_back(objectText);
			pos = open + objectText.size();
		}
		return objects;
	}

	static AsciiString joinValues(const std::vector<AsciiString> &values, const char *emptyText)
	{
		if (values.empty())
			return AsciiString(emptyText);

		AsciiString joined(values.front());
		for (size_t index = 1; index < values.size(); ++index)
		{
			joined.concat(", ");
			joined.concat(values[index]);
		}
		return joined;
	}

	static AsciiString formatCheckSummary(const APFixtureData &fixture)
	{
		Int checked = 0;
		for (size_t index = 0; index < fixture.checks.size(); ++index)
			if (fixture.checks[index].checked)
				++checked;
		AsciiString summary;
		summary.format("Completed %d of %d checks", checked, static_cast<Int>(fixture.checks.size()));
		return summary;
	}

	static Int countCompletedChecks(const APFixtureData &fixture)
	{
		Int checked = 0;
		for (size_t index = 0; index < fixture.checks.size(); ++index)
			if (fixture.checks[index].checked)
				++checked;
		return checked;
	}

	static Int countAvailableMissions(const APFixtureData &fixture)
	{
		Int available = 0;
		for (size_t index = 0; index < fixture.missions.size(); ++index)
		{
			if (fixture.missions[index].status.compareNoCase("locked") != 0)
				++available;
		}
		return available;
	}

	static AsciiString formatMissingValue(const std::vector<AsciiString> &values)
	{
		return joinValues(values, "None");
	}

	static void loadFixtureData()
	{
		if (s_fixture.loaded)
			return;

		s_fixture = APFixtureData();
		s_fixture.deck.hint = "Review shell only. Live sync and launch stay offline.";
		s_fixture.connection.state = "disconnected";
		s_fixture.connection.host = "localhost";
		s_fixture.connection.port = "38281";
		s_fixture.connection.slot = "slot";
		s_fixture.connection.playerName = "Unknown";

		std::string content = readTextFile(AP_FIXTURE_PATH);
		if (content.empty())
		{
			s_fixture.loaded = TRUE;
			return;
		}

		std::string section;
		if (extractValue(content, "deck", section))
		{
			s_fixture.deck.hint = readStringField(section, "hint");
			s_fixture.deck.completedCheckCount = readIntField(section, "completed_check_count", -1);
			s_fixture.deck.pendingCheckCount = readIntField(section, "pending_check_count", -1);
			s_fixture.deck.playerSlotLabel = readStringField(section, "player_slot_label");
		}

		if (extractValue(content, "connection", section))
		{
			s_fixture.connection.state = readStringField(section, "state");
			s_fixture.connection.host = readStringField(section, "host");
			s_fixture.connection.port = readStringField(section, "port");
			s_fixture.connection.slot = readStringField(section, "slot");
			s_fixture.connection.playerName = readStringField(section, "player_name");
			s_fixture.connection.lastError = readStringField(section, "last_error");
		}

		if (extractValue(content, "mission_selector", section))
		{
			s_fixture.missionSelector.currentId = readStringField(section, "current_id");
			std::string optionsSection;
			if (extractValue(section, "options", optionsSection))
			{
				std::vector<std::string> optionObjects = splitObjectArray(optionsSection);
				for (size_t optionIndex = 0; optionIndex < optionObjects.size(); ++optionIndex)
				{
					APMissionSelectorOption option;
					option.id = readStringField(optionObjects[optionIndex], "id");
					option.label = readStringField(optionObjects[optionIndex], "label");
					s_fixture.missionSelector.options.push_back(option);
				}
			}
		}

		if (extractValue(content, "missions", section))
		{
			std::vector<std::string> objects = splitObjectArray(section);
			for (size_t index = 0; index < objects.size(); ++index)
			{
				APMissionFixture mission;
				mission.id = readStringField(objects[index], "id");
				mission.label = readStringField(objects[index], "label");
				mission.status = readStringField(objects[index], "status");
				mission.holdMissing = readStringArrayField(objects[index], "hold_missing");
				mission.winMissing = readStringArrayField(objects[index], "win_missing");
				mission.minimapImage = readStringField(objects[index], "minimap_image");
				mission.emblemImage = readStringField(objects[index], "emblem_image");
				mission.emblemAbbrev = readStringField(objects[index], "emblem_abbrev");
				mission.selected = readBoolField(objects[index], "selected", FALSE);
				std::string clusterSection;
				if (extractValue(objects[index], "clusters", clusterSection))
				{
					std::vector<std::string> clusterObjects = splitObjectArray(clusterSection);
					for (size_t clusterIndex = 0; clusterIndex < clusterObjects.size(); ++clusterIndex)
					{
						APClusterFixture cluster;
						cluster.id = readStringField(clusterObjects[clusterIndex], "id");
						cluster.label = readStringField(clusterObjects[clusterIndex], "label");
						cluster.status = readStringField(clusterObjects[clusterIndex], "state");
						cluster.missingTypes = readStringArrayField(clusterObjects[clusterIndex], "missing_types");
						cluster.markerX = readIntField(clusterObjects[clusterIndex], "marker_x", 0);
						cluster.markerY = readIntField(clusterObjects[clusterIndex], "marker_y", 0);
						cluster.selected = readBoolField(clusterObjects[clusterIndex], "selected", FALSE);
						mission.clusters.push_back(cluster);
					}
				}
				s_fixture.missions.push_back(mission);
			}
		}

		if (extractValue(content, "checks", section))
		{
			std::vector<std::string> objects = splitObjectArray(section);
			for (size_t index = 0; index < objects.size(); ++index)
			{
				APCheckFixture check;
				check.id = readStringField(objects[index], "id");
				check.label = readStringField(objects[index], "label");
				check.source = readStringField(objects[index], "source");
				check.checked = readBoolField(objects[index], "checked", FALSE);
				s_fixture.checks.push_back(check);
			}
		}

		s_fixture.loaded = TRUE;
	}

	static GameWindow *findWindow(const char *name)
	{
		NameKeyType id = TheNameKeyGenerator->nameToKey(name);
		return TheWindowManager->winGetWindowFromId(nullptr, id);
	}

	static void setStaticText(const char *name, const AsciiString &text)
	{
		GameWindow *window = findWindow(name);
		if (window != nullptr)
			GadgetStaticTextSetText(window, toUnicode(text));
	}

	static Int defaultSelectedMissionIndex()
	{
		if (!s_fixture.missionSelector.currentId.isEmpty())
		{
			for (size_t index = 0; index < s_fixture.missions.size(); ++index)
			{
				if (s_fixture.missions[index].id.compareNoCase(s_fixture.missionSelector.currentId) == 0)
					return static_cast<Int>(index);
			}
		}
		for (size_t index = 0; index < s_fixture.missions.size(); ++index)
			if (s_fixture.missions[index].selected)
				return static_cast<Int>(index);
		return s_fixture.missions.empty() ? -1 : 0;
	}

	static Int findMissionIndexById(const AsciiString &missionId)
	{
		if (missionId.isEmpty())
			return -1;
		for (size_t index = 0; index < s_fixture.missions.size(); ++index)
		{
			if (s_fixture.missions[index].id.compareNoCase(missionId) == 0)
				return static_cast<Int>(index);
		}
		return -1;
	}

	static Int defaultSelectedClusterIndex(const APMissionFixture &mission)
	{
		for (size_t index = 0; index < mission.clusters.size(); ++index)
			if (mission.clusters[index].selected)
				return static_cast<Int>(index);
		return mission.clusters.empty() ? -1 : 0;
	}

	static Color missionStatusColor(const AsciiString &status)
	{
		if (status.compareNoCase("completed") == 0 || status.compareNoCase("win") == 0)
			return AP_GREEN_COLOR;
		if (status.compareNoCase("hold") == 0)
			return AP_YELLOW_COLOR;
		return AP_LOCKED_COLOR;
	}

	static Color clusterStatusColor(const AsciiString &status)
	{
		if (status.compareNoCase("green") == 0)
			return AP_GREEN_COLOR;
		if (status.compareNoCase("yellow") == 0)
			return AP_YELLOW_COLOR;
		return AP_RED_COLOR;
	}

	static Color connectionStatusColor()
	{
		if (s_fixture.connection.state.compareNoCase("connected") == 0)
			return AP_GREEN_COLOR;
		if (s_fixture.connection.state.compareNoCase("connecting") == 0)
			return AP_YELLOW_COLOR;
		return AP_RED_COLOR;
	}

	static Color missingValueColor(const std::vector<AsciiString> &values)
	{
		return values.empty() ? AP_GREEN_COLOR : AP_YELLOW_COLOR;
	}

	static AsciiString missionStateValue(const AsciiString &status)
	{
		if (status.compareNoCase("completed") == 0)
			return "COMPLETED";
		if (status.compareNoCase("win") == 0)
			return "WIN READY";
		if (status.compareNoCase("hold") == 0)
			return "HOLD READY";
		return "LOCKED";
	}

	static AsciiString clusterStateValue(const AsciiString &status)
	{
		if (status.compareNoCase("green") == 0)
			return "GREEN";
		if (status.compareNoCase("yellow") == 0)
			return "YELLOW";
		return "RED";
	}

	static AsciiString holdStatusValue(const APMissionFixture &mission)
	{
		return mission.holdMissing.empty() ? AsciiString("READY") : AsciiString("BLOCKED");
	}

	static AsciiString winStatusValue(const APMissionFixture &mission)
	{
		return mission.winMissing.empty() ? AsciiString("READY") : AsciiString("BLOCKED");
	}

	static AsciiString connectionSummary()
	{
		if (s_fixture.connection.state.compareNoCase("connected") == 0)
			return "SESSION ONLINE";
		if (s_fixture.connection.state.compareNoCase("connecting") == 0)
			return "LINKING...";
		if (!s_fixture.connection.lastError.isEmpty())
			return "LINK FAILED";
		return "OFFLINE";
	}

	static void setButtonAltSoundIfPresent(const char *name, const char *soundName)
	{
		GameWindow *window = findWindow(name);
		if (window != nullptr)
			GadgetButtonSetAltSound(window, AsciiString(soundName));
	}

	static void applyHubSounds()
	{
		setButtonAltSoundIfPresent("ArchipelagoHub.wnd:ButtonMissionIntel", "GUIGenShortcutClick");
		setButtonAltSoundIfPresent("ArchipelagoHub.wnd:ButtonCheckTracker", "GUICommandBarClick");
		setButtonAltSoundIfPresent("ArchipelagoHub.wnd:ButtonConnect", "GUICommandBarClick");
		setButtonAltSoundIfPresent("ArchipelagoHub.wnd:ButtonBack", "GUICommandBarClick");
	}

	static void applyConnectSounds()
	{
		setButtonAltSoundIfPresent("APConnect.wnd:ButtonConnect", "GUIGenShortcutClick");
		setButtonAltSoundIfPresent("APConnect.wnd:ButtonDisconnect", "GUICommandBarClick");
		setButtonAltSoundIfPresent("APConnect.wnd:ButtonBack", "GUICommandBarClick");
	}

	static void applyMissionIntelSounds()
	{
		setButtonAltSoundIfPresent("APMissionIntel.wnd:ButtonLaunch", "GUIGenShortcutClick");
		setButtonAltSoundIfPresent("APMissionIntel.wnd:ButtonBack", "GUICommandBarClick");
		char emblemName[64];
		for (Int index = 0; index < 8; ++index)
		{
			std::snprintf(emblemName, sizeof(emblemName), "APMissionIntel.wnd:ButtonEmblem%02d", index + 1);
			setButtonAltSoundIfPresent(emblemName, "GUICommandBarClick");
		}
		char markerName[64];
		for (Int index = 0; index < AP_MARKER_COUNT; ++index)
		{
			std::snprintf(markerName, sizeof(markerName), "APMissionIntel.wnd:ButtonClusterMarker%02d", index + 1);
			setButtonAltSoundIfPresent(markerName, "GUICommandBarClick");
		}
	}

	static void applyCheckTrackerSounds()
	{
		setButtonAltSoundIfPresent("APCheckTracker.wnd:ButtonBack", "GUICommandBarClick");
	}

	static void setTextColors(const char *name, Color color);

	static void populateHubScreen()
	{
		loadFixtureData();
		setStaticText("ArchipelagoHub.wnd:LabelConnectionState", connectionSummary());
		setTextColors("ArchipelagoHub.wnd:LabelConnectionState", connectionStatusColor());
		AsciiString completedText;
		completedText.format("%d", s_fixture.deck.completedCheckCount >= 0 ? s_fixture.deck.completedCheckCount : countCompletedChecks(s_fixture));
		setStaticText("ArchipelagoHub.wnd:LabelCompletedChecksValue", completedText);
		setTextColors("ArchipelagoHub.wnd:LabelCompletedChecksValue", AP_GREEN_COLOR);
		AsciiString pendingText;
		pendingText.format("%d", s_fixture.deck.pendingCheckCount >= 0 ? s_fixture.deck.pendingCheckCount : static_cast<Int>(s_fixture.checks.size()) - countCompletedChecks(s_fixture));
		setStaticText("ArchipelagoHub.wnd:LabelPendingChecksValue", pendingText);
		setTextColors("ArchipelagoHub.wnd:LabelPendingChecksValue", AP_YELLOW_COLOR);
		AsciiString playerText = s_fixture.deck.playerSlotLabel.isEmpty() ? s_fixture.connection.playerName : s_fixture.deck.playerSlotLabel;
		setStaticText("ArchipelagoHub.wnd:LabelPlayerValue", playerText.isEmpty() ? AsciiString("Unknown") : playerText);
		setTextColors("ArchipelagoHub.wnd:LabelPlayerValue", AP_LIST_COLOR);
		setStaticText("ArchipelagoHub.wnd:LabelFooterHint", s_fixture.deck.hint.isEmpty() ? AsciiString("Review shell only.") : s_fixture.deck.hint);
	}

	static void populateConnectScreen()
	{
		loadFixtureData();
		AsciiString hostText("Host: ");
		hostText.concat(s_fixture.connection.host);
		AsciiString portText("Port: ");
		portText.concat(s_fixture.connection.port);
		AsciiString slotText("Slot: ");
		slotText.concat(s_fixture.connection.slot);
		AsciiString passwordText("Password: ");
		passwordText.concat(s_fixture.connection.state.compareNoCase("connected") == 0 ? "Stored" : "--");
		setStaticText("APConnect.wnd:EditHost", hostText);
		setStaticText("APConnect.wnd:EditPort", portText);
		setStaticText("APConnect.wnd:EditSlot", slotText);
		setStaticText("APConnect.wnd:EditPassword", passwordText);
		setStaticText("APConnect.wnd:LabelPlayer", s_fixture.connection.playerName);
		setStaticText("APConnect.wnd:LabelStatus", connectionSummary());
		setTextColors("APConnect.wnd:LabelStatus", connectionStatusColor());

		GameWindow *buttonConnect = findWindow("APConnect.wnd:ButtonConnect");
		GameWindow *buttonDisconnect = findWindow("APConnect.wnd:ButtonDisconnect");
		if (buttonConnect != nullptr)
			buttonConnect->winEnable(FALSE);
		if (buttonDisconnect != nullptr)
			buttonDisconnect->winEnable(FALSE);
	}

	static void setTextColors(const char *name, Color color)
	{
		GameWindow *window = findWindow(name);
		if (window == nullptr)
			return;
		window->winSetEnabledTextColors(color, GameMakeColor(0, 0, 0, 255));
		window->winSetHiliteTextColors(color, GameMakeColor(0, 0, 0, 255));
	}

	static APScreenState &missionIntelState()
	{
		return s_screenStates[AP_SCREEN_MISSION_INTEL];
	}

	static const APMissionFixture *selectedMissionFixture()
	{
		APScreenState &state = missionIntelState();
		if (state.selectedMissionIndex < 0 || state.selectedMissionIndex >= static_cast<Int>(s_fixture.missions.size()))
			return nullptr;
		return &s_fixture.missions[state.selectedMissionIndex];
	}

	static const APClusterFixture *selectedClusterFixture()
	{
		const APMissionFixture *mission = selectedMissionFixture();
		if (mission == nullptr)
			return nullptr;

		APScreenState &state = missionIntelState();
		if (state.selectedClusterIndex < 0 || state.selectedClusterIndex >= static_cast<Int>(mission->clusters.size()))
			return nullptr;
		return &mission->clusters[state.selectedClusterIndex];
	}

	static void ensureMissionIntelSelection()
	{
		APScreenState &state = missionIntelState();
		if (state.selectedMissionIndex < 0 || state.selectedMissionIndex >= static_cast<Int>(s_fixture.missions.size()))
			state.selectedMissionIndex = defaultSelectedMissionIndex();

		const APMissionFixture *mission = selectedMissionFixture();
		if (mission == nullptr)
		{
			state.selectedClusterIndex = -1;
			return;
		}

		if (state.selectedClusterIndex < 0 || state.selectedClusterIndex >= static_cast<Int>(mission->clusters.size()))
			state.selectedClusterIndex = defaultSelectedClusterIndex(*mission);
	}

	static void selectMissionIntelMission(Int index)
	{
		APScreenState &state = missionIntelState();
		if (index < 0 || index >= static_cast<Int>(s_fixture.missions.size()))
			return;
		state.selectedMissionIndex = index;
		s_fixture.missionSelector.currentId = s_fixture.missions[index].id;
		state.selectedClusterIndex = defaultSelectedClusterIndex(s_fixture.missions[index]);
	}

	static void selectMissionIntelMissionById(const AsciiString &missionId)
	{
		Int index = findMissionIndexById(missionId);
		if (index >= 0)
			selectMissionIntelMission(index);
	}

	static void selectMissionIntelCluster(Int index)
	{
		const APMissionFixture *mission = selectedMissionFixture();
		if (mission == nullptr || index < 0 || index >= static_cast<Int>(mission->clusters.size()))
			return;
		missionIntelState().selectedClusterIndex = index;
	}

	static const Image *resolvePreviewImage(const AsciiString &imageName)
	{
		if (!imageName.isEmpty())
		{
			if (Image *preview = getMapPreviewImage(imageName))
				return preview;
			if (const Image *mapped = TheMappedImageCollection->findImageByName(imageName))
				return mapped;
		}
		return TheMappedImageCollection->findImageByName("UnknownMap");
	}

	static const Image *resolveEmblemImage(const AsciiString &imageName)
	{
		if (imageName.isEmpty())
			return nullptr;
		return TheMappedImageCollection->findImageByName(imageName);
	}

	static void populateMissionIntelPreview()
	{
		GameWindow *preview = findWindow("APMissionIntel.wnd:WinMapPreview");
		const APMissionFixture *mission = selectedMissionFixture();
		if (preview == nullptr)
			return;

		const Image *image = resolvePreviewImage(mission != nullptr ? mission->minimapImage : AsciiString::TheEmptyString);
		preview->winSetEnabledImage(0, image);
	}

	static AsciiString markerTooltipText(const APClusterFixture &cluster)
	{
		AsciiString tooltip(cluster.label);
		tooltip.concat(" - ");
		tooltip.concat(clusterStateValue(cluster.status));
		tooltip.concat(" / ");
		tooltip.concat(formatMissingValue(cluster.missingTypes));
		return tooltip;
	}

	static void configureMarkerButton(GameWindow *markerButton, const APClusterFixture &cluster, Bool selected)
	{
		if (markerButton == nullptr)
			return;

		markerButton->winHide(FALSE);
		markerButton->winEnable(TRUE);
		markerButton->winSetPosition(cluster.markerX + 72, cluster.markerY + 148);
		markerButton->winSetHiliteState(selected);
		markerButton->winSetTooltip(toUnicode(markerTooltipText(cluster)));

		const Color fill = clusterStatusColor(cluster.status);
		markerButton->winSetEnabledColor(0, fill);
		markerButton->winSetEnabledBorderColor(0, selected ? GameMakeColor(255, 255, 255, 255) : GameMakeColor(0, 0, 0, 255));
		markerButton->winSetDisabledColor(0, fill);
		markerButton->winSetHiliteColor(0, fill);
		markerButton->winSetHiliteBorderColor(0, GameMakeColor(255, 255, 255, 255));
		markerButton->winSetEnabledTextColors(GameMakeColor(0, 0, 0, 255), GameMakeColor(0, 0, 0, 255));
		markerButton->winSetHiliteTextColors(GameMakeColor(0, 0, 0, 255), GameMakeColor(0, 0, 0, 255));
	}

	static void hideUnusedMarkers()
	{
		char markerName[64];
		for (Int index = 0; index < AP_MARKER_COUNT; ++index)
		{
			std::snprintf(markerName, sizeof(markerName), "APMissionIntel.wnd:ButtonClusterMarker%02d", index + 1);
			GameWindow *markerButton = findWindow(markerName);
			if (markerButton != nullptr)
			{
				markerButton->winHide(TRUE);
				markerButton->winEnable(FALSE);
				markerButton->winSetHiliteState(FALSE);
			}
		}
	}

	static void populateMissionIntelMarkers()
	{
		hideUnusedMarkers();

		const APMissionFixture *mission = selectedMissionFixture();
		if (mission == nullptr)
			return;

		char markerName[64];
		for (Int index = 0; index < static_cast<Int>(mission->clusters.size()) && index < AP_MARKER_COUNT; ++index)
		{
			std::snprintf(markerName, sizeof(markerName), "APMissionIntel.wnd:ButtonClusterMarker%02d", index + 1);
			configureMarkerButton(findWindow(markerName), mission->clusters[index], index == missionIntelState().selectedClusterIndex);
		}
	}

	static void populateMissionIntelSelector()
	{
		GameWindow *combo = findWindow("APMissionIntel.wnd:ComboMissionSelect");
		if (combo == nullptr)
			return;

		GadgetComboBoxReset(combo);
		GadgetComboBoxSetIsEditable(combo, FALSE);

		Int selectedPos = -1;
		if (!s_fixture.missionSelector.options.empty())
		{
			for (size_t index = 0; index < s_fixture.missionSelector.options.size(); ++index)
			{
				const APMissionSelectorOption &option = s_fixture.missionSelector.options[index];
				Int missionIndex = findMissionIndexById(option.id);
				Color color = missionIndex >= 0 ? missionStatusColor(s_fixture.missions[missionIndex].status) : AP_LIST_COLOR;
				GadgetComboBoxAddEntry(combo, toUnicode(option.label), color);
				if (missionIndex == missionIntelState().selectedMissionIndex)
					selectedPos = static_cast<Int>(index);
			}
		}
		else
		{
			for (size_t index = 0; index < s_fixture.missions.size(); ++index)
			{
				GadgetComboBoxAddEntry(combo, toUnicode(s_fixture.missions[index].label), missionStatusColor(s_fixture.missions[index].status));
				if (static_cast<Int>(index) == missionIntelState().selectedMissionIndex)
					selectedPos = static_cast<Int>(index);
			}
		}

		if (selectedPos >= 0)
			GadgetComboBoxSetSelectedPos(combo, selectedPos, TRUE);
	}

	static void populateMissionIntelClusterDetail()
	{
		const APClusterFixture *cluster = selectedClusterFixture();
		if (cluster == nullptr)
		{
			setStaticText("APMissionIntel.wnd:LabelClusterName", "No cluster selected");
			setStaticText("APMissionIntel.wnd:LabelClusterState", "RED");
			setStaticText("APMissionIntel.wnd:LabelMissingTypes", "None");
			setTextColors("APMissionIntel.wnd:LabelClusterState", AP_RED_COLOR);
			setTextColors("APMissionIntel.wnd:LabelMissingTypes", AP_MUTED_COLOR);
			return;
		}

		setStaticText("APMissionIntel.wnd:LabelClusterName", cluster->label);
		setStaticText("APMissionIntel.wnd:LabelClusterState", clusterStateValue(cluster->status));
		setStaticText("APMissionIntel.wnd:LabelMissingTypes", formatMissingValue(cluster->missingTypes));
		setTextColors("APMissionIntel.wnd:LabelClusterState", clusterStatusColor(cluster->status));
		setTextColors("APMissionIntel.wnd:LabelMissingTypes", missingValueColor(cluster->missingTypes));
	}

	static void populateMissionIntelMissionDetail()
	{
		const APMissionFixture *mission = selectedMissionFixture();
		if (mission == nullptr)
		{
			setStaticText("APMissionIntel.wnd:LabelMissionName", "Mission");
			setStaticText("APMissionIntel.wnd:LabelMissionState", "LOCKED");
			setStaticText("APMissionIntel.wnd:LabelHoldState", "BLOCKED");
			setStaticText("APMissionIntel.wnd:LabelHoldMissing", "None");
			setStaticText("APMissionIntel.wnd:LabelWinState", "BLOCKED");
			setStaticText("APMissionIntel.wnd:LabelWinMissing", "None");
			setTextColors("APMissionIntel.wnd:LabelMissionState", AP_LOCKED_COLOR);
			setTextColors("APMissionIntel.wnd:LabelHoldState", AP_LOCKED_COLOR);
			setTextColors("APMissionIntel.wnd:LabelWinState", AP_LOCKED_COLOR);
			setTextColors("APMissionIntel.wnd:LabelHoldMissing", AP_MUTED_COLOR);
			setTextColors("APMissionIntel.wnd:LabelWinMissing", AP_MUTED_COLOR);
			return;
		}

		setStaticText("APMissionIntel.wnd:LabelMissionName", mission->label);
		setStaticText("APMissionIntel.wnd:LabelMissionState", missionStateValue(mission->status));
		setStaticText("APMissionIntel.wnd:LabelHoldState", holdStatusValue(*mission));
		setStaticText("APMissionIntel.wnd:LabelHoldMissing", formatMissingValue(mission->holdMissing));
		setStaticText("APMissionIntel.wnd:LabelWinState", winStatusValue(*mission));
		setStaticText("APMissionIntel.wnd:LabelWinMissing", formatMissingValue(mission->winMissing));
		setTextColors("APMissionIntel.wnd:LabelMissionState", missionStatusColor(mission->status));
		setTextColors("APMissionIntel.wnd:LabelHoldState", mission->holdMissing.empty() ? AP_GREEN_COLOR : AP_RED_COLOR);
		setTextColors("APMissionIntel.wnd:LabelWinState", mission->winMissing.empty() ? AP_GREEN_COLOR : AP_RED_COLOR);
		setTextColors("APMissionIntel.wnd:LabelHoldMissing", missingValueColor(mission->holdMissing));
		setTextColors("APMissionIntel.wnd:LabelWinMissing", missingValueColor(mission->winMissing));
	}

	static void populateMissionIntelEmblems()
	{
		char emblemName[64];
		for (Int index = 0; index < 8; ++index)
		{
			std::snprintf(emblemName, sizeof(emblemName), "APMissionIntel.wnd:ButtonEmblem%02d", index + 1);
			GameWindow *badge = findWindow(emblemName);
			if (badge == nullptr)
				continue;

			if (index >= static_cast<Int>(s_fixture.missions.size()))
			{
				badge->winHide(TRUE);
				badge->winEnable(FALSE);
				continue;
			}

			const APMissionFixture &mission = s_fixture.missions[index];
			const Bool selected = index == missionIntelState().selectedMissionIndex;
			badge->winHide(FALSE);
			badge->winEnable(TRUE);
			badge->winSetHiliteState(selected);
			badge->winSetEnabledBorderColor(0, selected ? GameMakeColor(255, 255, 255, 255) : GameMakeColor(84, 116, 218, 255));
			badge->winSetHiliteBorderColor(0, GameMakeColor(255, 255, 255, 255));
			badge->winSetEnabledColor(0, GameMakeColor(8, 12, 28, 236));
			badge->winSetHiliteColor(0, GameMakeColor(18, 30, 64, 244));
			badge->winSetTooltip(toUnicode(mission.label));
			setStaticText(emblemName, mission.emblemAbbrev.isEmpty() ? mission.label : mission.emblemAbbrev);
			setTextColors(emblemName, selected ? AP_GREEN_COLOR : missionStatusColor(mission.status));
		}
	}

	static void populateMissionIntelScreen()
	{
		APScreenState &state = missionIntelState();
		state.isPopulating = TRUE;

		DEBUG_LOG(("APMissionIntel: loadFixtureData"));
		loadFixtureData();
		DEBUG_LOG(("APMissionIntel: ensureMissionIntelSelection"));
		ensureMissionIntelSelection();
		DEBUG_LOG(("APMissionIntel: populate selector"));
		populateMissionIntelSelector();
		DEBUG_LOG(("APMissionIntel: populate emblems skipped"));
		DEBUG_LOG(("APMissionIntel: populate mission detail"));
		populateMissionIntelMissionDetail();
		DEBUG_LOG(("APMissionIntel: populate preview"));
		populateMissionIntelPreview();
		DEBUG_LOG(("APMissionIntel: populate markers"));
		populateMissionIntelMarkers();
		DEBUG_LOG(("APMissionIntel: populate cluster detail"));
		populateMissionIntelClusterDetail();

		GameWindow *buttonLaunch = findWindow("APMissionIntel.wnd:ButtonLaunch");
		if (buttonLaunch != nullptr)
			buttonLaunch->winEnable(FALSE);

		state.isPopulating = FALSE;
	}

	static void populateCheckTrackerScreen()
	{
		loadFixtureData();
		const Int checked = countCompletedChecks(s_fixture);
		const Int pending = static_cast<Int>(s_fixture.checks.size()) - checked;
		setStaticText("APCheckTracker.wnd:LabelSummary", formatCheckSummary(s_fixture));
		AsciiString completedText;
		completedText.format("%d", checked);
		setStaticText("APCheckTracker.wnd:LabelCompletedValue", completedText);
		AsciiString pendingText;
		pendingText.format("%d", pending);
		setStaticText("APCheckTracker.wnd:LabelPendingValue", pendingText);
		GameWindow *list = findWindow("APCheckTracker.wnd:ListChecks");
		if (list == nullptr)
			return;

		GadgetListBoxReset(list);
		for (size_t index = 0; index < s_fixture.checks.size(); ++index)
		{
			AsciiString label(s_fixture.checks[index].checked ? "[x] " : "[ ] ");
			label.concat(s_fixture.checks[index].label);
			label.concat(" (");
			label.concat(s_fixture.checks[index].source);
			label.concat(")");
			GadgetListBoxAddEntryText(list, toUnicode(label), s_fixture.checks[index].checked ? AP_CHECKED_COLOR : AP_LIST_COLOR, -1, -1);
		}
	}

	static void shutdownComplete(WindowLayout *layout, APScreenState &state)
	{
		state.isShuttingDown = FALSE;
		layout->hide(TRUE);
		TheShell->shutdownComplete(layout);
	}

	static void initScreen(WindowLayout *layout, APScreenState &state, const char *parentName, const char *transitionGroup)
	{
		state.buttonPushed = FALSE;
		state.isShuttingDown = FALSE;
		state.isPopulating = FALSE;
		TheShell->showShellMap(TRUE);
		layout->hide(FALSE);
		GameWindow *parent = findWindow(parentName);
		if (parent != nullptr)
			TheWindowManager->winSetFocus(parent);
		if (transitionGroup != nullptr)
			TheTransitionHandler->setGroup(transitionGroup);
	}

	static void shutdownScreen(WindowLayout *layout, void *userData, APScreenState &state, const char *transitionGroup)
	{
		state.isShuttingDown = TRUE;
		Bool popImmediate = userData != nullptr ? *(Bool *)userData : FALSE;
		if (popImmediate)
		{
			shutdownComplete(layout, state);
			return;
		}

		TheShell->reverseAnimatewindow();
		if (transitionGroup != nullptr)
			TheTransitionHandler->reverse(transitionGroup);
	}

	static void updateScreen(WindowLayout *layout, APScreenState &state)
	{
		if (state.isShuttingDown && TheShell->isAnimFinished() && TheTransitionHandler->isFinished())
			shutdownComplete(layout, state);
	}

	static void maybeCaptureReviewTarget(const char *expectedTarget, APScreenState &state)
	{
		if (s_reviewCaptureDone || state.buttonPushed || state.isShuttingDown)
			return;
		if (!TheShell->isAnimFinished() || !TheTransitionHandler->isFinished())
			return;

		const AsciiString target = readReviewTarget();
		if (target.isEmpty() || target.compareNoCase(expectedTarget) != 0)
			return;

		s_reviewCaptureDone = TRUE;
		TheDisplay->takeScreenShot();
	}

	static WindowMsgHandledType handleEsc(GameWindow *window, UnsignedInt msg, WindowMsgData mData1, WindowMsgData mData2, APScreenState &state, const char *backName)
	{
		if (msg != GWM_CHAR)
			return MSG_IGNORED;

		UnsignedByte key = mData1;
		UnsignedByte stateFlags = mData2;
		if (state.buttonPushed || key != KEY_ESC || !BitIsSet(stateFlags, KEY_STATE_UP))
			return MSG_IGNORED;

		NameKeyType backID = TheNameKeyGenerator->nameToKey(backName);
		GameWindow *button = TheWindowManager->winGetWindowFromId(window, backID);
		TheWindowManager->winSendSystemMsg(window, GBM_SELECTED, (WindowMsgData)button, backID);
		return MSG_HANDLED;
	}

	static WindowMsgHandledType handleCommonSystem(UnsignedInt msg, WindowMsgData mData1, WindowMsgData mData2)
	{
		if (msg == GWM_INPUT_FOCUS)
		{
			if (mData1 == TRUE)
				*(Bool *)mData2 = TRUE;
			return MSG_HANDLED;
		}
		return MSG_IGNORED;
	}

	static void hubPush(const char *wndName, APScreenState &state)
	{
		state.buttonPushed = TRUE;
		TheShell->push(wndName);
	}
}

void ArchipelagoHubInit(WindowLayout *layout, void *userData)
{
	initScreen(layout, s_screenStates[AP_SCREEN_HUB], "ArchipelagoHub.wnd:ArchipelagoHubParent", "ArchipelagoHubFade");
	s_reviewCaptureDone = FALSE;
	applyHubSounds();
	populateHubScreen();
}

void ArchipelagoHubUpdate(WindowLayout *layout, void *userData)
{
	updateScreen(layout, s_screenStates[AP_SCREEN_HUB]);
	maybeCaptureReviewTarget("hub", s_screenStates[AP_SCREEN_HUB]);
}

void ArchipelagoHubShutdown(WindowLayout *layout, void *userData)
{
	shutdownScreen(layout, userData, s_screenStates[AP_SCREEN_HUB], "ArchipelagoHubFade");
}

WindowMsgHandledType ArchipelagoHubInput(GameWindow *window, UnsignedInt msg, WindowMsgData mData1, WindowMsgData mData2)
{
	return handleEsc(window, msg, mData1, mData2, s_screenStates[AP_SCREEN_HUB], "ArchipelagoHub.wnd:ButtonBack");
}

WindowMsgHandledType ArchipelagoHubSystem(GameWindow *window, UnsignedInt msg, WindowMsgData mData1, WindowMsgData mData2)
{
	if (handleCommonSystem(msg, mData1, mData2) == MSG_HANDLED)
		return MSG_HANDLED;

	if (msg != GBM_SELECTED)
		return MSG_IGNORED;

	GameWindow *control = (GameWindow *)mData1;
	if (control == nullptr || s_screenStates[AP_SCREEN_HUB].buttonPushed)
		return MSG_HANDLED;

	Int controlID = control->winGetWindowId();
	if (controlID == TheNameKeyGenerator->nameToKey("ArchipelagoHub.wnd:ButtonConnect"))
		hubPush("Menus/APConnect.wnd", s_screenStates[AP_SCREEN_HUB]);
	else if (controlID == TheNameKeyGenerator->nameToKey("ArchipelagoHub.wnd:ButtonMissionIntel"))
		hubPush("Menus/APMissionIntel.wnd", s_screenStates[AP_SCREEN_HUB]);
	else if (controlID == TheNameKeyGenerator->nameToKey("ArchipelagoHub.wnd:ButtonCheckTracker"))
		hubPush("Menus/APCheckTracker.wnd", s_screenStates[AP_SCREEN_HUB]);
	else if (controlID == TheNameKeyGenerator->nameToKey("ArchipelagoHub.wnd:ButtonBack"))
	{
		s_screenStates[AP_SCREEN_HUB].buttonPushed = TRUE;
		TheShell->pop();
	}

	return MSG_HANDLED;
}

void APConnectInit(WindowLayout *layout, void *userData)
{
	initScreen(layout, s_screenStates[AP_SCREEN_CONNECT], "APConnect.wnd:APConnectParent", "APConnectFade");
	s_reviewCaptureDone = FALSE;
	applyConnectSounds();
	populateConnectScreen();
}

void APConnectUpdate(WindowLayout *layout, void *userData)
{
	updateScreen(layout, s_screenStates[AP_SCREEN_CONNECT]);
	maybeCaptureReviewTarget("connect", s_screenStates[AP_SCREEN_CONNECT]);
}

void APConnectShutdown(WindowLayout *layout, void *userData)
{
	shutdownScreen(layout, userData, s_screenStates[AP_SCREEN_CONNECT], "APConnectFade");
}

WindowMsgHandledType APConnectInput(GameWindow *window, UnsignedInt msg, WindowMsgData mData1, WindowMsgData mData2)
{
	return handleEsc(window, msg, mData1, mData2, s_screenStates[AP_SCREEN_CONNECT], "APConnect.wnd:ButtonBack");
}

WindowMsgHandledType APConnectSystem(GameWindow *window, UnsignedInt msg, WindowMsgData mData1, WindowMsgData mData2)
{
	if (handleCommonSystem(msg, mData1, mData2) == MSG_HANDLED)
		return MSG_HANDLED;

	if (msg != GBM_SELECTED)
		return MSG_IGNORED;

	GameWindow *control = (GameWindow *)mData1;
	if (control == nullptr || s_screenStates[AP_SCREEN_CONNECT].buttonPushed)
		return MSG_HANDLED;

	Int controlID = control->winGetWindowId();
	if (controlID == TheNameKeyGenerator->nameToKey("APConnect.wnd:ButtonBack"))
	{
		s_screenStates[AP_SCREEN_CONNECT].buttonPushed = TRUE;
		TheShell->pop();
	}

	return MSG_HANDLED;
}

void APMissionIntelInit(WindowLayout *layout, void *userData)
{
	initScreen(layout, s_screenStates[AP_SCREEN_MISSION_INTEL], "APMissionIntel.wnd:APMissionIntelParent", "APMissionIntelFade");
	s_reviewCaptureDone = FALSE;
	applyMissionIntelSounds();
	populateMissionIntelScreen();
}

void APMissionIntelUpdate(WindowLayout *layout, void *userData)
{
	updateScreen(layout, s_screenStates[AP_SCREEN_MISSION_INTEL]);
	maybeCaptureReviewTarget("mission-intel", s_screenStates[AP_SCREEN_MISSION_INTEL]);
}

void APMissionIntelShutdown(WindowLayout *layout, void *userData)
{
	shutdownScreen(layout, userData, s_screenStates[AP_SCREEN_MISSION_INTEL], "APMissionIntelFade");
}

WindowMsgHandledType APMissionIntelInput(GameWindow *window, UnsignedInt msg, WindowMsgData mData1, WindowMsgData mData2)
{
	return handleEsc(window, msg, mData1, mData2, s_screenStates[AP_SCREEN_MISSION_INTEL], "APMissionIntel.wnd:ButtonBack");
}

WindowMsgHandledType APMissionIntelSystem(GameWindow *window, UnsignedInt msg, WindowMsgData mData1, WindowMsgData mData2)
{
	if (handleCommonSystem(msg, mData1, mData2) == MSG_HANDLED)
		return MSG_HANDLED;

	if (msg != GBM_SELECTED)
		return MSG_IGNORED;

	GameWindow *control = (GameWindow *)mData1;
	if (control == nullptr || s_screenStates[AP_SCREEN_MISSION_INTEL].buttonPushed)
		return MSG_HANDLED;

	const Int controlID = control->winGetWindowId();
	if (controlID == TheNameKeyGenerator->nameToKey("APMissionIntel.wnd:ButtonBack"))
	{
		s_screenStates[AP_SCREEN_MISSION_INTEL].buttonPushed = TRUE;
		TheShell->pop();
	}

	return MSG_HANDLED;
}

void APCheckTrackerInit(WindowLayout *layout, void *userData)
{
	initScreen(layout, s_screenStates[AP_SCREEN_CHECK_TRACKER], "APCheckTracker.wnd:APCheckTrackerParent", "APCheckTrackerFade");
	s_reviewCaptureDone = FALSE;
	applyCheckTrackerSounds();
	populateCheckTrackerScreen();
}

void APCheckTrackerUpdate(WindowLayout *layout, void *userData)
{
	updateScreen(layout, s_screenStates[AP_SCREEN_CHECK_TRACKER]);
	maybeCaptureReviewTarget("check-tracker", s_screenStates[AP_SCREEN_CHECK_TRACKER]);
}

void APCheckTrackerShutdown(WindowLayout *layout, void *userData)
{
	shutdownScreen(layout, userData, s_screenStates[AP_SCREEN_CHECK_TRACKER], "APCheckTrackerFade");
}

WindowMsgHandledType APCheckTrackerInput(GameWindow *window, UnsignedInt msg, WindowMsgData mData1, WindowMsgData mData2)
{
	return handleEsc(window, msg, mData1, mData2, s_screenStates[AP_SCREEN_CHECK_TRACKER], "APCheckTracker.wnd:ButtonBack");
}

WindowMsgHandledType APCheckTrackerSystem(GameWindow *window, UnsignedInt msg, WindowMsgData mData1, WindowMsgData mData2)
{
	if (handleCommonSystem(msg, mData1, mData2) == MSG_HANDLED)
		return MSG_HANDLED;

	if (msg != GBM_SELECTED)
		return MSG_IGNORED;

	GameWindow *control = (GameWindow *)mData1;
	if (control == nullptr || s_screenStates[AP_SCREEN_CHECK_TRACKER].buttonPushed)
		return MSG_HANDLED;

	if (control->winGetWindowId() == TheNameKeyGenerator->nameToKey("APCheckTracker.wnd:ButtonBack"))
	{
		s_screenStates[AP_SCREEN_CHECK_TRACKER].buttonPushed = TRUE;
		TheShell->pop();
	}
	return MSG_HANDLED;
}
