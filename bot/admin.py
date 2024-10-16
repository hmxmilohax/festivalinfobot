import asyncio
import logging
import discord
from discord import app_commands
from discord.ext import commands

from bot import config, constants
from bot.tracks import JamTrackHandler

class AdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Define the base 'admin' group command
    admin_group = app_commands.Group(name="admin", description="Admin commands", guild_only=True)

    async def set_channel_subscription(self, interaction: discord.Interaction, channel: discord.channel.TextChannel, remove: bool = False) -> bool:
        channel_list = [subscribed_channel for subscribed_channel in self.bot.config.channels if subscribed_channel.id == channel.id]
        channel_exists = len(channel_list) > 0

        if remove:
            # User ran /unsubscribe on a channel which isnt subscribed
            if not channel_exists:
                await interaction.response.send_message(f"The channel {channel.mention} is not subscribed.")
                return False
            # User ran /unsubscribe
            else:
                try:
                    for _channel in channel_list:
                        self.bot.config.channels.remove(_channel)
                except ValueError as e:
                    await interaction.response.send_message(f"The channel {channel.mention} could not be unsubscribed: {e}")
                    return False
        else:
            # User ran /subscribe on a channel which is already subscribed
            if channel_exists:
                for i, _channel in enumerate(channel_list):
                    if i > 0:
                        logging.warning(f'Found another channel for {channel.id}? Channel no. {i}')

                    channel_events = _channel.events
                    if len(channel_events) == len(config.JamTrackEvent.get_all_events()):
                        await interaction.response.send_message(f"The channel {channel.mention} is already subscribed to all Jam Track events.")
                    else:    
                        await interaction.response.send_message(f"The channel {channel.mention} is already subscribed to the events \"{'\", \"'.join([constants.EVENT_NAMES[event] for event in channel_events])}\".")
                return False
            # User ran /subscribe
            else:
                self.bot.config.channels.append(config.SubscriptionChannel(channel.id, config.JamTrackEvent.get_all_events(), []))

        try:
            self.bot.config.save_config()
        except Exception as e:
            await interaction.response.send_message(f"The bot's subscription list could not be updated to " + ("remove" if remove else "include") + f" {channel.mention}: {e}\n" + ("Unsubscription" if remove else "Subscription") + " cancelled.")
            return False
                
        return True

    async def check_permissions(self, interaction: discord.Interaction, channel: discord.channel.TextChannel) -> bool:
        # There are so many permissions we have to check for

        # View the channel
        if not channel.permissions_for(channel.guild.me).view_channel:
            await interaction.response.send_message(f'I can\'t view that channel! Please make sure I have the "View Channel" permission in that channel.')
            return False
        
        # Send messages in the channel
        if not channel.permissions_for(channel.guild.me).send_messages:
            await interaction.response.send_message(f'I can\'t send messages in that channel! Please make sure I have the "Send Messages" permission in {channel.mention}.')
            return False
        
        # If news channel, publish messages (Manage Messages permission!!!)
        if channel.is_news():
            if not channel.permissions_for(channel.guild.me).manage_messages:
                await interaction.response.send_message(f'I can\'t publish messages in that Announcement channel! Please make sure I have the "Manage Messages" permission in {channel.mention}.')
                return False
            
        # Possible, "Embed Links", "Attach Files?"

        return True

    @admin_group.command(name="subscribe", description="Subscribe a channel to Jam Track events")
    @app_commands.describe(channel = "The channel to send Jam Track events to.")
    @app_commands.checks.has_permissions(administrator=True)
    async def subscribe(self, interaction: discord.Interaction, channel: discord.channel.TextChannel):
        permission_result = await self.check_permissions(interaction=interaction, channel=channel)
        if not permission_result:
            return
        
        subscription_result = await self.set_channel_subscription(interaction=interaction, channel=channel, remove=False)
        if not subscription_result:
            return
        
        if interaction.channel.permissions_for(interaction.guild.me).add_reactions:
            await interaction.response.send_message(content=f"The channel {channel.mention} has been subscribed to all Jam Track events.\n*React with ✅ to send a test message.*")
            message = await interaction.original_response()  # Retrieve the message object for reactions
            await message.add_reaction("✅")

            def check(reaction, user):
                return (
                    user == interaction.user and
                    user.guild_permissions.administrator and
                    str(reaction.emoji) == "✅" and
                    reaction.message.id == message.id
                )

            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=30.0, check=check)
            except asyncio.TimeoutError:
                # await message.clear_reactions()
                await interaction.edit_original_response(content=f"The channel {channel.mention} has been subscribed to all Jam Track events.")
            else:
                await channel.send("This channel is now subscribed to Jam Track events.\n*This is a test message.*")
                # await message.clear_reactions() # Bot will throw 403 if it can't manage messages
                await interaction.edit_original_response(content=f"The channel {channel.mention} has been subscribed to all Jam Track events.\n*Test message sent successfully.*")
        else:
            await interaction.response.send_message(content=f"The channel {channel.mention} has been subscribed to all Jam Track events.")

    @admin_group.command(name="unsubscribe", description="Unsubscribe a channel from Jam Track events")
    @app_commands.describe(channel = "The channel to stop sending Jam Track events to.")
    @app_commands.checks.has_permissions(administrator=True)
    async def unsubscribe(self, interaction: discord.Interaction, channel: discord.channel.TextChannel):
        permission_result = await self.check_permissions(interaction=interaction, channel=channel)
        if not permission_result:
            return
        
        subscription_result = await self.set_channel_subscription(interaction=interaction, channel=channel, remove=True)
        if not subscription_result:
            return
        
        await interaction.response.send_message(f"The channel {channel.mention} has been unsubscribed from all Jam Track events.")

    @admin_group.command(name="add_event", description="Add a Jam Track event to a channel")
    @app_commands.describe(channel = "The channel to add a Jam Track event to")
    @app_commands.describe(event = "The event to add")
    @app_commands.checks.has_permissions(administrator=True)
    async def add_event(self, interaction: discord.Interaction, channel: discord.channel.TextChannel, event: config.JamTrackEvent):
        channel_list = [subscribed_channel for subscribed_channel in self.bot.config.channels if subscribed_channel.id == channel.id]
        channel_exists = len(channel_list) > 0
        chosen_event = config.JamTrackEvent[str(event).replace('JamTrackEvent.', '')].value

        if not channel_exists:
            # Only check for permissions if the channel is added
            permission_result = await self.check_permissions(interaction=interaction, channel=channel)
            if not permission_result:
                return

            self.bot.config.channels.append(config.SubscriptionChannel(channel.id, [chosen_event], []))
        else:
            for i, _channel in enumerate(channel_list):
                if i > 0:
                    logging.warning(f'Found another channel for {channel.id}? Channel no. {i}')

                subscribed_events = self.bot.config.channels[self.bot.config.channels.index(_channel)].events
                if chosen_event in subscribed_events:
                    await interaction.response.send_message(f'The channel {channel.mention} is already subscribed to the event "{constants.EVENT_NAMES[chosen_event]}".')
                    return
                else:
                    self.bot.config.channels[self.bot.config.channels.index(_channel)].events.append(chosen_event)

        try:
            self.bot.config.save_config()
        except Exception as e:
            await interaction.response.send_message(f"The bot's subscription list could not be updated to add the event \"{constants.EVENT_NAMES[chosen_event]}\" to the channel {channel.mention}: {e}\nEvent subscription cancelled.")
            return
        
        await interaction.response.send_message(f'The channel {channel.mention} has been subscribed to the event "{constants.EVENT_NAMES[chosen_event]}".')

    @admin_group.command(name="remove_event", description="Remove a Jam Track event from a channel")
    @app_commands.describe(channel = "The channel to remove a Jam Track event from")
    @app_commands.describe(event = "The event to remove")
    @app_commands.checks.has_permissions(administrator=True)
    async def remove_event(self, interaction: discord.Interaction, channel: discord.channel.TextChannel, event: config.JamTrackEvent):
        channel_list = [subscribed_channel for subscribed_channel in self.bot.config.channels if subscribed_channel.id == channel.id]
        channel_exists = len(channel_list) > 0
        chosen_event = config.JamTrackEvent[str(event).replace('JamTrackEvent.', '')].value

        if not channel_exists:
            await interaction.response.send_message(f'The channel {channel.mention} is not subscribed to any events.')
            return
        else:
            for i, _channel in enumerate(channel_list):
                if i > 0:
                    logging.warning(f'Found another channel for {channel.id}? Channel no. {i}')

                subscribed_events = self.bot.config.channels[self.bot.config.channels.index(_channel)].events

                if chosen_event in subscribed_events:
                    try:
                        self.bot.config.channels[self.bot.config.channels.index(_channel)].events.remove(chosen_event)

                        # Remove the channel from the subscription list if it isnt subscribed to any events
                        if len(self.bot.config.channels[self.bot.config.channels.index(_channel)].events) < 1:
                            self.bot.config.channels.remove(_channel)
                            self.bot.config.save_config()
                            await interaction.response.send_message(f"The channel {channel.mention} has been removed from the subscription list because it is no longer subscribed to any events.")
                            return

                    except Exception as e:
                        await interaction.response.send_message(f"The bot's subscription list could not be updated to remove the event \"{constants.EVENT_NAMES[chosen_event]}\" from the channel {channel.mention}: {e}\nEvent unsubscription cancelled.")
                        return
                else:
                    await interaction.response.send_message(f'The channel {channel.mention} is not subscribed to the event "{constants.EVENT_NAMES[chosen_event]}".')
                    return

        try:
            self.bot.config.save_config()
        except Exception as e:
            await interaction.response.send_message(f"The bot's subscription list could not be updated to remove the event \"{constants.EVENT_NAMES[chosen_event]}\" from the channel {channel.mention}: {e}\nEvent unsubscription cancelled.")
            return
        
        await interaction.response.send_message(f'The channel {channel.mention} has been unsubscribed from the event "{constants.EVENT_NAMES[chosen_event]}".')

    @admin_group.command(name="add_role", description="Add a role ping to a channel's subscription messages")
    @app_commands.describe(channel = "The channel to add a role ping to")
    @app_commands.describe(role = "The role to add a ping for")
    @app_commands.checks.has_permissions(administrator=True)
    async def add_role(self, interaction: discord.Interaction, channel: discord.channel.TextChannel, role: discord.Role):
        channel_list = [subscribed_channel for subscribed_channel in self.bot.config.channels if subscribed_channel.id == channel.id]
        channel_exists = len(channel_list) > 0

        if not channel_exists:
            await interaction.response.send_message(f'The channel {channel.mention} is not subscribed to any events.')
            return
        else:
            for i, _channel in enumerate(channel_list):
                if i > 0:
                    logging.warning(f'Found another channel for {channel.id} Channel no. {i}')

                channel_roles = self.bot.config.channels[self.bot.config.channels.index(_channel)].roles

                if role.id in channel_roles:
                    await interaction.response.send_message(f"This role ping is already assigned to the channel {channel.mention}.")
                    return
                else:
                    self.bot.config.channels[self.bot.config.channels.index(_channel)].roles.append(role.id)

        try:
            self.bot.config.save_config()
        except Exception as e:
            await interaction.response.send_message(f"The bot's subscription list could not be updated to add this role ping to the channel {channel.mention}: {e}\nRole ping addition cancelled.")
            return
        
        await interaction.response.send_message(f'The channel {channel.mention} has been assigned to ping this role on future Jam Track events.')

    @admin_group.command(name="remove_role", description="Remove a role ping from a channel's subscription messages")
    @app_commands.describe(channel = "The channel to remove a role ping from")
    @app_commands.describe(role = "The role to remove a ping for")
    @app_commands.checks.has_permissions(administrator=True)
    async def remove_role(self, interaction: discord.Interaction, channel: discord.channel.TextChannel, role: discord.Role):
        channel_list = [subscribed_channel for subscribed_channel in self.bot.config.channels if subscribed_channel.id == channel.id]
        channel_exists = len(channel_list) > 0

        if not channel_exists:
            await interaction.response.send_message(f'The channel {channel.mention} is not subscribed to any events.')
            return
        else:
            for i, _channel in enumerate(channel_list):
                if i > 0:
                    logging.warning(f'Found another channel for {channel.id}? Channel no. {i}')

                channel_roles = self.bot.config.channels[self.bot.config.channels.index(_channel)].roles

                if role.id in channel_roles:
                    try:
                        self.bot.config.channels[self.bot.config.channels.index(_channel)].roles.remove(role.id)
                    except ValueError as e:
                        await interaction.response.send_message(f"This role ping could not be removed from the channel {channel.mention}: {e}\nRole ping removal cancelled.")
                        return
                else:
                    await interaction.response.send_message(f"This role ping is not assigned to the channel {channel.mention}.")
                    return

        try:
            self.bot.config.save_config()
        except Exception as e:
            await interaction.response.send_message(f"The bot's subscription list could not be updated to remove this role ping from the channel {channel.mention}: {e}\nRole ping removal cancelled.")
            return
        
        await interaction.response.send_message(f'The channel {channel.mention} has been assigned to not ping this role on future Jam Track events.')

    @admin_group.command(name="subscriptions", description="View the subscriptions in this guild")
    @app_commands.checks.has_permissions(administrator=True)
    async def subscriptions(self, interaction: discord.Interaction):
        embed = discord.Embed(title=f"Subscriptions for **{interaction.guild.name}**", color=0x8927A1)

        total_channels = 0

        for channel_to_search in self.bot.config.channels:
            channel = self.bot.get_channel(channel_to_search.id)

            if channel:
                if channel.guild.id == interaction.guild.id:
                    total_channels += 1
                    events_content = "**Events:** " + ", ".join([constants.EVENT_NAMES[event] for event in channel_to_search.events])
                    role_content = ""
                    if channel_to_search.roles:
                        if len(channel_to_search.roles) > 0:
                            role_content = "**Roles:** " + ", ".join([f'<@&{role.id}>' for role in channel_to_search.roles])
                    embed.add_field(name=f"{channel.mention}", value=f"{events_content}\n{role_content}", inline=False)

        if total_channels < 1:
            embed.add_field(name="There are no subscriptions in this guild.", value="")
        else:
            embed.description = f'{total_channels} found'

        await interaction.response.send_message(embed=embed)

    async def on_subscription_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(interaction.channel, discord.DMChannel) and interaction.command.guild_only: # just in case but the command wont show up in dms anyway
            await interaction.response.send_message(content="You cannot run this command in DMs.")
            return
        if isinstance(error, app_commands.errors.MissingPermissions):
            await interaction.response.send_message(content="You do not have the necessary permissions to run this command. Only administrators can use this command.", ephemeral=True)
            return

    subscribe.on_error = on_subscription_error
    unsubscribe.on_error = on_subscription_error
    add_event.on_error = on_subscription_error
    remove_event.on_error = on_subscription_error
    add_role.on_error = on_subscription_error
    remove_role.on_error = on_subscription_error
    subscriptions.on_error = on_subscription_error

