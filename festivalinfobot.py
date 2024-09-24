import json
import time
from discord.ext import commands, tasks
import discord
from discord import app_commands
from configparser import ConfigParser

from bot import config, constants, embeds
from bot.config import Config
from bot.history import HistoryHandler, LoopCheckHandler
from bot.leaderboard import LeaderboardCommandHandler
from bot.path import PathCommandHandler
from bot.tracks import SearchCommandHandler, JamTrackHandler
from bot.helpers import DailyCommandHandler, ShopCommandHandler, TracklistHandler

class FestivalInfoBot(commands.Bot):
    async def on_ready(self):
        print(f'Logged in as {self.user.name}')

        print("Bot now active on:")
        print("Name".ljust(30), "ID")
        for guild in self.guilds:
            print(guild.name.ljust(30), guild.id)

        print("Syncing slash command tree...")
        await self.tree.sync()

        print("Setting activity...")
        # Set up the rich presence activity
        activity = discord.Activity(
            type=discord.ActivityType.playing, 
            name=f"/help"
        )

        # Apply the activity
        await self.change_presence(activity=activity, status=discord.Status.online)

        @tasks.loop(minutes=self.CHECK_FOR_SONGS_INTERVAL)
        async def check_for_new_songs():
            await self.check_handler.handle_task()
        if self.CHECK_FOR_NEW_SONGS:
            check_for_new_songs.start()

        print("Bot is now running!")

    def __init__(self):
        # Load configuration from config.ini
        config = ConfigParser()
        config.read('config.ini')

        def reload_config():
           self.config = Config(config_file="channels.json", reload_callback=reload_config) 

        self.config = Config(config_file="channels.json", reload_callback=reload_config)

        # Read the Discord bot token and channel IDs from the config file
        DISCORD_TOKEN = config.get('discord', 'token')

        # Bot configuration properties
        self.CHECK_FOR_SONGS_INTERVAL = config.getint('bot', 'check_new_songs_interval', fallback=7)
        self.CHECK_FOR_NEW_SONGS = config.getboolean('bot', 'check_for_new_songs', fallback=True)
        self.DECRYPTION_ALLOWED = config.getboolean('bot', 'decryption', fallback=True)
        self.PATHING_ALLOWED = config.getboolean('bot', 'pathing', fallback=True)
        self.CHART_COMPARING_ALLOWED = config.getboolean('bot', 'chart_comparing', fallback=True)

        self.start_time = time.time()

        # Set up Discord bot with necessary intents
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True  # Enable message content intent

        super().__init__(
            # Prefix must be set, but no commands are in the 'text command list' so it wont do anything
            command_prefix="!",
            help_command=None,
            intents=intents
        )

        self.lb_handler = LeaderboardCommandHandler(self)
        self.search_handler = SearchCommandHandler(self)
        self.daily_handler = DailyCommandHandler()
        self.shop_handler = ShopCommandHandler()
        self.tracklist_handler = TracklistHandler()
        self.path_handler = PathCommandHandler()
        self.history_handler = HistoryHandler()
        self.check_handler = LoopCheckHandler(self)

        self.setup_commands()
        self.setup_subscribe_commands()

        self.run(DISCORD_TOKEN)

    def setup_commands(self):
        @self.tree.command(name="search", description="Search a song.")
        @app_commands.describe(query = "A search query: an artist, song name, or shortname.")
        async def search_command(interaction: discord.Interaction, query:str):
            await self.search_handler.handle_interaction(interaction=interaction, query=query)

        @self.tree.command(name="daily", description="Display the tracks currently in daily rotation.")
        async def daily_command(interaction: discord.Interaction):
            await self.daily_handler.handle_interaction(interaction=interaction)

        @self.tree.command(name="tracklist", description="Browse the full list of available Jam Tracks.")
        async def tracklist_command(interaction: discord.Interaction):
            await self.tracklist_handler.handle_interaction(interaction=interaction)

        @self.tree.command(name="shop", description="Display the tracks currently in the shop.")
        async def shop_command(interaction: discord.Interaction):
            await self.shop_handler.handle_interaction(interaction=interaction)

        @self.tree.command(name="count", description="View the total number of Jam Tracks in Fortnite Festival.")
        async def count_command(interaction: discord.Interaction):
            track_list = JamTrackHandler().get_jam_tracks()
            if not track_list:
                await interaction.response.send_message(content="Could not get tracks.", ephemeral=True)
                return

            embed = discord.Embed(
                title="Total Available Songs",
                description=f"There are currently **{len(track_list)}** songs available in Fortnite Festival.",
                color=0x8927A1
            )

            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="leaderboard", description="View the leaderboard of a song.")
        @app_commands.describe(song = "A search query: an artist, song name, or shortname.")
        @app_commands.describe(instrument = "The instrument to view the leaderboard of.")
        @app_commands.describe(rank = "A number from 1 to 500 to view a specific entry in the leaderboard.")
        @app_commands.describe(username = "An Epic Games account's username. Not case-sensitive.")
        @app_commands.describe(account_id = "An Epic Games account ID.")
        async def leaderboard_command(interaction: discord.Interaction, song:str, instrument:constants.Instruments, rank: discord.app_commands.Range[int, 1, 500] = None, username:str = None, account_id:str = None):
            await self.lb_handler.handle_interaction(
                interaction,
                song=song,
                instrument=instrument,
                rank=rank,
                username=username,
                account_id=account_id
            )

        @self.tree.command(name="path", description="Generates an Overdrive path for a song using CHOpt.")
        @app_commands.describe(song = "A search query: an artist, song name, or shortname.")
        @app_commands.describe(instrument = "The instrument to view the path of.")
        @app_commands.describe(squeeze_percent = "Squeeze Percent value")
        @app_commands.describe(difficulty = "The difficulty to view the path for")
        async def path_command(interaction: discord.Interaction, song:str, instrument:constants.Instruments, squeeze_percent: discord.app_commands.Range[int, 0, 100] = 20, difficulty:constants.Difficulties = constants.Difficulties.Expert):
            if not self.PATHING_ALLOWED or not self.DECRYPTION_ALLOWED:
                await interaction.response.send_message(content="This command is not enabled in this bot.", ephemeral=True)
                return

            await self.path_handler.handle_interaction(
                interaction,
                song=song,
                instrument=instrument,
                squeeze_percent=squeeze_percent,
                difficulty=difficulty
            )

        @self.tree.command(name="history", description="View the history of a Jam Track.")
        @app_commands.describe(song = "A search query: an artist, song name, or shortname.")
        async def history_command(interaction: discord.Interaction, song:str):
            if not self.CHART_COMPARING_ALLOWED or not self.DECRYPTION_ALLOWED:
                await interaction.response.send_message(content="This command is not enabled in this bot.", ephemeral=True)
                return
    
            await self.history_handler.handle_interaction(interaction=interaction, song=song)

        @self.tree.command(name="fullhistory", description="Only jnack can run this")
        async def full_history(interaction: discord.Interaction):
            if not self.CHART_COMPARING_ALLOWED or not self.DECRYPTION_ALLOWED:
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
                    # Send a message indicating which song's history is being processed
                    await interaction.channel.send(content=f"Processing the history for **{song_name}** by *{artist_name}*...")

                    # Call the history command with the song's title
                    await self.history_handler.handle_interaction(interaction=interaction, song=song_name, channel=interaction.channel, use_channel=True)

                except Exception as e:
                    await interaction.channel.send(content=f"Failed to process the history for **{song_name}**. Error: {e}")
                    print(e)
                    # Continue even if one song fails

            # Final message indicating the full history run is complete
            await interaction.channel.send(content="Full history run completed.")

        @self.tree.command(name="metahistory", description="View the metadata history of a Jam Track.")
        @app_commands.describe(song = "A search query: an artist, song name, or shortname.")
        async def metahistory_command(interaction: discord.Interaction, song:str):
            await self.history_handler.handle_metahistory_interaction(interaction=interaction, song=song)

        @self.tree.command(name="stats", description="Displays Festival Tracker stats")
        async def bot_stats(interaction: discord.Interaction):
            # Get the number of servers the bot is in
            server_count = len(self.guilds)
            handler = embeds.StatsCommandEmbedHandler()
            
            # Get the bot uptime
            current_time = time.time()
            uptime_seconds = int(current_time - self.start_time)
            uptime = handler.format_uptime(uptime_seconds)
            # GitHub
            remote_url = handler.get_remote_url().replace('.git', '')
            latest_commit_hash, last_update = handler.fetch_latest_github_commit_hash()
            # Git (Local)
            dirtyness, branch_name, local_commit_hash = handler.get_local_commit_hash()
            # Compare Hashes
            commit_status = handler.compare_commit_hashes(local_commit_hash, latest_commit_hash)
            # Timestamps
            last_update_timestamp = handler.iso_to_unix_timestamp(last_update)
            if last_update_timestamp:
                last_update_formatted = f"<t:{last_update_timestamp}:R>"  # Use Discord's relative time format
            else:
                last_update_formatted = "Unknown"

            upstream_commit_url = remote_url + '/commit/' + latest_commit_hash
            local_commit_url = remote_url + '/commit/' + local_commit_hash
            # Create an embed to display the statistics
            embed = discord.Embed(
                title="Festival Tracker Statistics",
                description="",
                color=0x8927A1
            )
            embed.add_field(name="Servers", value=f"{server_count} servers", inline=False)
            embed.add_field(name="Uptime", value=f"{uptime}", inline=False)
            embed.add_field(name="Latest Upstream Update", value=f"{last_update_formatted} ([`{latest_commit_hash[:7]}`]({upstream_commit_url}))", inline=False)
            embed.add_field(name="Local Commit Info", value=f"`{branch_name}` [`{local_commit_hash[:7]}`]({local_commit_url}) ({commit_status})", inline=False)
            if len(dirtyness) > 0:
                embed.add_field(name="Local Changes", value=f"```{dirtyness}```", inline=False)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="help", description="Show the help message")
        @app_commands.describe(command = "The command to view help about.")
        async def help_command(interaction: discord.Interaction, command:str = None):
            if command:
                if self.tree.get_command(command):
                    found_command = self.tree.get_command(command)
                    usage = f"`/{found_command.qualified_name}`"
                    embed = discord.Embed(
                        title=f"Help with `/{found_command.name}`",
                        description=f"{found_command.description}\n**Usage**: {usage}",
                        color=0x8927A1
                    )
                else:
                    await interaction.response.send_message(content=f"No command found with the name \"{command}\"", ephemeral=True)
                    return
            else:
                embed = discord.Embed(
                    title="Festival Tracker Help",
                    description=f"A simple and powerful bot to check Fortnite Festival song data. [Source code](https://github.com/hmxmilohax/festivalinfobot)\nUse `/help <command>` to get more information on a specific command.",
                    color=0x8927A1
                )
                # Walk through all commands registered in self.tree
                for command in self.tree.get_commands():
                    # Add command to embed
                    embed.add_field(
                        name=f"`/{command.name}`",
                        value=command.description or "No description",
                        inline=False
                    )

            await interaction.response.send_message(embed=embed)

    def setup_subscribe_commands(self):
        # Setup all the subscription commands
        
        async def set_channel_subscription(interaction: discord.Interaction, channel: discord.channel.TextChannel, remove: bool = False) -> bool:
            channel_list = [subscribed_channel for subscribed_channel in self.config.channels if subscribed_channel.id == channel.id]
            channel_exists = len(channel_list) > 0

            event_names = {
                'added': "Jam Track Added",
                'removed': "Jam Track Removed",
                'modified': "Jam Track Modified"
            }

            if remove:
                # User ran /unsubscribe on a channel which isnt subscribed
                if not channel_exists:
                    await interaction.response.send_message(f"The channel <#{channel.id}> is not subscribed.")
                    return False
                # User ran /unsubscribe
                else:
                    try:
                        self.config.channels.remove(channel_list[0])
                    except ValueError as e:
                        await interaction.response.send_message(f"The channel <#{channel.id}> could not be unsubscribed: {e}")
                        return False
            else:
                # User ran /subscribe on a channel which is already subscribed
                if channel_exists:
                    channel_events = channel_list[0].events
                    if len(channel_events) == len(config.JamTrackEvent.get_all_events()):
                        await interaction.response.send_message(f"The channel <#{channel.id}> is already subscribed to all Jam Track events.")
                    else:    
                        await interaction.response.send_message(f"The channel <#{channel.id}> is already subscribed to the events \"{'\", \"'.join([event_names[event] for event in channel_events])}\".")
                    return False
                # User ran /subscribe
                else:
                    new_channel = config.SubscriptionChannel()
                    new_channel.id = channel.id
                    new_channel.roles = []
                    new_channel.events = config.JamTrackEvent.get_all_events()
                    self.config.channels.append(new_channel)

            try:
                self.config.save_config()
            except Exception as e:
                await interaction.response.send_message(f"The bot's subscription list could not be updated to " + ("remove" if remove else "include") + f" <#{channel.id}>: {e}\n" + ("Unsubscription" if remove else "Subscription") + " cancelled.")
                return False
                    
            return True

        async def check_permissions(interaction: discord.Interaction, channel: discord.channel.TextChannel) -> bool:
            # There are so many permissions we have to check for

            # View the channel
            if not channel.permissions_for(channel.guild.me).view_channel:
                await interaction.response.send_message(f'I can\'t view that channel! Please make sure I have the "View Channel" permission in that channel.')
                return False
            
            # Send messages in the channel
            if not channel.permissions_for(channel.guild.me).send_messages:
                await interaction.response.send_message(f'I can\'t send messages in that channel! Please make sure I have the "Send Messages" permission in <#{channel.id}>.')
                return False
            
            # If news channel, publish messages (Manage Messages permission!!!)
            if channel.is_news():
                if not channel.permissions_for(channel.guild.me).manage_messages:
                    await interaction.response.send_message(f'I can\'t publish messages in that Announcement channel! Please make sure I have the "Manage Messages" permission in <#{channel.id}>.')
                    return False
                
            # Possible, "Embed Links", "Attach Files?"

            return True

        @self.tree.command(name="subscribe", description="Subscribe a channel to Jam Track events")
        @app_commands.describe(channel = "The channel to send Jam Track events to.")
        @app_commands.checks.has_permissions(administrator=True)
        async def subscribe(interaction: discord.Interaction, channel: discord.channel.TextChannel):
            permission_result = await check_permissions(interaction=interaction, channel=channel)
            if not permission_result:
                return
            
            subscription_result = await set_channel_subscription(interaction=interaction, channel=channel, remove=False)
            if not subscription_result:
                return
            
            await interaction.response.send_message(f"The channel <#{channel.id}> has been subscribed to all Jam Track events.")

        @self.tree.command(name="unsubscribe", description="Unsubscribe a channel from Jam Track events")
        @app_commands.describe(channel = "The channel to stop sending Jam Track events to.")
        @app_commands.checks.has_permissions(administrator=True)
        async def unsubscribe(interaction: discord.Interaction, channel: discord.channel.TextChannel):
            permission_result = await check_permissions(interaction=interaction, channel=channel)
            if not permission_result:
                return
            
            subscription_result = await set_channel_subscription(interaction=interaction, channel=channel, remove=True)
            if not subscription_result:
                return
            
            await interaction.response.send_message(f"The channel <#{channel.id}> has been unsubscribed from all Jam Track events.")

        @self.tree.command(name="add_event", description="Add a Jam Track event to a channel")
        @app_commands.describe(channel = "The channel to add a Jam Track event to")
        @app_commands.describe(event = "The event to add")
        @app_commands.checks.has_permissions(administrator=True)
        async def add_event(interaction: discord.Interaction, channel: discord.channel.TextChannel, event: config.JamTrackEvent):
            channel_list = [subscribed_channel for subscribed_channel in self.config.channels if subscribed_channel.id == channel.id]
            channel_exists = len(channel_list) > 0
            chosen_event = config.JamTrackEvent[str(event).replace('JamTrackEvent.', '')].value

            event_names = {
                'added': "Jam Track Added",
                'removed': "Jam Track Removed",
                'modified': "Jam Track Modified"
            }

            if not channel_exists:
                # Only check for permissions if the channel is added
                permission_result = await check_permissions(interaction=interaction, channel=channel)
                if not permission_result:
                    return

                new_channel = config.SubscriptionChannel()
                new_channel.id = channel.id
                new_channel.roles = []
                new_channel.events = [chosen_event]
                self.config.channels.append(new_channel)
            else:
                subscribed_events = self.config.channels[self.config.channels.index(channel_list[0])].events
                if chosen_event in subscribed_events:
                    await interaction.response.send_message(f'The channel <#{channel.id}> is already subscribed to the event "{event_names[chosen_event]}".')
                    return
                else:
                    self.config.channels[self.config.channels.index(channel_list[0])].events.append(chosen_event)

            try:
                self.config.save_config()
            except Exception as e:
                await interaction.response.send_message(f"The bot's subscription list could not be updated to add the event \"{event_names[chosen_event]}\" to the channel <#{channel.id}>: {e}\nEvent subscription cancelled.")
                return
            
            await interaction.response.send_message(f'The channel <#{channel.id}> has been subscribed to the event "{event_names[chosen_event]}".')

        @self.tree.command(name="remove_event", description="Remove a Jam Track event from a channel")
        @app_commands.describe(channel = "The channel to remove a Jam Track event from")
        @app_commands.describe(event = "The event to remove")
        @app_commands.checks.has_permissions(administrator=True)
        async def remove_event(interaction: discord.Interaction, channel: discord.channel.TextChannel, event: config.JamTrackEvent):
            channel_list = [subscribed_channel for subscribed_channel in self.config.channels if subscribed_channel.id == channel.id]
            channel_exists = len(channel_list) > 0
            chosen_event = config.JamTrackEvent[str(event).replace('JamTrackEvent.', '')].value

            event_names = {
                'added': "Jam Track Added",
                'removed': "Jam Track Removed",
                'modified': "Jam Track Modified"
            }

            if not channel_exists:
                await interaction.response.send_message(f'The channel <#{channel.id}> is not subscribed to any events.')
                return
            else:
                subscribed_events = self.config.channels[self.config.channels.index(channel_list[0])].events

                if chosen_event in subscribed_events:
                    try:
                        self.config.channels[self.config.channels.index(channel_list[0])].events.remove(chosen_event)

                        # Remove the channel from the subscription list if it isnt subscribed to any events
                        if len(self.config.channels[self.config.channels.index(channel_list[0])].events) < 1:
                            self.config.channels.remove(channel_list[0])
                            self.config.save_config()
                            await interaction.response.send_message(f"The channel <#{channel.id}> has been removed from the subscription list because it is no longer subscribed to any events.")
                            return

                    except Exception as e:
                        await interaction.response.send_message(f"The bot's subscription list could not be updated to remove the event \"{event_names[chosen_event]}\" from the channel <#{channel.id}>: {e}\nEvent unsubscription cancelled.")
                        return
                else:
                    await interaction.response.send_message(f'The channel <#{channel.id}> is not subscribed to the event "{event_names[chosen_event]}".')
                    return

            try:
                self.config.save_config()
            except Exception as e:
                await interaction.response.send_message(f"The bot's subscription list could not be updated to remove the event \"{event_names[chosen_event]}\" from the channel <#{channel.id}>: {e}\nEvent unsubscription cancelled.")
                return
            
            await interaction.response.send_message(f'The channel <#{channel.id}> has been unsubscribed from the event "{event_names[chosen_event]}".')

        @self.tree.command(name="add_role", description="Add a role ping to a channel's subscription messages")
        @app_commands.describe(channel = "The channel to add a role ping to")
        @app_commands.describe(role = "The role to add a ping for")
        @app_commands.checks.has_permissions(administrator=True)
        async def add_role(interaction: discord.Interaction, channel: discord.channel.TextChannel, role: discord.Role):
            channel_list = [subscribed_channel for subscribed_channel in self.config.channels if subscribed_channel.id == channel.id]
            channel_exists = len(channel_list) > 0

            if not channel_exists:
                await interaction.response.send_message(f'The channel <#{channel.id}> is not subscribed to any events.')
                return
            else:
                channel_roles = self.config.channels[self.config.channels.index(channel_list[0])].roles

                if role.id in channel_roles:
                    await interaction.response.send_message(f"This role ping is already assigned to the channel <#{channel.id}>.")
                    return
                else:
                    self.config.channels[self.config.channels.index(channel_list[0])].roles.append(role.id)

            try:
                self.config.save_config()
            except Exception as e:
                await interaction.response.send_message(f"The bot's subscription list could not be updated to add this role ping to the channel <#{channel.id}>: {e}\nRole ping addition cancelled.")
                return
            
            await interaction.response.send_message(f'The channel <#{channel.id}> has been assigned to ping this role on future Jam Track events.')

        @self.tree.command(name="remove_role", description="Remove a role ping from a channel's subscription messages")
        @app_commands.describe(channel = "The channel to remove a role ping from")
        @app_commands.describe(role = "The role to remove a ping for")
        @app_commands.checks.has_permissions(administrator=True)
        async def remove_role(interaction: discord.Interaction, channel: discord.channel.TextChannel, role: discord.Role):
            channel_list = [subscribed_channel for subscribed_channel in self.config.channels if subscribed_channel.id == channel.id]
            channel_exists = len(channel_list) > 0

            if not channel_exists:
                await interaction.response.send_message(f'The channel <#{channel.id}> is not subscribed to any events.')
                return
            else:
                channel_roles = self.config.channels[self.config.channels.index(channel_list[0])].roles

                if role.id in channel_roles:
                    try:
                        self.config.channels[self.config.channels.index(channel_list[0])].roles.remove(role.id)
                    except ValueError as e:
                        await interaction.response.send_message(f"This role ping could not be removed from the channel <#{channel.id}>: {e}\nRole ping removal cancelled.")
                        return
                else:
                    await interaction.response.send_message(f"This role ping is not assigned to the channel <#{channel.id}>.")
                    return

            try:
                self.config.save_config()
            except Exception as e:
                await interaction.response.send_message(f"The bot's subscription list could not be updated to remove this role ping from the channel <#{channel.id}>: {e}\nRole ping removal cancelled.")
                return
            
            await interaction.response.send_message(f'The channel <#{channel.id}> has been assigned to not ping this role on future Jam Track events.')

        @self.tree.command(name="subscriptions", description="View the subscriptions in this guild")
        @app_commands.checks.has_permissions(administrator=True)
        async def subscriptions(interaction: discord.Interaction):
            embed = discord.Embed(title=f"Subscriptions for **{interaction.guild.name}**", color=0x8927A1)

            event_names = {
                'added': "Jam Track Added",
                'removed': "Jam Track Removed",
                'modified': "Jam Track Modified"
            }

            total_channels = 0

            for channel_to_search in self.config.channels:
                channel = self.get_channel(channel_to_search.id)

                if channel:
                    if channel.guild.id == interaction.guild.id:
                        total_channels += 1
                        events_content = "Events: " + ", ".join([event_names[event] for event in channel_to_search.events])
                        role_content = ""
                        if channel_to_search.roles:
                            if len(channel_to_search.roles) > 0:
                                role_content = "Roles: " + ", ".join([f'<@&{role.id}>' for role in channel_to_search.roles])
                        embed.add_field(name=f"<#{channel_to_search.id}>", value=f"{events_content}\n{role_content}")

            if total_channels < 1:
                embed.add_field(name="There are no subscriptions in this guild.", value="")

            await interaction.response.send_message(embed=embed)

        async def on_subscription_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
            print(error)
            if isinstance(error, app_commands.errors.MissingPermissions):
                await interaction.response.send_message(content="You do not have the necessary permissions to run this command. Only administrators can use this command.", ephemeral=True)

        subscribe.on_error = on_subscription_error
        unsubscribe.on_error = on_subscription_error
        add_event.on_error = on_subscription_error
        remove_event.on_error = on_subscription_error
        add_role.on_error = on_subscription_error
        remove_role.on_error = on_subscription_error
        subscriptions.on_error = on_subscription_error

        # User DM subscriptions

        @self.tree.command(name="dm_subscribe", description="Subscribe yourself to Jam Track events")
        async def dm_subscribe(interaction: discord.Interaction):
            user_list = [subscribed_user for subscribed_user in self.config.users if subscribed_user.id == interaction.user.id]
            user_exists = len(user_list) > 0

            event_names = {
                'added': "Jam Track Added",
                'removed': "Jam Track Removed",
                'modified': "Jam Track Modified"
            }

            if not user_exists:
                new_user = config.SubscriptionUser()
                new_user.id = interaction.user.id
                new_user.events = config.JamTrackEvent.get_all_events()
                self.config.users.append(new_user)
            else:
                subscribed_user_events = self.config.users[self.config.users.index(user_list[0])].events
                if len(subscribed_user_events) == len(config.JamTrackEvent.get_all_events()):
                    await interaction.response.send_message(f"You're already subscribed to all Jam Track events.", ephemeral=True)
                else:    
                    await interaction.response.send_message(f"You're already subscribed to the events \"{'\", \"'.join([event_names[event] for event in subscribed_user_events])}\".", ephemeral=True)
                return

            try:
                self.config.save_config()
            except Exception as e:
                await interaction.response.send_message(f"The bot's subscription list could not be updated to add you: {e}\nSubscription cancelled.", ephemeral=True)
                return
            
            await interaction.response.send_message(f"You've been successfully added to the subscription list; I will now send you all Jam Track events.", ephemeral=True)
            
        @self.tree.command(name="dm_unsubscribe", description="Unsubscribe yourself from Jam Track events")
        async def dm_unsubscribe(interaction: discord.Interaction):
            user_list = [subscribed_user for subscribed_user in self.config.users if subscribed_user.id == interaction.user.id]
            user_exists = len(user_list) > 0

            if not user_exists:
                await interaction.response.send_message(f"You are not subscribed to any Jam Track events.", ephemeral=True)
                return
            else:
                try:
                    self.config.users.remove(user_list[0])
                except ValueError as e:
                    await interaction.response.send_message(f"The bot's subscription list could not be updated to remove you: {e}\nUnsubscription cancelled.", ephemeral=True)
                    return

            try:
                self.config.save_config()
            except Exception as e:
                await interaction.response.send_message(f"The bot's subscription list could not be updated to remove you: {e}\nUnsubscription cancelled.", ephemeral=True)
                return
            
            await interaction.response.send_message(f"You've been successfully removed from the subscription list; I will no longer send you any Jam Track events.", ephemeral=True)

        @self.tree.command(name="dm_add_event", description="Subscribe yourself to specific Jam Track events")
        async def dm_add_event(interaction: discord.Interaction, event: config.JamTrackEvent):
            user_list = [subscribed_user for subscribed_user in self.config.users if subscribed_user.id == interaction.user.id]
            user_exists = len(user_list) > 0
            chosen_event = config.JamTrackEvent[str(event).replace('JamTrackEvent.', '')].value

            event_names = {
                'added': "Jam Track Added",
                'removed': "Jam Track Removed",
                'modified': "Jam Track Modified"
            }

            if not user_exists:
                new_user = config.SubscriptionUser()
                new_user.id = interaction.user.id
                new_user.events = [chosen_event]
                self.config.users.append(new_user)
            else:
                subscribed_events = self.config.users[self.config.users.index(user_list[0])].events
                if chosen_event in subscribed_events:
                    await interaction.response.send_message(f'You are already subscribed to the event "{event_names[chosen_event]}".', ephemeral=True)
                    return
                else:
                    self.config.users[self.config.users.index(user_list[0])].events.append(chosen_event)

            try:
                self.config.save_config()
            except Exception as e:
                await interaction.response.send_message(f"The bot's subscription list could not be updated to add the event \"{event_names[chosen_event]}\" to you: {e}\nEvent subscription cancelled.", ephemeral=True)
                return
            
            await interaction.response.send_message(f'You have been subscribed to the event "{event_names[chosen_event]}".', ephemeral=True)

        @self.tree.command(name="dm_remove_event", description="Unsubscribe yourself from Jam Track events")
        async def dm_add_event(interaction: discord.Interaction, event: config.JamTrackEvent):
            user_list = [subscribed_user for subscribed_user in self.config.users if subscribed_user.id == interaction.user.id]
            user_exists = len(user_list) > 0
            chosen_event = config.JamTrackEvent[str(event).replace('JamTrackEvent.', '')].value

            event_names = {
                'added': "Jam Track Added",
                'removed': "Jam Track Removed",
                'modified': "Jam Track Modified"
            }

            if not user_exists:
                await interaction.response.send_message(f'You are not subscribed to any events.', ephemeral=True)
                return
            else:
                subscribed_events = self.config.users[self.config.users.index(user_list[0])].events

                if chosen_event in subscribed_events:
                    try:
                        self.config.users[self.config.users.index(user_list[0])].events.remove(chosen_event)

                        # Remove the channel from the subscription list if it isnt subscribed to any events
                        if len(self.config.users[self.config.users.index(user_list[0])].events) < 1:
                            self.config.users.remove(user_list[0])
                            self.config.save_config()
                            await interaction.response.send_message(f"You have been removed from the subscription list because you are no longer subscribed to any events.", ephemeral=True)
                            return

                    except Exception as e:
                        await interaction.response.send_message(f"The bot's subscription list could not be updated to remove the event \"{event_names[chosen_event]}\" from you: {e}\nEvent unsubscription cancelled.", ephemeral=True)
                        return
                else:
                    await interaction.response.send_message(f'You are not subscribed to the event "{event_names[chosen_event]}".', ephemeral=True)
                    return

            try:
                self.config.save_config()
            except Exception as e:
                await interaction.response.send_message(f"The bot's subscription list could not be updated to remove the event \"{event_names[chosen_event]}\" from you: {e}\nEvent unsubscription cancelled.", ephemeral=True)
                return
            
            await interaction.response.send_message(f'You have been unsubscribed from the event "{event_names[chosen_event]}".', ephemeral=True)

bot = FestivalInfoBot()