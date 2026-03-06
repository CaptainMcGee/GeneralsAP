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

////////////////////////////////////////////////////////////////////////////////
//																																						//
//  (c) 2001-2003 Electronic Arts Inc.																				//
//																																						//
////////////////////////////////////////////////////////////////////////////////

// FILE: InGameChat.cpp ///////////////////////////////////////////////////////////////////////
// Author: Matthew D. Campbell - June 2002
// Desc: GUI callbacks for the in-game chat entry
///////////////////////////////////////////////////////////////////////////////////////////////////

// INCLUDES ///////////////////////////////////////////////////////////////////////////////////////
#include "PreRTS.h"	// This must go first in EVERY cpp file in the GameEngine

#include "Common/Player.h"
#include "Common/PlayerList.h"
#include "Common/ThingFactory.h"
#include "Common/ThingTemplate.h"
#include "GameClient/DisconnectMenu.h"
#include "GameClient/GameWindow.h"
#include "GameClient/Gadget.h"
#include "GameClient/GadgetTextEntry.h"
#include "GameClient/GadgetStaticText.h"
#include "GameClient/GameClient.h"
#include "GameClient/GameText.h"
#include "GameClient/GUICallbacks.h"
#include "GameClient/InGameUI.h"
#include "GameClient/ControlBar.h"
#include "GameClient/LanguageFilter.h"
#include "GameLogic/GameLogic.h"
#include "GameLogic/ArchipelagoState.h"
#include "GameLogic/UnlockRegistry.h"
#include "GameClient/CommandXlat.h"
#include "GameNetwork/GameInfo.h"
#include "GameNetwork/NetworkInterface.h"

static GameWindow *chatWindow = nullptr;
static GameWindow *chatTextEntry = nullptr;
static GameWindow *chatTypeStaticText = nullptr;
static UnicodeString s_savedChat;
static InGameChatType inGameChatType;

// ------------------------------------------------------------------------------------------------
// ------------------------------------------------------------------------------------------------
void ShowInGameChat( Bool immediate )
{
	if (TheGameLogic->isInReplayGame())
		return;

	if (TheInGameUI->isQuitMenuVisible())
		return;

	if (TheDisconnectMenu && TheDisconnectMenu->isScreenVisible())
		return;

	if (chatWindow)
	{
		chatWindow->winHide(FALSE);
		chatWindow->winEnable(TRUE);
		chatTextEntry->winHide(FALSE);
		chatTextEntry->winEnable(TRUE);
		GadgetTextEntrySetText( chatTextEntry, s_savedChat );
		s_savedChat.clear();
	}
	else
	{
		chatWindow = TheWindowManager->winCreateFromScript( "InGameChat.wnd" );

		static NameKeyType textEntryChatID = TheNameKeyGenerator->nameToKey( "InGameChat.wnd:TextEntryChat" );
		chatTextEntry = TheWindowManager->winGetWindowFromId( nullptr, textEntryChatID );
		GadgetTextEntrySetText( chatTextEntry, UnicodeString::TheEmptyString );

		static NameKeyType chatTypeStaticTextID = TheNameKeyGenerator->nameToKey( "InGameChat.wnd:StaticTextChatType" );
		chatTypeStaticText = TheWindowManager->winGetWindowFromId( nullptr, chatTypeStaticTextID );
	}
	TheWindowManager->winSetFocus( chatTextEntry );
	SetInGameChatType( INGAME_CHAT_EVERYONE );
}

// ------------------------------------------------------------------------------------------------
// ------------------------------------------------------------------------------------------------
void ResetInGameChat( void )
{
	if(chatWindow)
		TheWindowManager->winDestroy( chatWindow );
	chatWindow = nullptr;
	chatTextEntry = nullptr;
	chatTypeStaticText = nullptr;
	s_savedChat.clear();
}

// ------------------------------------------------------------------------------------------------
// ------------------------------------------------------------------------------------------------
void HideInGameChat( Bool immediate )
{
	if (chatWindow)
	{
		s_savedChat = GadgetTextEntryGetText( chatTextEntry );
		chatWindow->winHide(TRUE);
		chatWindow->winEnable(FALSE);
		chatTextEntry->winHide(TRUE);
		chatTextEntry->winEnable(FALSE);
		TheWindowManager->winSetFocus( nullptr );
	}
	TheWindowManager->winSetFocus( nullptr );
}

