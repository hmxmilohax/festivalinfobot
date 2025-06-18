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

# jnack and tpose's personal commands
class TestCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Define the base 'admin' group command
    test_group = app_commands.Group(name="test", description="Test commands", guild_only=True, guild_ids=[constants.TEST_GUILD])

    @test_group.command(name="suggestions", description="Change if suggestions are enabled or not.")
    async def set_suggestions_command(self, interaction: discord.Interaction, enabled: bool):
        if not (interaction.user.id in constants.BOT_OWNERS):
            await interaction.response.send_message(content="You are not authorized to run this command.", ephemeral=True)
            return
        
        text = f"Suggestions are now turned {'ON' if enabled else 'OFF'}. Previously, they were {'ON' if self.bot.suggestions_enabled else 'OFF'}."
        self.bot.suggestions_enabled = enabled
        await interaction.response.send_message(content=text, ephemeral=True)

    @test_group.command(name="emit", description="Emit a message to all subscribed users.")
    @app_commands.describe(message = "A text file. This contains the message content.")
    async def test_command(self, interaction: discord.Interaction, message: discord.Attachment, image: discord.Attachment = None):
        if not (interaction.user.id in constants.BOT_OWNERS):
            await interaction.response.send_message(content="You are not authorized to run this command.", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        logging.debug(f'[GET] {message.url}')
        text_content = requests.get(message.url).text

        if image:
            logging.debug(f'[GET] {image.url}')
            
        png = io.BytesIO(requests.get(image.url).content) if image else None
        fname = image.filename if image else None

        bot_config: config.Config = self.bot.config
        all_channels = await bot_config.get_all()

        # Send a test message to all subscribed users
        for subscribed_channel in all_channels:
            channel: Union[discord.User, discord.TextChannel] = None
            if subscribed_channel.type == 'user':
                channel = self.bot.get_user(subscribed_channel.id)
            else:
                channel = self.bot.get_channel(subscribed_channel.id)

            if channel:
                try:
                    if png:
                        png.seek(0)
                    await channel.send(content=text_content, file=discord.File(png, filename=fname) if png else None)
                except Exception as e:
                    logging.error(f"Error sending message to {subscribed_channel.type} {channel.mention}", exc_info=e)
            else:
                logging.error(f"{subscribed_channel.type} with ID {subscribed_channel.id} not found.")
                
        result_files = [discord.File(io.StringIO(text_content), "content.txt")]
        if png: 
            png.seek(0)
            result_files.append(discord.File(png, filename=fname))

        await interaction.followup.send(content="Test messages have been sent.\nSource attached below.", files=result_files)

    delete_group = app_commands.Group(name="delete", description="Delete commands", parent=test_group, guild_ids=[constants.TEST_GUILD])
    
    @delete_group.command(name="channel_where", description="Delete a channel where guild_id = ? or channel_id = ?")
    async def channel_where(self, interaction: discord.Interaction, guild_id: str = None, channel_id: str = None):
        if not (interaction.user.id in constants.BOT_OWNERS):
            await interaction.response.send_message(content="You are not authorized to run this command.", ephemeral=True)
            return
        
        if (not guild_id) and (not channel_id):
            await interaction.response.send_message(content="Please specify at least one query parameter")

        await interaction.response.defer()

        bot_config: config.Config = self.bot.config

        if guild_id and channel_id:
            count = await bot_config._count_channels_with_query(f'WHERE guild_id = {guild_id} AND channel_id = {channel_id}')
            chs = await bot_config._sel_channels_with_query(f'WHERE guild_id = {guild_id} AND channel_id = {channel_id}')
        elif guild_id:
            count = await bot_config._count_channels_with_query(f'WHERE guild_id = {guild_id}')
            chs = await bot_config._sel_channels_with_query(f'WHERE guild_id = {guild_id}')
        elif channel_id:
            count = await bot_config._count_channels_with_query(f'WHERE channel_id = {channel_id}')
            chs = await bot_config._sel_channels_with_query(f'WHERE channel_id = {channel_id}')

        if count != 0:
            embeds = []
            for i in range(0, len(chs), 10):
                print(i)
                embed = discord.Embed(title="Deletion Results", color=0x8927A1)
                chunk = chs[i:i + 10]
                embed.add_field(name="Deleted", value=f"{count} channel(s)", inline=False)
                embed.add_field(name="List", value="```" + "\n".join([f"ID {ch.id} Events {ch.events} Roles {ch.roles}" for ch in chunk]) + "```", inline=False)
                embeds.append(embed)

            view = constants.PaginatorView(embeds, interaction.user.id)
            view.message = await interaction.edit_original_response(embed=view.get_embed(), view=view)

            if guild_id and channel_id:
                await bot_config._del_channels_with_query(f'WHERE guild_id = {guild_id} AND channel_id = {channel_id}')
            elif guild_id:
                await bot_config._del_channels_with_query(f'WHERE guild_id = {guild_id}')
            elif channel_id:
                await bot_config._del_channels_with_query(f'WHERE channel_id = {channel_id}')
        else:
            await interaction.edit_original_response(content="No channels to delete")

    @test_group.command(name="all_subscriptions", description="View all subscriptions")
    async def all_subscriptions(self, interaction: discord.Interaction):
        if not (interaction.user.id in constants.BOT_OWNERS):
            await interaction.response.send_message(content="You are not authorized to run this command.", ephemeral=True)
            return
        
        await interaction.response.defer()

        bot_config: config.Config = self.bot.config

        chs = await bot_config.get_all()

        if len(chs) != 0:
            embeds = []
            for i in range(0, len(chs), 10):
                print(i)
                embed = discord.Embed(title="Results", color=0x8927A1)
                chunk = chs[i:i + 10]
                embed.add_field(name="Subscriptions", value=f"{len(chs)} channel(s)", inline=False)
                txt = ''
                for sub in chunk:
                    txt += f"\nType {sub.type} ID {sub.id} Events {sub.events}"
                    if isinstance(sub, config.SubscriptionChannel):
                        txt += f' Roles {sub.roles}'
                
                embed.add_field(name="List", value=f'```{txt}```', inline=False)
                embeds.append(embed)

            view = constants.PaginatorView(embeds, interaction.user.id)
            view.message = await interaction.edit_original_response(embed=view.get_embed(), view=view)
        else:
            await interaction.edit_original_response(content="No subscriptions to show")

    @delete_group.command(name="user_where", description="Delete a channel where user_id = ?")
    async def user_where(self, interaction: discord.Interaction, user_id: str):
        if not (interaction.user.id in constants.BOT_OWNERS):
            await interaction.response.send_message(content="You are not authorized to run this command.", ephemeral=True)
            return
        
        await interaction.response.defer()

        bot_config: config.Config = self.bot.config

        count = await bot_config._count_users_with_query(f'WHERE user_id = {user_id}')
        chs = await bot_config._sel_users_with_query(f'WHERE user_id = {user_id}')

        if count != 0:
            embeds = []
            for i in range(0, len(chs), 10):
                embed = discord.Embed(title="Deletion Results", color=0x8927A1)
                chunk = chs[i:i + 10]
                embed.add_field(name="Deleted", value=f"{count} user(s)", inline=False)
                embed.add_field(name="List", value="```" + "\n".join([f"ID {ch.id} Events {ch.events}" for ch in chunk]) + "```", inline=False)
                embeds.append(embed)

            view = constants.PaginatorView(embeds, interaction.user.id)
            view.message = await interaction.edit_original_response(embed=view.get_embed(), view=view)

            await bot_config._del_users_with_query(f'WHERE user_id = {user_id}')
        else:
            await interaction.edit_original_response(content="No users to delete")

    @test_group.command(name="validate_users", description="Validate all users")
    async def validate_users(self, interaction: discord.Interaction):
        if not (interaction.user.id in constants.BOT_OWNERS):
            await interaction.response.send_message(content="You are not authorized to run this command.", ephemeral=True)
            return
        
        await interaction.response.defer()

        bot_config: config.Config = self.bot.config

        all_users = await bot_config._users()
        failed = []

        for u in all_users:
            if not self.bot.get_user(u.id):
                failed.append(u.id)
            
        if len(failed) != 0:
            embeds = []
            for i in range(0, len(failed), 10):
                embed = discord.Embed(title="Validation Results", color=0x8927A1)
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
            return (m.author.id in constants.BOT_OWNERS) and (m.channel.id == interaction.channel.id) and m.content == 'delete'

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

        bot_config: config.Config = self.bot.config

        all_channels = await bot_config._channels()
        failed = []

        for u in all_channels:
            if not self.bot.get_channel(u.id):
                failed.append(u.id)
            
        if len(failed) != 0:
            embeds = []
            for i in range(0, len(failed), 10):
                embed = discord.Embed(title="Validation Results", color=0x8927A1)
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
            return (m.author.id in constants.BOT_OWNERS) and (m.channel.id == interaction.channel.id) and m.content == 'delete'

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
        await self.bot.analytics_task()
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

        await interaction.edit_original_response(content="", attachments=[discord.File(io.StringIO(csv), "servers.csv")])

    @test_group.command(name="leave_guild", description="Leave a guild")
    @app_commands.describe(guild_id = "The ID of the guild to leave")
    async def leave_guild(self, interaction: discord.Interaction, guild_id: int):
        if not (interaction.user.id in constants.BOT_OWNERS):
            await interaction.response.send_message(content="You are not authorized to run this command.", ephemeral=True)
            return
        
        guild = self.bot.get_guild(guild_id)
        await guild.leave()
        await interaction.edit_original_response(content=f"Successfully left {guild.name} (`{guild.id}`)")

    @test_group.command(name="debug_tasks", description="Debug all tasks")
    async def debug_tasks(self, interaction: discord.Interaction):
        if not (interaction.user.id in constants.BOT_OWNERS):
            await interaction.response.send_message(content="You are not authorized to run this command.", ephemeral=True)
            return
        
        text = "Tasks debug"
        check: tasks.Loop = self.bot.check_new_songs_task
        text += f"\nCheck for new songs: \n- Interval: {check.minutes}m\n- Is Running: {check.is_running()}\n- Iter: {check.current_loop}"
        activity: tasks.Loop = self.bot.activity_task
        text += f"\nActivity: \n- Interval: {activity.minutes}m\n- Is Running: {activity.is_running()}\n- Iter: {activity.current_loop}"
        analytic: tasks.Loop = self.bot.analytic_loop
        text += f"\nAnalytics: \n- Interval: {analytic.hours}h\n- Is Running: {analytic.is_running()}\n- Iter: {analytic.current_loop}"
        
        await interaction.response.send_message(content=text)

    @test_group.command(name="stop_task", description="Stop a task (doesnt use .stop rather .cancel)")
    async def stop_task(self, interaction: discord.Interaction, task: Literal["Analytics", "Check", "Activity"]):
        if not (interaction.user.id in constants.BOT_OWNERS):
            await interaction.response.send_message(content="You are not authorized to run this command.", ephemeral=True)
            return
        
        check: tasks.Loop = self.bot.check_new_songs_task
        activity: tasks.Loop = self.bot.activity_task
        analytic: tasks.Loop = self.bot.analytic_loop

        if task == 'Check':
            check.cancel()
        elif task == 'Activity':
            activity.cancel()
        elif task == 'Analytics':
            analytic.cancel()

        await interaction.response.send_message(content=f"Task \"{task}\" stopped")

    @test_group.command(name="start_task", description="Start a task")
    async def stop_task(self, interaction: discord.Interaction, task: Literal["Analytics", "Check", "Activity"]):
        if not (interaction.user.id in constants.BOT_OWNERS):
            await interaction.response.send_message(content="You are not authorized to run this command.", ephemeral=True)
            return
        
        check: tasks.Loop = self.bot.check_new_songs_task
        activity: tasks.Loop = self.bot.activity_task
        analytic: tasks.Loop = self.bot.analytic_loop

        if task == 'Check':
            check.start()
        elif task == 'Activity':
            activity.start()
        elif task == 'Analytics':
            analytic.start()

        await interaction.response.send_message(content=f"Task \"{task}\" started")

    @test_group.command(name="restart_task", description="Restart a task (only reinitates it, doesnt start it if cancelled)")
    async def stop_task(self, interaction: discord.Interaction, task: Literal["Analytics", "Check", "Activity"]):
        if not (interaction.user.id in constants.BOT_OWNERS):
            await interaction.response.send_message(content="You are not authorized to run this command.", ephemeral=True)
            return
        
        check: tasks.Loop = self.bot.check_new_songs_task
        activity: tasks.Loop = self.bot.activity_task
        analytic: tasks.Loop = self.bot.analytic_loop

        if task == 'Check':
            check.restart()
        elif task == 'Activity':
            activity.restart()
        elif task == 'Analytics':
            analytic.restart()

        await interaction.response.send_message(content=f"Task \"{task}\" restarted")

    @test_group.command(name="error", description="Invoke an error")
    async def stop_task(self, interaction: discord.Interaction):
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
            logging.error(f'Account {current} not found', exc_info=e)
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

        await interaction.edit_original_response(attachments=[discord.File(io.StringIO(ini), 'song.ini')])

    @test_group.command(name="logdump", description="Get the last 100 lines of the log file")
    async def logdump(self, interaction: discord.Interaction):
        if not (interaction.user.id in constants.BOT_OWNERS):
            await interaction.response.send_message(content="You are not authorized to run this command.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)

        with open('logs/festivalinfobot.log', 'r', encoding='utf-8') as f:
            lines = f.readlines()[-100:]

        await interaction.edit_original_response(attachments=[discord.File(io.StringIO(''.join(lines)), 'log.txt')])

    @test_group.command(name="isrc", description="Get the spotify link from an isrc query")
    async def isrc(self, interaction: discord.Interaction, isrc: str):
        await interaction.response.defer()
        jt_handler = JamTrackHandler()
        link = jt_handler.get_spotify_link(isrc, str(interaction.user.id))
        if not link:
            link = 'invalid'

        await interaction.edit_original_response(content=link)