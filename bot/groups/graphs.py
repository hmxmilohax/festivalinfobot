# import logging
from discord import app_commands
import discord
from discord.ext import commands

from bot import constants, database
from bot.tools.graph import GraphingFuncs
from bot.tools.midi import MidiArchiveTools
from bot.tracks import JamTrackHandler
from bot import constants as const
import os

class GraphCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config = bot.config
        self.graph_handler = GraphCommandsHandler()

    graph_group = app_commands.Group(name="graph", description="Graph Command Group.", allowed_contexts=discord.app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True), allowed_installs=discord.app_commands.AppInstallationType(guild=True, user=True))

    graph_notes_group = app_commands.Group(name="counts", description="Graph the note and lift counts for a specific song.", parent=graph_group)
    @graph_notes_group.command(name="all", description="Graph the note counts for a specific song.")
    @app_commands.describe(song = "A search query: an artist, song name, or shortname.")
    async def graph_note_counts_command(self, interaction: discord.Interaction, song:str):
        await self.graph_handler.handle_pdi_interaction(interaction=interaction, song=song)

    @graph_notes_group.command(name="lifts", description="Graph the lift counts for a specific song.")
    @app_commands.describe(song = "A search query: an artist, song name, or shortname.")
    async def graph_note_counts_command(self, interaction: discord.Interaction, song:str):
        await self.graph_handler.handle_lift_interaction(interaction=interaction, song=song)

    @graph_notes_group.command(name="lanes", description="Graph the number of notes for each lane in a specific song, instrument, and difficulty.")
    @app_commands.describe(song = "A search query: an artist, song name, or shortname.")
    @app_commands.describe(instrument = "The instrument to view the #notes of.")
    @app_commands.describe(difficulty = "The difficulty to view the #notes for.")
    async def graph_lanes_command(self, interaction: discord.Interaction, song:str, instrument : constants.Instruments, difficulty : constants.Difficulties = constants.Difficulties.Expert):
        await self.graph_handler.handle_lanes_interaction(interaction=interaction, song=song, instrument=instrument, difficulty=difficulty)

    @graph_group.command(name="nps", description="Graph the NPS (Notes per second) for a specific song, instrument, and difficulty.")
    @app_commands.describe(song = "A search query: an artist, song name, or shortname.")
    @app_commands.describe(instrument = "The instrument to view the NPS of.")
    @app_commands.describe(difficulty = "The difficulty to view the NPS for.")
    async def graph_nps_command(self, interaction: discord.Interaction, song:str, instrument : constants.Instruments, difficulty : constants.Difficulties = constants.Difficulties.Expert):
        await self.graph_handler.handle_nps_interaction(interaction=interaction, song=song, instrument=instrument, difficulty=difficulty)

