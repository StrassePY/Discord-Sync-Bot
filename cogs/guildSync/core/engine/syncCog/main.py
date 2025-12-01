from __future__ import annotations

from typing import List, Optional, Tuple, TYPE_CHECKING

from discord.ext import commands

from interface.logger import Logger

if TYPE_CHECKING:
    from cogs.guildSync.core.engine.syncCommands.main import SyncCommandsEngine
    from cogs.guildSync.core.engine.syncGuilds.main import GuildSyncEngine


class SyncCogEngine:
    def __init__(
        self,
        bot: commands.Bot,
        guild_engine: "GuildSyncEngine",
        commands_engine: "SyncCommandsEngine",
    ) -> None:
        self.bot = bot
        self.guild_engine = guild_engine
        self.commands_engine = commands_engine

    def list_loaded_extensions(self) -> List[str]:
        return sorted(self.bot.extensions.keys())

    def list_configured_extensions(self) -> List[str]:
        configured = getattr(self.bot, "coglist", [])
        ordered: List[str] = []
        for entry in configured:
            if entry not in ordered:
                ordered.append(entry)
        return ordered

    def list_known_extensions(self) -> List[str]:
        known = set(self.list_loaded_extensions())
        known.update(self.list_configured_extensions())
        return sorted(known)

    def list_unloaded_extensions(self) -> List[str]:
        loaded = set(self.bot.extensions.keys())
        return [extension for extension in self.list_known_extensions() if extension not in loaded]

    async def reload_extension(self, extension: str) -> Tuple[bool, str]:
        if extension not in self.bot.extensions:
            return False, f"`{extension}` is not currently loaded."

        try:
            await self.bot.reload_extension(extension)
        except commands.ExtensionNotLoaded:
            return False, f"`{extension}` is not currently loaded."
        except commands.ExtensionFailed as exc:
            Logger.error("SyncCogEngine -", f"Failed to reload extension '{extension}': {exc}")
            return False, f"Reloading `{extension}` failed: {exc}."
        except Exception as exc:  # pragma: no cover - safety net
            Logger.error("SyncCogEngine -", f"Unexpected error reloading '{extension}': {exc}")
            return False, f"Unexpected error while reloading `{extension}`: {exc}."

        resynced, failure = await self._resync_commands()
        message = f"Reloaded `{extension}`." + self._format_resync_message(resynced)
        if failure is not None:
            message += f" Note: {failure}"
        return True, message

    async def enable_extension(self, extension: str) -> Tuple[bool, str]:
        if extension in self.bot.extensions:
            return False, f"`{extension}` is already loaded."

        try:
            await self.bot.load_extension(extension)
        except commands.ExtensionAlreadyLoaded:
            return False, f"`{extension}` is already loaded."
        except commands.ExtensionNotFound as exc:
            Logger.error("SyncCogEngine -", f"Extension '{extension}' not found: {exc}")
            return False, f"Extension `{extension}` was not found."
        except commands.NoEntryPointError as exc:
            Logger.error("SyncCogEngine -", f"Extension '{extension}' has no setup entry point: {exc}")
            return False, f"Extension `{extension}` is missing a setup entry point."
        except commands.ExtensionFailed as exc:
            Logger.error("SyncCogEngine -", f"Failed to enable extension '{extension}': {exc}")
            return False, f"Enabling `{extension}` failed: {exc}."
        except Exception as exc:  # pragma: no cover - safety net
            Logger.error("SyncCogEngine -", f"Unexpected error enabling '{extension}': {exc}")
            return False, f"Unexpected error while enabling `{extension}`: {exc}."

        resynced, failure = await self._resync_commands()
        message = f"Enabled `{extension}`." + self._format_resync_message(resynced)
        if failure is not None:
            message += f" Note: {failure}"
        return True, message

    async def disable_extension(self, extension: str) -> Tuple[bool, str]:
        if extension not in self.bot.extensions:
            return False, f"`{extension}` is not currently loaded."

        try:
            await self.bot.unload_extension(extension)
        except commands.ExtensionNotLoaded:
            return False, f"`{extension}` is not currently loaded."
        except Exception as exc:  # pragma: no cover - safety net
            Logger.error("SyncCogEngine -", f"Unexpected error disabling '{extension}': {exc}")
            return False, f"Unexpected error while disabling `{extension}`: {exc}."

        resynced, failure = await self._resync_commands()
        message = f"Disabled `{extension}`." + self._format_resync_message(resynced)
        if failure is not None:
            message += f" Note: {failure}"
        return True, message

    async def _resync_commands(self) -> Tuple[int, Optional[str]]:
        guilds = self.guild_engine.get_synced_guilds()
        if not guilds:
            return 0, None

        try:
            await self.commands_engine.sync_selected_guilds(
                guilds,
                clear_global=False,
                reset_snapshots=False,
                include_progress=False,
                progress_callback=None,
            )
        except Exception as exc:  # pragma: no cover - safety net
            Logger.error("SyncCogEngine -", f"Failed to resync commands after cog change: {exc}")
            return 0, "Command resync failed; check logs for details."

        return len(guilds), None

    @staticmethod
    def _format_resync_message(resynced: int) -> str:
        if resynced <= 0:
            return " Command resync skipped (no managed guilds)."
        if resynced == 1:
            return " Resynced commands for 1 guild."
        return f" Resynced commands for {resynced} guilds."
