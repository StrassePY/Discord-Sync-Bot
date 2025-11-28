from .main import DebugCog, debug_group

async def setup(bot):
    await bot.add_cog(DebugCog(bot))
    # bot.tree.add_command(debug_group)