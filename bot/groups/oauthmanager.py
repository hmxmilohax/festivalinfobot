from typing import List
import discord.ext.tasks as tasks
import discord
import requests
import bot.constants as constants
from discord.ext import commands
import logging

class EpicAccount:
    def __init__(self, account_id: str, display_name: str):
        self.account_id = account_id
        self.display_name = display_name

class EpicAccountPlatform:
    def __init__(self, account_id: str, platform: str, display_name: str):
        self.account_id = account_id
        self.platform = platform
        self.display_name = display_name

# this is th clsas that makes sure the device auth does not die
class OAuthManager:
    def __init__(self, bot: commands.Bot, device_id: str, account_id: str, device_secret: str):
        self.device_id = device_id
        self.account_id = account_id
        self.device_secret = device_secret
        self._access_token:str = None
        self._refresh_token:str = None
        self._session_data = None
        self.refresh_task: tasks.Loop = self.refresh_session
        self.bot = bot

    async def create_session(self):
        logging.info('[POST] https://account-public-service-prod.ol.epicgames.com/account/api/oauth/token')
        url = 'https://account-public-service-prod.ol.epicgames.com/account/api/oauth/token'
        headers = {
            'Authorization': 'Basic OThmN2U0MmMyZTNhNGY4NmE3NGViNDNmYmI0MWVkMzk6MGEyNDQ5YTItMDAxYS00NTFlLWFmZWMtM2U4MTI5MDFjNGQ3', # fortniteNewSwitchGameClient
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        data = {
            'grant_type': 'device_auth',
            'account_id': self.account_id,
            'device_id': self.device_id,
            'secret': self.device_secret
        }
        response = requests.post(url, headers=headers, data=data)
        self._session_data = response.json()
        self._access_token = self._session_data['access_token']
        self._refresh_token = self._session_data['refresh_token']

        await self.bot.get_channel(constants.LOG_CHANNEL).send(content='Device auth session started for ' + self._session_data['displayName'])

        self.refresh_task.start()
        self.verify_session.start()

    @tasks.loop(seconds=6900)
    async def refresh_session(self):
        logging.info('[POST] https://account-public-service-prod.ol.epicgames.com/account/api/oauth/token')
        url = 'https://account-public-service-prod.ol.epicgames.com/account/api/oauth/token'
        headers = {
            'Authorization': 'Basic OThmN2U0MmMyZTNhNGY4NmE3NGViNDNmYmI0MWVkMzk6MGEyNDQ5YTItMDAxYS00NTFlLWFmZWMtM2U4MTI5MDFjNGQ3', # fortniteNewSwitchGameClient
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': self._refresh_token
        }
        response = requests.post(url, headers=headers, data=data)
        self._session_data = response.json()
        self._access_token = self._session_data['access_token']
        self._refresh_token = self._session_data['refresh_token']

        await self.bot.get_channel(constants.LOG_CHANNEL).send(content='Device auth session refreshed for ' + self._session_data['displayName'])

    @tasks.loop(seconds=60)
    async def verify_session(self):
        logging.info('[GET] https://account-public-service-prod.ol.epicgames.com/account/api/oauth/verify')
        url = 'https://account-public-service-prod.ol.epicgames.com/account/api/oauth/verify'
        headers = {
            'Authorization': f'Bearer {self._access_token}'
        }
        response = requests.get(url, headers=headers)
        if not response.ok:
            await self.bot.get_channel(constants.LOG_CHANNEL).send(content='Device auth session ended for ' + self._session_data['displayName'])
            self.refresh_task.stop()
            self.verify_session.stop()
            await self.create_session()

    @property
    def session_token(self) -> str:
        return f'Bearer {self._access_token}'
    
    def get_accounts(self, account_ids: List[str]) -> List[EpicAccount]:
        if len(account_ids) > 100:
            raise ValueError('You can only get 100 accounts at a time')

        url = 'https://account-public-service-prod.ol.epicgames.com/account/api/public/account?'
        url += '&'.join([f'accountId={account_id}' for account_id in account_ids])

        logging.info(f'[GET] {url}')
        headers = {
            'Authorization': f'Bearer {self._access_token}'
        }
        response = requests.get(url, headers=headers)
        # print(response.content)
        response.raise_for_status()
        
        return [EpicAccount(account['id'], account.get('displayName', None)) for account in response.json()]
    
    def get_account_from_display_name(self, display_name: str) -> EpicAccount:
        url = f'https://account-public-service-prod.ol.epicgames.com/account/api/public/account/displayName/{display_name}'
        logging.info(f'[GET] {url}')
        headers = {
            'Authorization': f'Bearer {self._access_token}'
        }

        response = requests.get(url, headers=headers)
        response.raise_for_status()
        account = response.json()
        return EpicAccount(account['id'], account['displayName'])
    
    def search_users(self, username_prefix: str) -> EpicAccountPlatform:
        url = f'https://user-search-service-prod.ol.epicgames.com/api/v1/search/{self.account_id}?platform=epic&prefix={username_prefix}'
        logging.info(f'[GET] {url}')
        headers = {
            'Authorization': f'Bearer {self._access_token}'
        }

        response = requests.get(url, headers=headers)
        response.raise_for_status()
        matches = response.json()
        print(matches)
        
        matchlist = []
        for match in matches:
            matchlist.append(EpicAccountPlatform(
                match['accountId'], 
                match['matches'][0]['platform'], 
                match['matches'][0]['value']
            ))

        return matchlist