// ------------------------------------------------------------------------------------------------
// ------------------------------------------------------------------------------------------------
void SetInGameChatType( InGameChatType chatType )
{
	inGameChatType = chatType;
	if (chatTypeStaticText)
	{
		switch (inGameChatType)
		{
		case INGAME_CHAT_EVERYONE:
			if (ThePlayerList->getLocalPlayer()->isPlayerActive())
				GadgetStaticTextSetText( chatTypeStaticText, TheGameText->fetch("Chat:Everyone") );
			else
				GadgetStaticTextSetText( chatTypeStaticText, TheGameText->fetch("Chat:Observers") );
			break;
		case INGAME_CHAT_ALLIES:
			GadgetStaticTextSetText( chatTypeStaticText, TheGameText->fetch("Chat:Allies") );
			break;
		case INGAME_CHAT_PLAYERS:
			GadgetStaticTextSetText( chatTypeStaticText, TheGameText->fetch("Chat:Players") );
			break;
		}
	}
}

// ------------------------------------------------------------------------------------------------
// ------------------------------------------------------------------------------------------------
Bool IsInGameChatActive() {
	if (chatWindow != nullptr) {
		if (chatWindow->winIsHidden() == FALSE) {
			return TRUE;
		}
	}
	return FALSE;
}

// Slash commands -------------------------------------------------------------------------
extern "C" {
int getQR2HostingStatus(void);
}
extern int isThreadHosting;

