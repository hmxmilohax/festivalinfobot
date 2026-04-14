import logging
from discord import app_commands
import discord
from discord.ext import commands

from bot import constants, database
from bot.commands.leaderboard import LeaderboardCommandHandler

class LeaderboardCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config = bot.config
        self.lb_handler = LeaderboardCommandHandler(bot)

    lb_group = app_commands.Group(name="leaderboard", description="Leaderboard commands", allowed_contexts=discord.app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True), allowed_installs=discord.app_commands.AppInstallationType(guild=True, user=True))

    @lb_group.command(name="view", description="View the leaderboards of a song.")
    @app_commands.describe(song = "A search query: an artist, song name, or shortname.")
    @app_commands.describe(instrument = "The instrument to view the leaderboard of.")
    @app_commands.choices(
            instrument=[
                app_commands.Choice(name=kt.value.english, value=kt.value.lb_code) for kt in constants.Instruments.__members__.values()
            ]
        )
    async def leaderboard_command(self, interaction: discord.Interaction, song:str, instrument:app_commands.Choice[str]):
        real_instrument: constants.Instruments = None
        values = constants.Instruments.__members__.values()
        real_instrument = discord.utils.find(lambda v: v.value.lb_code == instrument.value, values)

        await self.lb_handler.handle_interaction(interaction, song=song, instrument=real_instrument)

    @lb_group.command(name="band", description="View the band leaderboards of a song.")
    @app_commands.describe(song = "A search query: an artist, song name, or shortname.")
    @app_commands.describe(type = "The band type to view the leaderboard of.")
    @app_commands.choices(
            type=[
                app_commands.Choice(name=kt.value.english, value=kt.value.code) for kt in constants.BandTypes.__members__.values()
            ]
        )
    async def leaderboard_command(self, interaction: discord.Interaction, song:str, type:app_commands.Choice[str]):
        real_type: constants.BandTypes = None
        values = constants.BandTypes.__members__.values()
        real_type = discord.utils.find(lambda v: v.value.code == type.value, values)

        await self.lb_handler.handle_band_interaction(interaction, song=song, band_type=real_type)

    @lb_group.command(name="all_time", description="View the All-Time leaderboards of a song.")
    @app_commands.describe(song = "A search query: an artist, song name, or shortname.")
    @app_commands.describe(type = "The leaderboard type to view the all-time leaderboard of.")
    @app_commands.choices(
            type=[
                app_commands.Choice(name=kt.value.english, value=kt.value.code) for kt in constants.AllTimeLBTypes.__members__.values()
            ]
        )
    async def leaderboard_command(self, interaction: discord.Interaction, song:str, type:app_commands.Choice[str]):
        real_type: constants.AllTimeLBTypes = None
        values = constants.AllTimeLBTypes.__members__.values()
        real_type = discord.utils.find(lambda v: v.value.code == type.value, values)

        await self.lb_handler.handle_alltime_interaction(interaction, song=song, type=real_type)