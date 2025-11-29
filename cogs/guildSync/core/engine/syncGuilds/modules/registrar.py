from __future__ import annotations

from typing import Optional

import discord
from discord.ext import commands

from interface.logger import Logger
from cogs.guildSync.core.config.lib import register_guild

from .collector import ConfiguredGuildsCollector


class ConfiguredGuildRegistrar:
    def __init__(self, bot: commands.Bot, collector: Optional[ConfiguredGuildsCollector] = None) -> None:
        self.bot = bot
        self.collector = collector or ConfiguredGuildsCollector(bot)

    async def add_guild_by_id(
        self,
        guild_id: int,
        *,
        alias: Optional[str] = None,
        overwrite: bool = False,
    ) -> Optional[discord.Guild]:
        guild = await self.collector.resolve_single(guild_id, alias)
        if guild is None:
            return None

        if not self.register_guild(guild, alias=alias, overwrite=overwrite):
            return None

        return guild

    def register_guild(
        self,
        guild: discord.Guild,
        *,
        alias: Optional[str] = None,
        overwrite: bool = False,
    ) -> bool:
        preferred_name = (alias or guild.name).strip()
        if not preferred_name:
            Logger.error(
                "GuildSyncEngine -",
                f"Cannot register guild {guild.id} without a name.",
            )
            return False

        try:
            changed = register_guild(preferred_name, guild.id, overwrite=overwrite)
        except ValueError as exc:
            Logger.error(
                "GuildSyncEngine -",
                f"Failed to register guild {preferred_name} ({guild.id}): {exc}",
            )
            return False

        if changed:
            Logger.success(
                "GuildSyncEngine -",
                f"Registered guild {preferred_name} ({guild.id}) in configuration.",
            )
        else:
            Logger.info(
                "GuildSyncEngine -",
                f"Guild {preferred_name} ({guild.id}) already present in configuration.",
            )

        return True
