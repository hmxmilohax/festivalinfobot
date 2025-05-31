import logging
from discord import app_commands
import discord
from discord.ext import commands

from bot import config, constants
from bot.history import HistoryHandler

class HistoryCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config = bot.config
        self.history_handler = HistoryHandler()

    history_group = app_commands.Group(name="history", description="History commands", allowed_contexts=discord.app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True), allowed_installs=discord.app_commands.AppInstallationType(guild=True, user=True))

    @history_group.command(name="chart", description="View the chart history of a Jam Track.")
    @app_commands.describe(song = "A search query: an artist, song name, or shortname.")
    async def history_command(self, interaction: discord.Interaction, song:str):
        if not self.bot.CHART_COMPARING_ALLOWED or not self.bot.DECRYPTION_ALLOWED:
            await interaction.response.send_message(content="This command is not enabled in this bot.", ephemeral=True)
            return

        await self.history_handler.handle_interaction(interaction=interaction, song=song)

    @history_group.command(name="meta", description="View the metadata history of a Jam Track.")
    @app_commands.describe(song = "A search query: an artist, song name, or shortname.")
    async def metahistory_command(self, interaction: discord.Interaction, song:str):
        await self.history_handler.handle_metahistory_interaction(interaction=interaction, song=song)