from __future__ import annotations

from dataclasses import dataclass

from Options import Choice, PerGameCommonOptions


class UnlockPreset(Choice):
    """Grouped alpha item preset."""

    display_name = "Unlock Preset"
    option_default = 0
    option_minimal = 1
    default = option_default


@dataclass
class GeneralsZHOptions(PerGameCommonOptions):
    unlock_preset: UnlockPreset


def unlock_preset_name(option: UnlockPreset) -> str:
    return option.current_key if hasattr(option, "current_key") else "default"
