import base64
import datetime
import json
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

    def _create_token(self):
        logging.info('[POST] https://account-public-service-prod.ol.epicgames.com/account/api/oauth/token (create)')
        url = 'https://account-public-service-prod.ol.epicgames.com/account/api/oauth/token'
        headers = {
            'Authorization': 'Basic OThmN2U0MmMyZTNhNGY4NmE3NGViNDNmYmI0MWVkMzk6MGEyNDQ5YTItMDAxYS00NTFlLWFmZWMtM2U4MTI5MDFjNGQ3', # fortniteNewSwitchGameClient
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        data = {
            'grant_type': 'device_auth',
            'account_id': self.account_id,
            'device_id': self.device_id,
            'secret': self.device_secret,
            'token_type': 'eg1'
        }
        response = requests.post(url, headers=headers, data=data)
        response.raise_for_status()
        self._session_data = response.json()
        self._access_token = self._session_data['access_token']
        self._refresh_token = self._session_data['refresh_token']

        # print(self._access_token)

    async def create_session(self, skip_create: bool = False):
        try:
            self._create_token()

            logging.info(f'Logged into EOS as {self.account_id}')

            await self.bot.get_channel(constants.LOG_CHANNEL).send(content=f'{constants.tz()} Device auth session started for ' + self._session_data['displayName'])

            if not skip_create:
                try:
                    self.refresh_task.start()
                    self.verify_session.start()
                except RuntimeError as e:
                    logging.debug(f'The task was already running... ({e})')
        except Exception as e:
            logging.critical(f'Cannot create token: {e}')
            await self.bot.get_channel(constants.LOG_CHANNEL).send(content=f'{constants.tz()} Device auth session cannot be started because of {e}')

    @tasks.loop(seconds=6900)
    async def refresh_session(self):
        logging.info('[POST] https://account-public-service-prod.ol.epicgames.com/account/api/oauth/token (refresh)')
        try:
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
            response.raise_for_status()
            self._session_data = response.json()
            self._access_token = self._session_data['access_token']
            self._refresh_token = self._session_data['refresh_token']

            await self.bot.get_channel(constants.LOG_CHANNEL).send(content=f'{constants.tz()} Device auth session refreshed for ' + self._session_data['displayName'])
        except Exception as e:
            logging.critical(f'Device auth session cannot be refreshed because of {e}')
            await self.bot.get_channel(constants.LOG_CHANNEL).send(content=f'{constants.tz()} Device auth session cannot be refreshed because of {e}')

    @tasks.loop(seconds=60)
    async def verify_session(self):
        logging.info('[GET] https://account-public-service-prod.ol.epicgames.com/account/api/oauth/verify (verify)')
        url = 'https://account-public-service-prod.ol.epicgames.com/account/api/oauth/verify'
        headers = {
            'Authorization': self.session_token
        }
        response = requests.get(url, headers=headers)
        # response.raise_for_status()
        if not response.ok:
            await self.bot.get_channel(constants.LOG_CHANNEL).send(content=f'{constants.tz()} Device auth session ended for ' + self._session_data['displayName'])
            await self.create_session(skip_create=True)

    @property
    def session_token(self) -> str:
        if self._access_token == None:
            raise Exception("Festival Tracker is not ready yet! Please try again in a few moments.")

        payload = json.loads(base64.urlsafe_b64decode(self._access_token.split('.')[1]))
        # TS PMO
        ts_exp = payload['exp']
        # ts_exp = 0
        date_exp = datetime.datetime.fromtimestamp(ts_exp, tz=datetime.timezone.utc)

        if datetime.datetime.now(tz=datetime.timezone.utc) > date_exp:
            self._create_token()
            logging.critical('Token forcefully regenerated as it was detected to be expired!')
            # why arent you running
            if not self.refresh_session.is_running():
                logging.critical('Token refresh is not running')
                self.refresh_session.start()
            if not self.verify_session.is_running():
                logging.critical('Token verify is not running')
                self.verify_session.start()

        # return 'lol' # testing only
    
        return f'Bearer {self._access_token}'
    
    def get_accounts(self, account_ids: List[str]) -> List[EpicAccount]:
        logging.info(f'[get accounts] {len(account_ids)} account ids given')

        accounts = []
        for i in range(0, len(account_ids), 100):
            batch_ids = account_ids[i:i + 100]
            url = 'https://account-public-service-prod.ol.epicgames.com/account/api/public/account?'
            url += '&'.join([f'accountId={account_id}' for account_id in batch_ids])

            logging.info(f'[GET] {url}')
            headers = {
                'Authorization': self.session_token
            }
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            accounts.extend([EpicAccount(account['id'], account.get('displayName', None)) for account in response.json()])
        
        return accounts
    
    def get_account_from_display_name(self, display_name: str) -> EpicAccount:
        url = f'https://account-public-service-prod.ol.epicgames.com/account/api/public/account/displayName/{display_name}'
        logging.info(f'[GET] {url}')
        headers = {
            'Authorization': self.session_token
        }

        response = requests.get(url, headers=headers)
        response.raise_for_status()
        account = response.json()
        return EpicAccount(account['id'], account['displayName'])
    
    def search_users(self, username_prefix: str) -> EpicAccountPlatform:
        url = f'https://user-search-service-prod.ol.epicgames.com/api/v1/search/{self.account_id}?platform=epic&prefix={username_prefix}'
        logging.info(f'[GET] {url}')
        headers = {
            'Authorization': self.session_token
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
