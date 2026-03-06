find_package(Python3 REQUIRED)

# Archipelago config: preset for unlock groups (default, minimal, chaos, or custom from presets.json)
set(ARCHIPELAGO_PRESET "default" CACHE STRING "Archipelago unlock group preset")
set_property(CACHE ARCHIPELAGO_PRESET PROPERTY STRINGS default minimal chaos)
set(GENERALS_ASSET_ROOT "$ENV{GENERALS_ASSET_ROOT}" CACHE PATH "Path to the local Generals Zero Hour install root or Data directory for retail assets")

if(GENERALS_ASSET_ROOT)
    set(_archipelago_asset_root "${GENERALS_ASSET_ROOT}")
else()
    set(_archipelago_asset_root "${CMAKE_SOURCE_DIR}")
endif()

if(EXISTS "${_archipelago_asset_root}/Data")
    set(ARCHIPELAGO_GAME_DATA_ROOT "${_archipelago_asset_root}/Data")
else()
    set(ARCHIPELAGO_GAME_DATA_ROOT "${_archipelago_asset_root}")
endif()

set(ARCHIPELAGO_CSF_PATH "${ARCHIPELAGO_GAME_DATA_ROOT}/English/generals.csf")
set(ARCHIPELAGO_COMMAND_BUTTON_PATH "${ARCHIPELAGO_GAME_DATA_ROOT}/INI/CommandButton.ini")
set(ARCHIPELAGO_FACTION_UNIT_PATH "${ARCHIPELAGO_GAME_DATA_ROOT}/INI/Object/FactionUnit.ini")
set(ARCHIPELAGO_FACTION_BUILDING_PATH "${ARCHIPELAGO_GAME_DATA_ROOT}/INI/Object/FactionBuilding.ini")

add_executable(z_generals WIN32)

# Use a binary name that doesn't conflict with original game.
if("${CMAKE_SYSTEM}" MATCHES "Windows")
    set_target_properties(z_generals PROPERTIES OUTPUT_NAME generalszh)
else()
    set_target_properties(z_generals PROPERTIES OUTPUT_NAME generalszh)
endif()

target_link_libraries(z_generals PRIVATE
    binkstub
    comctl32
    core_debug
    core_profile
    d3d8
    d3dx8
    dinput8
    dxguid
    imm32
    milesstub
    vfw32
    winmm
    z_gameengine
    z_gameenginedevice
    zi_always
)

# TODO Originally referred to build host and user, replace with git info perhaps?
file(WRITE ${CMAKE_CURRENT_BINARY_DIR}/GeneratedVersion.h
"#pragma once

#define VERSION_LOCALBUILDNUM 0
#define VERSION_BUILDUSER \"\"
#define VERSION_BUILDLOC \"\"
"
)

# Based on original binary values for these variables.
file(WRITE ${CMAKE_CURRENT_BINARY_DIR}/BuildVersion.h
"#pragma once

#define VERSION_MAJOR 1
#define VERSION_MINOR 4
#define VERSION_BUILDNUM 601
"
)

if(MSVC)
    target_link_options(z_generals PRIVATE "/NODEFAULTLIB:libci.lib")
endif()

target_include_directories(z_generals PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_BINARY_DIR}
)

target_sources(z_generals PRIVATE
    WinMain.cpp
    WinMain.h
)

# RC files optional for MinGW builds
# Icon: LoadIcon() handles missing resource gracefully (uses default system icon)
# Manifest: DPI awareness metadata (nice to have but not essential)
if(MSVC)
    # VS2005 and later adds default manifest, we need to turn it off to prevent conflict with custom manifest
    if(NOT IS_VS6_BUILD)
        target_link_options(z_generals PRIVATE
            "/MANIFEST:NO"
        )
    endif()

    target_sources(z_generals PRIVATE
        RTS.RC
    )
endif()

# Strip debug symbols to separate file for MinGW Release builds
# This creates generalszh.exe.debug (similar to MSVC .pdb files)
if(MINGW AND COMMAND add_debug_strip_target)
    add_debug_strip_target(z_generals)
endif()

# Generate localized Archipelago name data and Archipelago.ini from Data/Archipelago config.
set(ARCHIPELAGO_INGAME_NAMES "${CMAKE_SOURCE_DIR}/Data/Archipelago/ingame_names.json")
add_custom_command(OUTPUT "${ARCHIPELAGO_INGAME_NAMES}"
    COMMAND ${CMAKE_COMMAND} -E env "GENERALS_ASSET_ROOT=${GENERALS_ASSET_ROOT}" ${Python3_EXECUTABLE} "${CMAKE_SOURCE_DIR}/scripts/archipelago_build_localized_name_map.py"
        --output "${ARCHIPELAGO_INGAME_NAMES}"
    WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
    DEPENDS
        "${CMAKE_SOURCE_DIR}/scripts/archipelago_build_localized_name_map.py"
        "${CMAKE_SOURCE_DIR}/Data/Archipelago/display_names.json"
        "${ARCHIPELAGO_CSF_PATH}"
    COMMENT "Generating Archipelago in-game name map from generals.csf"
)
add_custom_target(archipelago_ingame_names DEPENDS "${ARCHIPELAGO_INGAME_NAMES}")

