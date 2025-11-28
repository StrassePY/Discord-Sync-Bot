from discord import app_commands

sync_group = app_commands.Group(
    name="sync",
    description="Synchronization related commands",
)

debug_group = app_commands.Group(
    name="debug",
    description="Debugging related commands",
)

ROOT_COMMAND_GROUPS = (
    sync_group,
    debug_group,
)