import discord
from bot.tracks import JamTrackHandler, ResultsJamTracks
from bot import constants

class MixHandler():
    def __init__(self) -> None:
        self.jam_track_handler = JamTrackHandler()
        self.elements_per_page = 10
        pass
    

    async def handle_embed(self, interaction: discord.Interaction, matched_tracks:list, key:str, mode:str, songName: str = '', was_song_search: bool = False, songArtist: str = ''):
        if not matched_tracks or len(matched_tracks) == 0:
            if not was_song_search or not songName:
                embed_description =f"No matching Jam Tracks found for {key} {mode}."
            else:
                embed_description = f"No matching Jam Tracks found for {songName} ({key} {mode})."

            embed = discord.Embed(
               title="No Matches Found",
               description=embed_description,
               colour=constants.ACCENT_COLOUR
            )

            await interaction.response.send_message(embed=embed)
            return
        
        embed_array = []

        if not was_song_search or not songName:
            embed_title =f"Matching Songs for {key} {mode}"
        else:
            embed_title = f"Songs Matching {songName} - {songArtist}"
            matched_tracks = list(filter(lambda track: track["track"]["tt"] != songName, matched_tracks))

        for i in range(0, len(matched_tracks), self.elements_per_page):
            embed = discord.Embed(
                title=embed_title,
                description=f"Choose any of these Jam Tracks for a seamless mix!",
                colour=constants.ACCENT_COLOUR
            )

            tracks_chunk = matched_tracks[i:i + self.elements_per_page]

            for track in tracks_chunk:
                embed.add_field(name=(track["track"]["an"]).strip(), value=(track["track"]["tt"]).strip(), inline=False)

            embed_array.append(embed)

        view = constants.PaginatorView(embed_array, interaction.user.id)
        message = await interaction.response.send_message(embed=view.get_embed(), view=view)
        view.message = message

    async def handle_keymode_match(self, interaction: discord.Interaction, key:constants.KeyTypes, mode:constants.ModeTypes):
        # Convert our key and mode string into an Enum value
        chosen_key = constants.KeyTypes[str(key).replace('KeyTypes.', '')].value
        chosen_mode = constants.ModeTypes[str(mode).replace('ModeTypes.', '')].value

        track_list = self.jam_track_handler.get_jam_tracks()

        if not track_list:
            await interaction.response.send_message(embed=constants.common_error_embed('Could not get tracks.'), ephemeral=True)
            return
        matched_tracks = self.jam_track_handler.get_matching_key_mode_jam_tracks(track_list, chosen_key.code, chosen_mode.code)

        await self.handle_embed(interaction=interaction, matched_tracks=matched_tracks, key=chosen_key.english, mode=chosen_mode.english,was_song_search=False)

    async def handle_keymode_match_from_song(self, interaction: discord.Interaction, song:str):
        view: ResultsJamTracks
        track_list = self.jam_track_handler.get_jam_tracks()

        if not track_list:
            await interaction.response.send_message(embed=constants.common_error_embed('Could not get tracks.'), ephemeral=True)
            return

        matched_tracks = self.jam_track_handler.fuzzy_search_tracks(track_list, song)
        if not matched_tracks:
            await interaction.response.send_message(embed=constants.common_error_embed(f"The search query \"{song}\" did not give any results."))
            return
        
        track = matched_tracks[0] # By default, select the first track searched for

        chosen_key = discord.utils.find(lambda k: k.value.code == track["track"]["mk"], constants.KeyTypes.__members__.values()).value
        chosen_mode = constants.ModeTypes[track["track"]["mm"]].value

        matched_tracks = self.jam_track_handler.get_matching_key_mode_jam_tracks(track_list, chosen_key.code, chosen_mode.code)

        await self.handle_embed(interaction=interaction, matched_tracks=matched_tracks, key=chosen_key.english, mode=chosen_mode.english, songName=track["track"]["tt"], was_song_search=True, songArtist=track["track"]["an"])
