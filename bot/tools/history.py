import asyncio
import logging
import os
import discord

from bot import constants

class HistoryViewActionRow(discord.ui.ActionRow):
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

class HistoryView(discord.ui.LayoutView): # YES YES YES
    def __init__(self, data, session_id, user_id, track_data):
        """
        receives a list full of tuples of (data dict, images list)
        """
        super().__init__(timeout=30)
        self.user_id = user_id
        self.current_page = 0
        self.message : discord.Message

        self.session_id = session_id
        self.data = list(filter(lambda d: d is not None, data))
        self.track_data = track_data

        self.total_pages = len(data)

        self.action_row = None

        logging.info(self.total_pages)

    def update_components(self) -> list[str]:
        """
        returns the attachments for the page
        """
        self.clear_items()

        pdata = self.data[self.current_page][0]
        _attchs = self.data[self.current_page][1]
        attchs = _attchs[:10]

        container = discord.ui.Container(
            discord.ui.Section(
                discord.ui.TextDisplay(f"**{self.track_data['track']['tt']}** - *{self.track_data['track']['an']}*"),
                discord.ui.TextDisplay(f"Detected {len(_attchs)} track change(s) in v{self.current_page + 2}"),
                discord.ui.TextDisplay(f"From {pdata['last_modified_old']}\n" +
                                       f"To {pdata['last_modified_new']}\n" + 
                                       f"Since {pdata['last_modified_new'].replace('D', 'R')}"),
                accessory=discord.ui.Thumbnail(self.track_data['track']['au'])
            ),
            discord.ui.MediaGallery(
                *[discord.MediaGalleryItem(media=f'attachment://{os.path.basename(file)}') for file in attchs]
            ),
            discord.ui.TextDisplay(f"-# Festival Tracker" + (f" · {len(_attchs) - 10} more image(s) not shown" if len(_attchs) > 10 else "")),
            accent_colour=0x8927A1
        )

        self.add_item(container)

        self.action_row = HistoryViewActionRow(self.current_page, self.total_pages, self.user_id)
        self.add_item(self.action_row)

        return attchs

    async def on_timeout(self):
        try:
            if self.action_row:
                for item in self.action_row.children:
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

        fpaths = view.update_components()
        attchs = [discord.File(fp, filename=os.path.basename(fp)) for fp in fpaths]

        await interaction.response.edit_message(view=view, attachments=attchs)

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
        
        fpaths = view.update_components()
        attchs = [discord.File(fp, filename=os.path.basename(fp)) for fp in fpaths]

        await interaction.response.edit_message(view=view, attachments=attchs)

class PageNumberButton(discord.ui.Button):
    def __init__(self, *args, **kwargs):
        self.user_id = kwargs.pop('user_id')
        super().__init__(*args, **kwargs)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your session. Please run the command yourself to start your own session.", ephemeral=True)
            return
        view: HistoryView = self.view
        
        fpaths = view.update_components()
        attchs = [discord.File(fp, filename=os.path.basename(fp)) for fp in fpaths]

        await interaction.response.edit_message(view=view, attachments=attchs)

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
        
        fpaths = view.update_components()
        attchs = [discord.File(fp, filename=os.path.basename(fp)) for fp in fpaths]

        await interaction.response.edit_message(view=view, attachments=attchs)

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
        
        fpaths = view.update_components()
        attchs = [discord.File(fp, filename=os.path.basename(fp)) for fp in fpaths]

        await interaction.response.edit_message(view=view, attachments=attchs)