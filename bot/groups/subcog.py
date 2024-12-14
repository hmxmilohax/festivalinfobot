from code import interact
import logging
from discord import app_commands
import discord
from discord.ext import commands

from bot import config, constants

class SubscriptionCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config: config.Config = bot.config

    sub_cog = app_commands.Group(name="subscription", description="Subscription Commands", allowed_contexts=discord.app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True), allowed_installs=discord.app_commands.AppInstallationType(guild=True, user=True))

    @sub_cog.command(name="events", description="View the events you are currently subscribed to")
    async def events(self, interaction: discord.Interaction):
        embed = discord.Embed(title=f"Your subscriptions", color=0x8927A1)
        user_exists = await self.config._user_exists(user=interaction.user)
        if not user_exists:
            embed.add_field(name="You are not subscribed.", value="")
        else:
            subscribed_events = await self.config._user_events(user=interaction.user)
            events_content = "**Events:** " + ", ".join([constants.EVENT_NAMES[event] for event in subscribed_events])
            embed.add_field(name=f"{len(subscribed_events)} events", value=f"{events_content}", inline=False)

        await interaction.response.send_message(embed=embed)

    add_subcommand_group = app_commands.Group(name="add", description="Add commands", parent=sub_cog)
    remove_subcommand_group = app_commands.Group(name="remove", description="Add commands", parent=sub_cog)
    
    @add_subcommand_group.command(name="me", description="Subscribe yourself to Jam Track events")
    async def dm_subscribe(self, interaction: discord.Interaction):
        user_exists = await self.config._user_exists(user=interaction.user)

        if not user_exists:
            await self.config._user_add(user=interaction.user)
            await interaction.response.send_message(f"You've been successfully added to the subscription list; I will now send you all Jam Track events.", ephemeral=True)
        else:
            subscribed_user_events = await self.config._user_events(user=interaction.user)
            if len(subscribed_user_events) == len(config.JamTrackEvent.get_all_events()):
                await interaction.response.send_message(f"You're already subscribed to all Jam Track events.", ephemeral=True)
            else:    
                await interaction.response.send_message(f"You're already subscribed to the events \"{'\", \"'.join([constants.EVENT_NAMES[event] for event in subscribed_user_events])}\".", ephemeral=True)
        
    @remove_subcommand_group.command(name="me", description="Unsubscribe yourself from Jam Track events")
    async def dm_unsubscribe(self, interaction: discord.Interaction):
        user_exists = await self.config._user_exists(user=interaction.user)

        if not user_exists:
            await interaction.response.send_message(f"You are not subscribed to any Jam Track events.", ephemeral=True)
            return
        else:
            await self.config._user_remove(user=interaction.user)
            await interaction.response.send_message(f"You've been successfully removed from the subscription list; I will no longer send you any Jam Track events.", ephemeral=True)

    @add_subcommand_group.command(name="event", description="Subscribe yourself to specific Jam Track events")
    async def dm_add_event(self, interaction: discord.Interaction, event: config.JamTrackEvent):
        user_exists = await self.config._user_exists(user=interaction.user)
        print(user_exists)
        chosen_event = config.JamTrackEvent[str(event).replace('JamTrackEvent.', '')]

        if not user_exists:
            await self.config._user_add_with_event(user=interaction.user, event=chosen_event)
            await interaction.response.send_message(f'You have been subscribed with the event "{constants.EVENT_NAMES[chosen_event.value]}".', ephemeral=True)
        else:
            subscribed_events = await self.config._user_events(user=interaction.user)
            print(subscribed_events)
            if chosen_event.value in subscribed_events:
                await interaction.response.send_message(f'You are already subscribed to the event "{constants.EVENT_NAMES[chosen_event.value]}".', ephemeral=True)
                return
            else:
                await self.config._user_add_event(user=interaction.user, event=chosen_event)
                await interaction.response.send_message(f'You have been subscribed to the event "{constants.EVENT_NAMES[chosen_event.value]}".', ephemeral=True)

    @remove_subcommand_group.command(name="event", description="Unsubscribe yourself from specific Jam Track events")
    async def dm_add_event(self, interaction: discord.Interaction, event: config.JamTrackEvent):
        user_exists = await self.config._user_exists(user=interaction.user)
        chosen_event = config.JamTrackEvent[str(event).replace('JamTrackEvent.', '')]

        if not user_exists:
            await interaction.response.send_message(f'You are not subscribed to any events.', ephemeral=True)
            return
        else:
            subscribed_events = await self.config._user_events(user=interaction.user)

            if chosen_event.value in subscribed_events:
                subscribed_events.remove(event.value)

                # Remove the channel from the subscription list if it isnt subscribed to any events
                if len(subscribed_events) == 0:
                    await self.config._user_remove(user=interaction.user)
                    await interaction.response.send_message(f"You have been removed from the subscription list because you are no longer subscribed to any events.", ephemeral=True)
                else:
                    await self.config._user_remove_event(user=interaction.user, event=chosen_event)
                    await interaction.response.send_message(f'You have been unsubscribed from the event "{constants.EVENT_NAMES[chosen_event.value]}".', ephemeral=True)
            else:
                await interaction.response.send_message(f'You are not subscribed to the event "{constants.EVENT_NAMES[chosen_event.value]}".', ephemeral=True)