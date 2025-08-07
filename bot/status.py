from datetime import datetime as dt
import datetime
import discord
from discord.ext import commands
import logging
from bot import constants
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

        embed = discord.Embed(title="Festival Status", description=data['message'], colour=colour)

        await interaction.edit_original_response(embed=embed)

    def generate_metrics(self, ccu, metrics_url):
        logging.debug(f'[GET] {metrics_url}')
        metrics_req = requests.get(metrics_url)
        metrics_req.raise_for_status()
        
        metrics_data = metrics_req.json()
        metrics = metrics_data['intervals']

        metric = ''
        same = '*️⃣'
        more = '🔼'
        less = '🔽'

        last_value = 0
        for interval in metrics:
            ts = interval['timestamp']
            vl = interval['value']

            if vl != None:
                differ = same
                if last_value > vl:
                    differ = less
                elif last_value < vl:
                    differ = more

                if last_value != 0:
                    fmt_ts = discord.utils.format_dt(datetime.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=datetime.timezone.utc), 'R')

                    metric = f'{differ} {fmt_ts}**: {vl}**\n{metric}'

                last_value = vl
            elif vl == None:
                metric = f'{ts}: ⛔ \n{metric}'

        metric_differ_now = same
        if last_value > ccu:
            metric_differ_now = less
        elif last_value < ccu:
            metric_differ_now = more

        metric_start = f'### {metric_differ_now} Now: {ccu}'
        return metric_start + f'\n{metric}'

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

        # epiclabs = f'https://fn-service-discovery-live-public.ogs.live.on.epicgames.com/api/v1/creator/page/63ba52bf92554227820f4dd0a8cc6845?playerId={self.oauth.account_id}&limit=100'
        # logging.debug(f'[GET] {epiclabs}')

        # epiclabsresponse = requests.get(epiclabs, headers={
        #     'Authorization': self.oauth.session_token
        # })

        links_info = f'https://links-public-service-live.ol.epicgames.com/links/api/fn/mnemonic?ignoreFailures=true'
        payload = [
            {
                "mnemonic": "set_battlestage_playlists",
                "type": "",
                "filter": False,
                "v": ""
            },
            {
                "mnemonic": "playlist_pilgrimquickplay",
                "type": "",
                "filter": False,
                "v": ""
            },
            {
                "mnemonic": "playlist_fmclubisland",
                "type": "",
                "filter": False,
                "v": ""
            },
        ]

        # epiclabsresponse.raise_for_status()
        response.raise_for_status()
        # print(response.text)
        data = response.json()

        links_req = requests.post(links_info, json=payload, headers={
            'Authorization': self.oauth.session_token
        })
        links_req.raise_for_status()
        # print(links_req.text)
        links_data = links_req.json()

        # datalabs = epiclabsresponse.json()
        jam_stage = discord.utils.find(lambda p: p['linkCode'] == 'playlist_fmclubisland', data['links'])
        battle_stage = discord.utils.find(lambda p: p['linkCode'] == 'set_battlestage_playlists', data['links'])
        main_stage = discord.utils.find(lambda p: p['linkCode'] == 'playlist_pilgrimquickplay', data['links'])
        # dance_with_sabrina = discord.utils.find(lambda p: p['linkCode'] == '4030-2345-0180', datalabs['links'])

        jam_stage_data = discord.utils.find(lambda p: p['mnemonic'] == 'playlist_fmclubisland', links_data)
        battle_stage_data = discord.utils.find(lambda p: p['mnemonic'] == 'set_battlestage_playlists', links_data)
        main_stage_data = discord.utils.find(lambda p: p['mnemonic'] == 'playlist_pilgrimquickplay', links_data)

        now_ts = datetime.datetime.now(datetime.timezone.utc)
        # FRICK YOU DATETIME MODULE
        now_3h_ago = (now_ts - datetime.timedelta(hours=3)).isoformat(timespec='milliseconds')[:-6] + 'Z'

        metrics_jam_stage = f'https://api.fortnite.com/ecosystem/v1/islands/playlist_fmclubisland/metrics/hour/peak-ccu?from={now_3h_ago}'
        metrics_battle_stage = f'https://api.fortnite.com/ecosystem/v1/islands/set_battlestage_playlists/metrics/hour/peak-ccu?from={now_3h_ago}'
        metrics_main_stage = f'https://api.fortnite.com/ecosystem/v1/islands/playlist_pilgrimquickplay/metrics/hour/peak-ccu?from={now_3h_ago}'

        # print(jam_stage_data)

        total_ccu = battle_stage['globalCCU'] + main_stage['globalCCU'] + jam_stage['globalCCU']
        
        jam_stage_metrics = self.generate_metrics(jam_stage['globalCCU'], metrics_jam_stage)
        battle_stage_metrics = self.generate_metrics(battle_stage['globalCCU'], metrics_battle_stage)
        main_stage_metrics = self.generate_metrics(main_stage['globalCCU'], metrics_main_stage)

        # TODO Localize images and titles

        view = discord.ui.LayoutView()
        ctr = discord.ui.Container()
        ctr.add_item(
            discord.ui.Section(
                "# Fortnite Festival Active Players",
                f"## Total: {total_ccu}",
                accessory=discord.ui.Thumbnail(f"attachment://{constants.KEYART_FNAME}")
            )
        ).add_item(
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small)
        ).add_item(
            discord.ui.Section(
                f"## {jam_stage_data['metadata']['title']}",
                jam_stage_metrics,
                accessory=discord.ui.Thumbnail(jam_stage_data['metadata']['image_url'])
            )
        ).add_item(
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small)
        ).add_item(
            discord.ui.Section(
                f"## {battle_stage_data['metadata']['title']}",
                battle_stage_metrics,
                accessory=discord.ui.Thumbnail(battle_stage_data['metadata']['image_url'])
            )
        ).add_item(
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small)
        ).add_item(
            discord.ui.Section(
                f"## {main_stage_data['metadata']['title']}",
                main_stage_metrics,
                accessory=discord.ui.Thumbnail(main_stage_data['metadata']['image_url'])
            )
        ).add_item(
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small)
        ).add_item(
            discord.ui.TextDisplay("-# Festival Tracker")
        )
        view.add_item(ctr)

        embed = discord.Embed(title="Fortnite Festival Active Players", color=0x8927A1)
        embed.add_field(name="Total", value=total_ccu, inline=False)
        # embed.add_field(name="Jam Stage", value=jam_stage['globalCCU'])
        embed.add_field(name="Battle Stage", value=battle_stage['globalCCU'])
        embed.add_field(name="Main Stage", value=main_stage['globalCCU'])
        embed.add_field(name="Jam Stage", value=jam_stage['globalCCU'])
        await interaction.edit_original_response(view=view, attachments=[discord.File(constants.KEYART_PATH, constants.KEYART_FNAME)])