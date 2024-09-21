import time
from discord.ext import commands, tasks
import discord
from configparser import ConfigParser

from bot import constants, embeds
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

        # Read the Discord bot token and channel IDs from the config file
        DISCORD_TOKEN = config.get('discord', 'token')
        CHANNEL_IDS = config.get('discord', 'channel_ids', fallback="").split(',')

        # Convert channel IDs to integers and filter out any empty strings
        self.CHANNEL_IDS = [int(id.strip()) for id in CHANNEL_IDS if id.strip()]

        # Bot configuration properties
        self.CHECK_FOR_SONGS_INTERVAL = config.getint('bot', 'check_new_songs_interval', fallback=7)
        self.CHECK_FOR_NEW_SONGS = config.getboolean('bot', 'check_for_new_songs', fallback=True)
        self.DECRYPTION_ALLOWED = config.getboolean('bot', 'decryption', fallback=True)
        self.PATHING_ALLOWED = config.getboolean('bot', 'pathing', fallback=True)
        self.CHART_COMPARING_ALLOWED = config.getboolean('bot', 'chart_comparing', fallback=True)

        self.start_time = time.time()

        # Set up Discord bot with necessary intents
        intents = discord.Intents.default()
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

        self.run(DISCORD_TOKEN)

    def setup_commands(self):
        @self.tree.command(name="search", description="Search a song.")
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

bot = FestivalInfoBot()