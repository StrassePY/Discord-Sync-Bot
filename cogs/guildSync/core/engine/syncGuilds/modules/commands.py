from __future__ import annotations

from typing import Optional, TYPE_CHECKING

import discord
from discord.ext import commands

from interface.logger import Logger

if TYPE_CHECKING:
    from cogs.guildSync.core.engine.syncCommands.main import SyncCommandsEngine


class GuildCommandSynchroniser:
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def sync_commands(
        self,
        guild_id: int,
        guild: discord.Guild,
        engine: Optional["SyncCommandsEngine"],
    ) -> None:
        if engine is not None:
            try:
                await engine.sync_selected_guilds(
                    {guild_id: guild},
                    clear_global=False,
                    reset_snapshots=False,
                    include_progress=False,
                )
            except Exception as exc:  # noqa: BLE001
                Logger.error(
                    "GuildSyncEngine -",
                    f"Failed to sync commands for guild {guild.name} ({guild_id}): {exc}",
                )
            return

        await self._fallback_sync(guild_id, guild)

    async def _fallback_sync(self, guild_id: int, guild: discord.Guild) -> None:
        guild_obj = discord.Object(id=guild_id)
        tree = self.bot.tree
        tree.copy_global_to(guild=guild_obj)
        try:
            await tree.sync(guild=guild_obj)
        except discord.DiscordException as exc:
            Logger.error(
                "GuildSyncEngine -",
                f"Failed to sync commands for guild {guild.name} ({guild_id}) via fallback: {exc}",
            )
