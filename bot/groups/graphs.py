import logging
from discord import app_commands
import discord
from discord.ext import commands

from bot import config, constants
from bot.graph import GraphCommandsHandler

class GraphCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config = bot.config
        self.graph_handler = GraphCommandsHandler()

    graph_group = app_commands.Group(name="graph", description="Graph Command Group.", allowed_contexts=discord.app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True), allowed_installs=discord.app_commands.AppInstallationType(guild=True, user=True))

    graph_notes_group = app_commands.Group(name="counts", description="Graph the note and lift counts for a specific song.", parent=graph_group)
    @graph_notes_group.command(name="all", description="Graph the note counts for a specific song.")
    @app_commands.describe(song = "A search query: an artist, song name, or shortname.")
    async def graph_note_counts_command(self, interaction: discord.Interaction, song:str):
        await self.graph_handler.handle_pdi_interaction(interaction=interaction, song=song)

    @graph_notes_group.command(name="lifts", description="Graph the lift counts for a specific song.")
    @app_commands.describe(song = "A search query: an artist, song name, or shortname.")
    async def graph_note_counts_command(self, interaction: discord.Interaction, song:str):
        await self.graph_handler.handle_lift_interaction(interaction=interaction, song=song)

    @graph_group.command(name="nps", description="Graph the NPS (Notes per second) for a specific song, instrument, and difficulty.")
    @app_commands.describe(song = "A search query: an artist, song name, or shortname.")
    @app_commands.describe(instrument = "The instrument to view the NPS of.")
    @app_commands.describe(difficulty = "The difficulty to view the NPS for.")
    async def graph_nps_command(self, interaction: discord.Interaction, song:str, instrument : constants.Instruments, difficulty : constants.Difficulties = constants.Difficulties.Expert):
        await self.graph_handler.handle_nps_interaction(interaction=interaction, song=song, instrument=instrument, difficulty=difficulty)

    @graph_group.command(name="lanes", description="Graph the number of notes for each lane in a specific song, instrument, and difficulty.")
    @app_commands.describe(song = "A search query: an artist, song name, or shortname.")
    @app_commands.describe(instrument = "The instrument to view the #notes of.")
    @app_commands.describe(difficulty = "The difficulty to view the #notes for.")
    async def graph_lanes_command(self, interaction: discord.Interaction, song:str, instrument : constants.Instruments, difficulty : constants.Difficulties = constants.Difficulties.Expert):
        await self.graph_handler.handle_lanes_interaction(interaction=interaction, song=song, instrument=instrument, difficulty=difficulty)