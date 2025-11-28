import discord
from discord.ext import commands
from discord import app_commands

from config.lib import TOKEN, GUILD_ID
from interface.logger import Logger

intents = discord.Intents.all() # Enable all intents
intents.message_content = True # Enable message content intent


## Start of the Bot Class, this is the main head for your bot. This is the script that will be used to start the bot.
## You can add cogs to the bot by adding them to the coglist in the aclient class.
## Make sure to add your cogs in the cogs folder and import them in the coglist.
## Example: 'cogs.example_cog.ExampleCog',
## You can run the bot by running this script.
## Make sure to install the required packages in requirements.txt
## To run the bot, use the command: python app.py
## Happy coding!

class aclient(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.synced = False # we use this to check if the slash commands are synced
        self.cogs_loaded = False # we use this to check if the cogs are loaded
        self.coglist = [
            # List your cogs here, e.g. 'cogs.example_cog.ExampleCog',
            # 'cogs.example_cog.ExampleCog',
            # Add your cogs here
            'cogs.guildSync',
            'cogs.debug'
        ]

    async def on_ready(self):
        await self.wait_until_ready()

        # Add the cog to the main head of the cog, so you dont have to add it in every cog
        if not self.cogs_loaded:
            print("") # ignore: this is just to add a new line
            if not self.coglist:
                Logger.info("Discord Client -", "No cogs to load.")
            else:
                for cog in self.coglist:
                    try:
                        await self.load_extension(cog)
                        Logger.success("Discord Client -", f"Loaded cog: {cog}")
                    except Exception as e:
                        Logger.error("Discord Client -", f"Failed to load cog {cog}: {e}")
            self.cogs_loaded = True
        
        print("") # ignore: this is just to add a new line
        if self.user:
            Logger.success("Discord Client -", f"Bot is online as {self.user} (ID: {self.user.id})")
        else:
            Logger.error("Discord Client -", "Bot user is not available.")

    async def setup_hook(self):
        pass # This function can be used to make views like: buttons, dropdowns, etc persistent. Check the REPO for information.

client = aclient()
client.run(TOKEN)