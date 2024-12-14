from datetime import datetime
import logging
import requests
import bot.constants as constants
import discord
from bot.tracks import JamTrackHandler

class LeaderboardEmbedHandler():
    def __init__(self) -> None:
        pass

    def format_stars(self, stars:int = 6):
        if stars > 5:
            stars = 5
            return '✪' * stars
        else:
            return '' + ('★' * stars) + ('☆' * (5-stars))

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
                specific_entries.extend([entry for entry in leaderboard_entries if username.lower() in str(entry.get('userName', 'N/A')).lower()] if username else [])
                specific_entries.extend([entry for entry in leaderboard_entries if entry['teamId'] == account_id] if account_id else [])
                specific_entries_unique = []
                for entry in specific_entries: 
                    if entry not in specific_entries_unique:
                        specific_entries_unique.append(entry)

                if len(specific_entries_unique) > 0:
                    specific_entries = []

                    for entry in specific_entries_unique:
                        specific_entries.append(self.leaderboard_embed_handler.generate_leaderboard_embed(matched_track, entry, chosen_instrument.english))

                    # why did i not think of this before
                    view = constants.PaginatorView(specific_entries, interaction.user.id)
                    view.message = await interaction.edit_original_response(embed=view.get_embed(), view=view)
                else:
                    await interaction.edit_original_response(content=f"No entries were found matching these parameters.")
        else:
            await interaction.edit_original_response(content=f"There are no entries in this leaderboard.") 