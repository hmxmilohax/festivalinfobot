import asyncio
import logging
import discord

from bot import constants


class HistoryView(discord.ui.View): # YES YES YES
    def __init__(self, embeds, attachments, session_id, user_id):
        """
        EMBEDS AND ATTACHMENTS MUST BE IN THE SAME ORDER
        """
        super().__init__(timeout=30)
        self.embeds = embeds
        self.user_id = user_id
        self.current_page = 0
        self.total_pages = len(embeds)
        self.add_buttons()
        self.message : discord.Message
        self.attachments = attachments
        self.session_id = session_id

    def add_buttons(self):
        self.clear_items()
        
        self.add_item(FirstButton(style=discord.ButtonStyle.primary if self.current_page > 0 else discord.ButtonStyle.secondary, label='First', disabled=not (self.current_page > 0), user_id=self.user_id))
        self.add_item(PreviousButton(style=discord.ButtonStyle.primary if self.current_page > 0 else discord.ButtonStyle.secondary, label='Previous', disabled=not (self.current_page > 0), user_id=self.user_id))

        self.add_item(PageNumberButton(label=f"Page {self.current_page + 1}/{self.total_pages}", user_id=self.user_id))

        self.add_item(NextButton(style=discord.ButtonStyle.primary if self.current_page < self.total_pages - 1 else discord.ButtonStyle.secondary, label='Next', disabled=not (self.current_page < self.total_pages - 1), user_id=self.user_id))
        self.add_item(LastButton(style=discord.ButtonStyle.primary if self.current_page < self.total_pages - 1 else discord.ButtonStyle.secondary, label='Last', disabled=not (self.current_page < self.total_pages - 1), user_id=self.user_id))

    def get_embed(self):
        return self.embeds[self.current_page]
    
    def get_cur_attch(self):
        # ah yes were reuploading the file to discord or something happens here
        return discord.File(self.attachments[self.current_page])

    def update_buttons(self):
        self.add_buttons()

    async def on_timeout(self):
        try:
            for item in self.children:
                item.disabled = True
            await self.message.edit(view=self)
            constants.delete_session_files(session_hash=str(self.session_id))
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
        view: HistoryView = self.view
        view.current_page = 0
        embed = view.get_embed()
        view.update_buttons()
        await interaction.response.edit_message(embed=embed, view=view, attachments=[view.get_cur_attch()])

class PreviousButton(discord.ui.Button):
    def __init__(self, *args, **kwargs):
        self.user_id = kwargs.pop('user_id')
        super().__init__(*args, **kwargs)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your session. Please run the command yourself to start your own session.", ephemeral=True)
            return
        view: HistoryView = self.view
        view.current_page -= 1
        embed = view.get_embed()
        view.update_buttons()
        await interaction.response.edit_message(embed=embed, view=view, attachments=[view.get_cur_attch()])

class PageNumberButton(discord.ui.Button):
    def __init__(self, *args, **kwargs):
        self.user_id = kwargs.pop('user_id')
        super().__init__(*args, **kwargs)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your session. Please run the command yourself to start your own session.", ephemeral=True)
            return
        view: HistoryView = self.view
        embed = view.get_embed()
        await interaction.response.edit_message(embed=embed, view=view, attachments=[view.get_cur_attch()])

class NextButton(discord.ui.Button):
    def __init__(self, *args, **kwargs):
        self.user_id = kwargs.pop('user_id')
        super().__init__(*args, **kwargs)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your session. Please run the command yourself to start your own session.", ephemeral=True)
            return
        view: HistoryView = self.view
        view.current_page += 1
        embed = view.get_embed()
        view.update_buttons()
        await interaction.response.edit_message(embed=embed, view=view, attachments=[view.get_cur_attch()])

class LastButton(discord.ui.Button):
    def __init__(self, *args, **kwargs):
        self.user_id = kwargs.pop('user_id')
        super().__init__(*args, **kwargs)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your session. Please run the command yourself to start your own session.", ephemeral=True)
            return
        view: HistoryView = self.view
        view.current_page = view.total_pages - 1
        embed = view.get_embed()
        view.update_buttons()
        await interaction.response.edit_message(embed=embed, view=view, attachments=[view.get_cur_attch()])