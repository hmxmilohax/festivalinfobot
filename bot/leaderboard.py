import logging
import requests
import bot.constants as constants
from bot.embeds import LeaderboardEmbedHandler
import discord
from bot.tracks import JamTrackHandler

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

    async def handle_interaction(self, interaction: discord.Interaction, song:str, instrument:constants.Instruments, rank: int = None, username:str = None, account_id:str = None):
        # Convert our instrument string into an Enum value
        chosen_instrument = constants.Instruments[str(instrument).replace('Instruments.', '')].value

        if not chosen_instrument.lb_enabled:
            await interaction.response.send_message(content=f"Instrument \"{chosen_instrument.english}\" cannot be used for leaderboards.")
            return

        tracklist = self.jam_track_handler.get_jam_tracks()
        if not tracklist:
            await interaction.response.send_message(content=f"Could not get tracks.", ephemeral=True)
            return

        # Perform fuzzy search
        matched_tracks = self.jam_track_handler.fuzzy_search_tracks(tracklist, song)
        if not matched_tracks:
            await interaction.response.send_message(content=f"The search query \"{song}\" did not give any results.")
            return

        await interaction.response.defer() # Makes the bot say Thinking...
        # From here on onwards, must use edit_original_response

        # Use the first matched track
        matched_track = matched_tracks[0]

        leaderboard_entries = self.fetch_leaderboard_of_track(matched_track['track']['sn'], chosen_instrument)
        individual_search = [rank, username, account_id].count(None) < 3

        if len(leaderboard_entries) > 0:
            if not individual_search:
                title = f"Leaderboard for\n**{matched_track['track']['tt']}** - *{matched_track['track']['an']}* ({chosen_instrument.english})"
                embeds_list = self.leaderboard_embed_handler.generate_leaderboard_entry_embeds(leaderboard_entries, title, chunk_size=10)
                view = constants.PaginatorView(embeds_list, interaction.user.id)
                view.message = await interaction.edit_original_response(embed=view.get_embed(), view=view)
            else:
                specific_entries = []
                specific_entries.extend([entry for entry in leaderboard_entries if entry['rank'] == rank] if rank else [])
                specific_entries.extend([entry for entry in leaderboard_entries if username.lower() in entry['userName'].lower()] if username else [])
                specific_entries.extend([entry for entry in leaderboard_entries if entry['teamId'] == account_id] if account_id else [])
                specific_entries_unique = []
                for entry in specific_entries: 
                    if entry not in specific_entries_unique:
                        specific_entries_unique.append(entry)

                if len(specific_entries_unique) > 0:
                    await interaction.edit_original_response(content=f"Found {len(specific_entries_unique)} entries matching these parameters:")

                    for entry in specific_entries_unique:
                        await interaction.channel.send(embed=self.leaderboard_embed_handler.generate_leaderboard_embed(matched_track, entry, chosen_instrument.english))
                else:
                    await interaction.edit_original_response(content=f"No entries were found matching these parameters.")
        else:
            await interaction.edit_original_response(content=f"There are no entries in this leaderboard.") 