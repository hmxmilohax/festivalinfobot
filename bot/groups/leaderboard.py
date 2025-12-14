import logging
from discord import app_commands
import discord
from discord.ext import commands

from bot import constants, database
from bot.leaderboard import LeaderboardCommandHandler

class LeaderboardCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config = bot.config
        self.lb_handler = LeaderboardCommandHandler(bot)

    lb_group = app_commands.Group(name="leaderboard", description="Leaderboard commands", allowed_contexts=discord.app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True), allowed_installs=discord.app_commands.AppInstallationType(guild=True, user=True))

    @lb_group.command(name="view", description="View the leaderboards of a song.")
    @app_commands.describe(song = "A search query: an artist, song name, or shortname.")
    @app_commands.describe(instrument = "The instrument to view the leaderboard of.")
    async def leaderboard_command(self, interaction: discord.Interaction, song:str, instrument:constants.Instruments):
        await self.lb_handler.handle_interaction(interaction, song=song, instrument=instrument)

    @lb_group.command(name="band", description="View the band leaderboards of a song.")
    @app_commands.describe(song = "A search query: an artist, song name, or shortname.")
    @app_commands.describe(type = "The band type to view the leaderboard of.")
    async def leaderboard_command(self, interaction: discord.Interaction, song:str, type:constants.BandTypes):
        await self.lb_handler.handle_band_interaction(interaction, song=song, band_type=type)

    @lb_group.command(name="all_time", description="View the All-Time leaderboards of a song.")
    @app_commands.describe(song = "A search query: an artist, song name, or shortname.")
    @app_commands.describe(type = "The leaderboard type to view the all-time leaderboard of.")
    async def leaderboard_command(self, interaction: discord.Interaction, song:str, type:constants.AllTimeLBTypes):
        await self.lb_handler.handle_alltime_interaction(interaction, song=song, type=type)