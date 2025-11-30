from __future__ import annotations

from typing import Awaitable, Callable, Dict, List, Optional, Tuple

import inspect

import discord
from discord.ext import commands
from discord.app_commands import AppCommand

from interface.logger import Logger
from interface.commands import ROOT_COMMAND_GROUPS

from .modules.sync import GuildSynchroniser

ProgressCallback = Callable[[int, int, int, float, str], Optional[Awaitable[None]]]

class SyncCommandsEngine:
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.root_groups = ROOT_COMMAND_GROUPS
        self.synchroniser = GuildSynchroniser(bot, self.root_groups)
        self.cloner = self.synchroniser.cloner
        self.state = self.synchroniser.state

    async def desync_commands(self, guilds: List[discord.Guild]) -> None:
        if not guilds:
            return

        await self.synchroniser.remove_global_commands()
        await self.synchroniser.desync_guilds(guilds)

    def list_available_command_keys(self) -> List[Tuple[str, str]]:
        return self.cloner.list_available_keys(include_groups=True)

    def expand_command_key(self, command_key: str) -> List[str]:
        return self.cloner.expand_key(command_key)

    async def sync_selected_guilds(
        self,
        guilds: Dict[int, discord.Guild],
        *,
        clear_global: bool = False,
        reset_snapshots: bool = False,
        include_progress: bool = False,
        progress_callback: ProgressCallback | None = None,
    ) -> Dict[int, List[AppCommand]]:
        if not guilds:
            Logger.warning("SyncCommandsEngine -", "No guilds provided for command sync.")
            return {}

        if clear_global:
            await self.synchroniser.remove_global_commands()

        if reset_snapshots:
            self.state.reset()

        results: Dict[int, List[AppCommand]] = {}
        total = len(guilds)

        progress_enabled = include_progress or progress_callback is not None

        for index, (guild_id, guild) in enumerate(guilds.items(), start=1):
            async def guild_progress(percent: float, message: str, *, idx=index, gid=guild_id) -> None:
                if progress_callback is None:
                    return

                outcome = progress_callback(idx, total, gid, percent, message)
                if inspect.isawaitable(outcome):
                    await outcome

            synced = await self.synchroniser.sync_guild(
                guild_id,
                guild,
                include_progress=progress_enabled,
                progress_notifier=guild_progress if progress_callback is not None else None,
            )
            if synced is not None:
                results[guild_id] = synced
                final_message = f"Completed sync for {guild.name} ({guild_id})."
            else:
                self.state.remove_guild(guild_id)
                final_message = f"Sync failed for {guild.name} ({guild_id})."

            if progress_callback is not None:
                if synced is None or total > 1:
                    await guild_progress(100.0, final_message)

        if not results:
            Logger.warning(
                "SyncCommandsEngine -",
                "No guilds successfully synced for commands.",
            )

        return results

    async def sync_commands(self, guilds: Dict[int, discord.Guild]) -> Dict[int, List[AppCommand]]:
        return await self.sync_selected_guilds(
            guilds,
            clear_global=True,
            reset_snapshots=True,
            include_progress=False,
        )

    def get_guild_commands(self) -> Dict[int, List[str]]:
        return self.state.snapshot()

    def get_disabled_groups(self) -> Dict[int, List[str]]:
        return self.state.disabled_snapshot()
        