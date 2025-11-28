from .main import GuildSyncCog

async def setup(bot) -> None:
    await bot.add_cog(GuildSyncCog(bot))
