from discord import app_commands
import discord
from discord.ext import commands

from bot.status import StatusHandler

class FortniteCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.lightswitch_handler = StatusHandler(bot)

    fortnite_group = app_commands.Group(name="festival", description="Festival Commands", allowed_contexts=discord.app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True), allowed_installs=discord.app_commands.AppInstallationType(guild=True, user=True))

    @fortnite_group.command(name="status", description="See if Fortnite is currently online or offline.")
    async def fortnitestatus_command(self, interaction: discord.Interaction):
        await self.lightswitch_handler.handle_fortnitestatus_interaction(interaction=interaction)

    @fortnite_group.command(name="players", description="See how many players are active across the three Festival gamemodes.")
    async def mainstage_command(self, interaction: discord.Interaction):
        await self.lightswitch_handler.handle_gamemode_interaction(interaction=interaction)