from __future__ import annotations

from typing import Iterable, List, Optional, Tuple

import discord
from discord import AppCommandType, app_commands
from discord.app_commands import AppCommand, Group

from interface.logger import Logger
from cogs.guildSync.core.config.lib import is_command_enabled_for_guild


class CommandCloner:
    def __init__(self, root_groups: Iterable[Group]) -> None:
        self.root_groups = list(root_groups)

    def iter_commands(self) -> Iterable[AppCommand]:
        for group in self.root_groups:
            yield from self._iter_commands(group)

    def _iter_commands(self, group: Group) -> Iterable[AppCommand]:
        for child in group.commands:
            if isinstance(child, app_commands.Group):
                yield from self._iter_commands(child)
            else:
                yield child

    def command_key(self, command: AppCommand) -> str:
        return command.qualified_name.replace(" ", ".").lower()

    def format_label(self, command: AppCommand) -> str:
        name = getattr(command, "qualified_name", None) or command.name
        cmd_type = getattr(command, "type", AppCommandType.chat_input)

        if cmd_type is AppCommandType.chat_input:
            return f"/{name}"
        if cmd_type is AppCommandType.user:
            return f"{name} [user]"
        if cmd_type is AppCommandType.message:
            return f"{name} [message]"
        type_name = getattr(cmd_type, "name", "unknown").lower()
        return f"{name} [{type_name}]"

    def clone_command(self, command: AppCommand) -> Optional[AppCommand]:
        if hasattr(command, "copy"):
            return command.copy()

        if hasattr(command, "_copy_with"):
            try:
                return command._copy_with(parent=None, binding=None)  # type: ignore[attr-defined]
            except TypeError as exc:
                Logger.error(
                    "SyncCommandsEngine -",
                    f"Failed to clone '{command.name}' via _copy_with: {exc}; skipping.",
                )
                return None

        Logger.error(
            "SyncCommandsEngine -",
            f"Encountered app command '{command.name}' without supported clone method; skipping.",
        )
        return None

    def clone_group(self, source: Group, guild_id: int) -> Optional[Group]:
        clone = app_commands.Group(
            name=source.name,
            description=source.description,
            nsfw=source.nsfw,
            default_permissions=source.default_permissions,
            guild_only=source.guild_only,
        )

        added = False

        for child in source.commands:
            if isinstance(child, app_commands.Group):
                nested = self.clone_group(child, guild_id)
                if nested is not None:
                    clone.add_command(nested)
                    added = True
                continue

            command_key = self.command_key(child)
            if not is_command_enabled_for_guild(command_key, guild_id):
                continue

            cloned = self.clone_command(child)
            if cloned is None:
                continue

            clone.add_command(cloned)
            added = True

        return clone if added else None

    def list_available_keys(self) -> List[Tuple[str, str]]:
        entries: List[Tuple[str, str]] = []
        for command in self.iter_commands():
            key = self.command_key(command)
            label = self.format_label(command)
            entries.append((key, label))

        entries.sort(key=lambda item: item[0])
        return entries
