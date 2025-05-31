import discord
from discord.ext import commands
from bot.tracks import JamTrackHandler
from bot import constants
import random

class MixHandler():
    def __init__(self, bot: commands.Bot) -> None:
        self.jam_track_handler = JamTrackHandler()
        pass

    async def handle_embed(self, interaction: discord.Interaction, matched_tracks:list, key:str, mode:str, songName: str = ''):
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

        view = constants.PaginatorView(embed_array, interaction.user.id)
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

        await self.handle_embed(interaction=interaction, matched_tracks=matched_tracks, key=chosen_key.code, mode=chosen_mode.code)

    async def handle_keymode_match_from_song(self, interaction: discord.Interaction, song:str):
        track_list = self.jam_track_handler.get_jam_tracks()

        if not track_list:
            await interaction.response.send_message(embed=constants.common_error_embed('Could not get tracks.'), ephemeral=True)
            return

        matched_track = self.jam_track_handler.fuzzy_search_tracks(track_list, song)
        if not matched_track:
            await interaction.response.send_message(embed=constants.common_error_embed(f"The search query \"{song}\" did not give any results."))
            return
            
        track = matched_track[0]

        chosen_key = constants.KeyTypes[track["track"]["mk"]].value
        chosen_mode = constants.ModeTypes[track["track"]["mm"]].value

        matched_tracks = self.jam_track_handler.get_matching_key_mode_jam_tracks(track_list, chosen_key.code, chosen_mode.code)

        await self.handle_embed(interaction=interaction, matched_tracks=matched_tracks, key=chosen_key.code, mode=chosen_mode.code, songName=track["track"]["tt"])