Bool handleInGameSlashCommands(UnicodeString uText)
{
	AsciiString message;
	message.translate(uText);

	if (message.getCharAt(0) != '/')
	{
		return FALSE; // not a slash command
	}

	AsciiString remainder = message.str() + 1;
	AsciiString token;
	remainder.nextToken(&token);
	token.toLower();

	if (token == "host")
	{
		UnicodeString s;
		s.format(L"Hosting qr2:%d thread:%d", getQR2HostingStatus(), isThreadHosting);
		TheInGameUI->message(s);
		return TRUE; // was a slash command
	}

#if defined(RTS_DEBUG)
	if (token == "ap_help" || token == "ap_commands")
	{
		if (TheInGameUI)
		{
			TheInGameUI->messageNoFormat(L"[ARCHIPELAGO] Chat debug commands:");
			TheInGameUI->messageNoFormat(L"/ap_status");
			TheInGameUI->messageNoFormat(L"/ap_unlock_next_general");
			TheInGameUI->messageNoFormat(L"/ap_unlock_next_group");
			TheInGameUI->messageNoFormat(L"/ap_unlock_all");
			TheInGameUI->messageNoFormat(L"/ap_unlock_capture");
			TheInGameUI->messageNoFormat(L"/ap_reset");
			TheInGameUI->messageNoFormat(L"/ap_save_path");
		}
		return TRUE;
	}
	if (token == "ap_unlock_all")
	{
		if (TheArchipelagoState)
			TheArchipelagoState->unlockAll();
		if (TheInGameUI)
			TheInGameUI->messageNoFormat(L"[ARCHIPELAGO] Unlock all");
		if (TheControlBar)
			TheControlBar->markUIDirty();
		return TRUE;
	}
	if (token == "ap_unlock_capture")
	{
		if (TheArchipelagoState)
			TheArchipelagoState->unlockUnit("Upgrade_InfantryCaptureBuilding");
		if (TheInGameUI)
			TheInGameUI->messageNoFormat(L"[ARCHIPELAGO] Capture upgrade unlocked");
		if (TheControlBar)
			TheControlBar->markUIDirty();
		return TRUE;
	}
	if (token == "ap_reset")
	{
		if (TheArchipelagoState)
			TheArchipelagoState->wipeProgress();
		debugResetArchipelagoIndices();
		if (TheInGameUI)
			TheInGameUI->messageNoFormat(L"[ARCHIPELAGO] Reset");
		if (TheControlBar)
			TheControlBar->markUIDirty();
		return TRUE;
	}
	if (token == "ap_unlock_next_general")
	{
		if (TheArchipelagoState && TheInGameUI)
		{
			for (Int i = 0; i < ArchipelagoState::GENERAL_COUNT; ++i)
			{
				if (!TheArchipelagoState->isGeneralUnlocked(i))
				{
					TheArchipelagoState->unlockGeneral(i);
					if (TheControlBar)
						TheControlBar->markUIDirty();
					return TRUE;
				}
			}
			TheInGameUI->messageNoFormat(L"[ARCHIPELAGO] All generals already unlocked");
		}
		return TRUE;
	}
	if (token == "ap_unlock_next_group")
	{
		debugUnlockNextGroup();
		return TRUE;
	}
	if (token == "ap_status")
	{
		if (TheArchipelagoState && TheUnlockRegistry && TheInGameUI)
		{
			Int unlockedGenerals = 0;
			for (Int i = 0; i < ArchipelagoState::GENERAL_COUNT; ++i)
			{
				if (TheArchipelagoState->isGeneralUnlocked(i))
					++unlockedGenerals;
			}

			Int unlockedUnits = 0;
			Int unlockedBuildings = 0;
			Int totalUnits = 0;
			Int totalBuildings = 0;
			std::vector<AsciiString> templates = TheUnlockRegistry->getAllTemplates();
			for (std::vector<AsciiString>::const_iterator it = templates.begin(); it != templates.end(); ++it)
			{
				if (TheUnlockRegistry->isBuildingTemplate(*it))
				{
					++totalBuildings;
					if (TheArchipelagoState->isBuildingUnlocked(*it))
						++unlockedBuildings;
				}
				else
				{
					++totalUnits;
					if (TheArchipelagoState->isUnitUnlocked(*it))
						++unlockedUnits;
				}
			}

			UnicodeString msg;
			msg.format(L"[ARCHIPELAGO] Generals %d/%d, Units %d/%d, Buildings %d/%d",
				unlockedGenerals, (Int)ArchipelagoState::GENERAL_COUNT, unlockedUnits, totalUnits, unlockedBuildings, totalBuildings);
			TheInGameUI->messageNoFormat(msg);
			const Bool usaDozerUnlocked = TheArchipelagoState->isUnitUnlocked("AmericaVehicleDozer") || TheArchipelagoState->isUnitUnlocked("AmericaDozer");
			const Bool chinaDozerUnlocked = TheArchipelagoState->isUnitUnlocked("ChinaVehicleDozer") || TheArchipelagoState->isUnitUnlocked("ChinaDozer");
			const Bool glaWorkerUnlocked = TheArchipelagoState->isUnitUnlocked("GLAInfantryWorker") || TheArchipelagoState->isUnitUnlocked("GLAWorker");
			UnicodeString essentials;
			essentials.format(L"[ARCHIPELAGO] Essentials: USA Dozer=%d, China Dozer=%d, GLA Worker=%d",
				usaDozerUnlocked ? 1 : 0, chinaDozerUnlocked ? 1 : 0, glaWorkerUnlocked ? 1 : 0);
			TheInGameUI->messageNoFormat(essentials);
			if (templates.size() <= 2)
				TheInGameUI->messageNoFormat(L"[ARCHIPELAGO] Warning: unlock registry has very few templates; check Archipelago.ini load path");
		}
		return TRUE;
	}
	if (token == "ap_save_path")
	{
		if (TheArchipelagoState && TheInGameUI)
		{
			UnicodeString msg;
			msg.format(L"[ARCHIPELAGO] Save: %hs", TheArchipelagoState->getSaveFilePath().str());
			TheInGameUI->messageNoFormat(msg);
		}
		return TRUE;
	}
#endif

	return FALSE; // not a slash command
}

