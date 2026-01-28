import asyncio
import discord.ext.tasks as tasks
import io
import logging
from typing import List, Literal, Union
import discord
from discord import app_commands
from discord.ext import commands
import requests

from bot import constants, database
from bot.tools.oauthmanager import OAuthManager
from bot.views.suggestions import SuggestionModal
from bot.tracks import JamTrackHandler

class SubscriptionManager():
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def handle_interaction(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        message = await interaction.original_response()

        if not self.bot.is_ready:
            await interaction.edit_original_response(embed=constants.common_error_embed("Festival Tracker is not ready yet. Please try again in a moment."))
            return

        view = SubscriptionsView(self.bot)
        await view.reply_to_initial(message)

class SubscriptionsView(discord.ui.View):
    def __init__(self, bot: commands.Bot, timeout=180):
        super().__init__(timeout=timeout)

        self.message: discord.Message = None
        self.bot: commands.Bot = bot

        self.add_item(SubscriptionTypesDropdown())

        async def problemsf(interaction: discord.Interaction):
            await interaction.response.send_modal(SuggestionModal(self.bot))

        problems = discord.ui.Button(label="Problems with Subscriptions / Concerns?", emoji=constants.ERROR_EMOJI, style=discord.ButtonStyle.secondary, row=1)
        problems.callback = problemsf
        self.add_item(problems)

    async def reply_to_initial(self, message: discord.Message):
        embed = discord.Embed(title=f"Subscription Manager", description="Manage your subscriptions to Festival Tracker.", colour=constants.ACCENT_COLOUR)
        embed.add_field(name="", value="To continue, please select the type of subscription to manage.")
        await message.edit(embed=embed, view=self)
        self.message = message

class SubscriptionTypesDropdown(discord.ui.Select):
    def __init__(self):

        # Set the options that will be presented inside the dropdown
        options = [
            discord.SelectOption(label='Server Subscriptions', description='Manage the subscriptions in this server', value='server'),
            discord.SelectOption(label='My Subscription', description='Manage your subscription')
        ]

        super().__init__(placeholder='Select the subscription type...', min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        # Use the interaction object to send a response message containing
        # the user's favourite colour or choice. The self object refers to the
        # Select object, and the values attribute gets a list of the user's
        # selected options. We only want the first one.
        view: SubscriptionsView = self.view
        message = view.message
        if self.values[0] == "server":
            if not message.guild:
                await interaction.response.send_message(embed=constants.common_error_embed("You are not in a server!"), ephemeral=True)
                return
            
            member = await message.guild.fetch_member(interaction.user.id)
            if not member:
                await interaction.response.send_message(embed=constants.common_error_embed("We are unable to check your permissions in this server. Due to this, you are currently unable to manage Server Subscriptions."), ephemeral=True)
                return
            
            doesnt_have_admin = not member.guild_permissions.administrator
            isnt_bot_owner = not (member.id in constants.BOT_OWNERS)

            if doesnt_have_admin and isnt_bot_owner:
                await interaction.response.send_message(embed=constants.common_error_embed("You do not have permission to manage subscriptions in this server! You need Administrator permissions."), ephemeral=True)
                return

            await interaction.response.defer()
            new_view = ServerSubscriptionsView(view.bot)
            await new_view.reply_to_initial(message)
        else:
            await interaction.response.defer()
            new_view = UserSubscriptionsView(view.bot)
            await new_view.reply_to_initial(message, interaction.user)

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
        embed = discord.Embed(title=f"Server Subscriptions", description=f"Manage the subscriptions for {message.guild.name}", colour=constants.ACCENT_COLOUR)

        channels_subscribed: List[database.SubscriptionChannel] = await self.bot.config._guild_channels(guild=message.guild)
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

        async def on_unsubscribe_btn(interaction: discord.Interaction):
            await interaction.response.defer()

            await self.bot.get_channel(constants.LOG_CHANNEL).send(f'{constants.tz()} Guild {interaction.guild.id} unsubscribed')

            await self.bot.config._guild_remove(interaction.guild)
            new_view = ServerSubscriptionsView(self.bot)
            await new_view.reply_to_initial(self.message)

        self.add_item(constants.StandaloneSimpleBtn(label="Add New", style=discord.ButtonStyle.secondary, on_press=on_add_btn))
        self.add_item(constants.StandaloneSimpleBtn(label="Unsubscribe Server", style=discord.ButtonStyle.danger, on_press=on_unsubscribe_btn))
        
        if len(channels_subscribed) > 0:
            self.add_item(GuildManageableSubscriptionChannelsDropdown(self.bot, channels_subscribed))

        await message.edit(embed=embed, view=self)
        self.message = message

class UserSubscriptionsView(discord.ui.View):
    def __init__(self, bot: commands.Bot, timeout=30):
        super().__init__(timeout=timeout)

        self.message: discord.Message = None
        self.bot: commands.Bot = bot

        async def on_back_button(interaction: discord.Interaction):
            view = SubscriptionsView(self.bot)
            await interaction.response.defer()
            await view.reply_to_initial(self.message)

        self.add_item(constants.StandaloneSimpleBtn(label="Back", style=discord.ButtonStyle.secondary, emoji=constants.PREVIOUS_EMOJI, on_press=on_back_button))

    async def reply_to_initial(self, message: discord.Message, user: discord.User):
        embed = discord.Embed(title=f"My Subscription", description=f"Manage your subscription.", colour=constants.ACCENT_COLOUR)

        embed.add_field(name="Managing", value="Select or deselect Jam Track events to be subscribed to.", inline=False)
        embed.add_field(name="Information", value="You must share at least one (1) mutual server with Festival Tracker to receive subscription messages.", inline=False)

        sub_user: database.SubscriptionUser = await self.bot.config._user(user)
        self.add_item(UserSubscriptionTypesDropdown(self.bot, message, sub_user))

        await message.edit(embed=embed, view=self)
        self.message = message

class UserSubscriptionTypesDropdown(discord.ui.Select):
    def __init__(self, bot: commands.Bot, message: discord.Message, sub_user: database.SubscriptionUser):
        self.bot = bot
        self.message = message
        self.sub_user = sub_user

        all_events = database.JamTrackEvents.get_all_events()

        # Set the options that will be presented inside the dropdown
        options = [
            discord.SelectOption(label=event.value.english, description=event.value.desc, value=event.value.id, default=False) for event in all_events
        ]

        if sub_user:
            for option in options:
                if option.value in sub_user.events:
                    option.default = True

        super().__init__(placeholder='Select subscription events...', min_values=0, max_values=len(options), options=options)

    async def callback(self, interaction: discord.Interaction):
        event_types = self.values
        await self.bot.config._user_edit_events(interaction.user, events=event_types)

        text = '[placeholder]'
        if not self.sub_user:
            await self.bot.get_channel(constants.LOG_CHANNEL).send(f'{constants.tz()} User {interaction.user.id} subscribed')
            text = 'You have been subscribed; changes saved successfully'
        elif len(event_types) == 0:
            await self.bot.get_channel(constants.LOG_CHANNEL).send(f'{constants.tz()} User {interaction.user.id} unsubscribed')
            text = 'You have been unsubscribed; changes saved successfully'
        else:
            text = 'Changes saved successfully'

        await self.bot.get_channel(constants.LOG_CHANNEL).send(f'{constants.tz()} User {interaction.user.id} edited feeds to {event_types}')

        await interaction.response.send_message(embed=constants.common_success_embed(text), ephemeral=True)
        new_view = UserSubscriptionsView(self.bot)
        await new_view.reply_to_initial(self.message, interaction.user)

class GuildManageableSubscriptionChannelsDropdown(discord.ui.Select):
    def __init__(self, bot: commands.Bot, subscribed_channels: List[database.SubscriptionChannel] = []):

        self.bot = bot

        # Set the options that will be presented inside the dropdown
        options = [discord.SelectOption(label=f'#{self.bot.get_channel(ch.id).name}', value=str(ch.id)) for ch in subscribed_channels]
        super().__init__(placeholder='Manage a channel...', min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        channel_id = self.values[0]
        channel = self.bot.get_channel(int(channel_id))

        view: SubscriptionsView = self.view
        new_view = GuildManageChannelView(view.bot, channel)
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
        embed = discord.Embed(title=f"Server Subscriptions", description=f"Subscribe a channel", colour=constants.ACCENT_COLOUR)

        channels_subscribed: List[database.SubscriptionChannel] = await self.bot.config._guild_channels(guild=message.guild)

        embed.add_field(name="Select Channel", value="Please select a channel from the dropdown to continue.", inline=False)
        embed.add_field(name="Required Permissions", value="- View Channel\n- Send Messages\n- Embed Links\n- Attach Files", inline=False)
        embed.add_field(name="Supported Channels", value="Text Channels, Announcement Channels", inline=False)

        self.add_item(ServerSubscribableChannelsDropdown(self.bot, channels_subscribed, message.guild))
        await message.edit(embed=embed, view=self)
        self.message = message

class ServerSubscribableChannelsDropdown(discord.ui.Select):
    def __init__(self, bot: commands.Bot, subscribed_channels: List[database.SubscriptionChannel] = [], guild: discord.Guild = None):

        self.bot = bot

        candidates: list[discord.TextChannel] = []

        for channel in guild.channels:
            if ((channel.type == discord.ChannelType.text) or (channel.type == discord.ChannelType.news)) and channel.permissions_for(guild.me).send_messages and channel.permissions_for(guild.me).embed_links and channel.permissions_for(guild.me).attach_files and channel.permissions_for(guild.me).view_channel:
                candidates.append(channel)

        for channel in subscribed_channels:
            if channel.id in [ch.id for ch in candidates]:
                candidates.remove(discord.utils.find(lambda ch: ch.id == channel.id, candidates))

        is_more_than_25 = len(candidates) > 20
        candidates = candidates[:20]  # Discord only allows 25 options max

        # Set the options that will be presented inside the dropdown
        options = [discord.SelectOption(label=f'#{ch.name}', value=str(ch.id)) for ch in candidates]
        super().__init__(placeholder=f"Select channel... {'[Truncated to 20 max.]' if is_more_than_25 else ''}", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        channel_id = self.values[0]
        channel = self.bot.get_channel(int(channel_id))

        view: SubscriptionsView = self.view
        new_view = ChannelSetupView(view.bot, channel)
        await interaction.response.defer()
        await new_view.reply_to_initial(view.message)
        # await interaction.response.defer()

class SubscriptionEventTypesDropdown(discord.ui.Select):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        all_events = database.JamTrackEvents.get_all_events()

        # Set the options that will be presented inside the dropdown
        options = [
            discord.SelectOption(label=event.value.english, description=event.value.desc, value=event.value.id, default=(True if event.value.id == 'announcements' else False)) for event in all_events
        ]

        super().__init__(placeholder='Select subscription events...', min_values=1, max_values=len(options), options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()

class MentionableRolesDropdown(discord.ui.Select):
    def __init__(self, bot: commands.Bot, guild: discord.Guild):
        self.bot = bot

        allowed_roles = [role for role in guild.roles if role.mentionable and role.id != guild.id]
        if guild.me.guild_permissions.mention_everyone:
            allowed_roles = [role for role in guild.roles if role.id != guild.id]

        # Set the options that will be presented inside the dropdown

        options = [discord.SelectOption(label=f'@{role.name}', value=str(role.id)) for role in allowed_roles]
        super().__init__(placeholder='Select roles to mention...', min_values=0, max_values=len(options), options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()

class ChannelSetupView(discord.ui.View):
    def __init__(self, bot: commands.Bot, channel: discord.TextChannel, timeout=30):
        super().__init__(timeout=timeout)

        self.message: discord.Message = None
        self.bot: commands.Bot = bot
        self.channel: discord.TextChannel = channel

        self.subtypes_view = SubscriptionEventTypesDropdown(self.bot)
        self.roles_view = MentionableRolesDropdown(self.bot, channel.guild)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, emoji=constants.PREVIOUS_EMOJI)
    async def on_back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = CreateServerSubscriptionView(self.bot)
        await interaction.response.defer()
        await view.reply_to_initial(self.message)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary, emoji=constants.NEXT_EMOJI)
    async def on_next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        event_types = self.subtypes_view.values
        role_ids = self.roles_view.values
        
        if len(event_types) == 0:
            embed = constants.common_error_embed("You didn't select any events! \nThere is a Discord bug that if you don't mess with the dropdown before continuing, there will be nothing selected! Please deselect and reselect any event type to try to fix it.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            view = SubscriptionSetupConfirmationView(self.bot, self.channel, event_types, role_ids)
            await interaction.response.defer()
            await view.reply_to_initial(self.message)

    async def reply_to_initial(self, message: discord.Message):
        embed = discord.Embed(title=f"Server Subscriptions", description=f"Subscribe {self.channel.mention} to Festival Tracker", colour=constants.ACCENT_COLOUR)

        embed.add_field(name="Select subscription events", value="Select or unselect the subscription events you wish to configure for this subscription.", inline=False)
        embed.add_field(name="Select roles to mention", value="Select roles to mention on subscription messages.", inline=False)

        self.add_item(self.subtypes_view)
        self.add_item(self.roles_view)
        await message.edit(embed=embed, view=self)
        self.message = message

class SubscriptionSetupConfirmationView(discord.ui.View):
    def __init__(self, bot: commands.Bot, channel: discord.TextChannel, event_types: list[str], role_ids: list[str], timeout=30):
        super().__init__(timeout=timeout)

        self.message: discord.Message = None
        self.bot: commands.Bot = bot
        self.channel: discord.TextChannel = channel
        self.event_types: list[str] = event_types
        self.role_ids: list[str] = role_ids
    
    @discord.ui.button(label="Test", style=discord.ButtonStyle.secondary, emoji=constants.PREVIOUS_EMOJI)
    async def on_back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.channel.send("This channel is now subscribed to Festival Tracker.\n*This is a test message.*")
        button.disabled = True
        await interaction.response.defer()
        await self.message.edit(view=self)

    @discord.ui.button(label="Finish", style=discord.ButtonStyle.secondary, emoji=constants.NEXT_EMOJI)
    async def on_next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        view = ServerSubscriptionsView(self.bot)
        await view.reply_to_initial(self.message)

    async def reply_to_initial(self, message: discord.Message):
        await self.bot.get_channel(constants.LOG_CHANNEL).send(f'{constants.tz()} Channel {self.channel.id} subscribed')

        await self.bot.config._channel_add(self.channel, self.event_types, self.role_ids)
        embed = discord.Embed(title=f"Server Subscriptions", description=f"{self.channel.mention} has been subscribed successfully.", colour=constants.ACCENT_COLOUR)
        await message.edit(embed=embed, view=self)
        self.message = message

class GuildManageChannelView(discord.ui.View):
    def __init__(self, bot: commands.Bot, channel: discord.TextChannel, timeout=30):
        super().__init__(timeout=timeout)

        self.message: discord.Message = None
        self.bot: commands.Bot = bot
        self.channel: discord.TextChannel = channel

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, emoji=constants.PREVIOUS_EMOJI)
    async def on_next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        view = ServerSubscriptionsView(self.bot)
        await view.reply_to_initial(self.message)

    @discord.ui.button(label="Unsubscribe", style=discord.ButtonStyle.danger)
    async def on_unsubscribe_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.bot.get_channel(constants.LOG_CHANNEL).send(f'{constants.tz()} Channel {self.channel.id} unsubscribed')

        await self.bot.config._channel_remove(self.channel)
        view = ServerSubscriptionsView(self.bot)
        await interaction.response.defer()
        await view.reply_to_initial(self.message)

    async def reply_to_initial(self, message: discord.Message):
        self.message = message
        embed = discord.Embed(title=f"Server Subscriptions", description=f"Manage the subscription for {self.channel.mention}", colour=constants.ACCENT_COLOUR)
        channel_subscription: database.SubscriptionChannel = await self.bot.config._channel(self.channel)

        embed.add_field(name="Subscription types", value=", ".join(channel_subscription.events), inline=False)

        roles: list[discord.Role] = []
        for role_id in channel_subscription.roles:
            role = self.message.guild.get_role(role_id)
            if role:
                roles.append(role)

        embed.add_field(name="Roles to mention", value=", ".join([role.mention for role in roles]), inline=False)

        embed.add_field(name="How to", value="Use the dropdowns below to customize the subscription. Changes will automatically save.", inline=False)

        self.add_item(ChannelManageEventTypesSelect(self.bot, self.message, self.channel, channel_subscription))
        self.add_item(ChannelManageMentionableRolesSelect(self.bot, self.message, self.channel, channel_subscription))

        await message.edit(embed=embed, view=self)

class ChannelManageEventTypesSelect(discord.ui.Select):
    def __init__(self, bot: commands.Bot, message: discord.Message, channel: discord.TextChannel, sub_channel: database.SubscriptionObject):
        self.bot = bot
        self.message = message
        self.channel = channel

        all_events = database.JamTrackEvents.get_all_events()

        # Set the options that will be presented inside the dropdown
        valid_options = [
            discord.SelectOption(label=event.value.english, description=event.value.desc, value=event.value.id) for event in all_events
        ]

        for option in valid_options:
            if option.value in sub_channel.events:
                option.default = True

        super().__init__(placeholder='Select subscription events...', min_values=1, max_values=len(valid_options), options=valid_options)

    async def callback(self, interaction: discord.Interaction):
        event_types = self.values
        await self.bot.config._channel_edit_events(self.channel, events=event_types)

        await self.bot.get_channel(constants.LOG_CHANNEL).send(f'{constants.tz()} Channel {self.channel.id} edited feeds to {event_types}')

        await interaction.response.send_message(embed=constants.common_success_embed("Changes saved successfully."), ephemeral=True)
        new_view = GuildManageChannelView(self.bot, self.channel)
        await new_view.reply_to_initial(self.message)

class ChannelManageMentionableRolesSelect(discord.ui.Select):
    def __init__(self, bot: commands.Bot, message: discord.Message, channel: discord.TextChannel, sub_channel: database.SubscriptionChannel):
        self.bot = bot
        self.message = message
        self.channel = channel
        guild = message.guild

        allowed_roles = [{
            "id": role.id,
            "name": role.name,
            "default": False
        } for role in guild.roles if role.mentionable and role.id != guild.id]
        if guild.me.guild_permissions.mention_everyone:
            allowed_roles = [{
                "id": role.id,
                "name": role.name,
                "default": False
            } for role in guild.roles if role.id != guild.id]

        for role_id in sub_channel.roles:
            found_role = discord.utils.find(lambda r: r["id"] == role_id, allowed_roles)
            if found_role:
                found_role["default"] = True
            else:
                if len(role_id) == 0:
                    role_id = 'invalid'

                allowed_roles.append({
                    "id": role_id,
                    "name": f"Unknown Role {role_id}",
                    "default": True
                })

        # Set the options that will be presented inside the dropdown

        options = [discord.SelectOption(label=f'@{role["name"]}', value=str(role["id"]), default=role["default"]) for role in allowed_roles]
        if len(options) == 0:
            options = [discord.SelectOption(label='No mentionable roles', value='none', default=True, description="I can't mention any roles in your server.")]
        if len(options) > 20:
            options = [discord.SelectOption(label='Too many roles', value='none', default=True, description="Your server has too many roles.")]

        super().__init__(placeholder='Select roles to mention...', min_values=0, max_values=len(options), options=options)

    async def callback(self, interaction: discord.Interaction):
        role_ids = self.values

        if 'none' in role_ids:
            await interaction.response.send_message(embed=constants.common_error_embed("Changes not saved"), ephemeral=True)
            return
        
        role_ids = [role_id for role_id in role_ids if len(role_id) > 0]
        role_ids = [role_id for role_id in role_ids if role_id != 'invalid']

        objects = [discord.Object(id=int(role_id)) for role_id in role_ids]
        await self.bot.config._channel_edit_roles(self.channel, roles=objects)

        await interaction.response.send_message(embed=constants.common_success_embed("Changes saved successfully."), ephemeral=True)
        new_view = GuildManageChannelView(self.bot, self.channel)
        await new_view.reply_to_initial(self.message)
