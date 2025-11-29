import discord
from discord.ext import commands
from discord import app_commands

from interface.logger import Logger
from interface.commands import debug_group
from discord import ui

class DebugCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

@debug_group.command(name="ping", description="Check the bot's latency.")
async def ping(interaction: discord.Interaction) -> None:
    latency = round(interaction.client.latency * 1000)  # Convert to milliseconds
    await interaction.response.send_message(f"Pong! Latency: {latency}ms", ephemeral=True)
