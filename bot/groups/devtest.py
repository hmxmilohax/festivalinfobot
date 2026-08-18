from aiohttp import client_exceptions
import mido
import asyncio
import json
import os
import time
import cloudscraper
import discord.ext.tasks as tasks
import io
import logging
from PIL import Image
from typing import List, Literal, Union
import discord
from discord import app_commands
from discord.ext import commands
import pycountry
import requests
from bs4 import BeautifulSoup

from bot import constants, database
from bot.tools.midi import MidiArchiveTools
from bot.tools.oauthmanager import OAuthManager
from bot.tracks import JamTrackHandler
from bot.tools.bestsellersrenderer import BestsellersRenderer

class TestCog(commands.Cog):
    def __init__(self, bot: constants.BotExt):
        self.bot = bot

    # Define the base 'test' group command
    test_group = app_commands.Group(name="test", description="Test commands", guild_only=True, guild_ids=[constants.TEST_GUILD])

    # we RAN OUT of commands???
    test2_group = app_commands.Group(name="test2", description="Test commands (cont'd)", guild_only=True, guild_ids=[constants.TEST_GUILD])

    @test_group.command(name="announcement", description="Announce a message to all subscribed users.")
    @app_commands.describe(message = "A text file. This contains the message content.")
    async def test_command(self, interaction: discord.Interaction, message: discord.Attachment, image: discord.Attachment = None, feed: Literal["added", "modified", "removed", "announcements", "best_sellers"] = None) : # type: ignore
        if not (interaction.user.id in constants.BOT_OWNERS):
            await interaction.response.send_message(content="You are not authorized to run this command.", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        logging.debug(f'[GET] {message.url}')
        text_content = requests.get(message.url).text
        # print(len(text_content))

        if image:
            logging.debug(f'[GET] {image.url}')
            
        png = io.BytesIO(requests.get(image.url).content) if image else None
        fname = image.filename if image else None

        bot_config: database.Config = self.bot.config
        all_channels = await bot_config.get_all()

        # Send a test message to all subscribed users
        for subscribed_channel in all_channels:
            channel: discord.User | discord.TextChannel | None = None
            if subscribed_channel.type == 'user':
                channel = self.bot.get_user(subscribed_channel.id)
            else:
                _channel = self.bot.get_channel(subscribed_channel.id)
                if isinstance(_channel, discord.TextChannel):
                    channel = _channel

            if feed:
                if not (feed in subscribed_channel.events):
                    logging.info(f'{subscribed_channel.type.capitalize()} {subscribed_channel.id} is not in feed {feed}, skipped')
                    continue

            if channel:
                try:
                    if png:
                        png.seek(0)
                        await channel.send(content=text_content, file=discord.File(png, filename=fname))
                    else:
                        await channel.send(content=text_content)
                except Exception as e:
                    logging.warning(f"Error sending message to {subscribed_channel.type} {channel.mention}", exc_info=e)
            else:
                logging.warning(f"{subscribed_channel.type} with ID {subscribed_channel.id} not found.")
                
        result_files = [discord.File(io.BytesIO(text_content.encode('utf-8')), "content.txt")]
        if png: 
            png.seek(0)
            result_files.append(discord.File(png, filename=fname))

        await interaction.followup.send(content="Test messages have been sent.\nSource attached below.", files=result_files)

    @test_group.command(name="all_subscriptions", description="View all subscriptions")
    async def all_subscriptions(self, interaction: discord.Interaction):
        if not (interaction.user.id in constants.BOT_OWNERS):
            await interaction.response.send_message(content="You are not authorized to run this command.", ephemeral=True)
            return
        
        await interaction.response.defer()

        bot_config: database.Config = self.bot.config

        chs = await bot_config.get_all()

        if len(chs) != 0:
            embeds = []
            for i in range(0, len(chs), 10):
                print(i)
                embed = discord.Embed(title="Results", colour=constants.ACCENT_COLOUR)
                chunk = chs[i:i + 10]
                embed.add_field(name="Subscriptions", value=f"{len(chs)} channel(s)", inline=False)
                txt = ''
                for sub in chunk:
                    txt += f"\nType {sub.type} ID {sub.id} Events {sub.events}"
                    if isinstance(sub, database.SubscriptionChannel):
                        txt += f' Roles {sub.roles}'
                
                embed.add_field(name="List", value=f'```{txt}```', inline=False)
                embeds.append(embed)

            view = constants.PaginatorView(embeds, interaction.user.id)
            view.message = await interaction.edit_original_response(embed=view.get_embed(), view=view)
        else:
            await interaction.edit_original_response(content="No subscriptions to show")

    @test_group.command(name="validate_users", description="Validate all users")
    async def validate_users(self, interaction: discord.Interaction):
        if not (interaction.user.id in constants.BOT_OWNERS):
            await interaction.response.send_message(content="You are not authorized to run this command.", ephemeral=True)
            return
        
        await interaction.response.defer()

        bot_config: database.Config = self.bot.config

        all_users = await bot_config.subscription_global('get_all_users')
        failed = []

        for u in all_users:
            if not self.bot.get_user(u.id):
                failed.append(u.id)
            
        if len(failed) != 0:
            embeds = []
            for i in range(0, len(failed), 10):
                embed = discord.Embed(title="Validation Results", colour=constants.ACCENT_COLOUR)
                chunk = failed[i:i + 10]
                embed.add_field(name="Failed", value=f"{len(failed)} user(s)", inline=False)
                embed.add_field(name="List", value="```" + "\n".join([str(id) for id in chunk]) + "```", inline=False)
                embed.add_field(name="Info", value=f"Any bot owner can type `delete` to delete all of these users within 30s", inline=False)
                embeds.append(embed)

            view = constants.PaginatorView(embeds, interaction.user.id)
            view.message = await interaction.edit_original_response(embed=view.get_embed(), view=view)
        else:
            await interaction.edit_original_response(content="No invalid users.")
            return

        def check(m: discord.Message):
            return (m.author.id in constants.BOT_OWNERS) and (interaction.channel is not None and m.channel.id == interaction.channel.id) and m.content == 'delete'

        try:
            msg = await self.bot.wait_for("message", check=check, timeout=30)
            for fid in failed:
                await bot_config.subscription_global('delete_users_with_query', query=f'WHERE user_id = {fid}')
            await msg.reply(mention_author=False, content=f"{len(failed)} users have been deleted")
        except TimeoutError:
            pass

    @test_group.command(name="validate_channels", description="Validate all channels")
    async def validate_channels(self, interaction: discord.Interaction):
        if not (interaction.user.id in constants.BOT_OWNERS):
            await interaction.response.send_message(content="You are not authorized to run this command.", ephemeral=True)
            return
        
        await interaction.response.defer()

        bot_config: database.Config = self.bot.config

        all_channels = await bot_config.subscription_global('get_all_channels')
        failed = []

        for u in all_channels:
            if not self.bot.get_channel(u.id):
                failed.append(u.id)
            
        if len(failed) != 0:
            embeds = []
            for i in range(0, len(failed), 10):
                embed = discord.Embed(title="Validation Results", colour=constants.ACCENT_COLOUR)
                chunk = failed[i:i + 10]
                embed.add_field(name="Failed", value=f"{len(failed)} channel(s)", inline=False)
                embed.add_field(name="List", value="```" + "\n".join([str(id) for id in chunk]) + "```", inline=False)
                embed.add_field(name="Info", value=f"Any bot owner can type `delete` to delete all of these channels within 30s", inline=False)
                embeds.append(embed)

            view = constants.PaginatorView(embeds, interaction.user.id)
            view.message = await interaction.edit_original_response(embed=view.get_embed(), view=view)
        else:
            await interaction.edit_original_response(content="No invalid channels.")
            return
            
        def check(m: discord.Message):
            return (m.author.id in constants.BOT_OWNERS) and (interaction.channel is not None and m.channel.id == interaction.channel.id) and m.content == 'delete'

        try:
            msg = await self.bot.wait_for("message", check=check, timeout=30)
            for fid in failed:
                await bot_config.subscription_global('delete_channels_with_query', query=f'WHERE channel_id = {fid}')
            await msg.reply(mention_author=False, content=f"{len(failed)} channels have been deleted")
        except TimeoutError:
            pass

    @test_group.command(name="force_analytics", description="Force analytics to run")
    async def force_analytics(self, interaction: discord.Interaction):
        if not (interaction.user.id in constants.BOT_OWNERS):
            await interaction.response.send_message(content="You are not authorized to run this command.", ephemeral=True)
            return
        
        await interaction.response.defer()
        await self.bot.analytics_task() # type: ignore
        await interaction.edit_original_response(content="Analytics have been run.")

    @test_group.command(name="server_list_csv", description="Get all guilds joined as a csv file")
    async def server_list_csv(self, interaction: discord.Interaction):
        if not (interaction.user.id in constants.BOT_OWNERS):
            await interaction.response.send_message(content="You are not authorized to run this command.", ephemeral=True)
            return
        
        await interaction.response.defer()

        guilds = self.bot.guilds
        csv = "ID,Name,Member Count,Date Joined\n"
        for guild in guilds:
            csv += f"{guild.id},{guild.name},{guild.member_count},{guild.me.joined_at}\n"

        await interaction.edit_original_response(content="", attachments=[discord.File(io.BytesIO(csv.encode()), "servers.csv")])

    @test_group.command(name="leave_guild", description="Leave a guild")
    @app_commands.describe(guild_id = "The ID of the guild to leave")
    async def leave_guild(self, interaction: discord.Interaction, guild_id: int):
        if not (interaction.user.id in constants.BOT_OWNERS):
            await interaction.response.send_message(content="You are not authorized to run this command.", ephemeral=True)
            return
        
        guild = self.bot.get_guild(guild_id)
        if not guild:
            await interaction.response.send_message(content=f"Guild with ID {guild_id} not found.", ephemeral=True)
            return
        
        await guild.leave()
        await interaction.edit_original_response(content=f"Successfully left {guild.name} (`{guild.id}`)")

    @test_group.command(name="debug_tasks", description="Debug all tasks")
    async def debug_tasks(self, interaction: discord.Interaction):        
        embed = discord.Embed(title="Task Debug", colour=constants.ACCENT_COLOUR)

        for task in constants.TASK_REGISTRY:
            next_iter = discord.utils.format_dt(task.next_iteration, 'R') if task.next_iteration else "N/A"
            next_iter_dt = discord.utils.format_dt(task.next_iteration, 'F') if task.next_iteration else "N/A"

            total_task_seconds_between_iters = int((task.hours * 3600) + (task.minutes * 60) + task.seconds)
            is_running = "Yes" if task.is_running() else "No"
            embed.add_field(name=task._name, value=
            f"Seconds Between Iterations: `{total_task_seconds_between_iters}s`\n" + 
            f"Running: `{is_running}`\n" +
            f"Current Iteration: `{task.current_loop}`\n" +
            f"Func Name: `{task.coro.__name__}`\n"
            f"Next Iteration: {next_iter} ({next_iter_dt})", inline=False)
        
        await interaction.response.send_message(embed=embed)

    @test_group.command(name="manage_task", description="Manage a task")
    async def manage_task(self, interaction: discord.Interaction, task: str, action: Literal['Cancel (Stop)', 'Start', 'Restart', 'Stop (Actual Stop)']):
        if not (interaction.user.id in constants.BOT_OWNERS):
            await interaction.response.send_message(content="You are not authorized to run this command.", ephemeral=True)
            return
        
        _task = discord.utils.find(lambda t: t._name.lower() == task.lower(), constants.TASK_REGISTRY)
        if not _task:
            await interaction.response.send_message(content=f"Task \"{task}\" not found.", ephemeral=True)
            return

        if action == 'Cancel (Stop)':
            _task.cancel()
        elif action == 'Start':
            _task.start()
        elif action == 'Restart':
            _task.restart()
        elif action == 'Stop (Actual Stop)':
            _task.stop()

        await interaction.response.send_message(content=f"{action} done on task \"{_task._name}\"")

    @manage_task.autocomplete('task')
    async def task_autocomplete(self, interaction: discord.Interaction, current: str):

        if current == '':
            return [
                app_commands.Choice(name=task._name, value=task._name) for task in constants.TASK_REGISTRY
            ]
        else:
            return [
                app_commands.Choice(name=task._name, value=task._name) for task in constants.TASK_REGISTRY if current.lower() in task._name.lower()
            ]
    
    @test_group.command(name="autocomplete", description="Test account username autocomplete")
    @app_commands.describe(username = "The Epic Account Username to search for")
    async def autocomplete(self, interaction: discord.Interaction, username: str):
        await interaction.response.send_message(content=f"Account id is: {username}")

    @autocomplete.autocomplete('username')
    async def autocomplete_callback(self, interaction: discord.Interaction, current: str):
        # Do stuff with the "current" parameter, e.g. querying it search results...

        oauth: OAuthManager = self.bot.oauth_manager
        try:
            account = oauth.search_users(current)
            return [
                app_commands.Choice(name='No results, please type your entire username.', value='NORESULTS')
            ]
        except Exception as e:
            logging.warning(f'Account {current} not found', exc_info=e)
            return [
                app_commands.Choice(name='No results, please type your entire username.', value='NORESULTS')
            ]

    @test_group.command(name="ini", description="Convert a track to ini")
    async def ini(self, interaction: discord.Interaction, song: str):
        tracklist = constants.get_jam_tracks()
        if not tracklist:
            await interaction.response.send_message(content=f"Could not get tracks.", ephemeral=True)
            return
        # Perform fuzzy search
        matched_tracks = JamTrackHandler().fuzzy_search_tracks(tracklist, song)
        if not matched_tracks:
            await interaction.response.send_message(content=f"The search query \"{song}\" did not yield any results.")
            return
        await interaction.response.defer()
        matched_track = matched_tracks[0]

        ini = '[song]\n'
        ini += f'name = {matched_track["track"]["tt"]}\n'
        ini += f'artist = {matched_track["track"]["an"]}\n'
        ini += f'album = Placeholder\n'
        ini += f'genre = Placeholder\n'
        ini += f'year = {matched_track["track"]["ry"]}\n'
        ini += f'song_length = {matched_track["track"]["dn"]}000\n'
        ini += f'charter = Harmonix\n'
        ini += f'diff_band = 0\n'
        ini += f'diff_guitar = 0\n'
        ini += f'diff_rhythm = 0\n'
        ini += f'diff_bass = 0\n'
        ini += f'diff_drums = 0\n'
        ini += f'diff_keys = 0\n'
        ini += f'diff_guitarghl = 0\n'
        ini += f'diff_rhythmghl = 0\n'
        ini += f'diff_bassghl = 0\n'
        ini += f'preview_start_time = 10000\n'
        ini += f'icon = 0\n'
        ini += f'playlist_track = \n'
        ini += f'delay = \n'
        ini += f'loading_phrase = \n'

        await interaction.edit_original_response(attachments=[discord.File(io.BytesIO(ini.encode()), 'song.ini')])

    @test_group.command(name="logdump", description="Get the last 100 lines of the log file")
    async def logdump(self, interaction: discord.Interaction):
        if not (interaction.user.id in constants.BOT_OWNERS):
            await interaction.response.send_message(content="You are not authorized to run this command.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)

        with open('cache/logs/FESTIVALTRACKERLOGS_V3.log', 'r', encoding='utf-8') as f:
            lines = f.readlines()[-100:]

        await interaction.edit_original_response(attachments=[discord.File(io.BytesIO(''.join(lines).encode()), 'log.txt')])

    @test_group.command(name="suball", description="Subscribe all subscribed channels to a specific feed")
    @app_commands.choices(
        feed=[
            app_commands.Choice(name=feed.value.english, value=feed.value.id) for feed in database.JamTrackEvents.get_all_events()
        ]
    )
    async def suball(self, interaction: discord.Interaction, feed: app_commands.Choice[str]):
        if not (interaction.user.id in constants.BOT_OWNERS):
            await interaction.response.send_message(content="You are not authorized to run this command.", ephemeral=True)
            return

        await interaction.response.defer()

        conf: database.Config = self.bot.config
        mod_count = 0

        all_channels = await conf.get_all()
        for ch in all_channels:
            events = ch.events
            events.append(feed.value)

            if ch.type == 'user':
                await conf.subscription_user('edit', user=discord.Object(ch.id), events=events)
            elif ch.type == 'channel':
                chan = self.bot.get_channel(ch.id)
                if not chan:
                    logging.warning(f'[Suball] Channel {ch.id} not found')
                    continue

                await conf._channel_edit_events(chan, events)

            mod_count+=1

        await interaction.edit_original_response(content=f"{mod_count} of {len(all_channels)} have been subbed to {feed.name} (`{feed.value}`)")

    @test_group.command(name="dbdump", description="Get a dump of the database")
    async def dbdump(self, interaction: discord.Interaction):
        if not (interaction.user.id in constants.BOT_OWNERS):
            await interaction.response.send_message(content="You are not authorized to run this command.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)

        f = open('festivaltracker.db', 'rb')
        data = f.read()
        f.close()

        # missing db-shm and db-wal here

        await interaction.edit_original_response(attachments=[discord.File(io.BytesIO(data), 'festivaltracker.db')])

    @test_group.command(name="send_dm", description="Send a private message to a user")
    async def pm(self, interaction: discord.Interaction, user_id: str, message: discord.Attachment):
        if not (interaction.user.id in constants.BOT_OWNERS):
            await interaction.response.send_message(content="You are not authorized to run this command.", ephemeral=True)
            return
        
        await interaction.response.defer()
        user = await self.bot.fetch_user(int(user_id))
        if not user:
            await interaction.edit_original_response(content=f"User with ID {user_id} not found.")
            return
        logging.debug(f'[GET] {message.url}')
        text_content = requests.get(message.url).text

        try:
            embed = discord.Embed(title="Festival Tracker Message", description="Hello, this is a message from a Festival Tracker developer:", colour=constants.ACCENT_COLOUR)
            embed.add_field(name="", value=text_content, inline=False)

            embed.set_thumbnail(url=interaction.client.user.display_avatar.url)
            embed.set_footer(text="Festival Tracker")

            await user.send(embed=embed)
            await interaction.edit_original_response(content=f"Message sent to {user.mention}")
        except Exception as e:
            logging.warning(f"Error sending message to User {user.mention}", exc_info=e)
            await interaction.edit_original_response(content=f"Failed to send message to {user.mention}")

    @test_group.command(name="bestsellers", description="Get the best selling Jam Tracks for all countries")
    async def bestsellers(self, interaction: discord.Interaction):
        embed = discord.Embed(colour=0xfcba03, title="Processing...")
        embed.add_field(name="Status", value="Starting...", inline=False)

        await interaction.response.send_message(embed=embed)

        url = "https://cdn2.unrealengine.com/fn_bsdata/ebb74910-dd35-44b8-b826-d58dc16c6456.json"
        print( f"[GET] {url} ")
        response = requests.get(url)
        bestsellers_data = response.json()

        country_best_sellers = {}

        for country, data in bestsellers_data.items():
            if country.startswith('bestsellers_list_'): # is a country
                offer_ids = data['offer_list']
                country_code = country.replace('bestsellers_list_', '')
                country_best_sellers[country_code] = offer_ids

        total_countries = len(country_best_sellers)

        logging.debug(f'[GET] {constants.FN_CATALOG}')
        headers = {
            'Authorization': self.bot.oauth_manager.session_token
        }
        response = requests.get(constants.FN_CATALOG, headers=headers)
        if response.status_code == 401 or response.status_code == 403:
            self.bot.oauth_manager._create_token()
            raise Exception('Please try again.')
        
        data = response.json()

        storefront = discord.utils.find(lambda storefront: storefront['name'] == 'BRWeeklyStorefront', data['storefronts'])
        shop_tracks = storefront['catalogEntries']
        
        jamtrack_bestellers = {}

        for country_code, data in country_best_sellers.items():
            country_name = ""
            try:
                country_name = pycountry.countries.get(alpha_2=country_code).name
            except Exception as e:
                country_name = f'Invalid({country_code})'

            for offer_id in data:
                offer_info = discord.utils.find(lambda item: item['offerId'] == offer_id, shop_tracks)
                if not offer_info:
                    continue

                jam_track_id = offer_info['meta']['templateId']
                if not jam_track_id.startswith('SparksSong:'):
                    continue

                rank = data.index(offer_id) + 1

                if jam_track_id not in jamtrack_bestellers:
                    jamtrack_bestellers[jam_track_id] = []

                jamtrack_bestellers[jam_track_id].append({
                    'country_code': country_code,
                    'country_name': country_name,
                    'rank': rank
                })

        all_jam_tracks = constants.get_jam_tracks(use_cache=True, max_cache_age=300)

        # final embed
        embed = discord.Embed(colour=constants.ACCENT_COLOUR, title="Jam Track Bestsellers")
        for jam_track_id, appearances in jamtrack_bestellers.items():
            track_info = discord.utils.find(lambda t: t['track']['ti'] == jam_track_id, all_jam_tracks)
            if not track_info:
                continue

            track_name = track_info['track']['tt']
            artist_name = track_info['track']['an']

            appearance_text = ''
            for appearance in appearances:
                r = appearance['rank']
                suffix = "tsnrhtdd"[((r//10%10!=1)*(r%10<4)*r%10)::4]

                appearance_text += f"\n- {appearance['country_name']}: {appearance['rank']}{suffix}"

            embed.add_field(name=f"**{track_name}** - *{artist_name}*", value=appearance_text, inline=False)

        await interaction.edit_original_response(embed=embed)

    @test_group.command(name="render_bestsellers", description="Render the bestsellers image")
    @app_commands.describe(cols = "Number of columns (default 4)")
    @app_commands.describe(auto = "Uses predetermined settings to generate the image. Overrides other parameters.")
    async def render_bestsellers(self, interaction: discord.Interaction, auto: bool = True, cols: int = 4):
        await interaction.response.defer()

        bestsellers_renderer: BestsellersRenderer = self.bot.bestsellers_renderer

        output_path = await bestsellers_renderer.capture_renderer_screenshot(auto=auto, cols=cols)
        if not output_path:
            await interaction.edit_original_response(content="Rendering the bestsellers image timed out.")
            return

        await interaction.edit_original_response(attachments=[discord.File(output_path, 'bestsellers_renderer.png')])

    @test_group.command(name="pro_vocals_json", description="Get all karaoke songs as a JSON array")
    async def pro_vocals_json(self, interaction: discord.Interaction):
        await interaction.response.defer()

        tracks = constants.get_jam_tracks(use_cache=True, max_cache_age=300)
        midi_tool = MidiArchiveTools()

        filtered_tracks = []
        for track in tracks:
            midi_url = track['track'].get('mu', '')
            if midi_url:
                midi_file = await midi_tool.save_chart(track['track']['mu'])
                if os.path.exists(midi_file):
                    with open(midi_file, 'rb') as mf:
                        if b'PRO VOCALS' in mf.read():
                            filtered_tracks.append(track)

        tracks = filtered_tracks

        track_list_json = []
        for track in tracks:
            track_list_json.append(track['track']['sn'])
        
        await interaction.edit_original_response(attachments=[discord.File(io.BytesIO(json.dumps(track_list_json, indent=4).encode()), 'pro_vocals_tracks.json')])

    @test_group.command(name="wipe_agreements_for_user", description="Wipe all agreements for a user")
    @app_commands.describe(user_id = "The user ID to wipe agreements for")
    async def wipe_agreements_for_user(self, interaction: discord.Interaction, user_id: str):
        if not (interaction.user.id in constants.BOT_OWNERS):
            await interaction.response.send_message(content="You are not authorized to run this command.", ephemeral=True)
            return

        await interaction.response.defer()

        agreement_data = constants.AGREEMENTS_DATA
        privacy_policy_version = agreement_data['privacy_policy']['version']
        terms_of_service_version = agreement_data['terms_of_service']['version']

        conf: database.Config = self.bot.config
        await conf.agreement(operation="update", user=discord.Object(int(user_id)), agreement_type="privacy_policy", agreement_version=privacy_policy_version, agreement_accepted=False)
        await conf.agreement(operation="update", user=discord.Object(int(user_id)), agreement_type="terms_of_service", agreement_version=terms_of_service_version, agreement_accepted=False)

        await interaction.edit_original_response(content=f"Agreements wiped for user <@{user_id}>")

    @test_group.command(name="compare_midi_generations", description="Compare the midi generations of a song")
    @app_commands.describe(shortname = "The shortname of the song to compare")
    async def compare_midi_generations(self, interaction: discord.Interaction, shortname: str):
        await interaction.response.defer()

        jam_tracks = constants.get_jam_tracks(use_cache=True)
        track = discord.utils.find(lambda t: t['track']['sn'] == shortname, jam_tracks)
        if not track:
            await interaction.edit_original_response(content="Track not found")
            return

        json_files = [f for f in os.listdir(constants.LOCAL_JSON_FOLDER) if f.endswith('.json')]
        json_files.sort(key=lambda x: os.path.getmtime(os.path.join(constants.LOCAL_JSON_FOLDER, x)))
        
        midi_tool = MidiArchiveTools()
        midi_url_list = [] # also the "generations"
        for json_file in json_files:
            file_path = os.path.join(constants.LOCAL_JSON_FOLDER, json_file)
            file_content = open(file_path, 'r').read()

            # easy skip
            if shortname not in file_content:
                continue

            file_data = json.loads(file_content)
            # print(file_data.keys())
            # find the jam track
            for key in file_data.keys():
                if not key.startswith('_') and key != 'lastModified': # a jam track
                    song = file_data[key]
                    # print(song)
                    if song['track']['sn'] == shortname: # the song
                        midi_url = song['track']['mu']
                        if midi_url not in midi_url_list:
                            midi_url_list.append(midi_url)
                        break

        last_generation = midi_url_list[-1]
        before_last_generation = None
        try:
            before_last_generation = midi_url_list[-2]
        except IndexError:
            before_last_generation = last_generation
            
        midis = {}

        for midi_url in [before_last_generation, last_generation]:
            midi_file = await midi_tool.save_chart(midi_url)
            if not os.path.exists(midi_file):
                continue
            
            mido_parse = mido.MidiFile(midi_file)
            mido_eventlist_as_repr = []
            for track in mido_parse.tracks:
                for msg in track:
                    mido_eventlist_as_repr.append(repr(msg))

            midis[midi_url] = mido_eventlist_as_repr

        import difflib

        old_lines = midis[before_last_generation]
        new_lines = midis[last_generation]

        diff = difflib.unified_diff(
            old_lines, new_lines,
            fromfile=before_last_generation,
            tofile=last_generation,
            lineterm=''
        )

        end_string = "\n".join(diff)

        print(end_string)

        await interaction.edit_original_response(attachments=[discord.File(io.BytesIO(end_string.encode()), 'diff.txt')])

    @test_group.command(name="brand", description="Generates brand assets for a given colour.")
    @app_commands.describe(red = "Red (0-255) - Leave None for current accent colour.")
    @app_commands.describe(green = "Green (0-255) - Leave None for current accent colour.")
    @app_commands.describe(blue = "Blue (0-255) - Leave None for current accent colour.")
    async def brand(self, interaction: discord.Interaction, red: app_commands.Range[int, 0, 255] = None, green: app_commands.Range[int, 0, 255] = None, blue: app_commands.Range[int, 0, 255] = None):
        await interaction.response.defer()
        
        if red is None or green is None or blue is None:
            primary_colour = constants.SEASON_COLOUR_COPY
        else:
            primary_colour = (red, green, blue)

        # try to import brand script
        try:
            from bot.tools import brand as brand_module
        except Exception as e:
            await interaction.edit_original_response(content=f"Error: {e}\nYou are probably missing the brand module.")
            return

        print("Generating brand assets...")
        print("Generating Discord PNG pfp...")
        await asyncio.to_thread(brand_module.make_discord_pfp, primary_colour, "discord_pfp.png")
        print("Generating Discord animated pfp...")
        await asyncio.to_thread(brand_module.make_discord_pfp_anim, primary_colour, "discord_pfp.webp", size=512)
        # convert animated webp to GIF (also ensures its below 5 mb)
        await asyncio.to_thread(lambda: Image.open("discord_pfp.webp").save("discord_pfp.gif", format="GIF", save_all=True, optimize=True))
        await asyncio.to_thread(brand_module.make_twitter_pfp, primary_colour, "twitter_pfp.png")
        print("Generating Discord PNG banner...")
        await asyncio.to_thread(brand_module.make_discord_banner, primary_colour, "discord_banner.png")
        print("Generating Twitter banner...")
        await asyncio.to_thread(brand_module.make_twitter_banner, primary_colour, "twitter_banner.png")

        # invert the primary colour
        inverted_color = tuple(255 - c for c in primary_colour)
        await asyncio.to_thread(brand_module.make_discord_pfp, inverted_color, "discord_pfp_dev.png")
        
        await interaction.edit_original_response(content="Done!", attachments=[
            discord.File("discord_pfp.png"), 
            discord.File("discord_pfp.webp"),
            discord.File("discord_pfp.gif"),
            discord.File("twitter_pfp.png"), 
            discord.File("discord_banner.png"), 
            discord.File("twitter_banner.png"), 
            discord.File("discord_pfp_dev.png")
        ])

    @test_group.command(name="force_bsellnotifhash_out_of_sync", description="Forces the bestsellers notification hash to be out of sync to test the notification.")
    async def force_bsells_notif_hash_out_of_sync(self, interaction: discord.Interaction):
        await interaction.response.defer()

        self.bot.bestsellers_renderer.last_notified_hash = 'test'

        await interaction.edit_original_response(content="Done!")

    @test2_group.command(name="packages_versions", description="Lists the versions of the packages used in the bot.")
    async def packages_versions(self, interaction: discord.Interaction):
        await interaction.response.defer()

        packages = constants.get_loaded_package_versions()
        packages_str = "\n".join([f"{package}: {version}" for package, version in packages.items()])
        await interaction.edit_original_response(attachments=[discord.File(io.BytesIO(packages_str.encode()), 'packages_versions.txt')])