import logging
import os
import discord

from bot import constants

class SetlistViewActionRow(discord.ui.ActionRow):
    def __init__(self, page, total, user_id):
        super().__init__()

        self.current_page = page
        self.total_pages = total
        self.user_id = user_id

        self.first = FirstButton(style=discord.ButtonStyle.secondary, emoji=constants.FIRST_EMOJI, disabled=not (self.current_page > 0), user_id=self.user_id)
        self.prev = PreviousButton(style=discord.ButtonStyle.secondary, emoji=constants.PREVIOUS_EMOJI, disabled=not (self.current_page > 0), user_id=self.user_id)
        self.page = PageNumberButton(label=f"{self.current_page + 1}/{self.total_pages}", user_id=self.user_id, style=discord.ButtonStyle.primary)
        self.next = NextButton(style=discord.ButtonStyle.secondary, emoji=constants.NEXT_EMOJI, disabled=not (self.current_page < self.total_pages - 1), user_id=self.user_id)
        self.last = LastButton(style=discord.ButtonStyle.secondary, emoji=constants.LAST_EMOJI, disabled=not (self.current_page < self.total_pages - 1), user_id=self.user_id)

        self.add_item(self.first)
        self.add_item(self.prev)
        self.add_item(self.page)
        self.add_item(self.next)
        self.add_item(self.last)

class SetlistView(discord.ui.LayoutView):
    def __init__(self, containers, user_id):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.current_page = 0
        self.message : discord.Message

        self.containers = containers

        self.total_pages = len(containers)
        self.action_row = None

        logging.info(self.total_pages)

    def update_components(self):
        """
        returns the attachments for the page
        """
        self.clear_items()

        container = self.containers[self.current_page]

        self.add_item(container)

        self.action_row = SetlistViewActionRow(self.current_page, self.total_pages, self.user_id)
        self.add_item(self.action_row)

    async def on_timeout(self):
        try:
            if self.action_row:
                for item in self.action_row.children:
                    item.disabled = True
                await self.message.edit(view=self)
        except discord.NotFound:
            logging.error("Message was not found when trying to edit after timeout.")
        except Exception as e:
            logging.error(f"An error occurred during on_timeout: {e}, {type(e)}, {self.message}")

class FirstButton(discord.ui.Button):
    def __init__(self, *args, **kwargs):
        self.user_id = kwargs.pop('user_id')
        super().__init__(*args, **kwargs)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your session. Please run the command yourself to start your own session.", ephemeral=True)
            return
        view: SetlistView = self.view
        view.current_page = 0
        view.update_components()

        await interaction.response.edit_message(view=view)

class PreviousButton(discord.ui.Button):
    def __init__(self, *args, **kwargs):
        self.user_id = kwargs.pop('user_id')
        super().__init__(*args, **kwargs)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your session. Please run the command yourself to start your own session.", ephemeral=True)
            return
        view: SetlistView = self.view
        view.current_page -= 1
        
        view.update_components()

        await interaction.response.edit_message(view=view)

class PageNumberButton(discord.ui.Button):
    def __init__(self, *args, **kwargs):
        self.user_id = kwargs.pop('user_id')
        super().__init__(*args, **kwargs)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your session. Please run the command yourself to start your own session.", ephemeral=True)
            return
        view: SetlistView = self.view
        
        view.update_components()

        await interaction.response.edit_message(view=view)

class NextButton(discord.ui.Button):
    def __init__(self, *args, **kwargs):
        self.user_id = kwargs.pop('user_id')
        super().__init__(*args, **kwargs)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your session. Please run the command yourself to start your own session.", ephemeral=True)
            return
        view: SetlistView = self.view
        view.current_page += 1
        view.update_components()

        await interaction.response.edit_message(view=view)

class LastButton(discord.ui.Button):
    def __init__(self, *args, **kwargs):
        self.user_id = kwargs.pop('user_id')
        super().__init__(*args, **kwargs)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your session. Please run the command yourself to start your own session.", ephemeral=True)
            return
        view: SetlistView = self.view
        view.current_page = view.total_pages - 1
        view.update_components()

        await interaction.response.edit_message(view=view)