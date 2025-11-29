import discord
from discord import ui
from typing import Dict, List, Optional

# from .buttons import ReSyncButton

class ViewSyncedContainer(ui.LayoutView):
    def __init__(
        self,
        synced_guild: Dict[int, discord.Guild],
        client: discord.Client,
        guild_commands: Optional[Dict[int, List[str]]] = None,
        disabled_groups: Optional[Dict[int, List[str]]] = None,
    ) -> None:
        super().__init__(timeout=None)
        self.client = client
        self.guild_commands = guild_commands or {}
        self.disabled_groups = disabled_groups or {}

        header = ui.TextDisplay("### SyncEngine - Synced Guilds 📡")
        if not synced_guild:
            body_lines = [
                "Synced Guilds",
                "⤷ No guilds are currently synced.",
            ]
        else:
            body_lines = [
                "**Synced Guilds**",
            ]

            for guild_id, guild in sorted(synced_guild.items(), key=lambda item: item[1].name.lower()):
                body_lines.append(f"> **⤷** *{guild.name}* (`{guild_id}`)")

                commands = self.guild_commands.get(guild_id, [])
                if commands:
                    for command in commands:
                        body_lines.append(f">    • `{command}`")
                else:
                    body_lines.append(">    • _No commands synced._")

                disabled = self.disabled_groups.get(guild_id, [])
                if disabled:
                    disabled_list = ", ".join(disabled)
                    body_lines.append(f">    • Disabled groups: {disabled_list}")

        body_text = ui.TextDisplay("\n".join(body_lines))

        section_kwargs = {}
        bot_user = getattr(self.client, "user", None)
        avatar_asset = getattr(bot_user.display_avatar, "url", None) if bot_user else None
        if avatar_asset:
            section_kwargs["accessory"] = ui.Thumbnail(media=avatar_asset)

        section = ui.Section(header, body_text, **section_kwargs)
        container_view = ui.Container(accent_color=discord.Color.blurple())
        container_view.add_item(section)
        # container_view.add_item(ui.Separator())
        # resync_row = ui.ActionRow()
        # resync_button = ReSyncButton(client=self.client)
        # resync_row.add_item(resync_button)
        # container_view.add_item(resync_row)
        

        self.add_item(container_view)