set(ARCHIPELAGO_TEMPLATE_NAMES "${CMAKE_SOURCE_DIR}/Data/Archipelago/template_ingame_names.json")
add_custom_command(OUTPUT "${ARCHIPELAGO_TEMPLATE_NAMES}"
    COMMAND ${CMAKE_COMMAND} -E env "GENERALS_ASSET_ROOT=${GENERALS_ASSET_ROOT}" ${Python3_EXECUTABLE} "${CMAKE_SOURCE_DIR}/scripts/archipelago_build_template_name_map.py"
        --output "${ARCHIPELAGO_TEMPLATE_NAMES}"
    WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
    DEPENDS
        "${ARCHIPELAGO_INGAME_NAMES}"
        "${CMAKE_SOURCE_DIR}/scripts/archipelago_build_template_name_map.py"
        "${CMAKE_SOURCE_DIR}/scripts/archipelago_build_localized_name_map.py"
        "${CMAKE_SOURCE_DIR}/scripts/archipelago_data_helpers.py"
        "${CMAKE_SOURCE_DIR}/Data/Archipelago/reference/archipelago_template_display_names.json"
        "${CMAKE_SOURCE_DIR}/Data/Archipelago/name_overrides.json"
        "${CMAKE_SOURCE_DIR}/Data/Archipelago/reference/unresolved_template_name_notes.json"
        "${ARCHIPELAGO_COMMAND_BUTTON_PATH}"
        "${ARCHIPELAGO_FACTION_UNIT_PATH}"
        "${ARCHIPELAGO_FACTION_BUILDING_PATH}"
        "${ARCHIPELAGO_CSF_PATH}"
    COMMENT "Generating Archipelago template name map"
)
add_custom_target(archipelago_template_names DEPENDS "${ARCHIPELAGO_TEMPLATE_NAMES}")

set(ARCHIPELAGO_INI_GENERATED "${CMAKE_BINARY_DIR}/Data/INI/Archipelago.ini")
add_custom_command(OUTPUT "${ARCHIPELAGO_INI_GENERATED}"
    COMMAND ${CMAKE_COMMAND} -E make_directory "${CMAKE_BINARY_DIR}/Data/INI"
    COMMAND ${CMAKE_COMMAND} -E env "GENERALS_ASSET_ROOT=${GENERALS_ASSET_ROOT}" ${Python3_EXECUTABLE} "${CMAKE_SOURCE_DIR}/scripts/archipelago_generate_ini.py"
        --preset ${ARCHIPELAGO_PRESET}
        --output "${ARCHIPELAGO_INI_GENERATED}"
    WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
    DEPENDS
        "${ARCHIPELAGO_INGAME_NAMES}"
        "${ARCHIPELAGO_TEMPLATE_NAMES}"
        "${CMAKE_SOURCE_DIR}/scripts/archipelago_generate_ini.py"
        "${CMAKE_SOURCE_DIR}/scripts/archipelago_data_helpers.py"
        "${CMAKE_SOURCE_DIR}/scripts/archipelago_expand_group_templates.py"
        "${CMAKE_SOURCE_DIR}/Data/Archipelago/groups.json"
        "${CMAKE_SOURCE_DIR}/Data/Archipelago/presets.json"
        "${CMAKE_SOURCE_DIR}/Data/Archipelago/always_unlocked.json"
        "${CMAKE_SOURCE_DIR}/Data/Archipelago/display_names.json"
        "${CMAKE_SOURCE_DIR}/Data/Archipelago/non_spawnable_templates.json"
        "${ARCHIPELAGO_FACTION_BUILDING_PATH}"
    COMMENT "Generating Archipelago.ini from Data/Archipelago config"
)
add_custom_target(archipelago_config ALL DEPENDS "${ARCHIPELAGO_INGAME_NAMES}" "${ARCHIPELAGO_TEMPLATE_NAMES}" "${ARCHIPELAGO_INI_GENERATED}")
add_dependencies(z_generals archipelago_config)

# Copy generated Archipelago.ini and UnlockableChecksDemo.ini to exe directory.
# Runs on every build (no output file) so INI updates are always applied regardless of
# build tool, incremental builds, or whether z_generals was relinked.
set(UNLOCKABLE_CHECKS_INI_SOURCE "${CMAKE_SOURCE_DIR}/Data/INI/UnlockableChecksDemo.ini")
add_custom_target(copy_ini_to_exe ALL
    COMMAND ${CMAKE_COMMAND}
        -DEXE_DIR=$<TARGET_FILE_DIR:z_generals>
        -DARCHIPELAGO_INI=${ARCHIPELAGO_INI_GENERATED}
        -DUNLOCKABLE_CHECKS_INI=${UNLOCKABLE_CHECKS_INI_SOURCE}
        -P ${CMAKE_CURRENT_SOURCE_DIR}/CopyIniToExeDir.cmake
    COMMENT "Copying Archipelago.ini and UnlockableChecksDemo.ini to exe directory"
)
add_dependencies(copy_ini_to_exe archipelago_config)
add_dependencies(z_generals copy_ini_to_exe)

