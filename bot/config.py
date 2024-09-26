from datetime import datetime
import enum
import json
import os

from bot import constants

class JamTrackEvent(enum.Enum):
    Modified = 'modified'
    Added = 'added'
    Removed = 'removed'

    def get_all_events():
        return ['added', 'modified', 'removed']

class SubscriptionChannel():
    def __init__(self) -> None:
        self.id : int = None
        self.events : list[str] = None
        self.roles : list[int] = None # Roles to ping when an event occurs
        self.type : str = 'channel'

class SubscriptionUser():
    def __init__(self) -> None:
        self.id : int = None
        self.events : list[str] = None
        self.roles : list[int] = None # Roles to ping when an event occurs
        self.type : str = 'user'

class Config:
    def __init__(self, config_file: str, reload_callback) -> None:
        self.channels : list[SubscriptionChannel] = []
        self.users : list[SubscriptionUser] = []
        self.file = config_file
        self.callback = reload_callback

        self.load()

    def save_config(self):
        list_object = {
            'channels': [],
            'users': []
        }
        for channel in self.channels:
            if any(user.id == channel.id for user in self.users): # Attempt to remove duplicates
                continue # PD: I don't know what causes duplication
            
            list_object['channels'].append({
                'id': channel.id,
                'events': channel.events,
                'roles': channel.roles,
                'type': 'channel'
            })

        for user in self.users:
            if any(channel.id == user.id for channel in self.channels): # Remove duplicates, too.
                continue

            list_object['users'].append({
                'id': user.id,
                'events': user.events,
                'roles': [],
                'type': 'user'
            })

        # if something fails, attempt to recover
        previous_file_content = open(self.file, 'r').read()

        try:
            # the json module likes erasing the entire file first before 
            # checking if the object is actually serializable
            open(self.file, 'w').write(json.dumps(list_object, indent=4))

            # Tell the bot to completely reload the config
            self.callback()

        except Exception as e:
            open(self.file, 'w').write(previous_file_content)
            print(f'RECOVERED CONFIG FILE: {e}\nRaising an Exception')
            raise Exception
        
        with open(os.path.join(constants.BACKUP_FOLDER, self.create_backup_name()), 'w') as backup_file:
            backup_file.write(open(self.file, 'r').read())
        
    def create_backup_name(self):
        return f'backup_channels_{int(datetime.now().timestamp())}.json'

    def load_channels(self, data):
        self.channels = []
        for channel in data.get('channels', []):
            channel_object = SubscriptionChannel()
            channel_object.id = channel['id']
            channel_object.events = channel['events']
            channel_object.roles = channel['roles']
            self.channels.append(channel_object)

    def load_users(self, data):
        self.users = []
        for user in data.get('users', []):
            user_object = SubscriptionUser()
            user_object.id = user['id']
            user_object.events = user['events']
            user_object.roles = []
            self.users.append(user_object)

    def load(self):
        if not os.path.exists(self.file):
            open(self.file, 'w').write('')
            self.save_config()

        data = json.load(open(self.file, 'r'))
        self.load_channels(data)
        self.load_users(data)