from datetime import datetime as dt
import datetime
import discord
from discord.ext import commands
import logging
from bot.groups.oauthmanager import OAuthManager

import requests

from bot.constants import OneButtonSimpleView

class StatusHandler():
    def __init__(self, bot: commands.Bot) -> None:
        self.oauth: OAuthManager = bot.oauth_manager

    async def handle_fortnitestatus_interaction(self, interaction: discord.Interaction):
        lightswitch_url = 'http://lightswitch-public-service-prod.ol.epicgames.com/lightswitch/api/service/Fortnite/status'
        logging.debug(f'[GET] {lightswitch_url}')

        await interaction.response.defer()

        response = requests.get(lightswitch_url, headers={
            'Authorization': self.oauth.session_token    
        })
        data = response.json()

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

        await interaction.edit_original_response(embed=embed)

    async def handle_gamemode_interaction(self, interaction: discord.Interaction):
        # battle stage: playlist_pilgrimbattlestage | set_battlestage_playlists
        # main stage: playlist_pilgrimquickplay
        # jam stage: playlist_fmclubisland

        discovery_profile = f'https://fn-service-discovery-live-public.ogs.live.on.epicgames.com/api/v1/creator/page/epic?playerId={self.oauth.account_id}&limit=100'
        logging.debug(f'[GET] {discovery_profile}')

        await interaction.response.defer()

        response = requests.get(discovery_profile, headers={
            'Authorization': self.oauth.session_token
        })

        epiclabs = f'https://fn-service-discovery-live-public.ogs.live.on.epicgames.com/api/v1/creator/page/63ba52bf92554227820f4dd0a8cc6845?playerId={self.oauth.account_id}&limit=100'
        logging.debug(f'[GET] {epiclabs}')

        epiclabsresponse = requests.get(epiclabs, headers={
            'Authorization': self.oauth.session_token
        })

        # print(epiclabsresponse.text)

        epiclabsresponse.raise_for_status()
        response.raise_for_status()

        data = response.json()
        datalabs = epiclabsresponse.json()
        # jam_stage = discord.utils.find(lambda p: p['linkCode'] == 'playlist_fmclubisland', data['links'])
        battle_stage = discord.utils.find(lambda p: p['linkCode'] == 'set_battlestage_playlists', data['links'])
        main_stage = discord.utils.find(lambda p: p['linkCode'] == 'playlist_pilgrimquickplay', data['links'])
        dance_with_sabrina = discord.utils.find(lambda p: p['linkCode'] == '4030-2345-0180', datalabs['links'])

        total_ccu = battle_stage['globalCCU'] + main_stage['globalCCU'] + dance_with_sabrina['globalCCU']

        embed = discord.Embed(title="Fortnite Festival Active Players", color=0x8927A1)
        embed.add_field(name="Total", value=total_ccu, inline=False)
        # embed.add_field(name="Jam Stage", value=jam_stage['globalCCU'])
        embed.add_field(name="Battle Stage", value=battle_stage['globalCCU'])
        embed.add_field(name="Main Stage", value=main_stage['globalCCU'])
        embed.add_field(name="Festival Jam Stage: Dance With Sabrina", value=dance_with_sabrina['globalCCU'])
        await interaction.edit_original_response(embed=embed)