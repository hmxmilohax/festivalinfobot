import asyncio
import json
import os
import time
import cloudscraper
import discord.ext.tasks as tasks
import io
import logging
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
from bot.leaderboard import LeaderboardPaginatorView, BandLeaderboardView, AllTimeLeaderboardView

# jnack and tpose's personal commands
class TestCog(commands.Cog):
    def __init__(self, bot: constants.BotExt):
        self.bot = bot

    # Define the base 'admin' group command
    test_group = app_commands.Group(name="test", description="Test commands", guild_only=True, guild_ids=[constants.TEST_GUILD])

    @test_group.command(name="announcement", description="Announce a message to all subscribed users.")
    @app_commands.describe(message = "A text file. This contains the message content.")
    async def test_command(self, interaction: discord.Interaction, message: discord.Attachment, image: discord.Attachment = None, feed: Literal["added", "modified", "removed", "announcements"] = None) : # type: ignore
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

        all_users = await bot_config._users()
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
                await bot_config._del_users_with_query(f'WHERE user_id = {fid}')
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

        all_channels = await bot_config._channels()
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
                await bot_config._del_channels_with_query(f'WHERE channel_id = {fid}')
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
        if not (interaction.user.id in constants.BOT_OWNERS):
            await interaction.response.send_message(content="You are not authorized to run this command.", ephemeral=True)
            return
        
        text = "Tasks debug"
        check: tasks.Loop = self.bot.utility_loop_task # type: ignore
        text += f"\nUtility: \n{check.minutes = }m\n{check.is_running() = }\n{check.current_loop = }"
        activity: tasks.Loop = self.bot.activity_task # type: ignore
        text += f"\nActivity: \n{activity.minutes = }m\n{activity.is_running() = }\n{activity.current_loop = }"
        analytic: tasks.Loop = self.bot.analytic_loop # type: ignore
        text += f"\nAnalytic: \n{analytic.minutes = }m\n{analytic.is_running() = }\n{analytic.current_loop = }"
        oauth_refresh: tasks.Loop = self.bot.oauth_manager.refresh_session # type: ignore
        text += f"\nOauth Refresh: \n{oauth_refresh.seconds = }s\n{oauth_refresh.is_running() = }\n{oauth_refresh.current_loop = }"
        oauth_verify: tasks.Loop = self.bot.oauth_manager.verify_session # type: ignore
        text += f"\nOauth Verify: \n{oauth_verify.seconds = }s\n{oauth_verify.is_running() = }\n{oauth_verify.current_loop = }"
        
        await interaction.response.send_message(content=text)

    @test_group.command(name="stop_task", description="Stop a task (doesnt use .stop rather .cancel)")
    async def stop_task(self, interaction: discord.Interaction, task: Literal["Analytics", "Utility", "Activity", "Verify OAuth", "Refresh OAuth"]):
        if not (interaction.user.id in constants.BOT_OWNERS):
            await interaction.response.send_message(content="You are not authorized to run this command.", ephemeral=True)
            return
        
        check: tasks.Loop = self.bot.utility_loop_task
        activity: tasks.Loop = self.bot.activity_task
        analytic: tasks.Loop = self.bot.analytic_loop
        oauth_refresh: tasks.Loop = self.bot.oauth_manager.refresh_session
        oauth_verify: tasks.Loop = self.bot.oauth_manager.verify_session

        if task == 'Check':
            check.cancel()
        elif task == 'Utility':
            activity.cancel()
        elif task == 'Analytics':
            analytic.cancel()
        elif task == 'Verify OAuth':
            oauth_verify.cancel()
        elif task == 'Refresh OAuth':
            oauth_refresh.cancel()

        await interaction.response.send_message(content=f"Task \"{task}\" stopped")

    @test_group.command(name="start_task", description="Start a task")
    async def start_task(self, interaction: discord.Interaction, task: Literal["Analytics", "Utility", "Activity", "Verify OAuth", "Refresh OAuth"]):
        if not (interaction.user.id in constants.BOT_OWNERS):
            await interaction.response.send_message(content="You are not authorized to run this command.", ephemeral=True)
            return
        
        check: tasks.Loop = self.bot.utility_loop_task
        activity: tasks.Loop = self.bot.activity_task
        analytic: tasks.Loop = self.bot.analytic_loop
        oauth_refresh: tasks.Loop = self.bot.oauth_manager.refresh_session
        oauth_verify: tasks.Loop = self.bot.oauth_manager.verify_session

        if task == 'Check':
            check.start()
        elif task == 'Activity':
            activity.start()
        elif task == 'Analytics':
            analytic.start()
        elif task == 'Verify OAuth':
            oauth_verify.start()
        elif task == 'Refresh OAuth':
            oauth_refresh.start()

        await interaction.response.send_message(content=f"Task \"{task}\" started")

    @test_group.command(name="restart_task", description="Restart a task (only reinitates it, doesnt start it if cancelled)")
    async def restart_task(self, interaction: discord.Interaction, task: Literal["Analytics", "Utility", "Activity", "Verify OAuth", "Refresh OAuth"]):
        if not (interaction.user.id in constants.BOT_OWNERS):
            await interaction.response.send_message(content="You are not authorized to run this command.", ephemeral=True)
            return
        
        check: tasks.Loop = self.bot.utility_loop_task
        activity: tasks.Loop = self.bot.activity_task
        analytic: tasks.Loop = self.bot.analytic_loop

        if task == 'Check':
            check.restart()
        elif task == 'Activity':
            activity.restart()
        elif task == 'Analytics':
            analytic.restart()
        elif task == 'Verify OAuth':
            self.bot.oauth_manager.verify_session.restart()
        elif task == 'Refresh OAuth':
            self.bot.oauth_manager.refresh_session.restart()

        await interaction.response.send_message(content=f"Task \"{task}\" restarted")

    @test_group.command(name="error", description="Invoke an error")
    async def error(self, interaction: discord.Interaction):
        if not (interaction.user.id in constants.BOT_OWNERS):
            await interaction.response.send_message(content="You are not authorized to run this command.", ephemeral=True)
            return
        
        raise ValueError("Error invoked here")
    
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
            await interaction.response.send_message(content=f"The search query \"{song}\" did not give any results.")
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

    @test_group.command(name="isrc", description="Get the spotify link from an isrc query")
    async def isrc(self, interaction: discord.Interaction, isrc: str):
        await interaction.response.defer()
        jt_handler = JamTrackHandler()
        link = jt_handler.get_spotify_link(isrc)
        if not link:
            link = 'invalid'

        await interaction.edit_original_response(content=link)

    @test_group.command(name="suball", description="Subscribe all subscribed channels to a specific feed")
    async def suball(self, interaction: discord.Interaction, feed: Literal["added", "modified", "removed", "announcements"]):
        if not (interaction.user.id in constants.BOT_OWNERS):
            await interaction.response.send_message(content="You are not authorized to run this command.", ephemeral=True)
            return

        await interaction.response.defer()

        conf: database.Config = self.bot.config

        mod_count = 0

        all_channels = await conf.get_all()
        for ch in all_channels:
            events = ch.events
            events.append('announcements')

            if ch.type == 'user':
                await conf._user_edit_events(discord.Object(ch.id), events)
                mod_count+=1
            elif ch.type == 'channel':
                chan = self.bot.get_channel(ch.id)
                if not chan:
                    logging.warning(f'[Suball] Channel {ch.id} not found')
                    continue

                await conf._channel_edit_events(chan, events)
                mod_count+=1

        await interaction.edit_original_response(content=f"{mod_count} of {len(all_channels)} have been subbed to {feed}")

    @test_group.command(name="dbdump", description="Get a dump of the database")
    async def dbdump(self, interaction: discord.Interaction):
        if not (interaction.user.id in constants.BOT_OWNERS):
            await interaction.response.send_message(content="You are not authorized to run this command.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)

        f = open('subscriptions.db', 'rb')
        data = f.read()
        f.close()

        await interaction.edit_original_response(attachments=[discord.File(io.BytesIO(data), 'subscriptions.db')])
    @test_group.command(name="pm", description="Send a private message to a user")
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

        logging.debug(f'[GET] {constants.SHOP_API}')
        headers = {
            'Authorization': self.bot.oauth_manager.session_token
        }
        response = requests.get(constants.SHOP_API, headers=headers)
        if response.status_code == 401 or response.status_code == 403:
            self.bot.oauth_manager._create_token()
            raise Exception('Please try again.')
        
        data = response.json()

        storefront = discord.utils.find(lambda storefront: storefront['name'] == 'BRWeeklyStorefront', data['storefronts'])
        shop_tracks = storefront['catalogEntries']

        # open('shop_data.json', 'w', encoding='utf-8').write(json.dumps(shop_tracks, indent=4))
        
        jamtrack_bestellers = {}

        for country_code, data in country_best_sellers.items():
            country_name = pycountry.countries.get(alpha_2=country_code).name

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

    @test_group.command(name="pro_vocals_json", description="Get all pro vocals songs as a JSON array")
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