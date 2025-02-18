import logging
from discord import app_commands
import discord
from discord.ext import commands

from bot import config, constants
from bot.linking import AccountLinking

class ProfileCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config: config.Config = bot.config

    profile_group = app_commands.Group(name="profile", description="Profile commands", guild_only=False, allowed_contexts=discord.app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True), allowed_installs=discord.app_commands.AppInstallationType(guild=True, user=True))

    @profile_group.command(name="view", description="View your profile")
    async def privacy_settings(self, interaction: discord.Interaction):
        pass

    @profile_group.command(name="privacy", description="View and edit your privacy settings")
    async def privacy_settings(self, interaction: discord.Interaction):
        link_handler: AccountLinking = self.bot.link_handler
        await link_handler.profile_privacy_menu_interaction(interaction)