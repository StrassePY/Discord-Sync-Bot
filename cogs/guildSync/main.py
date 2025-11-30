import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from typing import Dict, List

from interface.logger import Logger

from cogs.guildSync.core.engine.syncCommands.main import SyncCommandsEngine
from cogs.guildSync.core.engine.syncGuilds.main import GuildSyncEngine

from interface.commands import sync_group
from cogs.guildSync.core.ui.notificationView import (
    create_success_container,
    create_error_container,
)
from cogs.guildSync.core.config.lib import (
    disable_command_for_guild,
    disable_command_globally,
    enable_command_for_guild,
    enable_command_globally,
    get_command_scope,
)

REQUIRED_VERSION = (2, 3, 0)

def _current_version_tuple() -> tuple[int, int, int]:
    info = getattr(discord, "version_info", None)
    if info:
        return info.major, info.minor, info.micro

    parts: List[int] = []
    for part in discord.__version__.split("."):
        digits = "".join(ch for ch in part if ch.isdigit())
        if digits:
            parts.append(int(digits))
        if len(parts) == 3:
            break

    while len(parts) < 3:
        parts.append(0)

    return tuple(parts[:3])


class GuildSyncCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.sync_commands_engine = SyncCommandsEngine(bot)
        self.sync_guilds_engine = GuildSyncEngine(bot)
        self.sync_guilds_engine.attach_commands_engine(self.sync_commands_engine)

    async def cog_load(self) -> None:
        asyncio.create_task(self._sync_on_ready())

    async def _sync_on_ready(self) -> None:
        await self.bot.wait_until_ready()
        current = _current_version_tuple()
        if current < REQUIRED_VERSION:
            print("")
            Logger.warning(
                "GuildSyncCog -",
                f"Discord.py version {'.'.join(map(str, REQUIRED_VERSION))} or higher is needed to run the guildSync cog. Unloading cog. Your current version is: {discord.__version__}"
            )
            await self.bot.remove_cog(self.qualified_name)
            return

        await self.sync_guilds_engine.sync_guilds()
        synced_guilds = await self.sync_guilds_engine.ensure_guilds()
        if synced_guilds:
            await self.sync_commands_engine.sync_commands(synced_guilds)
            removed_ids = self.sync_guilds_engine.get_removed_guild_ids()
            if removed_ids:
                removed_guilds = [guild for guild in self.bot.guilds if guild.id in removed_ids]
                await self.sync_commands_engine.desync_commands(removed_guilds)

@sync_group.command(name="view", description="Show cached synced guilds.")
async def show_synced_guilds(interaction: discord.Interaction) -> None:
    await interaction.response.defer(ephemeral=True)

    guild_sync_cog = interaction.client.get_cog("GuildSyncCog")
    if guild_sync_cog is None:
        await interaction.followup.send("Guild sync cog is not loaded.", ephemeral=True)
        return

    assert isinstance(guild_sync_cog, GuildSyncCog)
    synced_guilds = guild_sync_cog.sync_guilds_engine.synced_guilds
    command_snapshot = guild_sync_cog.sync_commands_engine.get_guild_commands()
    disabled_groups = guild_sync_cog.sync_commands_engine.get_disabled_groups()
    from cogs.guildSync.core.ui.viewSyncedView import ViewSyncedContainer
    view = ViewSyncedContainer(
        synced_guild=synced_guilds,
        client=interaction.client,
        guild_commands=command_snapshot,
        disabled_groups=disabled_groups,
    )
    await interaction.followup.send(view=view, ephemeral=True)


async def _command_key_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> List[app_commands.Choice[str]]:
    guild_sync_cog = interaction.client.get_cog("GuildSyncCog")
    if not isinstance(guild_sync_cog, GuildSyncCog):
        return []

    entries = guild_sync_cog.sync_commands_engine.list_available_command_keys()
    current_lower = current.lower()
    choices: List[app_commands.Choice[str]] = []

    for key, label in entries:
        display = f"{label} ({key})"
        if current_lower and current_lower not in display.lower():
            continue
        choices.append(app_commands.Choice(name=display[:100], value=key))
        if len(choices) >= 25:
            break

    return choices


