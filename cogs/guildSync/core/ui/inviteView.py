from __future__ import annotations

from typing import TYPE_CHECKING, List

import discord
from discord import ui

from cogs.guildSync.core.config.lib import suppress_guild

if TYPE_CHECKING:
    from cogs.guildSync.core.engine.syncGuilds.main import GuildSyncEngine


class GuildSyncInviteView(ui.LayoutView):
    def __init__(self, engine: GuildSyncEngine, guild: discord.Guild) -> None:
        super().__init__(timeout=None)
        self.engine = engine
        self.guild = guild

        self._header_display = ui.TextDisplay("### Ready to Sync Commands")
        self._body_display = ui.TextDisplay(
            "This bot is currently not synchronizing commands for this guild. "
            "If you have the Manage Server permission you can opt in or dismiss this notice."
        )

        container = ui.Container(accent_color=discord.Color.blurple())
        container.add_item(self._header_display)
        container.add_item(self._body_display)

        self._buttons: List[ui.Button] = []
        button_row = ui.ActionRow()
        button_row.add_item(self._build_sync_button())
        button_row.add_item(self._build_decline_button())
        container.add_item(button_row)

        self.add_item(container)

    def _has_permission(self, interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            return False
        member = interaction.user
        return isinstance(member, discord.Member) and member.guild_permissions.manage_guild

    def _disable_buttons(self) -> None:
        for button in self._buttons:
            button.disabled = True

    async def _finalize(
        self,
        interaction: discord.Interaction,
        *,
        header: str,
        body: str,
        followup: str,
    ) -> None:
        self._header_display.content = header
        self._body_display.content = body
        self._disable_buttons()
        await interaction.message.edit(view=self)
        await interaction.followup.send(followup, ephemeral=True)

    def _build_sync_button(self) -> ui.Button:
        button = ui.Button(label="Sync Now", style=discord.ButtonStyle.success)
        button.callback = self._on_approve  # type: ignore[assignment]
        self._buttons.append(button)
        return button

    def _build_decline_button(self) -> ui.Button:
        button = ui.Button(label="Not Now", style=discord.ButtonStyle.danger)
        button.callback = self._on_deny  # type: ignore[assignment]
        self._buttons.append(button)
        return button

    async def _on_approve(self, interaction: discord.Interaction) -> None:
        if not self._has_permission(interaction):
            await interaction.response.send_message(
                "You need the Manage Server permission to enable command synchronization.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=False)

        success = await self.engine.add_guild(
            self.guild.id,
            alias=self.guild.name,
            persist=True,
            overwrite=False,
        )

        if success:
            self.engine.mark_invite_complete(self.guild.id)
            await self._finalize(
                interaction,
                header="### Sync Enabled ✅",
                body="Commands are now syncing for this guild.",
                followup="Sync registered and commands will begin propagating shortly.",
            )
        else:
            await interaction.followup.send(
                "Unable to register this guild automatically. Please ensure it is present in the configuration.",
                ephemeral=True,
            )

    async def _on_deny(self, interaction: discord.Interaction) -> None:
        if not self._has_permission(interaction):
            await interaction.response.send_message(
                "You need the Manage Server permission to dismiss this notification.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=False)

        suppress_guild(self.guild.id)
        self.engine.mark_invite_complete(self.guild.id)
        await self._finalize(
            interaction,
            header="### Sync Invitation Dismissed",
            body="We will remain quiet until synchronization is manually enabled.",
            followup="Understood. We will not send further sync invitations for this guild.",
        )