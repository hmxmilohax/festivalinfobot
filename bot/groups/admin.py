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
from bot.tracks import JamTrackHandler

class AdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config: config.Config = self.bot.config

    # Define the base 'admin' group command
    admin_group = app_commands.Group(name="admin", description="Admin commands", guild_only=True)

    async def set_channel_subscription(self, interaction: discord.Interaction, channel: discord.channel.TextChannel, remove: bool = False) -> bool:
        channel_exists = await self.config._channel_exists(channel=channel)

        if remove:
            if not channel_exists:
                await interaction.response.send_message(f"The channel {channel.mention} is not subscribed.")
                return False
            else:
                await self.config._channel_remove(channel=channel)
                return True
        else:
            if channel_exists:
                channel_events = await self.config._channel_events(channel=channel)
                if len(channel_events) == len(config.JamTrackEvent.get_all_events()):
                    await interaction.response.send_message(f"The channel {channel.mention} is already subscribed to all Jam Track events.")
                else:
                    await interaction.response.send_message(f"The channel {channel.mention} is already subscribed to the events \"{'\", \"'.join([constants.EVENT_NAMES[event] for event in channel_events])}\".")
                
                return False
            else:
                await self.config._channel_add(channel=channel)
                return True

        return False

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
            
        # Possible, "Embed Links", "Attach Files?"

        return True

    @admin_group.command(name="subscribe", description="Subscribe a channel to Jam Track events")
    @app_commands.describe(channel = "The channel to send Jam Track events to.")
    @app_commands.checks.has_permissions(administrator=True)
    async def subscribe(self, interaction: discord.Interaction, channel: discord.channel.TextChannel):
        # raise ValueError("No more festival tracker!!")

        permission_result = await self.check_permissions(interaction=interaction, channel=channel)
        if not permission_result:
            return
        
        subscription_result = await self.set_channel_subscription(interaction=interaction, channel=channel, remove=False)
        if not subscription_result:
            return
        
        # Reaction stuff to check if the channel works
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

    add_subcommand_group = app_commands.Group(name="add", description="Add commands", parent=admin_group)
    remove_subcommand_group = app_commands.Group(name="remove", description="Add commands", parent=admin_group)

    @add_subcommand_group.command(name="event", description="Add a Jam Track event to a channel")
    @app_commands.describe(channel = "The channel to add a Jam Track event to")
    @app_commands.describe(event = "The event to add")
    @app_commands.checks.has_permissions(administrator=True)
    async def add_event(self, interaction: discord.Interaction, channel: discord.channel.TextChannel, event: config.JamTrackEvent):
        channel_exists = await self.config._channel_exists(channel=channel)
        chosen_event = config.JamTrackEvent[str(event).replace('JamTrackEvent.', '')]

        if not channel_exists:
            # Only check for permissions if the channel is added
            permission_result = await self.check_permissions(interaction=interaction, channel=channel)
            if not permission_result:
                return

            await self.config._channel_add_with_event(channel=channel, event=chosen_event)
            await interaction.response.send_message(f'The channel {channel.mention} has been subscribed with the event "{constants.EVENT_NAMES[chosen_event.value]}".')
        else:
            subscribed_events = await self.config._channel_events(channel=channel)
            if chosen_event.value in subscribed_events:
                await interaction.response.send_message(f'The channel {channel.mention} is already subscribed to the event "{constants.EVENT_NAMES[chosen_event.value]}".')
                return
            else:
                await self.config._channel_add_event(channel=channel, event=chosen_event)
                await interaction.response.send_message(f'The channel {channel.mention} has been subscribed to the event "{constants.EVENT_NAMES[chosen_event.value]}".')

    @remove_subcommand_group.command(name="event", description="Remove a Jam Track event from a channel")
    @app_commands.describe(channel = "The channel to remove a Jam Track event from")
    @app_commands.describe(event = "The event to remove")
    @app_commands.checks.has_permissions(administrator=True)
    async def remove_event(self, interaction: discord.Interaction, channel: discord.channel.TextChannel, event: config.JamTrackEvent):
        channel_exists = await self.config._channel_exists(channel=channel)
        chosen_event = config.JamTrackEvent[str(event).replace('JamTrackEvent.', '')]

        if not channel_exists:
            await interaction.response.send_message(f'The channel {channel.mention} is not subscribed to any events.')
        else:
            subscribed_events = await self.config._channel_events(channel=channel)
            if chosen_event.value in subscribed_events:
                subscribed_events.remove(chosen_event.value)
                if len(subscribed_events) == 0:
                    await self.config._channel_remove(channel=channel)
                    await interaction.response.send_message(f"The channel {channel.mention} has been removed from the subscription list because it is no longer subscribed to any events.")
                else:
                    await self.config._channel_remove_event(channel=channel, event=chosen_event)
                    await interaction.response.send_message(f'The channel {channel.mention} has been unsubscribed from the event "{constants.EVENT_NAMES[chosen_event.value]}".')
            else:
                await interaction.response.send_message(f'The channel {channel.mention} is not subscribed to the event "{constants.EVENT_NAMES[chosen_event.value]}".')

    @add_subcommand_group.command(name="role", description="Add a role ping to a channel's subscription messages")
    @app_commands.describe(channel = "The channel to add a role ping to")
    @app_commands.describe(role = "The role to add a ping for")
    @app_commands.checks.has_permissions(administrator=True)
    async def add_role(self, interaction: discord.Interaction, channel: discord.channel.TextChannel, role: discord.Role):
        channel_exists = await self.config._channel_exists(channel=channel)

        if not channel_exists:
            await interaction.response.send_message(f'The channel {channel.mention} is not subscribed to any events.')
            return
        else:
            channel_roles = await self.config._channel_roles(channel=channel)

            if str(role.id) in channel_roles:
                await interaction.response.send_message(f"This role ping is already assigned to the channel {channel.mention}.")
                return
            else:
                await self.config._channel_add_role(channel=channel, role=role)
                await interaction.response.send_message(f'The channel {channel.mention} has been assigned to ping this role on future Jam Track events.')

    @remove_subcommand_group.command(name="role", description="Remove a role ping from a channel's subscription messages")
    @app_commands.describe(channel = "The channel to remove a role ping from")
    @app_commands.describe(role = "The role to remove a ping for")
    @app_commands.checks.has_permissions(administrator=True)
    async def remove_role(self, interaction: discord.Interaction, channel: discord.channel.TextChannel, role: discord.Role):
        channel_exists = await self.config._channel_exists(channel=channel)

        if not channel_exists:
            await interaction.response.send_message(f'The channel {channel.mention} is not subscribed to any events.')
            return
        else:
            channel_roles = await self.config._channel_roles(channel=channel)

            if str(role.id) in channel_roles:
                await self.config._channel_remove_role(channel=channel, role=role)
                await interaction.response.send_message(f'The channel {channel.mention} has been assigned to not ping this role on future Jam Track events.')
            else:
                await interaction.response.send_message(f"This role ping is not assigned to the channel {channel.mention}.")

    @admin_group.command(name="subscriptions", description="View the subscriptions in this guild")
    @app_commands.checks.has_permissions(administrator=True)
    async def subscriptions(self, interaction: discord.Interaction):
        embed = discord.Embed(title=f"Subscriptions for **{interaction.guild.name}**", color=0x8927A1)
        total_channels = 0
        guild_subscribed_channels: List[config.SubscriptionChannel] = await self.config._guild_channels(guild=interaction.guild)
        for channel_to_search in guild_subscribed_channels:
            channel = self.bot.get_channel(channel_to_search.id)

            if channel:
                if channel.guild.id == interaction.guild.id:
                    total_channels += 1
                    events_content = "**Events:** " + ", ".join([constants.EVENT_NAMES[event] for event in channel_to_search.events])
                    role_content = ""
                    if channel_to_search.roles:
                        if len(channel_to_search.roles) > 0:
                            role_content = "**Roles:** " + ", ".join([f'<@&{role}>' for role in channel_to_search.roles])
                    embed.add_field(name=f"{channel.mention}", value=f"{events_content}\n{role_content}", inline=False)

        if total_channels < 1:
            embed.add_field(name="There are no subscriptions in this guild.", value="")
        else:
            embed.description = f'{total_channels} found'

        await interaction.response.send_message(embed=embed)

    async def on_subscription_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(interaction.channel, discord.DMChannel) and interaction.command.guild_only: # just in case
            await interaction.response.send_message(content="You cannot run this command in DMs.")
            return
        if isinstance(error, app_commands.errors.MissingPermissions):
            await interaction.response.send_message(content="You do not have the necessary permissions to run this command. Only administrators can use this command.", ephemeral=True)
            return
        # actually not needed!!
        # await self.bot.tree.on_error(interaction, error)

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

    @test_group.command(name="migrate", description="Migrates channels.json to subscriptions.db")
    async def migrate(self, interaction: discord.Interaction):
        if not (interaction.user.id in constants.BOT_OWNERS):
            await interaction.response.send_message(content="You are not authorized to run this command.", ephemeral=True)
            return

        import migrate
        
        await interaction.response.defer()

        logging.debug('Starting migration process')
        results = await migrate.main(self.bot)
        embeds = []

        for i in range(0, len(results), 10):
            embed = discord.Embed(title="Migration Results", color=0x8927A1)
            chunk = results[i:i + 10]
            text = '\n'.join(chunk)
            embed.add_field(name="Logs", value=f"```{text}```")
            embeds.append(embed)

        view = constants.PaginatorView(embeds, interaction.user.id)
        view.message = await interaction.edit_original_response(embed=view.get_embed(), view=view)

        logging.debug('Migration process is over.')

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