async def _guild_target_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> List[app_commands.Choice[str]]:
    guild_sync_cog = interaction.client.get_cog("GuildSyncCog")
    if not isinstance(guild_sync_cog, GuildSyncCog):
        return []

    synced = guild_sync_cog.sync_guilds_engine.get_synced_guilds()
    current_lower = current.lower()
    choices: List[app_commands.Choice[str]] = []

    if not current or "global".startswith(current_lower):
        choices.append(app_commands.Choice(name="All guilds", value="global"))

    for guild_id, guild in sorted(synced.items(), key=lambda item: item[1].name.lower()):
        display = f"{guild.name} ({guild_id})"
        if current_lower and current_lower not in display.lower():
            continue
        choices.append(app_commands.Choice(name=display[:100], value=str(guild_id)))
        if len(choices) >= 25:
            break

    return choices


def _ensure_admin(interaction: discord.Interaction) -> bool:
    if interaction.guild is None:
        return False
    member = interaction.user
    return isinstance(member, discord.Member) and member.guild_permissions.administrator


def _resolve_target_guilds(
    guild_sync_cog: GuildSyncCog,
    target_value: str,
) -> Dict[int, discord.Guild]:
    synced = guild_sync_cog.sync_guilds_engine.get_synced_guilds()

    if target_value == "global":
        return synced

    try:
        target_id = int(target_value)
    except ValueError:
        return {}

    target_guild = synced.get(target_id) or guild_sync_cog.bot.get_guild(target_id)
    return {target_id: target_guild} if target_guild else {}


def _success_view(message: str) -> discord.ui.LayoutView:
    view = discord.ui.LayoutView(timeout=None)
    view.add_item(create_success_container(message))
    return view

def _error_view(message: str) -> discord.ui.LayoutView:
    view = discord.ui.LayoutView(timeout=None)
    view.add_item(create_error_container(message))
    return view

def _normalize_command_key(value: str) -> str:
    return value.replace(" ", ".").lower()


def _selection_display_label(entries: Dict[str, str], normalized_key: str, original_key: str) -> str:
    if normalized_key.endswith(".*"):
        return entries.get(normalized_key, original_key)
    return original_key


def _format_scope_value(scope: object) -> str:
    return "global" if scope is None else str(scope)


def _build_scope_summary(command_keys: List[str]) -> str:
    scope_values = [_format_scope_value(get_command_scope(key)) for key in command_keys]
    unique_scopes = sorted(set(scope_values))

    if len(command_keys) == 1 or len(unique_scopes) == 1:
        return f"Current scope: `{unique_scopes[0]}`."

    scope_list = ", ".join(f"`{scope}`" for scope in unique_scopes)
    return f"Updated {len(command_keys)} commands. Scopes include: {scope_list}."


@sync_group.command(name="disable-command", description="Disable a synced command and resync immediately.")
@app_commands.describe(
    command_key="Command to disable (e.g. sync.synced)",
    target_guild="Select the guild to apply the change to or choose all guilds",
)
@app_commands.autocomplete(command_key=_command_key_autocomplete, target_guild=_guild_target_autocomplete)
async def disable_command(
    interaction: discord.Interaction,
    command_key: str,
    target_guild: str,
) -> None:
    if not _ensure_admin(interaction):
        # await interaction.response.send_message(
        #     "You must run this command inside a guild with administrator permissions.",
        #     ephemeral=True,
        # )
        await interaction.response.send_message(
            view=_error_view("You must run this command inside a guild with administrator permissions."),
            ephemeral=True,
        )
        return

    await interaction.response.defer(ephemeral=True)

    guild_sync_cog = interaction.client.get_cog("GuildSyncCog")
    if not isinstance(guild_sync_cog, GuildSyncCog):
        await interaction.followup.send(
            view=_error_view("Guild sync cog is not loaded."),
            ephemeral=True,
        )
        return

    target_map = _resolve_target_guilds(guild_sync_cog, target_guild)
    if not target_map:
        await interaction.followup.send(
            view=_error_view("Unable to resolve the selected guild."),
            ephemeral=True,
        )
        return

    target_label = "all guilds" if target_guild == "global" else ", ".join(
        f"{guild.name} ({guild_id})" for guild_id, guild in target_map.items()
    )

    normalized_key = _normalize_command_key(command_key)
    available_entries = dict(guild_sync_cog.sync_commands_engine.list_available_command_keys())
    is_group_selection = normalized_key.endswith(".*")
    if not is_group_selection and normalized_key not in available_entries:
        expanded_keys: List[str] = []
    else:
        expanded_keys = guild_sync_cog.sync_commands_engine.expand_command_key(normalized_key)
    if not expanded_keys:
        await interaction.followup.send(
            view=_error_view(f"No commands matched `{command_key}`."),
            ephemeral=True,
        )
        return

    selection_display = _selection_display_label(available_entries, normalized_key, command_key)
    target_id = None if target_guild == "global" else next(iter(target_map))

    changed_keys: List[str] = []
    for resolved_key in expanded_keys:
        if target_guild == "global":
            if disable_command_globally(resolved_key):
                changed_keys.append(resolved_key)
        else:
            assert target_id is not None
            if disable_command_for_guild(resolved_key, target_id):
                changed_keys.append(resolved_key)

    if not changed_keys:
        await interaction.followup.send(
            view=_error_view(f"`{selection_display}` is already disabled for {target_label}."),
            ephemeral=True,
        )
        return

    await guild_sync_cog.sync_commands_engine.sync_selected_guilds(
        target_map,
        clear_global=(target_guild == "global"),
        reset_snapshots=(target_guild == "global"),
        include_progress=False,
        progress_callback=None,
    )

    scope_summary = _build_scope_summary(changed_keys)
    await interaction.followup.send(
        view=_success_view(
            f"Disabled `{selection_display}` for {target_label}. {scope_summary}"
        ),
        ephemeral=True,
    )


