import asyncio
import discord.ext.tasks as tasks
import io
import logging
from typing import List, Literal, Union
import discord
from discord import app_commands
from discord.ext import commands
import requests

from bot import config, constants
from bot.groups.oauthmanager import OAuthManager
from bot.tracks import JamTrackHandler
from bot.leaderboard import LeaderboardPaginatorView, BandLeaderboardView, AllTimeLeaderboardView

class SubscriptionManager():
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def handle_interaction(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        message = await interaction.original_response()
        view = SubscriptionsView(self.bot)
        await view.reply_to_initial(message)

class SubscriptionsView(discord.ui.View):
    def __init__(self, bot: commands.Bot, timeout=30):
        super().__init__(timeout=timeout)

        self.message: discord.Message = None
        self.bot: commands.Bot = bot

        self.add_item(SubscriptionTypesDropdown())

    async def reply_to_initial(self, message: discord.Message):
        embed = discord.Embed(title=f"Subscription Manager", description="Manage your subscriptions to Festival Tracker.", color=0x8927A1)
        embed.add_field(name="", value="To continue, please select the type of subscription to manage.")
        await message.edit(embed=embed, view=self)
        self.message = message

class SubscriptionTypesDropdown(discord.ui.Select):
    def __init__(self):

        # Set the options that will be presented inside the dropdown
        options = [
            discord.SelectOption(label='Server Subscriptions', description='Manage the subscriptions in this server'),
            discord.SelectOption(label='My Subscription', description='Manage your subscription')
        ]

        super().__init__(placeholder='Select the subscription type...', min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        # Use the interaction object to send a response message containing
        # the user's favourite colour or choice. The self object refers to the
        # Select object, and the values attribute gets a list of the user's
        # selected options. We only want the first one.
        view: SubscriptionsView = self.view
        new_view = ServerSubscriptionsView(view.bot)
        await interaction.response.defer()
        await new_view.reply_to_initial(view.message)
        # await interaction.response.defer()

class ServerSubscriptionsView(discord.ui.View):
    def __init__(self, bot: commands.Bot, timeout=30):
        super().__init__(timeout=timeout)

        self.message: discord.Message = None
        self.bot: commands.Bot = bot

        async def on_back_button(interaction: discord.Interaction):
            view = SubscriptionsView(self.bot)
            await interaction.response.defer()
            await view.reply_to_initial(self.message)

        self.add_item(constants.StandaloneSimpleBtn(label="Back", style=discord.ButtonStyle.secondary, emoji=constants.PREVIOUS_EMOJI, on_press=on_back_button))

    async def reply_to_initial(self, message: discord.Message):
        if not message.guild:
            await message.edit(embed=constants.common_error_embed("You are not in a server!"), view=self)
            return

        embed = discord.Embed(title=f"Server Subscriptions", description=f"Manage the subscriptions for {message.guild.name}", color=0x8927A1)

        channels_subscribed: List[config.SubscriptionChannel] = await self.bot.config._guild_channels(guild=message.guild)
        channel_text = ""

        for sub_channel in channels_subscribed:
            channel = self.bot.get_channel(sub_channel.id)
            channel_text += f"<#{channel.id}>\n"
        
        if len(channels_subscribed) == 0:
            channel_text = "There are no channels subscribed to Festival Tracker in this server!"

        embed.add_field(name="Channels", value=channel_text, inline=False)
        embed.add_field(name="Manage Channel", value="Select the channel from the dropdown to manage it", inline=False)
        embed.add_field(name="Add New", value="Click on \"Add New\" to subscribe a channel", inline=False)

        async def on_add_btn(interaction: discord.Interaction):
            view = CreateServerSubscriptionView(self.bot)
            await interaction.response.defer()
            await view.reply_to_initial(self.message)

        self.add_item(constants.StandaloneSimpleBtn(label="Add New", style=discord.ButtonStyle.secondary, on_press=on_add_btn))
        self.add_item(constants.StandaloneSimpleBtn(label="Unsubscribe Server", style=discord.ButtonStyle.danger, on_press=None))
        self.add_item(GuildManageableSubscriptionChannelsDropdown(self.bot, channels_subscribed))
        await message.edit(embed=embed, view=self)
        self.message = message

class GuildManageableSubscriptionChannelsDropdown(discord.ui.Select):
    def __init__(self, bot: commands.Bot, subscribed_channels: List[config.SubscriptionChannel] = []):

        self.bot = bot

        # Set the options that will be presented inside the dropdown
        options = [discord.SelectOption(label=f'#{self.bot.get_channel(ch.id).name}', value=str(ch.id)) for ch in subscribed_channels]
        super().__init__(placeholder='Manage a channel...', min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        # Use the interaction object to send a response message containing
        # the user's favourite colour or choice. The self object refers to the
        # Select object, and the values attribute gets a list of the user's
        # selected options. We only want the first one.
        view: SubscriptionsView = self.view
        new_view = ServerSubscriptionsView(view.bot)
        await interaction.response.defer()
        await new_view.reply_to_initial(view.message)
        # await interaction.response.defer()

class CreateServerSubscriptionView(discord.ui.View):
    def __init__(self, bot: commands.Bot, timeout=30):
        super().__init__(timeout=timeout)

        self.message: discord.Message = None
        self.bot: commands.Bot = bot

        async def on_back_button(interaction: discord.Interaction):
            view = ServerSubscriptionsView(self.bot)
            await interaction.response.defer()
            await view.reply_to_initial(self.message)

        self.add_item(constants.StandaloneSimpleBtn(label="Back", style=discord.ButtonStyle.secondary, emoji=constants.PREVIOUS_EMOJI, on_press=on_back_button))
    
    async def reply_to_initial(self, message: discord.Message):
        embed = discord.Embed(title=f"Server Subscriptions", description=f"Subscribe a channel", color=0x8927A1)

        channels_subscribed: List[config.SubscriptionChannel] = await self.bot.config._guild_channels(guild=message.guild)

        embed.add_field(name="Select Channel", value="Please select a channel from the dropdown to continue.", inline=False)
        embed.add_field(name="Required Permissions", value="- View Channel\n- Send Messages\n- Embed Links\n- Attach Files", inline=False)
        embed.add_field(name="Supported Channels", value="Text Channels, Announcement Channels", inline=False)

        self.add_item(ServerSubscribableChannelsDropdown(self.bot, channels_subscribed, message.guild))
        await message.edit(embed=embed, view=self)
        self.message = message

class ServerSubscribableChannelsDropdown(discord.ui.Select):
    def __init__(self, bot: commands.Bot, subscribed_channels: List[config.SubscriptionChannel] = [], guild: discord.Guild = None):

        self.bot = bot

        candidates: list[discord.TextChannel] = []

        for channel in guild.channels:
            if ((channel.type == discord.ChannelType.text) or (channel.type == discord.ChannelType.news)) and channel.permissions_for(guild.me).send_messages and channel.permissions_for(guild.me).embed_links and channel.permissions_for(guild.me).attach_files and channel.permissions_for(guild.me).view_channel:
                candidates.append(channel)

        for channel in subscribed_channels:
            if channel.id in [ch.id for ch in candidates]:
                candidates.remove(discord.utils.find(lambda ch: ch.id == channel.id, candidates))

        # Set the options that will be presented inside the dropdown
        options = [discord.SelectOption(label=f'#{ch.name}', value=str(ch.id)) for ch in candidates]
        super().__init__(placeholder='Select channel...', min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        # Use the interaction object to send a response message containing
        # the user's favourite colour or choice. The self object refers to the
        # Select object, and the values attribute gets a list of the user's
        # selected options. We only want the first one.
        view: SubscriptionsView = self.view
        new_view = ServerSubscriptionsView(view.bot)
        await interaction.response.defer()
        await new_view.reply_to_initial(view.message)
        # await interaction.response.defer()

    