# jnacks personal commands
class TestCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Define the base 'admin' group command
    test_group = app_commands.Group(name="test", description="Test commands")

    @test_group.command(name="notifs", description="Only the bot host can run this command. Tests subscriber notifications.")
    async def test_command(self, interaction: discord.Interaction):
        if interaction.user.id != 960524988824313876:
            await interaction.response.send_message(content="You are not authorized to run this command.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        # Send a test message to all subscribed channels
        for channel_to_search in self.bot.config.channels:
            channel = self.bot.get_channel(channel_to_search.id)
            if channel:
                try:
                    await channel.send(content="This is a test notification to ensure the bot is properly notifiying all subscribed channels and users.\nThis is only a test.\nApologies for the disruption. - jnack")
                except Exception as e:
                    logging.error(f"Error sending message to channel {channel.id}", exc_info=e)
            else:
                logging.error(f"Channel with ID {channel_to_search.id} not found.")

        # Send a test message to all subscribed users
        for user_to_send in self.bot.config.users:
            user = self.bot.get_user(user_to_send.id)
            if user:
                try:
                    await user.send(content="This is a test notification to ensure the bot is properly notifiying all subscribed channels and users.\nThis is only a test.\nApologies for the disruption. - jnack")
                except Exception as e:
                    logging.error(f"Error sending message to user {user.id}", exc_info=e)
            else:
                logging.error(f"User with ID {user_to_send.id} not found.")

        await interaction.followup.send(content="Test messages have been sent.", ephemeral=True)

    @test_group.command(name="logs", description="Only the bot host can run this command. Tests logging functions and levels.")
    async def test_command(self, interaction: discord.Interaction):
        if interaction.user.id != 960524988824313876:
            await interaction.response.send_message(content="You are not authorised to run this command.")
            return
        
        logging.debug("[festival tracker] This is a DEBUG message.")
        logging.info("[festival tracker] This is an INFO message.")
        logging.warning("[festival tracker] This is a WARNING message.")
        logging.error("[festival tracker] This is an ERROR message.", exc_info=Exception("This is a test exception."))
        logging.critical("[festival tracker] This is a CRITICAL message." , exc_info=Exception("This is a test exception."))

        logging.getLogger('discord').debug('[discord] This is a DEBUG message.')
        logging.getLogger('discord').info('[discord] This is an INFO message.')
        logging.getLogger('discord').warning('[discord] This is a WARNING message.')
        logging.getLogger('discord').error('[discord] This is an ERROR message.', exc_info=Exception("This is a test exception."))
        logging.getLogger('discord').critical('[discord] This is a CRITICAL message.', exc_info=Exception("This is a test exception."))

        await interaction.response.send_message(content="Successfully tested logging functions and levels.")
        
    @test_group.command(name="full_history", description="Only the bot host can run this command. Runs history for every known song.")
    async def full_history(self, interaction: discord.Interaction):
        if not self.bot.CHART_COMPARING_ALLOWED or not self.bot.DECRYPTION_ALLOWED:
            await interaction.response.send_message(content="This command is not enabled in this bot.", ephemeral=True)
            return

        if interaction.user.id != 960524988824313876:
            await interaction.response.send_message(content="You are not authorised to run this command.")
            return
        
        track_list = JamTrackHandler().get_jam_tracks()
        if not track_list:
            await interaction.response.send_message(content="Could not get tracks.", ephemeral=True)
            return
        
        await interaction.response.defer()

        # Loop through all the tracks and run the history command for each
        for track in track_list:
            song_name = track['track']['tt']
            artist_name = track['track']['an']

            try:
                # Call the history command with the song's title
                await self.bot.history_handler.handle_interaction(interaction=interaction, song=song_name, channel=interaction.channel, use_channel=True)

            except Exception as e:
                await interaction.channel.send(content=f"Failed to process the history for **{song_name}**. Error: {e}")
                logging.error("Unable to process the history", exc_info=e)
                # Continue even if one song fails

        # Final message indicating the full history run is complete
        await interaction.channel.send(content="Full history run completed.")
