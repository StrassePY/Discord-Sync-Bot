import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from typing import Dict, List

from interface.logger import Logger

from cogs.guildSync.core.engine.syncCommands.main import SyncCommandsEngine
from cogs.guildSync.core.engine.syncGuilds.main import GuildSyncEngine

from interface.commands import moderation_group
from cogs.guildSync.core.ui.success_container.container import create_success_container
from cogs.guildSync.core.config.lib import (
    disable_command_for_guild,
    disable_command_globally,
    enable_command_for_guild,
    enable_command_globally,
    get_command_scope,
)

if moderation_group.get_command("synced"):
    moderation_group.remove_command("synced")

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
        await self.sync_guilds_engine.sync_guilds()
        synced_guilds = await self.sync_guilds_engine.ensure_guilds()
        await self.sync_commands_engine.sync_commands(synced_guilds)
        unmanaged_guilds = [guild for guild in self.bot.guilds if guild.id not in synced_guilds]
        await self.sync_commands_engine.desync_commands(unmanaged_guilds)

@moderation_group.command(name="synced", description="Show cached synced guilds.")
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
    from cogs.guildSync.core.ui.containers import ViewSyncedContainer
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


@moderation_group.command(name="disable-command", description="Disable a synced command and resync immediately.")
@app_commands.describe(
    command_key="Command to disable (e.g. moderation.synced)",
    target_guild="Select the guild to apply the change to or choose all guilds",
)
@app_commands.autocomplete(command_key=_command_key_autocomplete, target_guild=_guild_target_autocomplete)
async def disable_command(
    interaction: discord.Interaction,
    command_key: str,
    target_guild: str,
) -> None:
    if not _ensure_admin(interaction):
        await interaction.response.send_message(
            "You must run this command inside a guild with administrator permissions.",
            ephemeral=True,
        )
        return

    await interaction.response.defer(ephemeral=True)

    guild_sync_cog = interaction.client.get_cog("GuildSyncCog")
    if not isinstance(guild_sync_cog, GuildSyncCog):
        await interaction.followup.send("Guild sync cog is not loaded.", ephemeral=True)
        return

    target_map = _resolve_target_guilds(guild_sync_cog, target_guild)
    if not target_map:
        await interaction.followup.send(
            "Unable to resolve the selected guild.",
            ephemeral=True,
        )
        return

    target_label = "all guilds" if target_guild == "global" else ", ".join(
        f"{guild.name} ({guild_id})" for guild_id, guild in target_map.items()
    )

    if target_guild == "global":
        changed = disable_command_globally(command_key)
    else:
        target_id = next(iter(target_map))
        changed = disable_command_for_guild(command_key, target_id)

    if not changed:
        await interaction.followup.send(
            f"`{command_key}` is already disabled for {target_label}.",
            ephemeral=True,
        )
        return

    await guild_sync_cog.sync_commands_engine.sync_selected_guilds(
        target_map,
        clear_global=(target_guild == "global"),
        reset_snapshots=(target_guild == "global"),
        include_progress=False,
    )

    new_scope = get_command_scope(command_key)
    await interaction.followup.send(
        view=_success_view(
            f"Disabled `{command_key}` for {target_label}. Current scope: `{new_scope}`.",
        ),
        ephemeral=True,
    )


@moderation_group.command(name="enable-command", description="Enable a previously disabled command and resync.")
@app_commands.describe(
    command_key="Command to enable (e.g. moderation.synced)",
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
            "You must run this command inside a guild with administrator permissions.",
            ephemeral=True,
        )
        return

    await interaction.response.defer(ephemeral=True)

    guild_sync_cog = interaction.client.get_cog("GuildSyncCog")
    if not isinstance(guild_sync_cog, GuildSyncCog):
        await interaction.followup.send("Guild sync cog is not loaded.", ephemeral=True)
        return

    target_map = _resolve_target_guilds(guild_sync_cog, target_guild)
    if not target_map:
        await interaction.followup.send(
            "Unable to resolve the selected guild.",
            ephemeral=True,
        )
        return

    target_label = "all guilds" if target_guild == "global" else ", ".join(
        f"{guild.name} ({guild_id})" for guild_id, guild in target_map.items()
    )

    if target_guild == "global":
        changed = enable_command_globally(command_key)
    else:
        target_id = next(iter(target_map))
        changed = enable_command_for_guild(command_key, target_id)

    if not changed:
        await interaction.followup.send(
            f"`{command_key}` is already enabled for {target_label}.",
            ephemeral=True,
        )
        return

    await guild_sync_cog.sync_commands_engine.sync_selected_guilds(
        target_map,
        clear_global=(target_guild == "global"),
        reset_snapshots=(target_guild == "global"),
        include_progress=False,
    )

    new_scope = get_command_scope(command_key)
    scope_display = "global" if new_scope is None else new_scope
    await interaction.followup.send(
        view=_success_view(
            f"Enabled `{command_key}` for {target_label}. Current scope: `{scope_display}`.",
        ),
        ephemeral=True,
    )