from .main import GuildSyncCog, moderation_group

async def setup(bot) -> None:
    await bot.add_cog(GuildSyncCog(bot))
