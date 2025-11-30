import logging
from discord import app_commands
import discord
from discord.ext import commands

from bot import config, constants
from bot.helpers import GamblingHandler

class RandomCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config = bot.config
        self.gambling_handler = GamblingHandler(bot)

    random_cog = app_commands.Group(name="random", description="Random Commands", allowed_contexts=discord.app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True), allowed_installs=discord.app_commands.AppInstallationType(guild=True, user=True))

    track_group = app_commands.Group(name="track", description="Track Only", parent=random_cog)

    @track_group.command(name="all", description="Get a random Jam Track from a list of all available Jam Tracks")
    async def random_track_command(self, interaction: discord.Interaction):
        await self.gambling_handler.handle_random_track_interaction(interaction=interaction)

    @track_group.command(name="shop", description="Get a random Jam Track from only the Jam Tracks currently in the Shop.")
    async def random_track_command(self, interaction: discord.Interaction):
        await self.gambling_handler.handle_random_track_interaction(interaction=interaction, shop=True)

    @track_group.command(name="weekly", description="Get a random Jam Track from only the Jam Tracks currently in the weekly rotation.")
    async def random_track_command(self, interaction: discord.Interaction):
        await self.gambling_handler.handle_random_track_interaction(interaction=interaction, daily=True)

    setlist_group = app_commands.Group(name="setlist", description="Setlist Only", parent=random_cog)

    @setlist_group.command(name="all", description="Get a random setlist from the list of all available Jam Tracks")
    @app_commands.describe(limit = 'How many Jam Tracks your setlist should have.')
    async def random_setlist_command(self, interaction: discord.Interaction, limit:app_commands.Range[int, 1, 20] = 4):
        await self.gambling_handler.handle_random_setlist_interaction(interaction=interaction, limit=limit)

    @setlist_group.command(name="shop", description="Get a random setlist from only the Jam Tracks currently in the Shop.")
    @app_commands.describe(limit = 'How many Jam Tracks your setlist should have.')
    async def random_setlist_command(self, interaction: discord.Interaction, limit:app_commands.Range[int, 1, 20] = 4):
        await self.gambling_handler.handle_random_setlist_interaction(interaction=interaction, shop=True, limit=limit)

    @setlist_group.command(name="weekly", description="Get a random setlist from only the Jam Tracks currently in the weekly rotation.")
    @app_commands.describe(limit = 'How many Jam Tracks your setlist should have.')
    async def random_setlist_command(self, interaction: discord.Interaction, limit:app_commands.Range[int, 1, 20] = 4):
        await self.gambling_handler.handle_random_setlist_interaction(interaction=interaction, daily=True, limit=limit)