from datetime import datetime
import json
import logging
from discord import app_commands
import discord
from discord.ext import commands
import requests

from bot.status import StatusHandler

FESTRPC_HIGHWIRE = 'http://festrpc.highwi.re'
FESTRPC_PORT = '8924'
FESTRPC_DATAPATH = 'data.json'
FESTRPC_URL = 'http://festrpc.highwi.re:8924/data.json'

class FestRPCCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    festrpc = app_commands.Group(name="festrpc", description="FestRPC Commands", allowed_contexts=discord.app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True), allowed_installs=discord.app_commands.AppInstallationType(guild=True, user=True))

    @festrpc.command(name="about", description="Display information about Festival RPC")
    async def about(self, interaction: discord.Interaction):
        embed = discord.Embed(title="Festival RPC", colour=0x50b424)
        embed.add_field(name='What is Festival RPC?', value="[Festival RPC](https://github.com/mmccall0813/BetterFortniteRPC/) is a program that allows you to display the songs you play in Fortnite Festival on your Discord profile as Rich Presence (or Activity).\nFestival RPC can also scrobble the songs you play to [last.fm](https://www.last.fm/), provided you have an API key.", inline=False)
        embed.add_field(name='How do I set-up Festival RPC?', value='To set-up Festival RPC, first [download it here](https://github.com/mmccall0813/BetterFortnite/archive/refs/heads/main.zip)\nNow, download [node.js](https://nodejs.org/en) and install it. The process wont take long.\nAfterwards, extract `festivalrpc-main.zip` and run `install_deps.bat`.\nNow, run `start.bat` and you\'re ready to share your activity!', inline=False)
        embed.add_field(name='Festival Tracker integration', value='By opting-in to analytics while starting Festival RPC for the first time, you will allow Festival Tracker to view your play time and statistics!\nSimply choose `y`, enter in a nickname to create your local profile and you are ready to share your statistics with others!', inline=False)
        await interaction.response.send_message(embed=embed)

    @festrpc.command(name="online", description="Ping the Festival RPC server to check if it is online.")
    async def online(self, interaction: discord.Interaction):
        await interaction.response.defer()

        festrpcdatauri = f'{FESTRPC_HIGHWIRE}:{FESTRPC_PORT}/{FESTRPC_DATAPATH}'
        logging.debug(f'[GET] {festrpcdatauri}')
        try:
            req = requests.get(festrpcdatauri)
        except:
            embed = discord.Embed(title="Festival RPC is not online.", colour=0xda1619)
            embed.add_field(name="", value="Sorry; Festival RPC is currently not online to process statistics.")
            await interaction.edit_original_response(embed=embed)
            return
        else:
            if not req.ok:
                embed = discord.Embed(title="Festival RPC is not available.", colour=0xda1619)
                embed.add_field(name="", value="Sorry; Festival RPC is currently not available to process statistics.")
                await interaction.edit_original_response(embed=embed)
            else:
                embed = discord.Embed(title="Festival RPC", colour=0x50b424)
                embed.add_field(name="", value="Festival RPC is online!")
                await interaction.edit_original_response(embed=embed)

    @festrpc.command(name="recent", description="View the most recent song plays by Festival RPC users.")
    async def recent(self, interaction: discord.Interaction):
        await interaction.response.defer()

        festrpcdatauri = f'{FESTRPC_HIGHWIRE}:{FESTRPC_PORT}/{FESTRPC_DATAPATH}'
        logging.debug(f'[GET] {festrpcdatauri}')
        try:
            req = requests.get(festrpcdatauri)
        except:
            embed = discord.Embed(title="Festival RPC is not online.", colour=0xda1619)
            embed.add_field(name="", value="Sorry; Festival RPC is currently not online to process statistics.")
            await interaction.edit_original_response(embed=embed)
            return
        else:
            if not req.ok:
                embed = discord.Embed(title="Festival RPC is not available.", colour=0xda1619)
                embed.add_field(name="", value="Sorry; Festival RPC is currently not available to process statistics.")
                await interaction.edit_original_response(embed=embed)
            else:
                all_plays = []
                data = req.json()
                for song in data.keys():
                    song_info = data[song]
                    play_info = song_info['plays']
                    for play in play_info:
                        play['song'] = song_info['meta']
                    
                    all_plays.extend(play_info)

                all_plays.sort(key=lambda x: x["date"], reverse=True)

                all_plays = all_plays[:10]

                embed = discord.Embed(title="Recent Plays", colour=0x8927A1)
                text = ''
                for entry in all_plays:
                    text += f'{discord.utils.format_dt(datetime.fromtimestamp(entry["date"] / 1000), 'R')}'
                    text += ' '
                    text += f'`{entry["difficulty"]} {entry["instrument"]}` '
                    text += f'**{entry["song"]["tt"]} - {entry["song"]["an"]}**\n'
                    text += f'{entry["id"]} for {entry["duration"]}s'
                    text += '\n\n'

                embed.add_field(name="", value="The last 10 plays recorded in Festival RPC.", inline=False)
                embed.add_field(name="Recent Plays", value=text, inline=False)
                await interaction.edit_original_response(embed=embed)