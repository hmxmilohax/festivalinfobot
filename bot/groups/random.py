import logging
import random
from discord import app_commands
import discord
from discord.ext import commands

from bot import constants, database
from bot.helpers import DailyCommandHandler, ShopCommandHandler

class RandomCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config = bot.config

        self.daily_handler = DailyCommandHandler(bot)   
        self.shop_handler = ShopCommandHandler(bot)

    random_cog = app_commands.Group(name="random", description="Random Commands", allowed_contexts=discord.app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True), allowed_installs=discord.app_commands.AppInstallationType(guild=True, user=True))

    track_group = app_commands.Group(name="track", description="Track Only", parent=random_cog)

    @track_group.command(name="all", description="Get a random Jam Track from a list of all available Jam Tracks")
    async def random_track_command(self, interaction: discord.Interaction):
        await self.handle_random_track_interaction(interaction=interaction)

    @track_group.command(name="shop", description="Get a random Jam Track from only the Jam Tracks currently in the Shop.")
    async def random_track_command(self, interaction: discord.Interaction):
        await self.handle_random_track_interaction(interaction=interaction, shop=True)
    @track_group.command(name="weekly", description="Get a random Jam Track from only the Jam Tracks currently in the weekly rotation.")
    async def random_track_command(self, interaction: discord.Interaction):
        await self.handle_random_track_interaction(interaction=interaction, daily=True)

    setlist_group = app_commands.Group(name="setlist", description="Setlist Only", parent=random_cog)

    @setlist_group.command(name="all", description="Get a random setlist from the list of all available Jam Tracks")
    @app_commands.describe(limit = 'How many Jam Tracks your setlist should have.')
    async def random_setlist_command(self, interaction: discord.Interaction, limit:app_commands.Range[int, 1, 20] = 4):
        await self.handle_random_setlist_interaction(interaction=interaction, limit=limit)

    @setlist_group.command(name="shop", description="Get a random setlist from only the Jam Tracks currently in the Shop.")
    @app_commands.describe(limit = 'How many Jam Tracks your setlist should have.')
    async def random_setlist_command(self, interaction: discord.Interaction, limit:app_commands.Range[int, 1, 20] = 4):
        await self.handle_random_setlist_interaction(interaction=interaction, shop=True, limit=limit)

    @setlist_group.command(name="weekly", description="Get a random setlist from only the Jam Tracks currently in the weekly rotation.")
    @app_commands.describe(limit = 'How many Jam Tracks your setlist should have.')
    async def random_setlist_command(self, interaction: discord.Interaction, limit:app_commands.Range[int, 1, 20] = 4):
        await self.handle_random_setlist_interaction(interaction=interaction, daily=True, limit=limit)

    async def handle_random_track_interaction(self, interaction: discord.Interaction, shop: bool = False, daily: bool = False):
        await interaction.response.defer()

        track_list = constants.get_jam_tracks()

        if not track_list:
            await interaction.response.send_message(embed=constants.common_error_embed('Could not get tracks.'), ephemeral=True)
            return
        
        shop_tracks = self.shop_handler.fetch_shop_tracks()
        weekly_tracks = self.daily_handler.fetch_daily_shortnames()

        if shop:
            def inshop(obj):
                return discord.utils.find(lambda offer: offer['meta']['templateId'] == obj['track']['ti'], shop_tracks)
            track_list = list(filter(inshop, track_list))

        if daily:
            def indaily(obj):
                sn = obj['track']['sn']
                return discord.utils.find(lambda t: t['metadata']['track']['sn'] == sn, weekly_tracks) != None

            track_list = list(filter(indaily, track_list))

        async def re_roll():
            chosen_track = random.choice(track_list)
            embed = await self.search_embed_handler.generate_track_embed(chosen_track, is_random=True)
            constants.add_fields(chosen_track, embed, weekly_tracks, shop_tracks)
            await interaction.edit_original_response(embed=embed, view=reroll_view)

        reroll_view = constants.OneButtonSimpleView(on_press=re_roll, user_id=interaction.user.id, label="Reroll Track")
        reroll_view.message = await interaction.original_response()

        await re_roll()

    async def handle_random_setlist_interaction(self, interaction: discord.Interaction, shop:bool = False, daily: bool = False, limit:int = 4):
        await interaction.response.defer()

        track_list = constants.get_jam_tracks()
        if not track_list:
            await interaction.response.send_message(cembed=constants.common_error_embed('Could not get tracks.'), ephemeral=True)
            return
        
        shop_tracks = self.shop_handler.fetch_shop_tracks()
        daily_tracks = self.daily_handler.fetch_daily_shortnames()

        if shop:
            def inshop(obj):
                return discord.utils.find(lambda offer: offer['meta']['templateId'] == obj['track']['ti'], shop_tracks)
            track_list = list(filter(inshop, track_list))

        if daily:
            def indaily(obj):
                sn = obj['track']['sn']
                return discord.utils.find(lambda t: t['metadata']['track']['sn'] == sn, daily_tracks) != None

            track_list = list(filter(indaily, track_list))

        async def re_roll():
            chosen_tracks = []
            for i in range(limit):
                chosen_tracks.append(random.choice(track_list))

            embed = discord.Embed(title="Your random setlist!", description=f"The {limit} tracks are...", colour=constants.ACCENT_COLOUR)
            embed.add_field(name="", value="\n".join([f'- **{str(track["track"]["tt"])}** - *{str(track["track"]["an"])}*' for track in chosen_tracks]))
            await interaction.edit_original_response(embed=embed, view=reroll_view)

        reroll_view = constants.OneButtonSimpleView(on_press=re_roll, user_id=interaction.user.id, label="Reroll Setlist")
        reroll_view.message = await interaction.original_response()

        await re_roll()