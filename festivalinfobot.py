import asyncio
import difflib
import logging
from datetime import datetime
import time
from typing import Union
from discord.ext import commands, tasks
import discord
from discord import app_commands
from configparser import ConfigParser

from bot import config, constants, embeds
from bot.festrpc import FestRPCCog
from bot.fortnitecog import FortniteCog
from bot.log import setup as setup_log
from bot.admin import AdminCog, TestCog
from bot.config import Config
from bot.history import HistoryHandler, LoopCheckHandler
from bot.leaderboard import LeaderboardCommandHandler
from bot.path import PathCommandHandler
from bot.randomcog import RandomCog
from bot.subcog import SubscriptionCog
from bot.suggestions import SuggestionModal
from bot.tracks import SearchCommandHandler, JamTrackHandler
from bot.helpers import DailyCommandHandler, OneButtonSimpleView, ShopCommandHandler, TracklistHandler
from bot.graph import GraphCommandsHandler

class FestivalInfoBot(commands.Bot):
    async def on_ready(self):
        # Setup all the subscription commands
        logging.debug("Setting up admin commands...")
        # Apparently this works, dont know why but
        # it is possible to await this function here
        await self.setup_cogs()
        
        logging.info(f'Logged in as {self.user.name}')

        logging.info("Bot going active on:")
        logging.info(' '.join(["No.".ljust(5), "Name".ljust(30), "ID".ljust(20), "Join Date"]))
        
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
            logging.info(
                ' '.join([str(index).ljust(5),
                    guild.name.ljust(30), 
                    str(guild.id).ljust(20), 
                    join_date
                ])
            )

        logging.debug("Syncing slash command tree...")
        await self.tree.sync()

        logging.debug(f"Registering background task every {self.CHECK_FOR_SONGS_INTERVAL}min")
        @tasks.loop(minutes=self.CHECK_FOR_SONGS_INTERVAL)
        async def check_for_new_songs():
            await self.check_handler.handle_task()

        if self.CHECK_FOR_NEW_SONGS:
            check_for_new_songs.start()

        @tasks.loop(minutes=2.5)
        async def activity_task():
            await self.check_handler.handle_activity_task()

        @activity_task.before_loop
        async def wait_thing(): 
            # This prewents the task from running before the bot can finish logging in
            # Was recommended to do this by StackOverflow
            await self.wait_until_ready()

        activity_task.start()

        logging.info("Bot is now running!")

    def __init__(self):
        # Load configuration from config.ini
        setup_log()

        config = ConfigParser()
        config.read('config.ini')

        self.config : Config = None
        self.suggestions_enabled = False

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
            command_prefix=commands.when_mentioned_or('ft!'),
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
        self.graph_handler = GraphCommandsHandler()

        self.setup_commands()
        # self.setup_subscribe_commands()

        self.run(DISCORD_TOKEN, log_handler=None)

    def setup_commands(self):

        # This command is secret; it can be used to inmediately check if Festival Tracker
        # is online without having to go through application commands
        # Invokable by "ft!online"
        @self.command(name="online")
        async def checkonline_command(ctx):
            if ctx.message.channel.permissions_for(ctx.message.channel.guild.me).add_reactions:
                await ctx.message.add_reaction("✅")
            else:
                await ctx.send(f"{ctx.message.channel.guild.me.display_name} is online.")

        @self.tree.command(name="search", description="Search a song.")
        @app_commands.allowed_installs(guilds=True, users=True)
        @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
        @app_commands.describe(query = "A search query: an artist, song name, or shortname.")
        async def search_command(interaction: discord.Interaction, query:str):
            await self.search_handler.handle_interaction(interaction=interaction, query=query)

        @self.tree.command(name="weekly", description="Display the tracks currently in weekly rotation.")
        @app_commands.allowed_installs(guilds=True, users=True)
        @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
        async def daily_command(interaction: discord.Interaction):
            await self.daily_handler.handle_interaction(interaction=interaction)

        tracklist_group = app_commands.Group(name="tracklist", description="Tracklist commands", allowed_contexts=discord.app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True), allowed_installs=discord.app_commands.AppInstallationType(guild=True, user=True))

        filter_group = app_commands.Group(name="filter", description="Tracklist commands", parent=tracklist_group)

        @tracklist_group.command(name="all", description="Browse the full list of available Jam Tracks.")
        async def tracklist_command(interaction: discord.Interaction):
            await self.tracklist_handler.handle_interaction(interaction=interaction)

        @filter_group.command(name="artist", description="Browse the list of available Jam Tracks that match a queried artist.")
        @app_commands.describe(artist = "A search query to use in the song name.")
        async def tracklist_command(interaction: discord.Interaction, artist:str):
            await self.tracklist_handler.handle_artist_interaction(interaction=interaction, artist=artist)

        @filter_group.command(name="regex", description="Browse the list of available Jam Tracks that match a Regex pattern in a customizable query format.")
        @app_commands.describe(regex = "A Regular Expression (Regex) to match. Leave empty to show help with this command.")
        @app_commands.describe(query = "A query that the Regex will match.")
        async def tracklist_command(interaction: discord.Interaction, regex:str = None, query:str = "%an - %tt"):
            await self.tracklist_handler.handle_regex_interaction(interaction=interaction, regex=regex, matched=query)

        self.tree.add_command(tracklist_group)

        @self.tree.command(name="shop", description="Display the tracks currently in the shop.")
        @app_commands.allowed_installs(guilds=True, users=True)
        @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
        async def shop_command(interaction: discord.Interaction):
            await self.shop_handler.handle_interaction(interaction=interaction)

        @self.tree.command(name="count", description="View the total number of Jam Tracks in Fortnite Festival.")
        @app_commands.allowed_installs(guilds=True, users=True)
        @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
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

        lb_group = app_commands.Group(name="leaderboard", description="Leaderboard commands", allowed_contexts=discord.app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True), allowed_installs=discord.app_commands.AppInstallationType(guild=True, user=True))

        @lb_group.command(name="view", description="View the leaderboards of a song.")
        @app_commands.describe(song = "A search query: an artist, song name, or shortname.")
        @app_commands.describe(instrument = "The instrument to view the leaderboard of.")
        async def leaderboard_command(interaction: discord.Interaction, song:str, instrument:constants.Instruments):
            await self.lb_handler.handle_interaction(interaction, song=song, instrument=instrument)

        @lb_group.command(name="entry", description="View a specific entry in the leaderboards of a song.")
        @app_commands.describe(song = "A search query: an artist, song name, or shortname.")
        @app_commands.describe(instrument = "The instrument to view the leaderboard of.")
        @app_commands.describe(rank = "A number from 1 to 500 to view a specific entry in the leaderboard.")
        @app_commands.describe(username = "An Epic Games account's username. Not case-sensitive.")
        @app_commands.describe(account_id = "An Epic Games account ID.")
        async def leaderboard_entry_command(interaction: discord.Interaction, song:str, instrument:constants.Instruments, rank: discord.app_commands.Range[int, 1, 500] = 1, username:str = None, account_id:str = None):
            await self.lb_handler.handle_interaction(interaction, song=song, instrument=instrument, rank=rank, username=username, account_id=account_id)

        self.tree.add_command(lb_group)

        @self.tree.command(name="path", description="Generates an Overdrive path for a song using CHOpt.")
        @app_commands.allowed_installs(guilds=True, users=True)
        @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
        @app_commands.describe(song = "A search query: an artist, song name, or shortname.")
        @app_commands.describe(instrument = "The instrument to view the path of.")
        @app_commands.describe(difficulty = "The difficulty to view the path for.")
        @app_commands.describe(squeeze_percent = "Change CHOpt's Squeeze parameter.")
        @app_commands.describe(lefty_flip = "Enable CHOpt to render in Lefty Flip mode.")
        @app_commands.describe(act_opacity = "Set the opacity of activations in images.")
        @app_commands.describe(no_bpms = "If set to True, CHOpt will not draw BPMs.")
        @app_commands.describe(no_solos = "If set to True, CHOpt will not draw Solo Sections.")
        @app_commands.describe(no_time_signatures = "If set to True, CHOpt will not draw Time Signatures.")
        async def path_command(interaction: discord.Interaction, song:str, instrument:constants.Instruments, difficulty:constants.Difficulties = constants.Difficulties.Expert, squeeze_percent: discord.app_commands.Range[int, 0, 100] = 20, lefty_flip : bool = False, act_opacity: discord.app_commands.Range[int, 0, 100] = None, no_bpms: bool = False, no_solos: bool = False, no_time_signatures: bool = False):
            if not self.PATHING_ALLOWED or not self.DECRYPTION_ALLOWED:
                await interaction.response.send_message(content="This command is not enabled in this bot.", ephemeral=True)
                return

            await self.path_handler.handle_interaction(
                interaction,
                song=song,
                instrument=instrument,
                squeeze_percent=squeeze_percent,
                difficulty=difficulty,
                extra_args=[
                    lefty_flip,
                    act_opacity,
                    no_bpms,
                    no_solos,
                    no_time_signatures
                ]
            )

        history_group = app_commands.Group(name="history", description="History commands", allowed_contexts=discord.app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True), allowed_installs=discord.app_commands.AppInstallationType(guild=True, user=True))

        @history_group.command(name="chart", description="View the chart history of a Jam Track.")
        @app_commands.describe(song = "A search query: an artist, song name, or shortname.")
        async def history_command(interaction: discord.Interaction, song:str):
            if not self.CHART_COMPARING_ALLOWED or not self.DECRYPTION_ALLOWED:
                await interaction.response.send_message(content="This command is not enabled in this bot.", ephemeral=True)
                return
    
            await self.history_handler.handle_interaction(interaction=interaction, song=song)

        @history_group.command(name="metadata", description="View the metadata history of a Jam Track.")
        @app_commands.describe(song = "A search query: an artist, song name, or shortname.")
        async def metahistory_command(interaction: discord.Interaction, song:str):
            await self.history_handler.handle_metahistory_interaction(interaction=interaction, song=song)

        self.tree.add_command(history_command)

        @self.tree.command(name="suggestion", description="Suggest a feature for Festival Tracker")
        @app_commands.allowed_installs(guilds=True, users=True)
        @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
        async def suggestion_command(interaction: discord.Interaction):
            try:
                if not self.suggestions_enabled:
                    await interaction.response.send_message(f"Sorry; Suggestions are currently not enabled.", ephemeral=True)
                    return
                else:
                    await interaction.response.send_modal(SuggestionModal(self))
            except Exception as e:
                await interaction.response.send_message(f'Unable to send the suggestion: {e}', ephemeral=True)

        @self.tree.command(name="stats", description="Displays Festival Tracker stats")
        @app_commands.allowed_installs(guilds=True, users=True)
        @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
        async def bot_stats(interaction: discord.Interaction):
            await interaction.response.defer()

            # Get the number of servers the bot is in
            server_count = len(self.guilds)
            channel_count = 0
            users_count = 0
            for guild in self.guilds:
                served_members = [m for m in guild.members]
                served_channels = [c for c in guild.channels]
                channel_count += len(served_channels)
                users_count += len(served_members)
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
                last_update_formatted = discord.utils.format_dt(last_update_timestamp, style="R")  # Use Discord's relative time format
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
            embed.add_field(name="Servers", value=f"{server_count} servers", inline=True)
            embed.add_field(name="Channels", value=f"{channel_count} channels", inline=True)
            embed.add_field(name="Users", value=f"{users_count} users", inline=True)
            embed.add_field(name="Subscriptions", value=f"{len(self.config.users)} users, {len(self.config.channels)} channels", inline=True)
            embed.add_field(name="Ping", value=f"{round(self.latency*1000, 2)}ms", inline=True)
            embed.add_field(name="Up Since", value=f"{discord.utils.format_dt(datetime.fromtimestamp(self.start_time), 'R')}", inline=True)
            embed.add_field(name="Uptime", value=f"{uptime}", inline=False)
            embed.add_field(name="Latest Upstream Info", value=f"[`{latest_commit_hash[:7]}`]({upstream_commit_url}) {last_update_formatted}", inline=False)
            embed.add_field(name="Local Commit Info", value=f"[`{branch_name}`]({remote_branch_url}) [`{local_commit_hash[:7]}`]({local_commit_url}) ({commit_status})", inline=False)
            if len(dirtyness) > 0:
                embed.add_field(name="Local Changes", value=f"```{dirtyness}```", inline=False)

            view = OneButtonSimpleView(None, interaction.user.id, "Invite Festival Tracker", "🔗", "https://festivaltracker.github.io", False)
            view.message = await interaction.original_response()

            await interaction.edit_original_response(embed=embed, view=view)

        @self.tree.command(name="help", description="Show the help message")
        @app_commands.allowed_installs(guilds=True, users=True)
        @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
        @app_commands.describe(command = "The command to view help about.")
        async def help_command(interaction: discord.Interaction, command:str = None):
            commands = []

            for _command in self.tree.get_commands():
                # Define a recursive function to traverse commands and subcommands
                def recurse_inner(c: Union[app_commands.Command, app_commands.Group]):
                    if isinstance(c, app_commands.Group):
                        # Loop through subcommands in the group
                        for group_command in c.commands:
                            recurse_inner(group_command)  # Recurse on each subcommand
                    else:
                        # If it's not a group, add it to the commands list
                        if c.parent and c.parent.guild_only and isinstance(interaction.channel, discord.DMChannel):
                            return  # Skip if guild-only and in a DM
                        commands.append({
                            "name": f"{c.qualified_name}",
                            "value": c.description or "No description",
                            "inline": False
                        })

                recurse_inner(_command)

            if command:
                found = discord.utils.find(lambda c: c['name'] == command, commands)
                if found:
                    found_command = self.find_command_by_string(found['name'])
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
                        title="",
                        description=f"A powerful bot for Fortnite Festival song data.",
                        color=0x8927A1
                    )
                    embed.add_field(name='Source Code', value='[View](https://www.github.com/hmxmilohax/festivalinfobot)')
                    embed.add_field(name='Privacy Policy', value='[View](https://github.com/hmxmilohax/festivalinfobot/blob/main/privacy_policy.md)')
                    embed.add_field(name='Terms of Service', value='[View](https://github.com/hmxmilohax/festivalinfobot/blob/main/terms_of_service.md)')
                    embed.add_field(name=f"Help with `/{found_command.qualified_name}`", value=description, inline=False)

                    embed.set_author(name="Festival Tracker", icon_url=self.user.avatar.url)
                    embed.set_thumbnail(url=self.user.avatar.url)

                    if any(not param.required for param in found_command.parameters):
                        embed.set_footer(text="Tip: Parameters with \"?\" mean they're optional.")
                    embed.add_field(name="Usage", value=usage, inline=False)

                    view = OneButtonSimpleView(None, interaction.user.id, "Invite Festival Tracker", "🔗", "https://festivaltracker.github.io", False)
                    await interaction.response.send_message(embed=embed, view=view)
                    view.message = await interaction.original_response()
                else:
                    command_list = [command['name'] for command in commands]
                    close_match = difflib.get_close_matches(command, command_list, n=1, cutoff=0.7)
                    tip = ""
                    if close_match:
                        if len(close_match) > 0:
                            tip = f"\n*Did you mean: `{close_match[0]}`?*"

                    await interaction.response.send_message(content=f"No command found with the name \"{command}\"{tip}", ephemeral=True)
                    return
            else:
                embeds = []

                for i in range(0, len(commands), 5):
                    embed = discord.Embed(
                        title="Festival Tracker Help",
                        description=f"A powerful bot for Fortnite Festival song data.\nUse `/help <command>` to get more information on a specific command.",
                        color=0x8927A1
                    )
                    embed.add_field(name='Source Code', value='[View](https://www.github.com/hmxmilohax/festivalinfobot)')
                    embed.add_field(name='Privacy Policy', value='[View](https://github.com/hmxmilohax/festivalinfobot/blob/main/privacy_policy.md)')
                    embed.add_field(name='Terms of Service', value='[View](https://github.com/hmxmilohax/festivalinfobot/blob/main/terms_of_service.md)')
                    embed.add_field(name='Invite Link', value='[Add Festival Tracker to your server!](https://festivaltracker.github.io)', inline=False)
                    chunk = commands[i:i + 5]

                    for command in chunk:
                        embed.add_field(name=f'`/{command["name"]}`', value=command['value'], inline=command['inline'])
                    
                    embed.set_thumbnail(url=self.user.avatar.url)

                    embeds.append(embed)

                view = constants.PaginatorView(embeds, interaction.user.id)
                await interaction.response.send_message(embed=view.get_embed(), view=view)
                view.message = await interaction.original_response()

        graph_group = app_commands.Group(name="graph", description="Graph Command Group.", allowed_contexts=discord.app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True), allowed_installs=discord.app_commands.AppInstallationType(guild=True, user=True))

        graph_notes_group = app_commands.Group(name="counts", description="Graph the note and lift counts for a specific song.", parent=graph_group)
        @graph_notes_group.command(name="all", description="Graph the note counts for a specific song.")
        @app_commands.describe(song = "A search query: an artist, song name, or shortname.")
        async def graph_note_counts_command(interaction: discord.Interaction, song:str):
            if not self.DECRYPTION_ALLOWED:
                await interaction.response.send_message(content="This command is not enabled in this bot.", ephemeral=True)
                return
            await self.graph_handler.handle_pdi_interaction(interaction=interaction, song=song)

        @graph_notes_group.command(name="lifts", description="Graph the lift counts for a specific song.")
        @app_commands.describe(song = "A search query: an artist, song name, or shortname.")
        async def graph_note_counts_command(interaction: discord.Interaction, song:str):
            if not self.DECRYPTION_ALLOWED:
                await interaction.response.send_message(content="This command is not enabled in this bot.", ephemeral=True)
                return
            
            await self.graph_handler.handle_lift_interaction(interaction=interaction, song=song)

        @graph_group.command(name="nps", description="Graph the NPS (Notes per second) for a specific song, instrument, and difficulty.")
        @app_commands.describe(song = "A search query: an artist, song name, or shortname.")
        @app_commands.describe(instrument = "The instrument to view the NPS of.")
        @app_commands.describe(difficulty = "The difficulty to view the NPS for.")
        async def graph_nps_command(interaction: discord.Interaction, song:str, instrument : constants.Instruments, difficulty : constants.Difficulties = constants.Difficulties.Expert):
            if not self.DECRYPTION_ALLOWED:
                await interaction.response.send_message(content="This command is not enabled in this bot.", ephemeral=True)
                return
            
            await self.graph_handler.handle_nps_interaction(interaction=interaction, song=song, instrument=instrument, difficulty=difficulty)

        @graph_group.command(name="lanes", description="Graph the number of notes for each lane in a specific song, instrument, and difficulty.")
        @app_commands.describe(song = "A search query: an artist, song name, or shortname.")
        @app_commands.describe(instrument = "The instrument to view the #notes of.")
        @app_commands.describe(difficulty = "The difficulty to view the #notes for.")
        async def graph_lanes_command(interaction: discord.Interaction, song:str, instrument : constants.Instruments, difficulty : constants.Difficulties = constants.Difficulties.Expert):
            if not self.DECRYPTION_ALLOWED:
                await interaction.response.send_message(content="This command is not enabled in this bot.", ephemeral=True)
                return
            
            await self.graph_handler.handle_lanes_interaction(interaction=interaction, song=song, instrument=instrument, difficulty=difficulty)

        self.tree.add_command(graph_group)

    async def setup_cogs(self):
        admin_cog = AdminCog(self)
        await self.add_cog(admin_cog)

        test_cog = TestCog(self)
        await self.add_cog(test_cog)

        fort_cog = FortniteCog(self)
        await self.add_cog(fort_cog)

        sub_cog = SubscriptionCog(self)
        await self.add_cog(sub_cog)

        random_cog = RandomCog(self)
        await self.add_cog(random_cog)

        festrpc = FestRPCCog(self)
        await self.add_cog(festrpc)

    def find_command_by_string(self, command: str):
        words = command.split()
        if not words:
            return None 

        current_level = self.tree.get_commands()

        for word in words:
            found = None
            for cmd in current_level:
                if cmd.name == word:
                    found = cmd
                    break

            if not found:
                return None

            if isinstance(found, app_commands.Group):
                current_level = found.commands
            else:
                if word != words[-1]:
                    return None
                return found

        return found

bot = FestivalInfoBot()
