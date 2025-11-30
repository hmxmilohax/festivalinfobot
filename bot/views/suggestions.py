import discord
from discord import app_commands
import discord.ui
from discord.ext.commands import Bot

from discord.ui import Modal, TextInput

from bot import constants

class SuggestionModal(Modal):
    def __init__(self, bot):
        super().__init__(title="Give feedback to Festival Tracker")

        self.bot: Bot = bot

        self.add_item(TextInput(label="Subject", required=False, max_length=200, style=discord.TextStyle.short, placeholder="What is your feedback about?"))
        self.add_item(TextInput(label="Description", required=True, style=discord.TextStyle.paragraph, max_length=4000, placeholder="Describe your feedback. Your message is private and only you see this modal."))

    async def on_submit(self, interaction: discord.Interaction):
        subject = self.children[0].value
        desc = self.children[1].value
        user = self.bot.get_channel(constants.SUG_CHANNEL)
        sug_content = f"# New Suggestion\n> Subject: {subject}\n> {desc}\n\n-# In ||**{interaction.guild.name if interaction.guild else 'DMs'}**||, by ||{interaction.user.mention}||"
        await user.send(sug_content)
        await interaction.response.send_message(f"Your feedback has been submitted successfully!", ephemeral=True)