// ------------------------------------------------------------------------------------------------
// ------------------------------------------------------------------------------------------------
void ToggleInGameChat( Bool immediate )
{
	static Bool justHid = false;
	if (justHid)
	{
		justHid = false;
		return;
	}

	if (TheGameLogic->isInReplayGame())
		return;

	if (!TheGameInfo->isMultiPlayer() && TheGlobalData->m_netMinPlayers)
	{
		// In this build, allow chat UI even in singleplayer for debugging.
	}

	if (chatWindow)
	{
		Bool show = chatWindow->winIsHidden();
		if (show)
			ShowInGameChat( immediate );
		else
		{
			if (chatTextEntry)
			{
				// Send what is there, clear it out, and hide the window
				UnicodeString msg = GadgetTextEntryGetText( chatTextEntry );
				msg.trim();
				if (!msg.isEmpty() && !handleInGameSlashCommands(msg))
				{
					if (TheNetwork && TheGameLogic->isInMultiplayerGame())
					{
						const Player *localPlayer = ThePlayerList->getLocalPlayer();
						AsciiString playerName;
						Int playerMask = 0;

						for (Int i=0; i<MAX_SLOTS; ++i)
						{
							playerName.format("player%d", i);
							const Player *player = ThePlayerList->findPlayerWithNameKey( TheNameKeyGenerator->nameToKey( playerName ) );
							if (player && localPlayer)
							{
								switch (inGameChatType)
								{
								case INGAME_CHAT_EVERYONE:
									if (!TheGameInfo->getConstSlot(i)->isMuted())
										playerMask |= (1<<i);
									break;
								case INGAME_CHAT_ALLIES:
									if ( (player->getRelationship(localPlayer->getDefaultTeam()) == ALLIES &&
										localPlayer->getRelationship(player->getDefaultTeam()) == ALLIES) || player==localPlayer )
										playerMask |= (1<<i);
									break;
								case INGAME_CHAT_PLAYERS:
									if ( player == localPlayer )
										playerMask |= (1<<i);
									break;
								}
							}
						}
						TheLanguageFilter->filterLine(msg);
						TheNetwork->sendChat(msg, playerMask);
					}
					// In singleplayer debug sessions we still allow chat UI for slash commands,
					// but skip network send entirely.
				}
				GadgetTextEntrySetText( chatTextEntry, UnicodeString::TheEmptyString );
				HideInGameChat( immediate );
				justHid = true;
			}
		}
	}
	else
	{
		ShowInGameChat( immediate );
	}
}


//-------------------------------------------------------------------------------------------------
//-------------------------------------------------------------------------------------------------
WindowMsgHandledType InGameChatInput( GameWindow *window, UnsignedInt msg,
																			WindowMsgData mData1, WindowMsgData mData2 )
{

	switch( msg )
	{

		// --------------------------------------------------------------------------------------------
		case GWM_CHAR:
		{
			UnsignedByte key = mData1;
//			UnsignedByte state = mData2;

			switch( key )
			{

				// ----------------------------------------------------------------------------------------
				case KEY_ESC:
				{
					HideInGameChat();
					return MSG_HANDLED;
					//return MSG_IGNORED;
				}

			}

			return MSG_HANDLED;

		}

	}

	return MSG_IGNORED;

}

//-------------------------------------------------------------------------------------------------
//-------------------------------------------------------------------------------------------------
WindowMsgHandledType InGameChatSystem( GameWindow *window, UnsignedInt msg,
																			 WindowMsgData mData1, WindowMsgData mData2 )
{
	switch( msg )
	{
		//---------------------------------------------------------------------------------------------
		case GGM_FOCUS_CHANGE:
		{
//			Bool focus = (Bool) mData1;
			//if (focus)
				//TheWindowManager->winSetGrabWindow( chatTextEntry );
			break;
		}

		//---------------------------------------------------------------------------------------------
		case GWM_INPUT_FOCUS:
		{
			// if we're givin the opportunity to take the keyboard focus we must say we want it
			if( mData1 == TRUE )
				*(Bool *)mData2 = TRUE;

			return MSG_HANDLED;
		}

		//---------------------------------------------------------------------------------------------
		case GEM_EDIT_DONE:
		{
			ToggleInGameChat();
			//HideInGameChat();

			break;

		}

		//---------------------------------------------------------------------------------------------
		case GBM_SELECTED:
		{
			GameWindow *control = (GameWindow *)mData1;
			static NameKeyType buttonClearID = TheNameKeyGenerator->nameToKey( "InGameChat.wnd:ButtonClear" );
			if (control && control->winGetWindowId() == buttonClearID)
			{
				if (chatTextEntry)
					GadgetTextEntrySetText( chatTextEntry, UnicodeString::TheEmptyString );
				s_savedChat.clear();
			}
			break;

		}

		//---------------------------------------------------------------------------------------------
		default:
			return MSG_IGNORED;

	}

	return MSG_HANDLED;

}

