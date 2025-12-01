from discord import app_commands

sync_group = app_commands.Group(
    name="sync",
    description="Synchronization related commands",
)

sync_cog_group = app_commands.Group(
    name="cog",
    description="Disable/Enable/Reload cogs with guildSync",
    parent=sync_group,
)

sync_command_group = app_commands.Group(
    name="command",
    description="Disable/Enable commands with guildSync",
    parent=sync_group,
)

debug_group = app_commands.Group(
    name="debug",
    description="Debugging related commands",
)

ROOT_COMMAND_GROUPS = (
    sync_group,
    debug_group,
)