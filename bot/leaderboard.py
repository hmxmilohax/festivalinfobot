from datetime import datetime
from datetime import timezone
import logging
import math
import re
import requests
import bot.constants as constants
import discord
from bot.groups.oauthmanager import OAuthManager
from bot.tracks import JamTrackHandler

# a custom view for leaderboards so they load fast as shit
class LeaderboardPaginatorView(discord.ui.View):
    def __init__(self, song_event_id: str, season_str: str, instrument: constants.Instrument, user_id: int, oauth_manager: OAuthManager, matched_track: dict):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.total_pages = 0
        self.current_page = 0
        self.message : discord.Message
        self.add_buttons()
        self.page_data: dict = {}
        self.account_names: dict = {}
        self.song_event_id = song_event_id
        self.season_str = season_str
        self.instrument = instrument
        self.oauth_manager = oauth_manager
        self.embed_manager = LeaderboardEmbedHandler()
        self.matched_track = matched_track
        self.current_selected_in_page = 0

        self.per_page = 10

    async def force_update(self):
        embed = self.get_embed()
        self.update_buttons()
        await self.message.edit(embed=embed, view=self)

    def update_buttons(self):
        self.add_buttons()

    def add_buttons(self):
        self.clear_items()
        
        self.add_item(FirstButton(style=discord.ButtonStyle.secondary, emoji=constants.FIRST_EMOJI, disabled=not (self.current_page > 0), user_id=self.user_id))
        self.add_item(PreviousButton(style=discord.ButtonStyle.secondary, emoji=constants.PREVIOUS_EMOJI, disabled=not (self.current_page > 0), user_id=self.user_id))

        self.add_item(PaginatorButton(label=f"{self.current_page + 1}/{self.total_pages}", user_id=self.user_id, style=discord.ButtonStyle.primary))

        self.add_item(NextButton(style=discord.ButtonStyle.secondary, emoji=constants.NEXT_EMOJI, disabled=not (self.current_page < self.total_pages - 1), user_id=self.user_id))
        self.add_item(LastButton(style=discord.ButtonStyle.secondary, emoji=constants.LAST_EMOJI, disabled=not (self.current_page < self.total_pages - 1), user_id=self.user_id))

        self.add_item(JumpToPlayerButton(style=discord.ButtonStyle.secondary, emoji=constants.SEARCH_EMOJI, user_id=self.user_id, row=1, label='Player', disabled=True))
        self.add_item(JumpRankButton(style=discord.ButtonStyle.secondary, emoji=constants.LAST_EMOJI, user_id=self.user_id, row=1, label='Rank'))
        self.add_item(JumpToPageButton(style=discord.ButtonStyle.secondary, emoji=constants.LAST_EMOJI, user_id=self.user_id, row=1, label='Page'))

        self.add_item(ScrollUpButton(style=discord.ButtonStyle.secondary, emoji=constants.UP_EMOJI, user_id=self.user_id, row=2))
        self.add_item(ScrollDownButton(style=discord.ButtonStyle.secondary, emoji=constants.DOWN_EMOJI, user_id=self.user_id, row=2))
        self.add_item(PaginatorButton(style=discord.ButtonStyle.secondary, emoji=constants.INFORMATION_EMOJI, user_id=self.user_id, row=2, label='View', disabled=True))

    def get_embed(self):
        # the api returns 100 entries per page however we show 10 entries per page only
        # find the nearest page to the current page
        entry_start_page = page = self.current_page * self.per_page
        page = math.floor(entry_start_page / 100)
        # logging.info(f'At API page {page} of Embed page {self.current_page} in {entry_start_page}')
        if self.page_data.get(str(page)) is None:
            self.get_page_data(page)

        entries = self.page_data[str(page)]['entries']

        page_updated = datetime.strptime(self.page_data[str(page)]['updatedTime'], '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=timezone.utc)

        # print(entries)

        _entries_start = math.floor((self.current_page * self.per_page) % 100)
        _entries_end = math.floor(_entries_start + self.per_page)

        # logging.info((self.current_page * self.per_page))
        # logging.info(_entries_start)
        # logging.info(_entries_end)

        selected_entries = entries[_entries_start:_entries_end] # in epic format
        title = f"Leaderboard for\n**{self.matched_track['track']['tt']}** - *{self.matched_track['track']['an']}* ({self.instrument.english})"

        return self.embed_manager.leaderboard_entries(selected_entries, title, self.account_names, self.current_selected_in_page, page_updated)
    
    def load_all_pages(self):
        self.get_page_data(0)
        for page in range(1, self.page_data['0']['totalPages']):
            self.get_page_data(page)

    def get_url(self, page):
        return f'https://events-public-service-live.ol.epicgames.com/api/v1/leaderboards/FNFestival/{self.season_str}_{self.song_event_id}/{self.song_event_id}_{self.instrument.lb_code}/{self.oauth_manager.account_id}?page={page}&rank=0&teamAccountIds&showLiveSessions=false&appId=Fortnite'
            
    def get_page_data(self, page):
        url = self.get_url(page)
        logging.info(f'[GET] {url}')
        headers = {
            'Authorization': self.oauth_manager.session_token
        }
        
        response = requests.get(url, headers=headers)
        if response.status_code == 401 or response.status_code == 403:
            self.oauth_manager._create_token()
            raise Exception('Please try again.')

        response.raise_for_status()
        data = response.json()

        update = False
        if self.total_pages == 0: update = True
            
        self.total_pages = math.floor((data['totalPages'] * 100) / self.per_page)
        if update:
            self.update_buttons()

        account_ids = []
        for entry in data['entries']:
            account_ids.extend(entry['teamAccountIds'])

        account_names = self.oauth_manager.get_accounts(account_ids)
        for account in account_names:
            self.account_names[account.account_id] = account.display_name

        self.page_data[str(page)] = data

    async def on_timeout(self):
        try:
            for item in self.children:
                item.disabled = True
            await self.message.edit(view=self)
        except discord.NotFound:
            logging.error("Message was not found when trying to edit after timeout.")
        except Exception as e:
            logging.error(f"An error occurred during on_timeout: {e}, {type(e)}, {self.message}")

class BandLeaderboardView(LeaderboardPaginatorView):
    def __init__(self, song_event_id, season_str, band_type: constants.BandType, user_id, oauth_manager, matched_track):
        super().__init__(song_event_id, season_str, None, user_id, oauth_manager, matched_track)

        self.per_page = 2
        self.band_type = band_type

    def add_buttons(self):
        self.clear_items()
        
        self.add_item(FirstButton(style=discord.ButtonStyle.secondary, emoji=constants.FIRST_EMOJI, disabled=not (self.current_page > 0), user_id=self.user_id))
        self.add_item(PreviousButton(style=discord.ButtonStyle.secondary, emoji=constants.PREVIOUS_EMOJI, disabled=not (self.current_page > 0), user_id=self.user_id))

        self.add_item(PaginatorButton(label=f"{self.current_page + 1}/{self.total_pages}", user_id=self.user_id, style=discord.ButtonStyle.primary))

        self.add_item(NextButton(style=discord.ButtonStyle.secondary, emoji=constants.NEXT_EMOJI, disabled=not (self.current_page < self.total_pages - 1), user_id=self.user_id))
        self.add_item(LastButton(style=discord.ButtonStyle.secondary, emoji=constants.LAST_EMOJI, disabled=not (self.current_page < self.total_pages - 1), user_id=self.user_id))

        self.add_item(PaginatorButton(style=discord.ButtonStyle.secondary, emoji=constants.SEARCH_EMOJI, user_id=self.user_id, row=1, label='Player', disabled=True))  # we copied the entire function just for this. fr
        self.add_item(JumpRankButton(style=discord.ButtonStyle.secondary, emoji=constants.LAST_EMOJI, user_id=self.user_id, row=1, label='Rank'))
        self.add_item(JumpToPageButton(style=discord.ButtonStyle.secondary, emoji=constants.LAST_EMOJI, user_id=self.user_id, row=1, label='Page'))

        self.add_item(ScrollUpButton(style=discord.ButtonStyle.secondary, emoji=constants.UP_EMOJI, user_id=self.user_id, row=2))
        self.add_item(ScrollDownButton(style=discord.ButtonStyle.secondary, emoji=constants.DOWN_EMOJI, user_id=self.user_id, row=2))
        self.add_item(PaginatorButton(style=discord.ButtonStyle.secondary, emoji=constants.INFORMATION_EMOJI, user_id=self.user_id, row=2, label='View', disabled=True))

    def get_embed(self):
        entry_start_page = page = self.current_page * self.per_page
        page = math.floor(entry_start_page / 100)
        if self.page_data.get(str(page)) is None:
            self.get_page_data(page)

        entries = self.page_data[str(page)]['entries']
        page_updated = datetime.strptime(self.page_data[str(page)]['updatedTime'], '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=timezone.utc)

        # print(entries)

        _entries_start = math.floor((self.current_page * self.per_page) % 100)
        _entries_end = math.floor(_entries_start + self.per_page)

        selected_entries = entries[_entries_start:_entries_end] # in epic format
        title = f"Band Leaderboard for\n**{self.matched_track['track']['tt']}** - *{self.matched_track['track']['an']}* ({self.band_type.english})"

        return self.embed_manager.band_leaderboard_entries(selected_entries, title, self.account_names, self.current_selected_in_page, page_updated)
    
    def get_url(self, page):
        return f'https://events-public-service-live.ol.epicgames.com/api/v1/leaderboards/FNFestival/{self.season_str}_{self.song_event_id}/{self.song_event_id}_Band_{self.band_type.code}/{self.oauth_manager.account_id}?page={page}&rank=0&teamAccountIds&showLiveSessions=false&appId=Fortnite'

class AllTimeLeaderboardView(LeaderboardPaginatorView):
    def __init__(self, song_event_id, season_str, lbtype: constants.AllTimeLBType, user_id, oauth_manager, matched_track):
        super().__init__(song_event_id, season_str, None, user_id, oauth_manager, matched_track)

        self.alltime_lbtype: constants.AllTimeLBType = lbtype
        if self.alltime_lbtype.is_band:
            self.per_page = 2

    def add_buttons(self):
        self.clear_items()
        
        self.add_item(FirstButton(style=discord.ButtonStyle.secondary, emoji=constants.FIRST_EMOJI, disabled=not (self.current_page > 0), user_id=self.user_id))
        self.add_item(PreviousButton(style=discord.ButtonStyle.secondary, emoji=constants.PREVIOUS_EMOJI, disabled=not (self.current_page > 0), user_id=self.user_id))

        self.add_item(PaginatorButton(label=f"{self.current_page + 1}/{self.total_pages}", user_id=self.user_id, style=discord.ButtonStyle.primary))

        self.add_item(NextButton(style=discord.ButtonStyle.secondary, emoji=constants.NEXT_EMOJI, disabled=not (self.current_page < self.total_pages - 1), user_id=self.user_id))
        self.add_item(LastButton(style=discord.ButtonStyle.secondary, emoji=constants.LAST_EMOJI, disabled=not (self.current_page < self.total_pages - 1), user_id=self.user_id))

        self.add_item(PaginatorButton(style=discord.ButtonStyle.secondary, emoji=constants.SEARCH_EMOJI, user_id=self.user_id, row=1, label='Player', disabled=True))  # we copied the entire function just for this. fr
        self.add_item(JumpRankButton(style=discord.ButtonStyle.secondary, emoji=constants.LAST_EMOJI, user_id=self.user_id, row=1, label='Rank'))
        self.add_item(JumpToPageButton(style=discord.ButtonStyle.secondary, emoji=constants.LAST_EMOJI, user_id=self.user_id, row=1, label='Page'))

        self.add_item(ScrollUpButton(style=discord.ButtonStyle.secondary, emoji=constants.UP_EMOJI, user_id=self.user_id, row=2))
        self.add_item(ScrollDownButton(style=discord.ButtonStyle.secondary, emoji=constants.DOWN_EMOJI, user_id=self.user_id, row=2))
        self.add_item(PaginatorButton(style=discord.ButtonStyle.secondary, emoji=constants.INFORMATION_EMOJI, user_id=self.user_id, row=2, label='View', disabled=True))

    def get_url(self, page):
        return f'https://events-public-service-live.ol.epicgames.com/api/v1/leaderboards/FNFestival/alltime_{self.song_event_id}_{self.alltime_lbtype.code}/alltime/{self.oauth_manager.account_id}?page={page}&rank=0&teamAccountIds&showLiveSessions=false&appId=Fortnite'

    def get_embed(self):
        entry_start_page = page = self.current_page * self.per_page
        page = math.floor(entry_start_page / 100)
        if self.page_data.get(str(page)) is None:
            self.get_page_data(page)

        entries = self.page_data[str(page)]['entries']

        page_updated = datetime.strptime(self.page_data[str(page)]['updatedTime'], '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=timezone.utc)

        _entries_start = math.floor((self.current_page * self.per_page) % 100)
        _entries_end = math.floor(_entries_start + self.per_page)

        selected_entries = entries[_entries_start:_entries_end] # in epic format
        title = f"All-Time Leaderboard for\n**{self.matched_track['track']['tt']}** - *{self.matched_track['track']['an']}* ({self.alltime_lbtype.english})"

        if self.alltime_lbtype.is_band:
            return self.embed_manager.band_leaderboard_entries(selected_entries, title, self.account_names, self.current_selected_in_page, page_updated)
        else:
            return self.embed_manager.leaderboard_entries(selected_entries, title, self.account_names, self.current_selected_in_page, page_updated)

class PaginatorButton(discord.ui.Button):
    def __init__(self, *args, **kwargs):
        self.user_id = kwargs.pop('user_id')
        super().__init__(*args, **kwargs)

    def update_page(self, view: LeaderboardPaginatorView):
        pass

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your session. Please run the command yourself to start your own session.", ephemeral=True)
            return
        
        await interaction.response.defer() 
        view: LeaderboardPaginatorView = self.view
        self.update_page(view)
        embed = view.get_embed()
        view.update_buttons()
        await interaction.edit_original_response(embed=embed, view=view)
class FirstButton(PaginatorButton):
    def update_page(self, view: LeaderboardPaginatorView): view.current_page = 0
class PreviousButton(PaginatorButton):
    def update_page(self, view: LeaderboardPaginatorView): view.current_page -= 1
class NextButton(PaginatorButton):
    def update_page(self, view: LeaderboardPaginatorView): view.current_page += 1
class LastButton(PaginatorButton):
    def update_page(self, view: LeaderboardPaginatorView): view.current_page = view.total_pages - 1
class ScrollUpButton(PaginatorButton):
    def update_page(self, view: LeaderboardPaginatorView): 
        if view.current_selected_in_page > 1:
            view.current_selected_in_page -= 1
        else:
            view.current_selected_in_page = view.per_page
class ScrollDownButton(PaginatorButton):
    def update_page(self, view: LeaderboardPaginatorView): 
        if view.current_selected_in_page < view.per_page:
            view.current_selected_in_page += 1
        else:
            view.current_selected_in_page = 1

class JumpRankButton(PaginatorButton):
    async def callback(self, interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your session. Please run the command yourself to start your own session.", ephemeral=True)
            return
        
        view: LeaderboardPaginatorView = self.view
        modal = JumpRankModal(view)
        await interaction.response.send_modal(modal)

class JumpToPlayerButton(PaginatorButton):
    async def callback(self, interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your session. Please run the command yourself to start your own session.", ephemeral=True)
            return
        
        view: LeaderboardPaginatorView = self.view
        modal = JumpPlayerModal(view)
        await interaction.response.send_modal(modal)

class JumpToPageButton(PaginatorButton):
    async def callback(self, interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your session. Please run the command yourself to start your own session.", ephemeral=True)
            return
        
        view: LeaderboardPaginatorView = self.view
        modal = JumpPageModal(view)
        await interaction.response.send_modal(modal)
    
class JumpRankModal(discord.ui.Modal):
    def __init__(self, view: LeaderboardPaginatorView):
        super().__init__(title="Jump to a rank in this leaderboard")

        self.view = view
        total_ranks = self.view.total_pages * self.view.per_page

        self.add_item(discord.ui.TextInput(label="Enter rank", required=False, max_length=len(str(total_ranks)), style=discord.TextStyle.short, placeholder=f"Enter the rank to jump to. (1 - {total_ranks})"))

    async def on_submit(self, interaction: discord.Interaction):
        rank = self.children[0].value
        # print(self.view.total_pages)
        total_ranks = self.view.total_pages * self.view.per_page
        # print(total_ranks)

        try:
            rank = int(rank)
            if rank < 1 or rank > total_ranks:
                raise ValueError

            self.view.current_page = math.floor(rank / self.view.per_page)
            self.view.current_selected_in_page = rank % self.view.per_page

            await interaction.response.send_message(embed=constants.common_success_embed(f"Jumped to {rank} in page {self.view.current_page + 1}"), ephemeral=True)

            await self.view.force_update()

        except ValueError:
            await interaction.response.send_message(embed=constants.common_error_embed(f"The rank must be a number between 1 to {total_ranks}."), ephemeral=True)
            return
        
class JumpPageModal(discord.ui.Modal):
    def __init__(self, view: LeaderboardPaginatorView):
        super().__init__(title="Jump to a page in this leaderboard")

        self.view = view

        self.add_item(discord.ui.TextInput(label="Enter page", required=False, max_length=len(str(view.total_pages)), style=discord.TextStyle.short, placeholder=f"Enter the page to jump to. (1 - {view.total_pages})"))

    async def on_submit(self, interaction: discord.Interaction):
        page = self.children[0].value
        try:
            page = int(page)
            if page < 1 or page > self.view.total_pages:
                raise ValueError
            
            self.view.current_page = (page - 1)
            await interaction.response.send_message(embed=constants.common_success_embed(f"Jumped to page {self.view.current_page + 1}."), ephemeral=True)
            await self.view.force_update()

        except ValueError:
            await interaction.edit_original_response(embed=constants.common_error_embed(f"The page must be a number between 1 to {self.view.total_pages}."), ephemeral=True)
            return
        
class JumpPlayerModal(discord.ui.Modal):
    def __init__(self, view: LeaderboardPaginatorView):
        super().__init__(title="Jump to a player in this leaderboard")

        self.view = view

        self.add_item(discord.ui.TextInput(label="Player username", required=False, max_length=50, min_length=1, style=discord.TextStyle.short, placeholder=f"Enter the username of the player to jump to."))
        self.add_item(discord.ui.TextInput(label="Account ID", required=False, max_length=32, style=discord.TextStyle.short, placeholder=f"Or alternatively, the account ID of the player to jump to."))

    def entry_details(self, page_idx, accid):
        page_data = self.view.page_data[str(page_idx)]
        for i in range(len(page_data['entries'])):
            entry = page_data['entries'][i]
            if entry['teamId'] == accid:
                page_num = int(page_idx)
                entry_relative_index = (page_num * 100) + i
                # print(page_num, entry_relative_index, i)

                return (math.floor(entry_relative_index / 10), (i % 10) + 1)
            
        return None
    
    async def check_page(self, accid, page_idx, interaction: discord.Interaction):
        if self.entry_details(page_idx, accid) is not None:
            self.view.current_page, self.view.current_selected_in_page = self.entry_details(page_idx, accid)
            # print(self.view.current_page, self.view.current_selected_in_page)
            await interaction.edit_original_response(embed=constants.common_success_embed(f"Jumped to {accid} in page {self.view.current_page + 1}"))
            await self.view.force_update()
            return True
        return False

    async def jump_to_account_id(self, accid, interaction: discord.Interaction):
        await interaction.response.send_message('Please wait...', ephemeral=True)

        self.view.get_page_data(0)
        if await self.check_page(accid, 0, interaction):
            return
        
        total_pages = self.view.page_data['0']['totalPages']

        if total_pages > 1:
            for page_idx in range(1, total_pages):
                self.view.get_page_data(page_idx)

                if await self.check_page(accid, page_idx, interaction):
                    return

        await interaction.edit_original_response(embed=constants.common_error_embed(f"Could not find an entry for {accid}."))

    async def on_submit(self, interaction: discord.Interaction):
        username = self.children[0].value
        accountid = self.children[1].value
        
        if len(accountid) > 0:
            await self.jump_to_account_id(accountid, interaction)
        else:
            accounts = self.view.oauth_manager.search_users(username)
            if len(accounts) == 1:
                await self.jump_to_account_id(accounts[0].account_id, interaction)
            else:
                interaction.response.send_message(embed=discord.Embed(colour=0x3AB00B, title="Select the user", description=f"{constants.SEARCH_EMOJI} Select the correct user to continue."))

class LeaderboardEmbedHandler():
    def __init__(self) -> None:
        pass

    def format_stars(self, stars:int = 6):
        if stars > 5:
            stars = 5
            return '✪' * stars
        else:
            return '' + ('★' * stars) + ('☆' * (5-stars))
    
    # normal leaderboard entries
    def leaderboard_entries(self, entries: list, title: str, account_usernames: dict, selected_player: int = 0, updated_ts: datetime = None):
        # ALL IN EPIC FORMAT
        embed = discord.Embed(title=title, color=0x8927A1)
        embed.add_field(name="Last Updated", value=discord.utils.format_dt(updated_ts, 'R') if updated_ts else 'Unknown', inline=False)
        field_text = '```'

        for index in range(len(entries)):
            entry = entries[index]
            try:
                # Prepare leaderboard entry details
                account_id = entry['teamId']
                username = account_usernames.get(account_id, '[unknown]')
                if username == None:
                    username = '[unknown]'

                rank = f"#{entry['rank']}"
                best_session = discord.utils.find(lambda session: session['trackedStats']['SCORE'] == entry['score'], entry['sessionHistory'])
                player_id = 0
                # print(best_session)

                for _key, _value in best_session['trackedStats'].items():
                    key: str = _key
                    if key.endswith(f'_ID_{account_id}') and key.startswith('M_'):
                        player_id = int(key.split('_')[1])
                        break

                stats = best_session['trackedStats']

                _difficulty = stats.get(f'M_{player_id}_DIFFICULTY', 3)
                _accuracy = stats.get(f'M_{player_id}_ACCURACY', 1000000) / 10000
                _stars = stats.get(f'M_{player_id}_STARS_EARNED', 6)
                _score = stats.get(f'M_{player_id}_SCORE', 0)
                _is_fullcombo = stats.get(f'M_{player_id}_FULL_COMBO', 0) == 1
                _instrument = stats.get(f'M_{player_id}_INSTRUMENT', 6)

                difficulty = ['E', 'M', 'H', 'X'][_difficulty]
                accuracy = f"{_accuracy}%".replace('.0', '')
                stars = self.format_stars(_stars)
                score = f"{_score}"
                # fc_status = "FC" if _is_fullcombo else ""
                if _is_fullcombo:
                    accuracy = 'FC'

                instrument = ['LD', 'BS', 'VL', 'DS', 'PL', 'PB', '??'][_instrument]
                diff_inst = difficulty + instrument

                _season = stats.get(f'M_{player_id}_SEASON', None)
                season = 'S'
                season += _season or '?'

                # Add the formatted line for this entry
                if selected_player == (index + 1):
                    rank = '>>>'

                # field_text += f"{rank:<5}{username:<18}{difficulty:<2}{accuracy:<5}{fc_status:<3}{stars:<7}{score:>8}"
                field_text += rank.ljust(5)
                field_text += username.ljust(17)
                field_text += difficulty.ljust(2)
                field_text += accuracy.rjust(4)
                field_text += ' '
                # field_text += fc_status.ljust(3)
                field_text += stars.ljust(7)
                field_text += score.rjust(8)

            except Exception as e:
                logging.error(f"Error in leaderboard entry formatting", exc_info=e)
            field_text += '\n'
        field_text += '```'

        if field_text == '``````': # basic ahh
            field_text = 'No entries found.'

        embed.add_field(name="", value=field_text, inline=False)
        return embed
    
    # band leaderboard entries
    def band_leaderboard_entries(self, entries: list, title: str, account_usernames: dict, selected_player: int = 0, updated_ts: datetime = None):
        # ALL IN EPIC FORMAT
        embed = discord.Embed(title=title, color=0x8927A1)
        embed.add_field(name="Last Updated", value=discord.utils.format_dt(updated_ts, 'R') if updated_ts else 'Unknown', inline=False)
        field_text = '```'

        for index in range(len(entries)):
            entry = entries[index]
            try:
                # Prepare leaderboard entry details

                rank = f"#{entry['rank']}"
                best_session = discord.utils.find(lambda session: session['trackedStats']['SCORE'] == entry['score'], entry['sessionHistory'])
                # player_id = 0
                # # print(best_session)

                # for _key, _value in best_session['trackedStats'].items():
                #     key: str = _key
                #     if key.endswith(f'_ID_{account_id}') and key.startswith('M_'):
                #         player_id = int(key.split('_')[1])
                #         break

                stats = best_session['trackedStats']

                _accuracy = stats.get('ACCURACY', 1000000) / 10000
                _stars = stats.get('STARS_EARNED', 6)
                _score = stats.get('SCORE', 0)
                _is_fullcombo = stats.get('FULL_COMBO', 0) == 1

                accuracy = f"{_accuracy}%".replace('.0', '')
                stars = self.format_stars(_stars)
                score = f"{_score}"
                # fc_status = "FC" if _is_fullcombo else ""
                if _is_fullcombo:
                    accuracy = 'FC'

                # instrument = ['LD', 'BS', 'VL', 'DS', 'PL', 'PB', '??'][_instrument]
                # difficulty = ''
                # diff_inst = difficulty + instrument

                # _season = stats.get(f'M_{player_id}_SEASON', None)
                # season = 'S'
                # season += _season or '?'

                # Add the formatted line for this entry
                if selected_player == (index + 1):
                    rank = '>>>'

                # field_text += f"{rank:<5}{username:<18}{difficulty:<2}{accuracy:<5}{fc_status:<3}{stars:<7}{score:>8}"
                field_text += rank.ljust(5)
                field_text += '-' * 16
                field_text += ' '
                field_text += accuracy.rjust(8)
                field_text += ' '
                # field_text += fc_status.ljust(3)
                field_text += stars.ljust(7)
                field_text += score.rjust(8)

                for _key, _value in stats.items():
                    pattern = r"^M_[0-3]_ID_[0-9a-f]{32}$"
                    match = re.match(pattern, _key)
                    matches = bool(match)

                    if matches:
                        player_id = _key.split('_')[1]
                        account_id = _key.split('_')[3]
                        username = account_usernames.get(account_id, '[unknown]')
                        if username == None:
                            username = '[unknown]'

                        _player_accuracy = stats.get(f'M_{player_id}_ACCURACY', 1000000) / 10000
                        _player_score = stats.get(f'M_{player_id}_SCORE', 0)
                        _player_is_fullcombo = stats.get(f'M_{player_id}_FULL_COMBO', 0) == 1
                        _player_stars = stats.get(f'M_{player_id}_STARS_EARNED', 6)
                        _player_difficulty = stats.get(f'M_{player_id}_DIFFICULTY', 3)
                        _player_instrument = stats.get(f'M_{player_id}_INSTRUMENT', 6)

                        accuracy = f"{_player_accuracy}%".replace('.0', '')
                        stars = self.format_stars(_player_stars)
                        score = f"{_player_score}"
                        difficulty = ['E', 'M', 'H', 'X'][_player_difficulty]
                        instrument = ['LD', 'BS', 'VL', 'DS', 'PL', 'PB', '??'][_player_instrument]
                        if _player_is_fullcombo:
                            accuracy = 'FC'

                        diff_inst = difficulty + instrument

                        field_text += '\n'
                        field_text += '     '
                        field_text += username.ljust(17)
                        field_text += diff_inst.ljust(4)
                        field_text += accuracy.rjust(4)
                        field_text += ' '
                        # field_text += fc_status.ljust(3)
                        field_text += stars.ljust(7)
                        field_text += score.rjust(8)

                field_text += '\n'
                field_text += '     [  Base Score  ]                   '
                field_text += f'{stats.get("B_BASESCORE", 0)}'.rjust(8)
                field_text += '\n'
                field_text += '     [ Instr. Bonus ]                   '
                field_text += f'{stats.get("B_INSTRUMENT_BONUS", 0)}'.rjust(8)
                field_text += '\n'
                field_text += '     [   OD Bonus   ]                   '
                field_text += f'{stats.get("B_OVERDRIVE_BONUS", 0)}'.rjust(8)

            except Exception as e:
                logging.error(f"Error in leaderboard entry formatting", exc_info=e)
            field_text += '\n'
        field_text += '```'

        if field_text == '``````': # basic ahh
            field_text = 'No entries found.'

        embed.add_field(name="", value=field_text, inline=False)
        return embed

    def generate_leaderboard_entry_embeds(self, entries, title, chunk_size=5):
        embeds = []

        for i in range(0, len(entries), chunk_size):
            embed = discord.Embed(title=title, color=0x8927A1)
            chunk = entries[i:i + chunk_size]
            field_text = '```'
            for entry in chunk:
                try:
                    # Prepare leaderboard entry details
                    rank = f"#{entry['rank']}"
                    username = entry.get('userName', '[Unknown]')
                    difficulty = ['E', 'M', 'H', 'X'][entry['best_run']['difficulty']]
                    accuracy = f"{entry['best_run']['accuracy']}%"
                    stars = self.format_stars(entry['best_run']['stars'])
                    score = f"{entry['best_run']['score']}"
                    fc_status = "FC" if entry['best_run']['fullcombo'] else ""

                    # Add the formatted line for this entry
                    field_text += f"{rank:<5}{username:<18}{difficulty:<2}{accuracy:<5}{fc_status:<3}{stars:<7}{score:>8}"

                except Exception as e:
                    logging.error(f"Error in leaderboard entry formatting", exc_info=e)
                field_text += '\n'
            field_text += '```'

            embed.add_field(name="", value=field_text, inline=False)
            embeds.append(embed)


        return embeds

    def generate_leaderboard_embed(self, track_data, entry_data, instrument):
        track = track_data['track']
        title = track['tt']
        embed = discord.Embed(title="", description=f"**{title}** - *{track['an']}*", color=0x8927A1)

        # Best Run information
        difficulty = ['Easy', 'Medium', 'Hard', 'Expert'][entry_data['best_run']['difficulty']]
        accuracy = f"{entry_data['best_run']['accuracy']}%"
        stars = self.format_stars(entry_data['best_run']['stars'])
        score = f"{entry_data['best_run']['score']}"
        fc_status = "FC" if entry_data['best_run']['fullcombo'] else ""

        # Add player info
        embed.add_field(name="Player", value=entry_data.get('userName', '[Unknown]'), inline=True)
        embed.add_field(name="Rank", value=f"#{entry_data['rank']}", inline=True)
        embed.add_field(name="Instrument", value=instrument, inline=True)

        # Add Best run info
        difficulty = f'[{difficulty}]'
        field_text = f"{difficulty:<18}{accuracy:<5}{fc_status:<3}{stars:<7}{score:>8}"
        embed.add_field(name="Best Run", value=f"```{field_text}```", inline=False)

        # Session data (if present)
        for session in entry_data.get('sessions', []):
            session_field_text = '```'
            is_solo = len(session['stats']['players']) == 1
            for player in session['stats']['players']:
                try:
                    username = entry_data['userName'] if player['is_valid_entry'] else f"[Band Member] {['L', 'B', 'V', 'D', 'PL', 'PB'][player['instrument']]}"
                    difficulty = ['E', 'M', 'H', 'X'][player['difficulty']]
                    accuracy = f"{player['accuracy']}%"
                    stars = self.format_stars(player['stars'])
                    score = f"{player['score']}"
                    fc_status = "FC" if player['fullcombo'] else ""

                    session_field_text += f"{username:<18}{difficulty:<2}{accuracy:<5}{fc_status:<3}{stars:<7}{score:>8}\n"
                except Exception as e:
                    logging.error(f"Error in session formatting", exc_info=e)

            # Band data
            if not is_solo:
                band = session['stats']['band']
                name =     '[Band Score]'
                accuracy = f'{band['accuracy']}%'
                stars = self.format_stars(band['stars'])
                base_score = band['scores']['base_score']
                od_bonus = band['scores']['overdrive_bonus']
                show_od_bonus = od_bonus > 0
                total = band['scores']['total']
                fc_status = "FC" if band['fullcombo'] else ""
                session_field_text += f"{name:<20}{accuracy:<5}{fc_status:<3}{stars:<7}{base_score:>8}\n"
                if show_od_bonus:
                    name = '[OD Bonus]'
                    od_bonus = f'+{od_bonus}'
                    session_field_text += f"{name:<36}{od_bonus:>9}\n"

                    name = '[Total Score]'
                    session_field_text += f"{name:<35}{total:>10}\n"

            session_field_text += '```'
            embed.add_field(name=discord.utils.format_dt(datetime.fromtimestamp(int(session['time'])), style="R"), value=session_field_text, inline=False)

        return embed

class LeaderboardCommandHandler:
    def __init__(self, bot:discord.ext.commands.Bot) -> None:
        self.bot = bot
        self.jam_track_handler = JamTrackHandler()
        self.leaderboard_embed_handler = LeaderboardEmbedHandler()

    def fetch_leaderboard_of_track(self, shortname:str, instrument:constants.Instrument):
        season_url = f'{constants.LEADERBOARD_DB_URL}meta.json'
        logging.debug(f'[GET] {season_url}')

        season_number_request = requests.get(season_url)
        current_season_number = season_number_request.json()['season']

        song_url = f'{constants.LEADERBOARD_DB_URL}leaderboards/season{current_season_number}/{shortname}/'

        fetched_entries = []
        fetched_pages = 0
        while (fetched_pages < 5):
            json_url = f'{song_url}{instrument.lb_code}_{fetched_pages}.json'
            try:
                logging.debug(f'[GET] {json_url}')

                response = requests.get(json_url)
                response.raise_for_status()
                data = response.json()
                fetched_entries.extend(data['entries'])
                fetched_pages += 1
            except Exception as e: # No more entries, the leaderboard isn't full yet
                logging.warning(f'There aren\'t enough entries to fetch', exc_info=e)
                return fetched_entries
        else: # 5 pages have been fetched
            return fetched_entries

    async def handle_interaction(self, interaction: discord.Interaction, song:str, instrument:constants.Instruments):
        # Convert our instrument string into an Enum value
        chosen_instrument = constants.Instruments[str(instrument).replace('Instruments.', '')].value

        if not chosen_instrument.lb_enabled:
            await interaction.response.send_message(embed=constants.common_error_embed(f"Instrument \"{chosen_instrument.english}\" cannot be used for leaderboards."))
            return

        tracklist = self.jam_track_handler.get_jam_tracks()
        if not tracklist:
            await interaction.response.send_message(embed=constants.common_error_embed(f"Could not get tracks."), ephemeral=True)
            return

        # Perform fuzzy search
        matched_tracks = self.jam_track_handler.fuzzy_search_tracks(tracklist, song)
        if not matched_tracks:
            await interaction.response.send_message(embed=constants.common_error_embed(f"The search query \"{song}\" did not give any results."))
            return

        await interaction.response.defer() # Makes the bot say Thinking...
        # From here on onwards, must use edit_original_response

        # Use the first matched track
        matched_track = matched_tracks[0]

        view = LeaderboardPaginatorView(matched_track['track']['su'], constants.get_season_lb_str(), chosen_instrument, interaction.user.id, self.bot.oauth_manager, matched_track)
        view.message = await interaction.edit_original_response(embed=view.get_embed(), view=view)

    async def handle_band_interaction(self, interaction: discord.Interaction, song:str, band_type:constants.BandTypes):
        oauth: OAuthManager = self.bot.oauth_manager

        chosen_band_type = constants.BandTypes[str(band_type).replace('BandTypes.', '')].value

        tracklist = constants.get_jam_tracks()
        if not tracklist:
            await interaction.response.send_message(embed=constants.common_error_embed("Could not get tracks."), ephemeral=True)
            return

        # Perform fuzzy search
        matched_tracks = JamTrackHandler().fuzzy_search_tracks(tracklist, song)
        if not matched_tracks:
            await interaction.response.send_message(embed=constants.common_error_embed(f"The search query \"{song}\" did not give any results."))
            return

        await interaction.response.defer() # Makes the bot say Thinking...

        matched_track = matched_tracks[0]

        view = BandLeaderboardView(matched_track['track']['su'], constants.get_season_lb_str(), chosen_band_type, interaction.user.id, oauth, matched_track)
        view.message = await interaction.edit_original_response(embed=view.get_embed(), view=view)

    async def handle_alltime_interaction(self, interaction: discord.Interaction, song: str, type: constants.AllTimeLBTypes):
        oauth: OAuthManager = self.bot.oauth_manager

        chosen_instrument = constants.AllTimeLBTypes[str(type).replace('AllTimeLBTypes.', '')].value

        tracklist = constants.get_jam_tracks()
        if not tracklist:
            await interaction.response.send_message(embed=constants.common_error_embed(f"Could not get tracks."), ephemeral=True)
            return
        # Perform fuzzy search
        matched_tracks = JamTrackHandler().fuzzy_search_tracks(tracklist, song)
        if not matched_tracks:
            await interaction.response.send_message(embed=constants.common_error_embed(f"The search query \"{song}\" did not give any results."))
            return
        await interaction.response.defer() # Makes the bot say Thinking...
        matched_track = matched_tracks[0]

        view = AllTimeLeaderboardView(matched_track['track']['su'], constants.get_season_lb_str(), chosen_instrument, interaction.user.id, oauth, matched_track)
        view.message = await interaction.edit_original_response(embed=view.get_embed(), view=view)
