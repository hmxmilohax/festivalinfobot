import logging
from discord import app_commands
import discord
from discord.ext import commands

from bot import config, constants

class SubscriptionCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config = bot.config

    sub_cog = app_commands.Group(name="subscription", description="Subscription Commands", allowed_contexts=discord.app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True), allowed_installs=discord.app_commands.AppInstallationType(guild=True, user=True))

    add_subcommand_group = app_commands.Group(name="add", description="Add commands", parent=sub_cog)
    remove_subcommand_group = app_commands.Group(name="remove", description="Add commands", parent=sub_cog)
    
    @add_subcommand_group.command(name="me", description="Subscribe yourself to Jam Track events")
    async def dm_subscribe(self, interaction: discord.Interaction):
        user_list = [subscribed_user for subscribed_user in self.config.users if subscribed_user.id == interaction.user.id]
        user_exists = len(user_list) > 0

        if not user_exists:
            self.config.users.append(config.SubscriptionUser(interaction.user.id, config.JamTrackEvent.get_all_events()))
        else:
            for i, _user in enumerate(user_list):
                if i > 0:
                    logging.warning(f'Found another user for {interaction.user.id}? User no. {i}')

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
        
    @remove_subcommand_group.command(name="me", description="Unsubscribe yourself from Jam Track events")
    async def dm_unsubscribe(self, interaction: discord.Interaction):
        user_list = [subscribed_user for subscribed_user in self.config.users if subscribed_user.id == interaction.user.id]
        user_exists = len(user_list) > 0

        if not user_exists:
            await interaction.response.send_message(f"You are not subscribed to any Jam Track events.", ephemeral=True)
            return
        else:
            for i, _user in enumerate(user_list):
                if i > 0:
                    logging.warning(f'Found another user for {interaction.user.id}? User no. {i}')
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

    @add_subcommand_group.command(name="event", description="Subscribe yourself to specific Jam Track events")
    async def dm_add_event(self, interaction: discord.Interaction, event: config.JamTrackEvent):
        user_list = [subscribed_user for subscribed_user in self.config.users if subscribed_user.id == interaction.user.id]
        user_exists = len(user_list) > 0
        chosen_event = config.JamTrackEvent[str(event).replace('JamTrackEvent.', '')].value

        if not user_exists:
            self.config.users.append(config.SubscriptionUser(interaction.user.id, [chosen_event]))
        else:
            for i, _user in enumerate(user_list):
                if i > 0:
                    logging.warning(f'Found another user for {interaction.user.id}? User no. {i}')

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

    @remove_subcommand_group.command(name="event", description="Unsubscribe yourself from specific Jam Track events")
    async def dm_add_event(self, interaction: discord.Interaction, event: config.JamTrackEvent):
        user_list = [subscribed_user for subscribed_user in self.config.users if subscribed_user.id == interaction.user.id]
        user_exists = len(user_list) > 0
        chosen_event = config.JamTrackEvent[str(event).replace('JamTrackEvent.', '')].value

        if not user_exists:
            await interaction.response.send_message(f'You are not subscribed to any events.', ephemeral=True)
            return
        else:
            for i, _user in enumerate(user_list):
                if i > 0:
                    logging.warning(f'Found another user for {interaction.user.id}? User no. {i}')

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