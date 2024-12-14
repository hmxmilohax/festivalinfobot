from discord import app_commands
import discord
from discord.ext import commands

from bot.status import StatusHandler

class FortniteCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.lightswitch_handler = StatusHandler()

    fortnite_group = app_commands.Group(name="fortnite", description="Fortnite Commands", allowed_contexts=discord.app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True), allowed_installs=discord.app_commands.AppInstallationType(guild=True, user=True))

    @fortnite_group.command(name="status", description="See if Fortnite is currently online or offline.")
    async def fortnitestatus_command(self, interaction: discord.Interaction):
        await self.lightswitch_handler.handle_fortnitestatus_interaction(interaction=interaction)

    fest_group = app_commands.Group(name="festival", description="Festival Commands", parent=fortnite_group)

    @fest_group.command(name="mainstage", description="View information about Festival Main Stage.")
    async def mainstage_command(self, interaction: discord.Interaction):
        await self.lightswitch_handler.handle_gamemode_interaction(interaction=interaction)

    @fest_group.command(name="battlestage", description="View information about Festival Battle Stage.")
    async def battlestage_command(self, interaction: discord.Interaction):
        await self.lightswitch_handler.handle_gamemode_interaction(interaction=interaction, search_for="Festival Battle Stage")

    @fest_group.command(name="jamstage", description="View information about Festival Jam Stage.") 
    async def jamstage_command(self, interaction: discord.Interaction):
        await self.lightswitch_handler.handle_gamemode_interaction(interaction=interaction, search_for="Festival Jam Stage")