from __future__ import annotations

from typing import Dict, List, Optional, Set, TYPE_CHECKING

import discord
from discord.ext import commands

from cogs.guildSync.core.config.lib import is_guild_suppressed, loaded_guilds
from interface.logger import Logger

from .modules.collector import ConfiguredGuildsCollector
from .modules.commands import GuildCommandSynchroniser
from .modules.registrar import ConfiguredGuildRegistrar
from .modules.state import ConfiguredGuildsState
from cogs.guildSync.core.ui.inviteView import GuildSyncInviteView

if TYPE_CHECKING:
    from cogs.guildSync.core.engine.syncCommands.main import SyncCommandsEngine


class GuildSyncEngine:
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.collector = ConfiguredGuildsCollector(bot)
        self.command_synchroniser = GuildCommandSynchroniser(bot)
        self.state = ConfiguredGuildsState()
        self.synced_guilds = self.state.guilds
        self.registrar = ConfiguredGuildRegistrar(bot, self.collector)
        self.commands_engine: Optional["SyncCommandsEngine"] = None
        self._active_invites: Set[int] = set()
        self._removed_ids: Set[int] = set()

    def attach_commands_engine(self, engine: "SyncCommandsEngine") -> None:
        self.commands_engine = engine

    async def sync_guilds(self) -> Dict[int, discord.Guild]:
        if not loaded_guilds:
            Logger.warning("GuildSyncEngine -", "No guilds configured; nothing to sync.")
            self.state.clear()
            await self._prompt_unmanaged_guilds(list(self.bot.guilds))
            return self.state.snapshot()

        Logger.info("GuildSyncEngine -", "Starting guild synchronization process.")

        previous_ids = set(self.synced_guilds.keys())
        result = await self.collector.collect(loaded_guilds)
        self.state.replace(result.resolved)
        current_ids = set(result.resolved.keys())
        self._removed_ids = previous_ids - current_ids

        self.collector.report_missing(result.missing)
        unmanaged = self.collector.report_unmanaged(loaded_guilds.values())
        await self._prompt_unmanaged_guilds(unmanaged)

        return self.state.snapshot()

    async def add_guild(
        self,
        guild_id: int,
        *,
        alias: Optional[str] = None,
        persist: bool = True,
        overwrite: bool = False,
    ) -> bool:
        guild = self.state.get(guild_id)

        if persist:
            if guild is None:
                guild = await self.registrar.add_guild_by_id(
                    guild_id,
                    alias=alias,
                    overwrite=overwrite,
                )
                if guild is None:
                    return False
            else:
                if not self.registrar.register_guild(
                    guild,
                    alias=alias,
                    overwrite=overwrite,
                ):
                    return False
        else:
            if guild is None:
                guild = await self.collector.resolve_single(guild_id, alias)
                if guild is None:
                    return False

        self.state.update(guild_id, guild)
        self.mark_invite_complete(guild_id)
        await self._sync_commands_for_guild(guild_id, guild)
        return True

    def get_synced_guilds(self) -> Dict[int, discord.Guild]:
        return self.state.snapshot()

    async def ensure_guilds(self) -> Dict[int, discord.Guild]:
        return self.state.snapshot()

    async def _sync_commands_for_guild(self, guild_id: int, guild: discord.Guild) -> None:
        await self.command_synchroniser.sync_commands(guild_id, guild, self.commands_engine)

    def get_removed_guild_ids(self) -> Set[int]:
        return set(self._removed_ids)

    async def _prompt_unmanaged_guilds(self, unmanaged_guilds: List[discord.Guild]) -> None:
        if not unmanaged_guilds:
            return

        for guild in unmanaged_guilds:
            if guild.id in self.state.guilds:
                continue

            if is_guild_suppressed(guild.id):
                continue

            if guild.id in self._active_invites:
                continue

            channel = self._select_notification_channel(guild)
            if channel is None:
                Logger.warning(
                    "GuildSyncEngine -",
                    f"No suitable channel found to prompt sync in guild {guild.name} ({guild.id}).",
                )
                continue

            view = GuildSyncInviteView(self, guild)
            self._active_invites.add(guild.id)

            try:
                await channel.send(view=view)
                Logger.info(
                    "GuildSyncEngine -",
                    f"Prompted guild {guild.name} ({guild.id}) for sync authorization.",
                )
            except discord.Forbidden:
                Logger.warning(
                    "GuildSyncEngine -",
                    f"Missing permissions to send sync prompt in guild {guild.name} ({guild.id}).",
                )
                self._active_invites.discard(guild.id)
            except discord.HTTPException as exc:
                Logger.error(
                    "GuildSyncEngine -",
                    f"Failed to send sync prompt in guild {guild.name} ({guild.id}): {exc}",
                )
                self._active_invites.discard(guild.id)

    def mark_invite_complete(self, guild_id: int) -> None:
        self._active_invites.discard(guild_id)

    def _select_notification_channel(self, guild: discord.Guild) -> Optional[discord.TextChannel]:
        bot_user = self.bot.user
        if bot_user is None:
            return None

        member = guild.me or guild.get_member(bot_user.id)
        if member is None:
            return None

        system_channel = getattr(guild, "system_channel", None)
        if system_channel and system_channel.permissions_for(member).send_messages:
            return system_channel

        for channel in sorted(guild.text_channels, key=lambda c: c.position):
            perms = channel.permissions_for(member)
            if perms.send_messages and perms.view_channel:
                return channel

        return None
    
