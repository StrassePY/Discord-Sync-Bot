from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

import discord


@dataclass
class ConfiguredGuildsState:
    guilds: Dict[int, discord.Guild] = field(default_factory=dict)

    def replace(self, entries: Dict[int, discord.Guild]) -> None:
        self.guilds.clear()
        self.guilds.update(entries)

    def update(self, guild_id: int, guild: discord.Guild) -> None:
        self.guilds[guild_id] = guild

    def get(self, guild_id: int) -> Optional[discord.Guild]:
        return self.guilds.get(guild_id)

    def remove(self, guild_id: int) -> None:
        self.guilds.pop(guild_id, None)

    def clear(self) -> None:
        self.guilds.clear()

    def snapshot(self) -> Dict[int, discord.Guild]:
        return dict(self.guilds)
