from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import Awaitable, Callable, Dict, Iterable, List, Optional

import inspect

import discord
from discord.ext import commands
from discord import AppCommandType, app_commands
from discord.app_commands import AppCommand, Group

from interface.logger import Logger

from .commands import CommandCloner
from .state import SyncState


ProgressNotifier = Callable[[float, str], Optional[Awaitable[None]]]


class GuildSynchroniser:
    def __init__(self, bot: commands.Bot, root_groups: Iterable[Group]) -> None:
        from discord.ext import commands

        self.bot = bot
        self.tree = bot.tree
        self.cloner = CommandCloner(root_groups)
        self.state = SyncState()

    async def remove_global_commands(self) -> None:
        for group in self.cloner.root_groups:
            self.tree.remove_command(group.name, type=AppCommandType.chat_input)
        try:
            await self.tree.sync()
        except discord.DiscordException as exc:
            Logger.warning(
                "SyncCommandsEngine -",
                f"Failed to sync global command removal: {exc}",
            )

    async def desync_guilds(self, guilds: List[discord.Guild]) -> None:
        if not guilds:
            return

        for guild in guilds:
            guild_obj = discord.Object(id=guild.id)
            removed_any = False
            for group in self.cloner.root_groups:
                removed = self.tree.remove_command(
                    group.name,
                    type=AppCommandType.chat_input,
                    guild=guild_obj,
                )
                removed_any = removed_any or removed is not None

            if not removed_any:
                continue

            try:
                await self.tree.sync(guild=guild_obj)
            except discord.DiscordException as exc:
                Logger.warning(
                    "SyncCommandsEngine -",
                    f"Failed to desync commands for {guild.name} ({guild.id}): {exc}",
                )
            else:
                Logger.info(
                    "SyncCommandsEngine -",
                    f"Desynced commands from {guild.name} ({guild.id}).",
                )
                self.state.remove_guild(guild.id)

    async def sync_guild(
        self,
        guild_id: int,
        guild: discord.Guild,
        *,
        include_progress: bool,
        progress_notifier: ProgressNotifier | None = None,
    ) -> Optional[List[AppCommand]]:
        guild_obj = discord.Object(id=guild_id)

        async def notify(percent: float, message: str) -> None:
            if progress_notifier is None:
                return

            outcome = progress_notifier(percent, message)
            if inspect.isawaitable(outcome):
                await outcome

        await notify(0.0, f"Preparing sync for {guild.name} ({guild_id})...")

        enabled_groups: List[str] = []
        disabled_groups: List[str] = []
        tree = self.tree

        total_steps = max(1, len(self.cloner.root_groups)) + 1
        current_step = 0

        for root_group in self.cloner.root_groups:
            tree.remove_command(root_group.name, type=AppCommandType.chat_input, guild=guild_obj)

            clone = self.cloner.clone_group(root_group, guild_id)
            stage_message: str

            if clone is None:
                disabled_groups.append(root_group.name)
                stage_message = (
                    f"Group '{root_group.name}' disabled for {guild.name} ({guild_id})."
                )
            else:
                added_successfully = False
                try:
                    tree.add_command(clone, guild=guild_obj)
                except app_commands.AppCommandAlreadyRegistered:
                    tree.remove_command(root_group.name, type=AppCommandType.chat_input, guild=guild_obj)
                    try:
                        tree.add_command(clone, guild=guild_obj)
                    except discord.DiscordException as exc:
                        Logger.error(
                            "SyncCommandsEngine -",
                            f"Failed to register command group '{root_group.name}' for {guild.name} ({guild_id}): {exc}",
                        )
                        disabled_groups.append(root_group.name)
                        stage_message = (
                            f"Failed to register '{root_group.name}' for {guild.name} ({guild_id})."
                        )
                    else:
                        added_successfully = True
                        stage_message = (
                            f"Registered '{root_group.name}' for {guild.name} ({guild_id})."
                        )
                except discord.DiscordException as exc:
                    Logger.error(
                        "SyncCommandsEngine -",
                        f"Failed to register command group '{root_group.name}' for {guild.name} ({guild_id}): {exc}",
                    )
                    disabled_groups.append(root_group.name)
                    stage_message = (
                        f"Failed to register '{root_group.name}' for {guild.name} ({guild_id})."
                    )
                else:
                    added_successfully = True
                    stage_message = (
                        f"Registered '{root_group.name}' for {guild.name} ({guild_id})."
                    )

                if added_successfully:
                    enabled_groups.append(root_group.name)

            current_step += 1
            percent = (current_step / total_steps) * 100
            await notify(percent, stage_message)

        tree.copy_global_to(guild=guild_obj)

        submission_percent = (current_step / total_steps) * 100
        await notify(min(99.0, submission_percent), f"Submitting sync to Discord for {guild.name} ({guild_id})...")

        countdown_task: Optional[asyncio.Task[None]] = None
        if include_progress:
            pending_clause = "apply commands to" if enabled_groups else "remove commands from"
            complete_clause = "finished applying commands to" if enabled_groups else "finished removing commands from"

            if progress_notifier is None:
                status_callback = None
            else:
                async def status_callback(message: str) -> None:
                    outcome = progress_notifier(min(99.0, submission_percent), message)
                    if inspect.isawaitable(outcome):
                        await outcome

            countdown_task = asyncio.create_task(
                self._wait_with_logs(
                    guild.name,
                    guild_id,
                    pending_clause=pending_clause,
                    complete_clause=complete_clause,
                    status_callback=status_callback if progress_notifier is not None else None,
                )
            )

        try:
            synced_commands = await tree.sync(guild=guild_obj)
        except discord.HTTPException as exc:
            Logger.error(
                "SyncCommandsEngine -",
                f"Failed to sync commands for {guild.name} ({guild_id}): {exc}",
            )
            await notify(submission_percent, f"Failed to sync commands for {guild.name}: {exc}")
            return None
        except discord.DiscordException as exc:
            Logger.error(
                "SyncCommandsEngine -",
                f"Unexpected Discord error while syncing {guild.name} ({guild_id}): {exc}",
            )
            await notify(submission_percent, f"Unexpected Discord error while syncing {guild.name}: {exc}")
            return None
        finally:
            if countdown_task is not None:
                countdown_task.cancel()
                with suppress(asyncio.CancelledError):
                    await countdown_task

        await notify(100.0, f"Discord confirmed sync for {guild.name} ({guild_id}).")

        labels = sorted({self.cloner.format_label(command) for command in synced_commands})
        disabled_unique = sorted(set(disabled_groups))
        self.state.update_guild(guild_id, labels, disabled_unique)

        if enabled_groups:
            joined_groups = ", ".join(sorted(enabled_groups))
            commands_desc = ", ".join(labels) if labels else "(no commands registered)"
            message = (
                f"Synced {len(synced_commands)} commands to {guild.name} ({guild_id})"
                f" | groups: {joined_groups} | commands: {commands_desc}"
            )

            if disabled_unique:
                message += f" | disabled groups: {', '.join(disabled_unique)}"

            Logger.success("SyncCommandsEngine -", message)
        else:
            message = f"No commands configured for {guild.name} ({guild_id}); ensured removal."
            if disabled_unique:
                message += f" Disabled groups: {', '.join(disabled_unique)}."

            Logger.info("SyncCommandsEngine -", message)

        return synced_commands

    async def _wait_with_logs(
        self,
        guild_name: str,
        guild_id: int,
        pending_clause: str,
        complete_clause: str,
        interval: int = 5,
        status_callback: Callable[[str], Awaitable[None] | None] | None = None,
    ) -> None:
        async def emit_status(message: str) -> None:
            if status_callback is None:
                return

            outcome = status_callback(message)
            if inspect.isawaitable(outcome):
                await outcome

        try:
            for remaining in range(interval, 0, -1):
                await emit_status(
                    f"Waiting for Discord to {pending_clause} {guild_name} ({guild_id}) (~{remaining}s)..."
                )
                Logger.info(
                    "SyncCommandsEngine -",
                    f"Waiting for Discord to {pending_clause} {guild_name} ({guild_id}) (~{remaining}s)...",
                )
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            await emit_status(
                f"Discord {complete_clause} {guild_name} ({guild_id})."
            )
            Logger.info(
                "SyncCommandsEngine -",
                f"Discord {complete_clause} {guild_name} ({guild_id}).",
            )
            return

        await emit_status(
            f"Discord is taking longer than expected to {pending_clause} {guild_name} ({guild_id}); continuing to wait..."
        )
        Logger.warning(
            "SyncCommandsEngine -",
            f"Discord is taking longer than expected to {pending_clause} {guild_name} ({guild_id}); continuing to wait...",
        )

        try:
            while True:
                await asyncio.sleep(interval)
                await emit_status(
                    f"Still waiting on Discord to {pending_clause} {guild_name} ({guild_id})..."
                )
                Logger.info(
                    "SyncCommandsEngine -",
                    f"Still waiting on Discord to {pending_clause} {guild_name} ({guild_id})...",
                )
        except asyncio.CancelledError:
            await emit_status(
                f"Discord {complete_clause} {guild_name} ({guild_id})."
            )
            Logger.info(
                "SyncCommandsEngine -",
                f"Discord {complete_clause} {guild_name} ({guild_id}).",
            )
            return