class GraphCommandsHandler():
    def __init__(self) -> None:
        self.jam_track_handler = JamTrackHandler()
        self.midi_tool = MidiArchiveTools()

    async def handle_pdi_interaction(self, interaction:discord.Interaction, song:str):
        tracklist = constants.get_jam_tracks(use_cache=True, max_cache_age=60)
        if not tracklist:
            await interaction.response.send_message(embed=const.common_error_embed('Could not get tracks.'), ephemeral=True)
            return

        matched_tracks = self.jam_track_handler.fuzzy_search_tracks(tracklist, song)
        if not matched_tracks:
            await interaction.response.send_message(embed=const.common_error_embed(f"The search query \"{song}\" did not give any results."))
            return

        await interaction.response.defer() # Makes the bot say Thinking...
        # From here on onwards, must use edit_original_response

        user_id = interaction.user.id
        session_hash = constants.generate_session_hash(user_id, song)

        # Use the first matched track
        song_data = matched_tracks[0]
        song_url = song_data['track'].get('mu')
        album_art_url = song_data['track'].get('au')
        track_title = song_data['track'].get('tt')
        short_name = song_data['track'].get('sn')
        artist_title = song_data['track'].get('an')

        midi_file = await self.midi_tool.save_chart(song_url)
        
        image_path = f'{short_name}_pdi_graph_{session_hash}.png'
        GraphingFuncs().generate_no_notes_pdi_chart(midi_path=midi_file, path=image_path, song_name=track_title, song_artist=artist_title)
        
        embed = discord.Embed(title=f"Note counts for\n**{track_title}** - *{artist_title}*", colour=constants.ACCENT_COLOUR)
        file = discord.File(os.path.join(constants.TEMP_FOLDER, image_path), filename=image_path)
        embed.set_image(url=f"attachment://{image_path}")
        embed.set_thumbnail(url=album_art_url)
        embed.set_footer(text="Festival Tracker")
        await interaction.edit_original_response(embed=embed, attachments=[file])

        constants.delete_session_files(session_hash)

    async def handle_lift_interaction(self, interaction:discord.Interaction, song:str):
        tracklist = constants.get_jam_tracks(use_cache=True, max_cache_age=60)
        if not tracklist:
            await interaction.response.send_message(embed=const.common_error_embed('Could not get tracks.'), ephemeral=True)
            return

        matched_tracks = self.jam_track_handler.fuzzy_search_tracks(tracklist, song)
        if not matched_tracks:
            await interaction.response.send_message(embed=const.common_error_embed(f"The search query \"{song}\" did not give any results."))
            return

        await interaction.response.defer() # Makes the bot say Thinking...
        # From here on onwards, must use edit_original_response

        user_id = interaction.user.id
        session_hash = constants.generate_session_hash(user_id, song)

        song_data = matched_tracks[0]
        song_url = song_data['track'].get('mu')
        album_art_url = song_data['track'].get('au')
        track_title = song_data['track'].get('tt')
        short_name = song_data['track'].get('sn')
        artist_title = song_data['track'].get('an')

        midi_file = await self.midi_tool.save_chart(song_url)
        
        image_path = f'{short_name}_lift_graph_{session_hash}.png'
        GraphingFuncs().generate_no_notes_pdi_chart(midi_path=midi_file, path=image_path, song_name=track_title, song_artist=artist_title, lifts=True)
        
        embed = discord.Embed(title=f"Lift counts for\n**{track_title}** - *{artist_title}*", colour=constants.ACCENT_COLOUR)
        file = discord.File(os.path.join(constants.TEMP_FOLDER, image_path), filename=image_path)
        embed.set_image(url=f"attachment://{image_path}")
        embed.set_thumbnail(url=album_art_url)
        embed.set_footer(text="Festival Tracker")
        await interaction.edit_original_response(embed=embed, attachments=[file])

        constants.delete_session_files(session_hash)

    async def handle_nps_interaction(self, interaction:discord.Interaction, song:str, instrument : constants.Instruments, difficulty : constants.Difficulties = constants.Difficulties.Expert):
        chosen_instrument = constants.Instruments[str(instrument).replace('Instruments.', '')].value
        chosen_diff = constants.Difficulties[str(difficulty).replace('Difficulties.', '')].value

        tracklist = constants.get_jam_tracks(use_cache=True, max_cache_age=60)
        if not tracklist:
            await interaction.response.send_message(embed=const.common_error_embed('Could not get tracks.'), ephemeral=True)
            return

        matched_tracks = self.jam_track_handler.fuzzy_search_tracks(tracklist, song)
        if not matched_tracks:
            await interaction.response.send_message(embed=const.common_error_embed(f"The search query \"{song}\" did not give any results."))
            return

        await interaction.response.defer() # Makes the bot say Thinking...
        # From here on onwards, must use edit_original_response

        user_id = interaction.user.id
        session_hash = constants.generate_session_hash(user_id, song)

        song_data = matched_tracks[0]
        song_url = song_data['track'].get('mu')
        album_art_url = song_data['track'].get('au')
        track_title = song_data['track'].get('tt')
        short_name = song_data['track'].get('sn')
        artist_title = song_data['track'].get('an')

        midi_file = await self.midi_tool.save_chart(song_url)
        
        image_path = f'{short_name}_nps_graph_{session_hash}.png'
        GraphingFuncs().generate_nps_chart(midi_path=midi_file, path=image_path, inst=chosen_instrument, diff=chosen_diff, song_name=track_title, song_artist=artist_title)
        
        embed = discord.Embed(title=f"NPS Graph for\n**{track_title}** - *{artist_title}*", colour=constants.ACCENT_COLOUR)
        file = discord.File(os.path.join(constants.TEMP_FOLDER, image_path), filename=image_path)
        embed.set_image(url=f"attachment://{image_path}")
        embed.set_thumbnail(url=album_art_url)
        embed.set_footer(text="Festival Tracker")
        await interaction.edit_original_response(embed=embed, attachments=[file])

        constants.delete_session_files(session_hash)

    async def handle_lanes_interaction(self, interaction:discord.Interaction, song:str, instrument : constants.Instruments, difficulty : constants.Difficulties = constants.Difficulties.Expert):
        chosen_instrument = constants.Instruments[str(instrument).replace('Instruments.', '')].value
        chosen_diff = constants.Difficulties[str(difficulty).replace('Difficulties.', '')].value

        tracklist = constants.get_jam_tracks(use_cache=True, max_cache_age=60)
        if not tracklist:
            await interaction.response.send_message(embed=const.common_error_embed('Could not get tracks.'), ephemeral=True)
            return

        matched_tracks = self.jam_track_handler.fuzzy_search_tracks(tracklist, song)
        if not matched_tracks:
            await interaction.response.send_message(embed=const.common_error_embed(f"The search query \"{song}\" did not give any results."))
            return

        await interaction.response.defer() # Makes the bot say Thinking...
        # From here on onwards, must use edit_original_response

        user_id = interaction.user.id
        session_hash = constants.generate_session_hash(user_id, song)

        # Use the first matched track
        song_data = matched_tracks[0]
        song_url = song_data['track'].get('mu')
        album_art_url = song_data['track'].get('au')
        track_title = song_data['track'].get('tt')
        short_name = song_data['track'].get('sn')
        artist_title = song_data['track'].get('an')

        midi_file = await self.midi_tool.save_chart(song_url)
        
        image_path = f'{short_name}_lanes_graph_{session_hash}.png'
        GraphingFuncs().generate_lanes_chart(midi_path=midi_file, spath=image_path, inst=chosen_instrument, diff=chosen_diff, song_name=track_title, song_artist=artist_title)
        
        embed = discord.Embed(title=f"Notes per lane graph for\n**{track_title}** - *{artist_title}*", colour=constants.ACCENT_COLOUR)
        file = discord.File(os.path.join(constants.TEMP_FOLDER, image_path), filename=image_path)
        embed.set_image(url=f"attachment://{image_path}")
        embed.set_thumbnail(url=album_art_url)
        embed.set_footer(text="Festival Tracker")
        await interaction.edit_original_response(embed=embed, attachments=[file])

        constants.delete_session_files(session_hash)