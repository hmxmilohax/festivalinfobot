from datetime import datetime
import enum
from typing import List

import aiosqlite
import discord
import asyncio

from bot import constants

# TERROR

class JamTrackEvent(enum.Enum):
    Modified = 'modified'
    Added = 'added'
    Removed = 'removed'

    def get_all_events():
        return ['added', 'modified', 'removed']

class SubscriptionObject():
    id: int
    events: list[str]
    type: str

    def __init__(self):
        pass

class SubscriptionChannel(SubscriptionObject):
    def __init__(self, cid, events, roles) -> None:
        self.id = cid
        self.events = events
        self.roles : list[int] = roles # Roles to ping when an event occurs
        self.type = 'channel'

class SubscriptionUser(SubscriptionObject):
    def __init__(self, uid, events) -> None:
        self.id = uid
        self.events = events
        self.type = 'user'

class Config:
    def __init__(self) -> None:
        self.channels: list[SubscriptionChannel] = []
        self.users: list[SubscriptionUser] = []
        self.db: aiosqlite.Connection = None
        # jolly good golly im NOT getting errors now, you silly wonkie toots!
        self.lock = asyncio.Lock()

    async def initialize(self) -> None:
        self.db = await aiosqlite.connect('subscriptions.db')
        async with self.lock:
            await self.db.execute("PRAGMA journal_mode=WAL;")
            await self.db.execute('''
                CREATE TABLE IF NOT EXISTS channel_subscriptions (
                    channel_id TEXT PRIMARY KEY,
                    guild_id TEXT,
                    events TEXT,
                    roles TEXT
                );
            ''')
            await self.db.execute('''
                CREATE TABLE IF NOT EXISTS user_subscriptions (
                    user_id TEXT PRIMARY KEY,
                    events TEXT 
                );
            ''')
            await self.db.commit()

    async def close_connection(self) -> None:
        if self.db:
            await self.db.close()

    async def _channel_exists(self, channel: discord.TextChannel) -> bool:
        async with self.lock:
            async with self.db.execute(
                "SELECT COUNT(*) FROM channel_subscriptions WHERE guild_id = ? AND channel_id = ?",
                (str(channel.guild.id), str(channel.id))
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] > 0

    async def _channel_remove(self, channel: discord.TextChannel) -> None:
        async with self.lock:
            await self.db.execute(
                "DELETE FROM channel_subscriptions WHERE guild_id = ? AND channel_id = ?",
                (str(channel.guild.id), str(channel.id))
            )
            await self.db.commit()

    async def _channel_add(self, channel: discord.TextChannel, default_events = ['added', 'modified', 'removed'], role_ids = []) -> None:
        async with self.lock:
            await self.db.execute(
                "INSERT OR IGNORE INTO channel_subscriptions (guild_id, channel_id, events, roles) VALUES (?, ?, ?, ?)",
                (str(channel.guild.id), str(channel.id), ",".join(default_events), ",".join(role_ids))
            )
            await self.db.commit()

    async def _channel_add_with_event(self, channel: discord.TextChannel, event: JamTrackEvent) -> None:
        async with self.lock:
            await self.db.execute(
                "INSERT OR IGNORE INTO channel_subscriptions (guild_id, channel_id, events, roles) VALUES (?, ?, ?, '')",
                (str(channel.guild.id), str(channel.id), event.value)
            )
            await self.db.commit()

    async def _channel_event_exists(self, channel: discord.TextChannel, event: JamTrackEvent) -> bool:
        async with self.lock:
            async with self.db.execute(
                "SELECT events FROM channel_subscriptions WHERE guild_id = ? AND channel_id = ?",
                (str(channel.guild.id), str(channel.id))
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    subscribed_events = row[0].split(',')
                    return event.value in subscribed_events
                return False

    async def _channel_events(self, channel: discord.TextChannel) -> List[str]:
        async with self.lock:
            async with self.db.execute(
                "SELECT events FROM channel_subscriptions WHERE guild_id = ? AND channel_id = ?",
                (str(channel.guild.id), str(channel.id))
            ) as cursor:
                row = await cursor.fetchone()
                return row[0].split(',') if row else []

    async def _channel_add_event(self, channel: discord.TextChannel, event: JamTrackEvent) -> None:
        current_events = await self._channel_events(channel=channel)

        async with self.lock:
            if event.value not in current_events:
                current_events.append(event.value)
                await self.db.execute(
                    "UPDATE channel_subscriptions SET events = ? WHERE guild_id = ? AND channel_id = ?",
                    (",".join(current_events), str(channel.guild.id), str(channel.id))
                )
                await self.db.commit()
    
    async def _channel_remove_event(self, channel: discord.TextChannel, event: JamTrackEvent) -> None:
        current_events = await self._channel_events(channel=channel)

        async with self.lock:
            if event.value in current_events:
                current_events.remove(event.value)
                await self.db.execute(
                    "UPDATE channel_subscriptions SET events = ? WHERE guild_id = ? AND channel_id = ?",
                    (",".join(current_events), str(channel.guild.id), str(channel.id))
                )
                await self.db.commit()

    async def _guild_channels(self, guild: discord.Guild) -> List[SubscriptionChannel]:
        async with self.lock:
            async with self.db.execute("SELECT channel_id, events, roles FROM channel_subscriptions WHERE guild_id = ?", (str(guild.id),)) as cursor:
                rows = await cursor.fetchall()
                channels = []
                for row in rows:
                    channel_id, events_str, roles_str = row
                    events = events_str.split(',') 
                    roles = [int(role_id) for role_id in roles_str.split(',') if len(role_id) > 0] if roles_str else []
                    channels.append(SubscriptionChannel(int(channel_id), events, roles)) 
                return channels
            
    async def _channel_roles(self, channel: discord.TextChannel) -> List[str]:
        async with self.lock:
            async with self.db.execute(
                "SELECT roles FROM channel_subscriptions WHERE guild_id = ? AND channel_id = ?",
                (str(channel.guild.id), str(channel.id))
            ) as cursor:
                row = await cursor.fetchone()
                return row[0].split(',') if row else []
            
    async def _channel_add_role(self, channel: discord.TextChannel, role: discord.Role) -> None:
        current_roles = await self._channel_roles(channel=channel)

        async with self.lock:
            if str(role.id) not in current_roles:
                current_roles.append(str(role.id))
                await self.db.execute(
                    "UPDATE channel_subscriptions SET roles = ? WHERE guild_id = ? AND channel_id = ?",
                    (",".join(current_roles), str(channel.guild.id), str(channel.id))
                )
                await self.db.commit()
    
    async def _channel_remove_role(self, channel: discord.TextChannel, role: discord.Role) -> None:
        current_roles = await self._channel_roles(channel=channel)

        async with self.lock:
            if str(role.id) in current_roles:
                current_roles.remove(str(role.id))
                await self.db.execute(
                    "UPDATE channel_subscriptions SET roles = ? WHERE guild_id = ? AND channel_id = ?",
                    (",".join(current_roles), str(channel.guild.id), str(channel.id))
                )
                await self.db.commit()

    async def _user_exists(self, user: discord.User) -> bool:
        async with self.lock:
            print(len(str(user.id)))
            async with self.db.execute(
                "SELECT COUNT(*) FROM user_subscriptions WHERE user_id = ?",
                (str(user.id),)
            ) as cursor:
                row = await cursor.fetchone()
                print(row[0])
                return row[0] > 0

    async def _user_remove(self, user: discord.User) -> None:
        async with self.lock:
            await self.db.execute(
                "DELETE FROM user_subscriptions WHERE user_id = ?",
                (str(user.id),)
            )
            await self.db.commit()

    async def _user_add(self, user: discord.User) -> None:
        default_events = ['added', 'modified', 'removed']
        async with self.lock:
            await self.db.execute(
                "INSERT INTO user_subscriptions (user_id, events) VALUES (?, ?)",
                (str(user.id), ",".join(default_events))
            )
            await self.db.commit()

    async def _user_add_event(self, user: discord.User, event: JamTrackEvent) -> None:
        current_events = await self._user_events(user=user)

        async with self.lock:
            if event.value not in current_events:
                current_events.append(event.value)
                await self.db.execute(
                    "UPDATE user_subscriptions SET events = ? WHERE user_id = ?",
                    (",".join(current_events), str(user.id))
                )
                await self.db.commit()
    
    async def _user_remove_event(self, user: discord.User, event: JamTrackEvent) -> None:
        current_events = await self._user_events(user=user)

        async with self.lock:
            if event.value in current_events:
                current_events.remove(event.value)
                await self.db.execute(
                    "UPDATE user_subscriptions SET events = ? WHERE user_id = ?",
                    (",".join(current_events), str(user.id))
                )
                await self.db.commit()

    async def _user_events(self, user: discord.User) -> List[str]:
        async with self.lock:
            async with self.db.execute(
                "SELECT events FROM user_subscriptions WHERE user_id = ?",
                (str(user.id),)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0].split(',') if row else []
            
    async def _user_add_with_event(self, user: discord.User, event: JamTrackEvent) -> None:
        async with self.lock:
            await self.db.execute(
                "INSERT OR IGNORE INTO user_subscriptions (user_id, events) VALUES (?, ?)",
                (str(user.id), event.value)
            )
            await self.db.commit()

    async def _channels(self) -> list[SubscriptionChannel]:
        async with self.lock:
            channels = []
            async with self.db.execute("SELECT channel_id, events, roles FROM channel_subscriptions") as cursor:
                rows = await cursor.fetchall()
                for row in rows:
                    channel_id, events_str, roles_str = row
                    events = events_str.split(',') 
                    roles = [int(role_id) for role_id in roles_str.split(',') if len(role_id) > 0] if roles_str else []
                    channels.append(SubscriptionChannel(int(channel_id), events, roles))
                return channels 
            
    async def _users(self) -> list[SubscriptionUser]:
        async with self.lock:
            channels = []
            async with self.db.execute("SELECT user_id, events FROM user_subscriptions") as cursor:
                rows = await cursor.fetchall()
                for row in rows:
                    user_id, events_str = row
                    events = events_str.split(',')
                    channels.append(SubscriptionUser(int(user_id), events))
                return channels

    async def get_all(self) -> list[SubscriptionObject]:
        channels : list[SubscriptionObject] = []

        text_channels = await self._channels()
        for c in text_channels:
            channels.append(c)

        user_channels = await self._users()
        for u in user_channels:
            channels.append(u)

        return channels
    
    async def _count_channels_with_query(self, query: str) -> int:
        async with self.lock:
            thing = f"SELECT COUNT(*) FROM channel_subscriptions {query}"
            async with self.db.execute(
                thing
            ) as cursor:
                row = await cursor.fetchone()
                return row[0]
            
    async def _del_channels_with_query(self, query: str) -> int:
        async with self.lock:
            await self.db.execute(f"DELETE FROM channel_subscriptions {query}")
            await self.db.commit()
            
    async def _sel_channels_with_query(self, query: str) -> List[SubscriptionChannel]:
        async with self.lock:
            async with self.db.execute(f"SELECT channel_id, events, roles FROM channel_subscriptions {query}") as cursor:
                rows = await cursor.fetchall()
                channels = []
                for row in rows:
                    channel_id, events_str, roles_str = row
                    events = events_str.split(',') 
                    roles = [int(role_id) for role_id in roles_str.split(',') if len(role_id) > 0] if roles_str else []
                    channels.append(SubscriptionChannel(int(channel_id), events, roles)) 
                return channels
    
    async def _count_users_with_query(self, query: str) -> int:
        async with self.lock:
            thing = f"SELECT COUNT(*) FROM user_subscriptions {query}"
            async with self.db.execute(
                thing
            ) as cursor:
                row = await cursor.fetchone()
                return row[0]
            
    async def _del_users_with_query(self, query: str) -> int:
        async with self.lock:
            await self.db.execute(f"DELETE FROM user_subscriptions {query}")
            await self.db.commit()

    async def _sel_users_with_query(self, query: str) -> list[SubscriptionUser]:
        async with self.lock:
            channels = []
            async with self.db.execute(f"SELECT user_id, events FROM user_subscriptions {query}") as cursor:
                rows = await cursor.fetchall()
                for row in rows:
                    user_id, events_str = row
                    events = events_str.split(',')
                    channels.append(SubscriptionUser(int(user_id), events))
                return channels