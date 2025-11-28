from discord import app_commands

moderation_group = app_commands.Group(
    name="moderation",
    description="Moderation related commands",
)

debug_group = app_commands.Group(
    name="debug",
    description="Debugging related commands",
)

ROOT_COMMAND_GROUPS = (
    moderation_group,
    debug_group,
)