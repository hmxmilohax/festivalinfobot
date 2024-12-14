from datetime import datetime as dt
import datetime
import discord
import logging

import requests

from bot.constants import OneButtonSimpleView

class StatusHandler():
    def __init__(self) -> None:
        pass

    async def handle_fortnitestatus_interaction(self, interaction: discord.Interaction):
        lightswitch_url = 'https://raw.githubusercontent.com/FNLookup/data/main/nitestats/light_switch.json'
        timestamp_url = 'https://raw.githubusercontent.com/FNLookup/data/refs/heads/main/nitestats/timestamp.json'
        logging.debug(f'[GET] {lightswitch_url}')
        logging.debug(f'[GET] {timestamp_url}')

        await interaction.response.defer()

        response = requests.get(lightswitch_url)
        data = response.json()[0]

        timestamp = requests.get(timestamp_url).json()['timestamp']

        is_fortnite_online = data['status'] == 'UP'
        status_unknown = False
        if data['status'] not in ['UP', 'DOWN']:
            is_fortnite_online = True
            status_unknown = True

        colour = 0x25be56 # green
        if not is_fortnite_online:
            colour = 0xbe2625 # red
        if status_unknown:
            colour = 0xff7a08 # orange (perhaps)

        embed = discord.Embed(title="Fortnite Status", description=data['message'], colour=colour)
        date = dt.fromtimestamp(float(timestamp), datetime.timezone.utc).strftime('%B %d, %Y at %I:%M:%S %p UTC')
        embed.set_footer(text=f"Last Updated: {date}")

        await interaction.edit_original_response(embed=embed)

    async def handle_gamemode_interaction(self, interaction: discord.Interaction, search_for:str = 'Festival Main Stage'):
        manifest_url = 'https://raw.githubusercontent.com/FNLookup/data/main/page/context_en-US.json'
        logging.debug(f'[GET] {manifest_url}')

        await interaction.response.defer()

        response = requests.get(manifest_url)
        island_groups = response.json()['state']['loaderData']['routes/_index']['islands'] # hopefully this doesnt break
        
        island_data = None

        for group in island_groups:
            for island in group['islands']:
                if island.get('title', '') == search_for:
                    island_data = island

        if island_data:
            desc = "Play in a band with friends or perform solo on stage with hit music by your favorite artists in Fortnite Festival! On the Main Stage, play a featured rotation of Jam Tracks. Compete against friends for the best performance or team up to climb the leaderboards. The festival is just beginning with more Jam Tracks, Music Icons, concerts, and stages coming soon. Take your stage in Fortnite Festival!"
            if search_for == 'Festival Battle Stage':
                desc = "Let the battle begin! Compete in a musical free-for-all where only one player will emerge victorious. Perform a 4-song setlist of hit music, while taking and launching attacks. Seize the stage!"
            elif search_for == 'Festival Jam Stage':
                desc = "Explore the Jam Stage festival grounds to find friends and stages where you can mix hit music using the Jam Tracks in your locker. The festival is just beginning with more Jam Tracks, Music Icons, concerts, and stages coming soon. Take your stage in Fortnite Festival!"

            embed = discord.Embed(title=island_data['title'], description=desc, color=0x8927A1)
            if island_data.get('label', False):
                embed.add_field(name="Label", value=island_data['label'])
            embed.add_field(name="Players", value=island_data['ccu'])

            rating = island_data['ageRatingTextAbbr']
            if island_data['ageRatingTextAbbr'] == 'T':
                rating = 'Teen'
            if island_data['ageRatingTextAbbr'] == 'E10+':
                rating = 'Everyone 10+'

            embed.add_field(name="Rating", value=rating)
            embed.set_image(url=island_data['squareImgSrc'])

            view = OneButtonSimpleView(on_press=None, user_id=interaction.user.id, label="View More", link=f"https://fortnite.com{island_data['islandUrl']}", emoji=None)
            view.message = await interaction.original_response()

            await interaction.edit_original_response(embed=embed, view=view)
        else:
            embed = discord.Embed(title=search_for, description="The island is currently not available in the API.", color=0x8927A1)
            await interaction.edit_original_response(embed=embed)