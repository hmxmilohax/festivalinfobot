import asyncio
from datetime import datetime
import json
import time
from discord.ext import commands, tasks
import discord
from discord import app_commands
from configparser import ConfigParser

from bot import config, constants, embeds
from bot.admin import AdminCog, TestCog
from bot.config import Config
from bot.history import HistoryHandler, LoopCheckHandler
from bot.leaderboard import LeaderboardCommandHandler
from bot.path import PathCommandHandler
from bot.tracks import SearchCommandHandler, JamTrackHandler
from bot.helpers import DailyCommandHandler, ShopCommandHandler, TracklistHandler, GamblingHandler

class FestivalInfoBot(commands.Bot):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def on_ready(self):
        # Setup all the subscription commands
        print("Setting up admin commands...")
        # Apparently this works, dont know why but
        # it is possible to await this function here
        await self.setup_admin_commands()
        
        print(f'Logged in as {self.user.name}')

        print("Bot now active on:")
        print("No.".ljust(5), "Name".ljust(30), "ID".ljust(20), "Join Date")
        
        # Sort guilds by the bot's join date
        sorted_guilds = sorted(
            self.guilds, 
            key=lambda guild: guild.me.joined_at or datetime.min
        )
        
        # Enumerate over sorted guilds to get the join number
        for index, guild in enumerate(sorted_guilds, start=1):
            join_date = (
                guild.me.joined_at.strftime("%Y-%m-%d %H:%M:%S") 
                if guild.me.joined_at else "Unknown"
            )
            print(
                str(index).ljust(5),
                guild.name.ljust(30), 
                str(guild.id).ljust(20), 
                join_date
            )

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

        reload_config()

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
        self.gambling_handler = GamblingHandler()

        self.setup_commands()
        self.setup_subscribe_commands()

        self.run(DISCORD_TOKEN)

    def setup_commands(self):
        @self.tree.command(name="search", description="Search a song.")
        @app_commands.describe(query = "A search query: an artist, song name, or shortname.")
        async def search_command(interaction: discord.Interaction, query:str):
            await self.search_handler.handle_interaction(interaction=interaction, query=query)

        @self.tree.command(name="random_track", description="Get a random Jam Track from the list of available Jam Tracks!")
        async def random_track_command(interaction: discord.Interaction):
            await self.gambling_handler.handle_random_track_interaction(interaction=interaction)

        @self.tree.command(name="random_setlist", description="Get a random setlist from the list of available Jam Tracks!")
        async def random_setlist_command(interaction: discord.Interaction):
            await self.gambling_handler.handle_random_setlist_interaction(interaction=interaction)

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
            remote_branch_url = remote_url + '/tree/' + branch_name + '/'
            # Create an embed to display the statistics
            embed = discord.Embed(
                title="Festival Tracker Statistics",
                description="",
                color=0x8927A1
            )
            embed.add_field(name="Ping", value=f"{round(self.latency*1000, 2)}ms", inline=True)
            embed.add_field(name="Servers", value=f"{server_count} servers", inline=True)
            embed.add_field(name="Uptime", value=f"{uptime}", inline=False)
            embed.add_field(name="Latest Upstream Info", value=f"[`{latest_commit_hash[:7]}`]({upstream_commit_url}) {last_update_formatted}", inline=False)
            embed.add_field(name="Local Commit Info", value=f"[`{branch_name}`]({remote_branch_url}) [`{local_commit_hash[:7]}`]({local_commit_url}) ({commit_status})", inline=False)
            if len(dirtyness) > 0:
                embed.add_field(name="Local Changes", value=f"```{dirtyness}```", inline=False)

            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="help", description="Show the help message")
        @app_commands.describe(command = "The command to view help about.")
        async def help_command(interaction: discord.Interaction, command:str = None):
            _commands = self.tree.get_commands()
            commands = []
            for _command in _commands:
                # Add command to embed
                if isinstance(_command, discord.app_commands.commands.Group):
                    for group_command in _command.commands:
                        if group_command.guild_only and isinstance(interaction.channel, discord.DMChannel):
                            continue
                        commands.append({
                            "name":f"`/{_command.name} {group_command.name}`",
                            "value":group_command.description or "No description",
                            "inline":False
                        })
                else:
                    commands.append({
                        "name":f"`/{_command.name}`",
                        "value":_command.description or "No description",
                        "inline":False
                    })

            if command:
                if self.tree.get_command(command.split(' ')[0]):
                    found_command = self.tree.get_command(command.split(' ')[0])
                    try:
                        if isinstance(found_command, discord.app_commands.commands.Group):
                            found_command = found_command.get_command(command.split(' ')[1])
                    except Exception as e:
                        print(e)
                        await interaction.response.send_message(content=f"No command found with the name \"{command}\"", ephemeral=True)
                        return
                    
                    parameters = " ".join([f'<{"" if param.required else "?"}{param.name}>' for param in found_command.parameters])
                    usage = f"`/{found_command.qualified_name}" + (f" {parameters}" if len(parameters) > 0 else "") + "`"

                    for param in found_command.parameters:
                        # cmd_type = str(param.type).split('.').pop()
                        usage += '\n- '
                        usage += '`' + ('?' if not param.required else '') + f'{param.name}`'
                        # usage += f' ({cmd_type})'
                        usage += f': {param.description}' + ('.' if not param.description.endswith('.') else '') + (f' *Default: {str(param.default).split(".").pop()}*' if not param.required and param.default != None else "")

                    description = f'{found_command.description}'
                    description += '\n*(Server-only command)*' if found_command.guild_only else ''

                    embed = discord.Embed(
                        title="Festival Tracker Help",
                        description=f"A simple and powerful bot to check Fortnite Festival song data. [Source code](https://github.com/hmxmilohax/festivalinfobot)",
                        color=0x8927A1
                    )
                    embed.add_field(name=f"Help with `/{found_command.qualified_name}`", value=description, inline=False)

                    if any(not param.required for param in found_command.parameters):
                        embed.set_footer(text="Tip: Parameters with \"?\" mean they're optional.")
                    embed.add_field(name="Usage", value=usage, inline=False)

                    await interaction.response.send_message(embed=embed)
                else:
                    await interaction.response.send_message(content=f"No command found with the name \"{command}\"", ephemeral=True)
                    return
            else:
                embeds = []

                for i in range(0, len(commands), 5):
                    embed = discord.Embed(
                        title="Festival Tracker Help",
                        description=f"A simple and powerful bot to check Fortnite Festival song data. [Source code](https://github.com/hmxmilohax/festivalinfobot)\nUse `/help <command>` to get more information on a specific command.",
                        color=0x8927A1
                    )
                    chunk = commands[i:i + 5]
                    # Walk through all commands registered in self.tree

                    for command in chunk:
                        embed.add_field(name=command['name'], value=command['value'], inline=command['inline'])
                    
                    embeds.append(embed)

                view = constants.PaginatorView(embeds, interaction.user.id)
                await interaction.response.send_message(embed=view.get_embed(), view=view)
                view.message = await interaction.original_response()

    async def setup_admin_commands(self):
        admin_cog = AdminCog(self)
        await self.add_cog(admin_cog)
        # await self.tree.add_command(admin_cog.admin_group)

        test_cog = TestCog(self)
        await self.add_cog(test_cog)

    def setup_subscribe_commands(self):
        # User DM subscriptions

        @self.tree.command(name="subscribe", description="Subscribe yourself to Jam Track events")
        async def dm_subscribe(interaction: discord.Interaction):
            user_list = [subscribed_user for subscribed_user in self.config.users if subscribed_user.id == interaction.user.id]
            user_exists = len(user_list) > 0

            if not user_exists:
                self.config.users.append(config.SubscriptionUser(interaction.user.id, config.JamTrackEvent.get_all_events()))
            else:
                for i, _user in enumerate(user_list):
                    if i > 0:
                        print(f'Found another user for {interaction.user.id}?\nUser no. {i}')

                    subscribed_user_events = self.config.users[self.config.users.index(_user)].events
                    if len(subscribed_user_events) == len(config.JamTrackEvent.get_all_events()):
                        await interaction.response.send_message(f"You're already subscribed to all Jam Track events.", ephemeral=True)
                    else:    
                        await interaction.response.send_message(f"You're already subscribed to the events \"{'\", \"'.join([constants.EVENT_NAMES[event] for event in subscribed_user_events])}\".", ephemeral=True)
                    return

            try:
                self.config.save_config()
            except Exception as e:
                await interaction.response.send_message(f"The bot's subscription list could not be updated to add you: {e}\nSubscription cancelled.", ephemeral=True)
                return
            
            await interaction.response.send_message(f"You've been successfully added to the subscription list; I will now send you all Jam Track events.", ephemeral=True)
            
        @self.tree.command(name="unsubscribe", description="Unsubscribe yourself from Jam Track events")
        async def dm_unsubscribe(interaction: discord.Interaction):
            user_list = [subscribed_user for subscribed_user in self.config.users if subscribed_user.id == interaction.user.id]
            user_exists = len(user_list) > 0

            if not user_exists:
                await interaction.response.send_message(f"You are not subscribed to any Jam Track events.", ephemeral=True)
                return
            else:
                for i, _user in enumerate(user_list):
                    if i > 0:
                        print(f'Found another user for {interaction.user.id}?\nUser no. {i}')
                    try:
                        self.config.users.remove(_user)
                    except ValueError as e:
                        await interaction.response.send_message(f"The bot's subscription list could not be updated to remove you: {e}\nUnsubscription cancelled.", ephemeral=True)
                        return

            try:
                self.config.save_config()
            except Exception as e:
                await interaction.response.send_message(f"The bot's subscription list could not be updated to remove you: {e}\nUnsubscription cancelled.", ephemeral=True)
                return
            
            await interaction.response.send_message(f"You've been successfully removed from the subscription list; I will no longer send you any Jam Track events.", ephemeral=True)

        @self.tree.command(name="add_event", description="Subscribe yourself to specific Jam Track events")
        async def dm_add_event(interaction: discord.Interaction, event: config.JamTrackEvent):
            user_list = [subscribed_user for subscribed_user in self.config.users if subscribed_user.id == interaction.user.id]
            user_exists = len(user_list) > 0
            chosen_event = config.JamTrackEvent[str(event).replace('JamTrackEvent.', '')].value

            if not user_exists:
                self.config.users.append(config.SubscriptionUser(interaction.user.id, [chosen_event]))
            else:
                for i, _user in enumerate(user_list):
                    if i > 0:
                        print(f'Found another user for {interaction.user.id}?\nUser no. {i}')

                    subscribed_events = self.config.users[self.config.users.index(_user)].events
                    if chosen_event in subscribed_events:
                        await interaction.response.send_message(f'You are already subscribed to the event "{constants.EVENT_NAMES[chosen_event]}".', ephemeral=True)
                        return
                    else:
                        self.config.users[self.config.users.index(_user)].events.append(chosen_event)

            try:
                self.config.save_config()
            except Exception as e:
                await interaction.response.send_message(f"The bot's subscription list could not be updated to add the event \"{constants.EVENT_NAMES[chosen_event]}\" to you: {e}\nEvent subscription cancelled.", ephemeral=True)
                return
            
            await interaction.response.send_message(f'You have been subscribed to the event "{constants.EVENT_NAMES[chosen_event]}".', ephemeral=True)

        @self.tree.command(name="remove_event", description="Unsubscribe yourself from Jam Track events")
        async def dm_add_event(interaction: discord.Interaction, event: config.JamTrackEvent):
            user_list = [subscribed_user for subscribed_user in self.config.users if subscribed_user.id == interaction.user.id]
            user_exists = len(user_list) > 0
            chosen_event = config.JamTrackEvent[str(event).replace('JamTrackEvent.', '')].value

            if not user_exists:
                await interaction.response.send_message(f'You are not subscribed to any events.', ephemeral=True)
                return
            else:
                for i, _user in enumerate(user_list):
                    if i > 0:
                        print(f'Found another user for {interaction.user.id}?\nUser no. {i}')

                    subscribed_events = self.config.users[self.config.users.index(_user)].events

                    if chosen_event in subscribed_events:
                        try:
                            self.config.users[self.config.users.index(_user)].events.remove(chosen_event)

                            # Remove the channel from the subscription list if it isnt subscribed to any events
                            if len(self.config.users[self.config.users.index(_user)].events) < 1:
                                self.config.users.remove(_user)
                                self.config.save_config()
                                await interaction.response.send_message(f"You have been removed from the subscription list because you are no longer subscribed to any events.", ephemeral=True)
                                return

                        except Exception as e:
                            await interaction.response.send_message(f"The bot's subscription list could not be updated to remove the event \"{constants.EVENT_NAMES[chosen_event]}\" from you: {e}\nEvent unsubscription cancelled.", ephemeral=True)
                            return
                    else:
                        await interaction.response.send_message(f'You are not subscribed to the event "{constants.EVENT_NAMES[chosen_event]}".', ephemeral=True)
                        return

            try:
                self.config.save_config()
            except Exception as e:
                await interaction.response.send_message(f"The bot's subscription list could not be updated to remove the event \"{constants.EVENT_NAMES[chosen_event]}\" from you: {e}\nEvent unsubscription cancelled.", ephemeral=True)
                return
            
            await interaction.response.send_message(f'You have been unsubscribed from the event "{constants.EVENT_NAMES[chosen_event]}".', ephemeral=True)

bot = FestivalInfoBot()