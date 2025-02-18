import asyncio
from datetime import datetime, timedelta
import json
import logging
import secrets
import discord
import jwt
import requests
import bot.constants as const

def embed_kwargs_creator(title:str, desc: str, rm_view: bool = False) -> dict:
    pl = {
        "embed": discord.Embed(title=title, colour=0x8927A1, description=desc)
    }
    if rm_view:
        pl.update(view=None)

    return pl

def embed_simple_str_al(desc: str, rm_view: bool = False) -> dict:
    return embed_kwargs_creator("Account Linking", desc, rm_view)

def embed_simple_str_al_err(desc: str, rm_view: bool = False) -> dict:
    return embed_kwargs_creator("Account Linking", f"<:error:1327736288807358629> {desc}", rm_view)

def embed_simple_str_pm(desc: str, rm_view: bool = False) -> dict:
    return embed_kwargs_creator("Privacy Settings", desc, rm_view)

def embed_simple_str_pm_err(desc: str, rm_view: bool = False) -> dict:
    return embed_kwargs_creator("Privacy Settings", f"<:error:1327736288807358629> {desc}", rm_view)

# dont worry this works
class AccountLinking():
    def __init__(self, bot: discord.Client):
        self.bot = bot


    async def unlink_interaction(self, interaction: discord.Interaction):
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        logging.info(f'[DELETE] {const.SERVER_URL}/profile/service/link/')
        unlinkreq = requests.delete(
            f'{const.SERVER_URL}/profile/service/link/', 
            json={'discord_user_id': str(interaction.user.id)}, 
            headers={'Authorization': const.BOT_TOKEN})
        if not unlinkreq.ok:
            if unlinkreq.json()['error'] == 'ACCOUNT_NOT_LINKED':
                await interaction.edit_original_response(**embed_simple_str_al_err("Your account is not linked. Please link an account first!"))
                return
            
            await interaction.edit_original_response(**embed_simple_str_al_err("An error occurred while trying to unlink your account."))
        else:
            await interaction.edit_original_response(**embed_simple_str_al("<:purple_check:1327738590624616609> Your account has been unlinked successfully."))

    async def link_interaction(self, interaction: discord.Interaction):
        # first check if the account isnt linked

        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        logging.debug(f'[GET] {const.SERVER_URL}/profile/service/link/{interaction.user.id}')
        islinked = requests.get(
            f'{const.SERVER_URL}/profile/service/link/{interaction.user.id}', 
            headers={'Authorization': const.BOT_TOKEN})
        if islinked.status_code == 200:
            await interaction.edit_original_response(**embed_simple_str_al_err("Your account is already linked to an Epic Games account.\nPlease unlink it first before linking another Epic Games account.", rm_view=True))
            return
        
        # initiate an "oauth flow"

        state = secrets.token_hex(32)
        logging.debug(f'[POST] {const.SERVER_URL}/authorize/oauth/{state}')
        statereq = requests.post(
            f'{const.SERVER_URL}/authorize/oauth/{state}', 
            json={"user_id": str(interaction.user.id)}, 
            headers={'Authorization': const.BOT_TOKEN})
        
        if not statereq.ok:
            if statereq.json()['error'] == 'FLOW_ALREADY_EXISTS':
                await interaction.edit_original_response(**embed_simple_str_al_err("Something went wrong. Try again later."))
                return
            
            statereq.raise_for_status()
        else:
            # create a loop every 10 seconds
            expire_time = datetime.fromisoformat(statereq.json()['expires_at'])

            linked = False
            epic_code = None

            while not linked:
                logging.debug(f'[GET] {const.SERVER_URL}/authorize/oauth/{state}')
                linkedreq = requests.get(f'{const.SERVER_URL}/authorize/oauth/{state}', headers={'Authorization': const.BOT_TOKEN})

                if linkedreq.status_code == 200:
                    epic_code = linkedreq.json()['authorization_code']
                    linked = True
                    break
                elif linkedreq.status_code == 400:
                    embed = discord.Embed(title="Account Linking", colour=0x8927A1)
                    embed.add_field(name="<:link:1327738503844462623> Linking your Epic Games account", value="To link your account, please press the \"Authorize\" button.\nBy linking your account, you agree to the [Terms of Service](https://github.com/hmxmilohax/festivalinfobot/blob/main/terms_of_service.md) and [Privacy Policy](https://github.com/hmxmilohax/festivalinfobot/blob/main/privacy_policy.md).", inline=False)
                    embed.add_field(name="Next Retry", value=f"{discord.utils.format_dt(datetime.now() + timedelta(seconds=10), 'R')}", inline=True)
                    embed.add_field(name="Link Expires", value=f"{discord.utils.format_dt(expire_time, 'R')}", inline=True)
                    embed.set_footer(text="Festival Tracker is not associated or affiliated with Epic Games.")
                    embed.set_thumbnail(url=self.bot.user.avatar.url)
                    view = const.OneButtonSimpleView(on_press=None, user_id=interaction.user.id, label="Authorize", emoji="<:link:1327738503844462623>", link=statereq.json()['authorize_url'])
                    view.message = await interaction.edit_original_response(embed=embed, view=view)
                elif linkedreq.status_code == 404:
                    await interaction.edit_original_response(**embed_simple_str_al_err("The time ran out. Please try again.", True))
                    return
                else:
                    await interaction.edit_original_response(**embed_simple_str_al_err("An error occurred while trying to link your account.", True))
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

                logging.debug(f'[GET] {const.SERVER_URL}/profile/service/link/epic/{accid}')
                is_epic_acc_already_linked = requests.get(f'{const.SERVER_URL}/profile/service/link/epic/{accid}')
                if is_epic_acc_already_linked.ok:
                    await interaction.edit_original_response(**embed_simple_str_al_err(f"{displayname} is already linked to another user. Please use a different account.", rm_view=True))
                    return

                logging.debug(f'[GET] https://api.epicgames.dev/epic/id/v2/accounts?accountId={accid}')
                acclinkinfo = requests.get(f'https://api.epicgames.dev/epic/id/v2/accounts?accountId={accid}', headers={
                    "Authorization": f"Bearer {token}"
                })

                identityprovideremojidict = {
                    "epic": "<:epic:1327742779807236216>",
                    "psn": "<:playstation:1327743004211023993>",
                    "xbl": "<:xbox:1327743019289411766>",
                    "nintendo": "<:switch:1327742992651522211>",
                    "steam": "<:steam:1327742992651522211>",
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
                        await self.create_profile(interaction, accid)

                    async def optionsmenu():
                        async def cancel():
                            await interaction.edit_original_response(**embed_simple_str_al("You stopped linking your account.", True))
                        
                        async def switchaccount():
                            return await self.link_interaction(interaction)

                        optionsmenuemed = discord.Embed(title="Account Linking", colour=0x8927A1, description="<:gear:1327738496244256848> Options")
                        optionsmenuemed.add_field(name="**Switch Account**", value="Create a new linking process", inline=False)
                        optionsmenuemed.add_field(name="**Stop Linking**", value="Cancel this linking process", inline=False) 
                        optionsmenuemed.set_footer(text="For security, you cannot return from the Options menu.")
                        optionsmenuemed.set_thumbnail(url=self.bot.user.avatar.url)
                        optimenu = const.ButtonedView(user_id=interaction.user.id, buttons=[
                            const.Button(on_press=switchaccount, label="Switch Account", emoji="<:link:1327738503844462623>", style=discord.ButtonStyle.secondary),
                            const.Button(on_press=cancel, label="Stop Linking", emoji="<:error:1327736288807358629>", style=discord.ButtonStyle.danger)
                        ])
                        optimenu.message = await interaction.edit_original_response(embed=optionsmenuemed, view=optimenu)

                    twooptview = const.ButtonedView(user_id=interaction.user.id, buttons=[
                        const.Button(on_press=continuelink, label="Continue", emoji="<:checkmark:1327738579287412897>", style=discord.ButtonStyle.success),
                        const.Button(on_press=optionsmenu, label="Options", emoji="<:gear:1327738496244256848>", style=discord.ButtonStyle.secondary)
                    ])
                    twooptview.message = await interaction.edit_original_response(embed=linkconfirmembed, view=twooptview)

                    logging.debug(f'[DELETE] {const.SERVER_URL}/authorize/oauth/{state}')
                    requests.delete(f'{const.SERVER_URL}/authorize/oauth/{state}', headers={'Authorization': const.BOT_TOKEN})
                else:
                    await interaction.edit_original_response(**embed_simple_str_al_err("An error occurred while trying to access your account's information.", rm_view=True))

            else:
                await interaction.edit_original_response(**embed_simple_str_al_err("An error occurred while trying to link your account.", rm_view=True))
            
    async def create_profile(self, interaction: discord.Interaction, account_id: str):
        logging.info(f'[GET] {const.SERVER_URL}/profile/{account_id}')

        profile_exists = requests.get(
            f'{const.SERVER_URL}/profile/{account_id}', 
            headers={'Authorization': const.BOT_TOKEN})

        if profile_exists.status_code == 200:
            logging.info(f'[POST] {const.SERVER_URL}/profile/service/link/')

            create_link = requests.post(
                f'{const.SERVER_URL}/profile/service/link/', 
                json={'account_id': account_id, 'discord_user_id': str(interaction.user.id)}, 
                headers={'Authorization': const.BOT_TOKEN})
            
            args = embed_simple_str_al("Your account has been re-linked to your profile successfully.", rm_view=True)
            embed: discord.Embed = args.get("embed")
            
            if profile_exists.json()['avatar'] != None:
                avatar_id = profile_exists.json()['avatar']
                pfp_uri = None
                logging.info(f'https://fortnite-api.com/v2/cosmetics/br/search?id={avatar_id}')
                item = requests.get(
                    f'https://fortnite-api.com/v2/cosmetics/br/search?id={avatar_id}')

                if item.ok:
                    if item.json()['data']['images'].get('smallIcon', None):
                        pfp_uri = item.json()['data']['images'].get('smallIcon')

                if pfp_uri:
                    embed.set_thumbnail(url=pfp_uri)
                    args.update(embed=embed)

            await interaction.edit_original_response(**args)
            
        elif profile_exists.status_code == 404:
            logging.info(f'[POST] {const.SERVER_URL}/profile/')

            create_profile = requests.post(
                f'{const.SERVER_URL}/profile/', 
                json={'account_id': account_id}, 
                headers={'Authorization': const.BOT_TOKEN})
            
            logging.info(f'[POST] {const.SERVER_URL}/profile/service/link/')

            create_link = requests.post(
                f'{const.SERVER_URL}/profile/service/link/', 
                json={'account_id': account_id, 'discord_user_id': str(interaction.user.id)}, 
                headers={'Authorization': const.BOT_TOKEN})
            
            if create_link.ok:
                async def privacysettings():
                    await self.profile_privacy_menu_interaction(interaction)

                async def finishlinking():
                    await interaction.edit_original_response(**embed_simple_str_al("Your account has been linked to your profile successfully.", rm_view=True))

                continue_view = const.ButtonedView(user_id=interaction.user.id, buttons=[
                    const.Button(on_press=privacysettings, label="Yes", emoji="<:checkmark:1327738579287412897>"),
                    const.Button(on_press=finishlinking, label="No", emoji="<:gear:1327738496244256848>")
                ])
                continue_view.message = await interaction.edit_original_response(embed=discord.Embed(title="Account Linking", colour=0x8927A1, description="<:purple_check:1327738590624616609> Your profile has been created. Would you like to update your privacy settings?"), view=continue_view)
            else:
                await interaction.edit_original_response(**embed_simple_str_al_err("An error occurred while trying to create your profile.", rm_view=True))

    async def profile_privacy_menu_interaction(self, interaction: discord.Interaction):
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        logging.debug(f'[GET] {const.SERVER_URL}/profile/service/link/{interaction.user.id}')
        link_req = requests.get(
            f'{const.SERVER_URL}/profile/service/link/{interaction.user.id}', 
            headers={'Authorization': const.BOT_TOKEN})
        
        if link_req.status_code != 200:
            await interaction.edit_original_response(**embed_simple_str_pm_err("Your account is not linked. Please link an account first!", rm_view=True))
            return

        account_id = link_req.json()["account_id"]

        logging.debug(f'[GET] {const.SERVER_URL}/epic/account-info/{account_id}')
        usernamereq = requests.get(
            f'{const.SERVER_URL}/epic/account-info/{account_id}', 
            headers={'Authorization': const.BOT_TOKEN})
        
        profile = requests.get(
            f'{const.SERVER_URL}/profile/{account_id}', 
            headers={'Authorization': const.BOT_TOKEN})
        
        if usernamereq.ok:
            username = usernamereq.json()['displayName']
            privacyembed = discord.Embed(title=f"Privacy Settings", colour=0x8927A1, description=f"Edit your privacy settings.")
            privacyembed.add_field(name=f"{username}'s privacy settings", value="Select an option below to edit it.", inline=False)

            if profile.json()['avatar'] != None:
                avatar_id = profile.json()['avatar']
                logging.info(f'https://fortnite-api.com/v2/cosmetics/br/search?id={avatar_id}')
                item = requests.get(
                    f'https://fortnite-api.com/v2/cosmetics/br/search?id={avatar_id}')

                if item.ok:
                    if item.json()['data']['images'].get('smallIcon', None):
                        privacyembed.set_thumbnail(url=item.json()['data']['images'].get('smallIcon'))

            dd = DropdownView(user_id=interaction.user.id, account_id=account_id, display_name=username)
            dd.message = await interaction.edit_original_response(embed=privacyembed, view=dd)

        else:
            await interaction.edit_original_response(**embed_simple_str_pm_err("Your Epic Games account could not be found.", rm_view=True))

class PrivacyOptionsSelect(discord.ui.Select):
    def __init__(self):

        # Set the options that will be presented inside the dropdown
        options = [
            discord.SelectOption(label='Avatar Visibility', description='Toggle who can view your avatar.'),
            discord.SelectOption(label='Friend Requests', description='Toggle friend requests.')
        ]

        super().__init__(placeholder='Press here to select a setting...', min_values=1, max_values=1, options=options)

    async def reset(self):
        view: DropdownView = self.view
        message = view.message
        embed = message.embeds.pop()
        embed._fields.clear() # fields does not clear anything cause its a proxy!!
        embed.add_field(name=f"{view.display_name}'s privacy settings", value="Select an option below to edit it.", inline=False)

        print(embed.fields)

        view.message = await message.edit(embed=embed, view=self.view)

    async def callback(self, interaction: discord.Interaction):
        view: DropdownView = self.view
        if view.user_id != interaction.user.id:
            await interaction.response.send_message("This is not your session. Please run the command yourself to start your own session.", ephemeral=True)
            return

        selected = self.values[0]

        if selected == "Avatar Visibility":
            message = view.message
            embed = message.embeds.pop()
            # embed.fields.clear()

            await interaction.response.defer()

            logging.debug(f"[GET] {const.SERVER_URL}/profile/{view.account_id}")
            privacysettings = requests.get(
                f'{const.SERVER_URL}/profile/{view.account_id}', 
                headers={'Authorization': const.BOT_TOKEN})
            current = privacysettings.json()['private_avatar'] == True

            desc_value = "Change who can see your avatar."
            desc_value += "\n- " + ("**" if current else "") + "Only Me" + ("**" if current else "")
            desc_value += "\n- " + ("**" if not current else "") + "Everyone" + ("**" if not current else "")

            embed.add_field(name="Avatar Visibility", value=desc_value)

            async def toggle():
                # ------------
                logging.debug(f"[GET] {const.SERVER_URL}/profile/{view.account_id}")
                privacysettings = requests.get(
                    f'{const.SERVER_URL}/profile/{view.account_id}', 
                    headers={'Authorization': const.BOT_TOKEN})
                prev = privacysettings.json()['private_avatar'] == True
                # ------------ all this code couldve technically not been necessary

                current = not prev

                logging.debug(f"[PATCH] {const.SERVER_URL}/profile/{view.account_id}/privacy")
                privacysettings_update = requests.patch(
                f'{const.SERVER_URL}/profile/{view.account_id}/privacy',
                json={"private_avatar": current}, 
                headers={'Authorization': const.BOT_TOKEN})

                current = privacysettings_update.json()['private_avatar'] == 1
                _message = view.message
                _embed = _message.embeds.pop()
                _embed._fields.pop()
                
                desc_value = "Change who can see your avatar."
                desc_value += "\n- " + ("**" if current else "") + "Only Me" + ("**" if current else "")
                desc_value += "\n- " + ("**" if not current else "") + "Everyone" + ("**" if not current else "")
                _embed.add_field(name="Avatar Visibility", value=desc_value)

                view.message = await _message.edit(embed=_embed)

            btnview = const.ButtonedView(view.user_id, buttons=[
                const.Button(on_press=toggle, label="Toggle", style=discord.ButtonStyle.primary),
                const.Button(on_press=self.reset, label="Back", style=discord.ButtonStyle.secondary)
            ])
            btnview.message = await message.edit(embed=embed, view=btnview)
            view.message = btnview.message

        elif selected == 'Friend Requests':
            message = view.message
            embed = message.embeds.pop()
            # embed.fields.clear()

            await interaction.response.defer()

            logging.debug(f"[GET] {const.SERVER_URL}/profile/{view.account_id}")
            privacysettings = requests.get(
                f'{const.SERVER_URL}/profile/{view.account_id}', 
                headers={'Authorization': const.BOT_TOKEN})
            current = privacysettings.json()['friend_requests'] == True

            desc_value = "Change who can send you friend requests.\nChanging this modifies it in your Epic Games Account the next time you open the Festival Tracker App."
            desc_value += "\nFriend Requests are currently **" + ("ON" if current else "OFF") + "**."

            embed.add_field(name="Friend Requests", value=desc_value)

            async def on_changed():
                option = discord.utils.find(lambda o: o.label == "Friend Requests", self._underlying.options)
                self._underlying.options.remove(option)

                await self.reset()

            btnview = const.ButtonedView(view.user_id, buttons=[
                const.Button(on_press=on_changed, label="Change", style=discord.ButtonStyle.primary),
                const.Button(on_press=self.reset, label="Back", style=discord.ButtonStyle.secondary)
            ])
            btnview.message = await message.edit(embed=embed, view=btnview)
            view.message = btnview.message

class DropdownView(discord.ui.View):
    def __init__(self, user_id: int, account_id: str, display_name: str):
        super().__init__(timeout=30)
        self.user_id = user_id
        self.account_id = account_id
        self.display_name = display_name
        # self.avatar_url = 
        self.message: discord.Message


        # Adds the dropdown to our view object.
        self.add_item(PrivacyOptionsSelect())