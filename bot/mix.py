import discord
from bot.tracks import JamTrackHandler, ResultsJamTracks
from bot import constants
import random

class MixHandler():
    def __init__(self) -> None:
        self.jam_track_handler = JamTrackHandler()
        pass
    

    async def handle_embed(self, interaction: discord.Interaction, matched_tracks:list, key:str, mode:str, songName: str = '', should_edit_response: bool = False):
        embed_array = []
        random.shuffle(matched_tracks) # Some uniqueness every time you execute, especially for longer lists

        if not songName:
            embed_title =f"Matching Songs for {key} {mode}"
        else:
            embed_title = f"Songs Matching {songName}"
            matched_tracks = list(filter(lambda track: track["track"]["tt"] != songName, matched_tracks))

        for i in range(0, len(matched_tracks), 25):
            embed = discord.Embed(
                title=embed_title,
                description=f"Choose any of these Jam Tracks for a seamless mix!",
                color=0x8927A1
            )

            tracks_chunk = matched_tracks[i:i + 25]

            for track in tracks_chunk:
                embed.add_field(name=(track["track"]["an"]).strip(), value=(track["track"]["tt"]).strip())

            embed_array.append(embed)

        if len(embed_array) == 1:
            if should_edit_response:
                await interaction.edit_original_response(embed=embed_array[0])
            else:
                await interaction.response.send_message(embed=embed_array[0])
        else:
            view = constants.PaginatorView(embed_array, interaction.user.id)
            
            if should_edit_response:
                await interaction.edit_original_response(embed=view.get_embed(), view=view)
            else:
                await interaction.response.send_message(embed=view.get_embed(), view=view)

    async def handle_keymode_match(self, interaction: discord.Interaction, key:constants.KeyTypes, mode:constants.ModeTypes):
        # Convert our key and mode string into an Enum value
        chosen_key = constants.KeyTypes[str(key).replace('KeyTypes.', '')].value
        chosen_mode = constants.ModeTypes[str(mode).replace('ModeTypes.', '')].value

        track_list = self.jam_track_handler.get_jam_tracks()

        if not track_list:
            await interaction.response.send_message(embed=constants.common_error_embed('Could not get tracks.'), ephemeral=True)
            return
        matched_tracks = self.jam_track_handler.get_matching_key_mode_jam_tracks(track_list, chosen_key.code, chosen_mode.code)

        await self.handle_embed(interaction=interaction, matched_tracks=matched_tracks, key=chosen_key.code, mode=chosen_mode.code,should_edit_response=False)

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
        
        async def selected(new_interaction: discord.Interaction):
            if new_interaction:
                if new_interaction.user.id != interaction.user.id:
                    await interaction.edit_original_response(content="", embed=constants.common_error_embed("This is not your session. Please start your own session."))
                    return

                await new_interaction.response.defer()

            is_timed_out = len(view.select.values) < 1
            if is_timed_out:
                return None

            shortname = view.select.values[0]
            view.stop()
            return discord.utils.find(lambda t: t['track']['sn'] == shortname, matched_tracks)
        
        async def timed_out():
            await interaction.edit_original_response(content="", embed=constants.common_error_embed("You didn't respond in time. Search cancelled."), view=None)
            view.stop()
        
        if len(matched_tracks) > 1:
            view = ResultsJamTracks(matched_tracks, selected)
            view.on_timeout = timed_out
            await interaction.response.send_message(view=view)
            await view.wait()

            track = await selected(None)

            success_text = f"Searching for songs that match the key and mode of {track["track"]["tt"]}..."
            await interaction.edit_original_response(content="", 
                                                     embed= discord.Embed(colour=0x3AB00B, title="Success", description=success_text), 
                                                     view=None)
        else:
            track = matched_tracks[0]
        
        should_edit_response = len(matched_tracks) > 1

        chosen_key = constants.KeyTypes[track["track"]["mk"]].value
        chosen_mode = constants.ModeTypes[track["track"]["mm"]].value

        matched_tracks = self.jam_track_handler.get_matching_key_mode_jam_tracks(track_list, chosen_key.code, chosen_mode.code)

        await self.handle_embed(interaction=interaction, matched_tracks=matched_tracks, key=chosen_key.code, mode=chosen_mode.code, songName=track["track"]["tt"], should_edit_response=should_edit_response)
