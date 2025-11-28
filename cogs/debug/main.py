import discord
from discord.ext import commands
from discord import app_commands

from discord import ui

from interface.logger import Logger
from interface.commands import debug_group

class PingView(ui.LayoutView):
    def __init__(self, interaction: discord.Interaction) -> None:
        super().__init__(timeout=None)

        latency = round(interaction.client.latency * 1000)

        header = ui.TextDisplay("### Debug - Ping 🏓")
        body = ui.TextDisplay(f"The bot's latency is **{latency}ms**.")

        container = ui.Container(accent_color=discord.Color.green())
        container.add_item(header)
        container.add_item(body)
        self.add_item(container)

class DebugCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

@debug_group.command(name="ping", description="Check the bot's latency.")
async def ping(interaction: discord.Interaction) -> None:
    # latency = round(interaction.client.latency * 1000)  # Convert to milliseconds
    # await interaction.response.send_message(f"Pong! Latency: {latency}ms", ephemeral=True)

    await interaction.response.send_message(view=PingView(interaction), ephemeral=True)