@sync_group.command(name="enable-command", description="Enable a previously disabled command and resync.")
@app_commands.describe(
    command_key="Command to enable (e.g. sync.synced)",
    target_guild="Select the guild to apply the change to or choose all guilds",
)
@app_commands.autocomplete(command_key=_command_key_autocomplete, target_guild=_guild_target_autocomplete)
async def enable_command(
    interaction: discord.Interaction,
    command_key: str,
    target_guild: str,
) -> None:
    if not _ensure_admin(interaction):
        await interaction.response.send_message(
            view=_error_view("You must run this command inside a guild with administrator permissions."),
            ephemeral=True,
        )
        return

    await interaction.response.defer(ephemeral=True)

    guild_sync_cog = interaction.client.get_cog("GuildSyncCog")
    if not isinstance(guild_sync_cog, GuildSyncCog):
        await interaction.followup.send(view=_error_view("Guild sync cog is not loaded."))
        return

    target_map = _resolve_target_guilds(guild_sync_cog, target_guild)
    if not target_map:
        await interaction.followup.send(
            view=_error_view("Unable to resolve the selected guild."),
            ephemeral=True,
        )
        return

    target_label = "all guilds" if target_guild == "global" else ", ".join(
        f"{guild.name} ({guild_id})" for guild_id, guild in target_map.items()
    )

    normalized_key = _normalize_command_key(command_key)
    available_entries = dict(guild_sync_cog.sync_commands_engine.list_available_command_keys())
    is_group_selection = normalized_key.endswith(".*")
    if not is_group_selection and normalized_key not in available_entries:
        expanded_keys: List[str] = []
    else:
        expanded_keys = guild_sync_cog.sync_commands_engine.expand_command_key(normalized_key)
    if not expanded_keys:
        await interaction.followup.send(
            f"No commands matched `{command_key}`.",
            ephemeral=True,
        )
        return

    selection_display = _selection_display_label(available_entries, normalized_key, command_key)
    target_id = None if target_guild == "global" else next(iter(target_map))

    changed_keys: List[str] = []
    for resolved_key in expanded_keys:
        if target_guild == "global":
            if enable_command_globally(resolved_key):
                changed_keys.append(resolved_key)
        else:
            assert target_id is not None
            if enable_command_for_guild(resolved_key, target_id):
                changed_keys.append(resolved_key)

    if not changed_keys:
        await interaction.followup.send(
            view=_error_view(f"`{selection_display}` is already enabled for {target_label}."),
            ephemeral=True,
        )
        return

    await guild_sync_cog.sync_commands_engine.sync_selected_guilds(
        target_map,
        clear_global=(target_guild == "global"),
        reset_snapshots=(target_guild == "global"),
        include_progress=False,
        progress_callback=None,
    )

    scope_summary = _build_scope_summary(changed_keys)
    await interaction.followup.send(
        view=_success_view(
            f"Enabled `{selection_display}` for {target_label}. {scope_summary}"
        ),
        ephemeral=True,
    )