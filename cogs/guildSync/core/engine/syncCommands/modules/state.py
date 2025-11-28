from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class GuildSyncState:
    command_labels: List[str] = field(default_factory=list)
    disabled_groups: List[str] = field(default_factory=list)


@dataclass
class SyncState:
    guilds: Dict[int, GuildSyncState] = field(default_factory=dict)

    def update_guild(self, guild_id: int, labels: List[str], disabled: List[str]) -> None:
        self.guilds[guild_id] = GuildSyncState(labels, disabled)

    def remove_guild(self, guild_id: int) -> None:
        self.guilds.pop(guild_id, None)

    def reset(self) -> None:
        self.guilds.clear()

    def snapshot(self) -> Dict[int, List[str]]:
        return {gid: list(state.command_labels) for gid, state in self.guilds.items()}

    def disabled_snapshot(self) -> Dict[int, List[str]]:
        return {gid: list(state.disabled_groups) for gid, state in self.guilds.items()}
