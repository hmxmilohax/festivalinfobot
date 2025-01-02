import asyncio
from datetime import datetime, timedelta
import json
import logging
import secrets
import discord
import jwt
import requests
import bot.constants as const

# dont worry this works
class AccountLinking():
    def __init__(self, bot: discord.Client):
        self.bot = bot

    async def link_interaction(self, interaction: discord.Interaction):
        # first check if the account isnt linked

        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        logging.debug(f'[GET] {const.SERVER_URL}/link/{interaction.user.id}')
        islinked = requests.get(f'{const.SERVER_URL}/link/{interaction.user.id}', headers={'Authorization': const.BOT_TOKEN})
        if islinked.status_code == 200:
            failure_embed = discord.Embed(title="Account Linking", colour=0x8927A1)
            failure_embed.add_field(name="❌ Account Already Linked", value="Your account is already linked to an Epic Games account.\nPlease unlink it first before linking another account.")
            await interaction.edit_original_response(embed=failure_embed, view=None)
            return
        
        # initiate an "oauth flow"

        state = secrets.token_hex(32)
        logging.debug(f'[POST] {const.SERVER_URL}/oauth/{state}')
        statereq = requests.post(f'{const.SERVER_URL}/oauth/{state}', json={
            "user_id": str(interaction.user.id)
        }, headers={'Authorization': const.BOT_TOKEN})
        # print(statereq.text, statereq.status_code)
        if not statereq.ok:
            try:
                if statereq.json()['error'] == 'FLOW_ALREADY_EXISTS':
                    await interaction.edit_original_response(embed=discord.Embed(title="Account Linking", colour=0x8927A1, description="❌ Something is wrong. Try again, maybe?"))
                    return
                else:
                    statereq.raise_for_status()
            except:
                await interaction.edit_original_response(embed=discord.Embed(title="Account Linking", colour=0x8927A1, description="❌ An error occurred while trying to link your account."))
                return
        else:
            # create a loop every 10 seconds
            expire_time = datetime.fromisoformat(statereq.json()['expires_at'])

            linked = False
            epic_code = None

            while not linked:
                logging.debug(f'[GET] {const.SERVER_URL}/oauth/{state}')
                linkedreq = requests.get(f'{const.SERVER_URL}/oauth/{state}', headers={'Authorization': const.BOT_TOKEN})

                if linkedreq.status_code == 200:
                    epic_code = linkedreq.json()['authorization_code']
                    linked = True
                    break
                elif linkedreq.status_code == 400:
                    embed = discord.Embed(title="Account Linking", colour=0x8927A1)
                    embed.add_field(name="🔗 Linking your account...", value="To link your account, please press the \"Authorize\" button.\nBy linking your account, you agree to the [Terms of Service](https://github.com/hmxmilohax/festivalinfobot/blob/main/terms_of_service.md) and [Privacy Policy](https://github.com/hmxmilohax/festivalinfobot/blob/main/privacy_policy.md).", inline=False)
                    embed.add_field(name="Next Retry", value=f"{discord.utils.format_dt(datetime.now() + timedelta(seconds=10), 'R')}", inline=True)
                    embed.add_field(name="Expires", value=f"{discord.utils.format_dt(expire_time, 'R')}", inline=True)
                    embed.set_footer(text="Festival Tracker is not associated or affiliated with Epic Games.")
                    embed.set_thumbnail(url=self.bot.user.avatar.url)
                    view = const.OneButtonSimpleView(on_press=None, user_id=interaction.user.id, label="Authorize", emoji="🔗", link=statereq.json()['authorize_url'])
                    view.message = await interaction.edit_original_response(embed=embed, view=view)
                elif linkedreq.status_code == 404:
                    await interaction.edit_original_response(embed=discord.Embed(title="Account Linking", colour=0x8927A1, description="⏰ The time ran out. Please try again."))
                    return
                else:
                    await interaction.edit_original_response(embed=discord.Embed(title="Account Linking", colour=0x8927A1, description="❌ An error occurred while trying to link your account."))
                    return
                
                await asyncio.sleep(10)

            # if linked, then we can continue
            logging.debug(f'[POST] https://api.epicgames.dev/epic/oauth/v2/token')
            epicidentity = requests.post('https://api.epicgames.dev/epic/oauth/v2/token', data={
                "grant_type": "authorization_code",
                "code": epic_code
            }, headers={
                "Authorization": const.APP_TOKEN
            })

            if epicidentity.ok:
                token = epicidentity.json()['access_token']
                header = jwt.get_unverified_header(token)
                decoded_jwt = jwt.decode(token, options={"verify_signature": False})
                displayname = decoded_jwt['dn']
                accid = epicidentity.json()['account_id']
                logging.debug(f'[GET] https://api.epicgames.dev/epic/id/v2/accounts?accountId={accid}')
                acclinkinfo = requests.get(f'https://api.epicgames.dev/epic/id/v2/accounts?accountId={accid}', headers={
                    "Authorization": f"Bearer {token}"
                })

                identityprovideremojidict = {
                    "epic": "<:epic:1320256573704114237>",
                    "psn": "<:psn:1320256396763205722>",
                    "xbl": "<:xbl:1320256098149859358>",
                    "nintendo": "<:nintendo:1320257203910869052>",
                    "steam": "<:steam:1320256805611245669>",
                }

                if acclinkinfo.ok:
                    identityproviders: list = acclinkinfo.json()[0]['linkedAccounts']
                    identityproviders.insert(0, {"identityProviderId": "epic", "displayName": displayname})
                    identityproviderstr = " • ".join([f"{identityprovideremojidict.get(i['identityProviderId'], i['identityProviderId'])} {i['displayName']}" for i in identityproviders])

                    linkconfirmembed = discord.Embed(title="Account Linking", description=f"Logged in as **{displayname}**", colour=0x8927A1)
                    linkconfirmembed.add_field(name="", value=identityproviderstr, inline=False)

                    linkconfirmembed.add_field(name="Continue?", value="By linking your account, you agree to the [Terms of Service](https://github.com/hmxmilohax/festivalinfobot/blob/main/terms_of_service.md) and [Privacy Policy](https://github.com/hmxmilohax/festivalinfobot/blob/main/privacy_policy.md).", inline=False)

                    linkconfirmembed.set_footer(text="Festival Tracker is not affiliated to Epic Games. By continuing, you authorize to create a profile in our services, identifiable by your Epic Games account. If you wish to cancel, press \"Options\". You cannot return from the Options menu.")
                    linkconfirmembed.set_thumbnail(url=self.bot.user.avatar.url)

                    async def continuelink():
                        # TODO
                        pass

                    async def optionsmenu():
                        async def cancel():
                            await interaction.edit_original_response(embed=discord.Embed(title="Account Linking", colour=0x8927A1, description="❌ You stopped linking your account."), view=discord.ui.View())
                            return
                        
                        async def switchaccount():
                            return await self.link_interaction(interaction)

                        optionsmenuemed = discord.Embed(title="Account Linking", colour=0x8927A1, description="⚙️ Options")
                        optionsmenuemed.add_field(name="**Cancel**", value="Stop linking your account", inline=False)
                        optionsmenuemed.add_field(name="**Switch Account**", value="Switch the account you're linking", inline=False)
                        optionsmenuemed.set_thumbnail(url=self.bot.user.avatar.url)
                        optimenu = const.TwoButtonSimpleView(onpress1=switchaccount, onpress2=cancel, user_id=interaction.user.id, label1="Switch Account", emoji1="🔁", label2="Stop Linking", emoji2=None)
                        optimenu.message = await interaction.edit_original_response(embed=optionsmenuemed, view=optimenu)

                    twooptview = const.TwoButtonSimpleView(onpress1=continuelink, onpress2=optionsmenu, user_id=interaction.user.id, label1="Continue", emoji1="✅", label2="Options", emoji2="⚙️")
                    twooptview.message = await interaction.edit_original_response(embed=linkconfirmembed, view=twooptview)

                    logging.debug(f'[DELETE] {const.SERVER_URL}/oauth/{state}')
                    deletestatereq = requests.delete(f'{const.SERVER_URL}/oauth/{state}', headers={'Authorization': const.BOT_TOKEN})
                else:
                    await interaction.edit_original_response(embed=discord.Embed(title="Account Linking", colour=0x8927A1, description="❌ An error occurred while trying to retrieve your account's information."))
                    return
            else:
                await interaction.edit_original_response(embed=discord.Embed(title="Account Linking", colour=0x8927A1, description="❌ An error occurred while trying to link your account."))
                return