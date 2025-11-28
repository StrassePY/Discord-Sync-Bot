from __future__ import annotations

from typing import Dict, Optional, TYPE_CHECKING

import discord
from discord.ext import commands

from cogs.guildSync.core.config.lib import loaded_guilds
from interface.logger import Logger

from .modules.collector import ConfiguredGuildsCollector
from .modules.commands import GuildCommandSynchroniser
from .modules.state import ConfiguredGuildsState

if TYPE_CHECKING:
    from cogs.guildSync.core.engine.syncCommands.main import SyncCommandsEngine


class GuildSyncEngine:
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.collector = ConfiguredGuildsCollector(bot)
        self.command_synchroniser = GuildCommandSynchroniser(bot)
        self.state = ConfiguredGuildsState()
        self.synced_guilds = self.state.guilds
        self.commands_engine: Optional["SyncCommandsEngine"] = None

    def attach_commands_engine(self, engine: "SyncCommandsEngine") -> None:
        self.commands_engine = engine

    async def sync_guilds(self) -> Dict[int, discord.Guild]:
        if not loaded_guilds:
            Logger.warning("GuildSyncEngine -", "No guilds configured; nothing to sync.")
            self.state.clear()
            return self.state.snapshot()

        Logger.info("GuildSyncEngine -", "Starting guild synchronization process.")

        result = await self.collector.collect(loaded_guilds)
        self.state.replace(result.resolved)

        self.collector.report_missing(result.missing)
        self.collector.report_unmanaged(loaded_guilds.values())

        return self.state.snapshot()

    async def add_guild(self, guild_id: int) -> bool:
        guild = self.state.get(guild_id)
        if guild is None:
            guild = await self.collector.resolve_single(guild_id)
            if guild is None:
                return False

        self.state.update(guild_id, guild)
        await self._sync_commands_for_guild(guild_id, guild)
        return True

    def get_synced_guilds(self) -> Dict[int, discord.Guild]:
        return self.state.snapshot()

    async def ensure_guilds(self) -> Dict[int, discord.Guild]:
        return self.state.snapshot()

    async def _sync_commands_for_guild(self, guild_id: int, guild: discord.Guild) -> None:
        await self.command_synchroniser.sync_commands(guild_id, guild, self.commands_engine)
    
