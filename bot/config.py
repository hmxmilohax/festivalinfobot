from datetime import datetime
import enum
from typing import List

import aiosqlite
import discord
import asyncio

# TERROR

class JamTrackEvent():
    def __init__(self, _id: str, english: str, desc: str) -> None:
        self.english = english
        self.id = _id
        self.desc = desc

class JamTrackEvents(enum.Enum):
    Added = JamTrackEvent('added', 'Jam Track Added', desc='A Jam Track has been added to the API.')
    Modified = JamTrackEvent('modified', 'Jam Track Modified', desc='A Jam Track has been modified.')
    Removed = JamTrackEvent('removed', 'Jam Track Removed', desc='A Jam Track has been removed from the API.')

    def get_all_events():
        return list(JamTrackEvents.__members__.values())

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

class WishlistEntry():
    def __init__(self, user: discord.User, shortname: str, created_at: datetime, lock_rotation_active: bool = False, lock_shop_active: bool = False) -> None:
        self.user = user
        self.shortname = shortname
        self.created_at = created_at
        self.lock_rotation_active = lock_rotation_active
        self.lock_shop_active = lock_shop_active

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
            await self.db.execute('''
                CREATE TABLE IF NOT EXISTS wishlists (
                    user_id TEXT,
                    shortname TEXT,
                    created_at TEXT,
                    lock_rotation_active INTEGER DEFAULT 0,
                    lock_shop_active INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id, shortname)
                );
            ''')
            await self.db.commit()

    async def close_connection(self) -> None:
        if self.db:
            await self.db.close()

    async def _channel_remove(self, channel: discord.TextChannel) -> None:
        async with self.lock:
            await self.db.execute(
                "DELETE FROM channel_subscriptions WHERE guild_id = ? AND channel_id = ?",
                (str(channel.guild.id), str(channel.id))
            )
            await self.db.commit()

    async def _channel(self, channel: discord.TextChannel) -> SubscriptionChannel:
        async with self.lock:
            async with self.db.execute(
                "SELECT channel_id, events, roles FROM channel_subscriptions WHERE guild_id = ? AND channel_id = ?",
                (str(channel.guild.id), str(channel.id))
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    channel_id, events_str, roles_str = row
                    events = events_str.split(',') 
                    roles = [int(role_id) for role_id in roles_str.split(',') if len(role_id) > 0] if roles_str else []
                    return SubscriptionChannel(int(channel_id), events, roles)
                return None
            
    async def _channel_add(self, channel: discord.TextChannel, default_events = ['added', 'modified', 'removed'], role_ids = []) -> None:
        async with self.lock:
            await self.db.execute(
                "INSERT OR IGNORE INTO channel_subscriptions (guild_id, channel_id, events, roles) VALUES (?, ?, ?, ?)",
                (str(channel.guild.id), str(channel.id), ",".join(default_events), ",".join(role_ids))
            )
            await self.db.commit()

    async def _channel_edit_events(self, channel: discord.TextChannel, events: list[str]) -> None:
        async with self.lock:
            await self.db.execute(
                "UPDATE channel_subscriptions SET events = ? WHERE guild_id = ? AND channel_id = ?",
                (",".join(events), str(channel.guild.id), str(channel.id))
            )
            await self.db.commit()

    async def _channel_edit_roles(self, channel: discord.TextChannel, roles: list[discord.Object]) -> None:
        role_ids = [str(role.id) for role in roles]
        async with self.lock:
            await self.db.execute(
                "UPDATE channel_subscriptions SET roles = ? WHERE guild_id = ? AND channel_id = ?",
                (",".join(role_ids), str(channel.guild.id), str(channel.id))
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
            
    async def _guild_remove(self, guild: discord.Guild) -> None:
        async with self.lock:
            await self.db.execute(
                "DELETE FROM channel_subscriptions WHERE guild_id = ?",
                (str(guild.id),)
            )
            await self.db.commit()

    async def _user(self, user: discord.User) -> SubscriptionUser:
        async with self.lock:
            async with self.db.execute(
                "SELECT user_id, events FROM user_subscriptions WHERE user_id = ?",
                (str(user.id),)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    user_id, events_str = row
                    events = events_str.split(',')
                    return SubscriptionUser(int(user_id), events)
                return None

    async def _user_edit_events(self, user: discord.User, events: list[str]) -> None:
        async with self.lock:
            async with self.db.execute(
            "SELECT user_id FROM user_subscriptions WHERE user_id = ?",
            (str(user.id),)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    if len(events) > 0:
                        await self.db.execute(
                            "UPDATE user_subscriptions SET events = ? WHERE user_id = ?",
                            (",".join(events), str(user.id))
                        )
                    else:
                        await self.db.execute(
                            "DELETE FROM user_subscriptions WHERE user_id = ?",
                            (str(user.id),)
                        )
                else:
                    await self.db.execute(
                        "INSERT INTO user_subscriptions (user_id, events) VALUES (?, ?)",
                        (str(user.id), ",".join(events))
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
            
    async def _del_channels_with_query(self, query: str) -> int:
        async with self.lock:
            await self.db.execute(f"DELETE FROM channel_subscriptions {query}")
            await self.db.commit()
            
    async def _del_users_with_query(self, query: str) -> int:
        async with self.lock:
            await self.db.execute(f"DELETE FROM user_subscriptions {query}")
            await self.db.commit()

    async def _add_to_wishlist(self, user: discord.User, shortname: str) -> None:
        async with self.lock:
            await self.db.execute(
                "INSERT OR REPLACE INTO wishlists (user_id, shortname, created_at, lock_rotation_active, lock_shop_active) VALUES (?, ?, ?, ?, ?)",
                (str(user.id), shortname, datetime.now().isoformat(), 0, 0)
            )
            await self.db.commit()

    async def _remove_from_wishlist(self, user: discord.User, shortname: str) -> None:
        async with self.lock:
            await self.db.execute(
                "DELETE FROM wishlists WHERE user_id = ? AND shortname = ?",
                (str(user.id), shortname)
            )
            await self.db.commit()

    async def _already_in_wishlist(self, user: discord.User, shortname: str) -> bool:
        async with self.lock:
            async with self.db.execute(
                "SELECT 1 FROM wishlists WHERE user_id = ? AND shortname = ?",
                (str(user.id), shortname)
            ) as cursor:
                row = await cursor.fetchone()
                return row is not None
            
    async def _get_wishlist_of_user(self, user: discord.User) -> List[WishlistEntry]:
        async with self.lock:
            async with self.db.execute(
                "SELECT shortname, created_at, lock_rotation_active, lock_shop_active FROM wishlists WHERE user_id = ?",
                (str(user.id),)
            ) as cursor:
                rows = await cursor.fetchall()
                return [
                    WishlistEntry(
                        user,
                        row[0],
                        datetime.fromisoformat(row[1]),
                        bool(row[2]),
                        bool(row[3])
                    )
                    for row in rows
                ] if rows else []
            
    async def _get_all_wishlists(self) -> List[tuple[int, str]]:
        async with self.lock:
            async with self.db.execute("SELECT user_id, shortname, created_at, lock_rotation_active, lock_shop_active FROM wishlists") as cursor:
                rows = await cursor.fetchall()
                return [
                    WishlistEntry(
                        user=discord.Object(id=int(row[0])),
                        shortname=row[1],
                        created_at=datetime.fromisoformat(row[2]),
                        lock_rotation_active=bool(row[3]),
                        lock_shop_active=bool(row[4])
                    )
                    for row in rows
                ] if rows else []
            
    async def _lock_wishlist_rotation(self, entry: WishlistEntry) -> None:
        async with self.lock:
            await self.db.execute(
                "UPDATE wishlists SET lock_rotation_active = 1 WHERE user_id = ? AND shortname = ?",
                (str(entry.user.id), entry.shortname)
            )
            await self.db.commit()

    async def _unlock_wishlist_rotation(self, entry: WishlistEntry) -> None:
        async with self.lock:
            await self.db.execute(
                "UPDATE wishlists SET lock_rotation_active = 0 WHERE user_id = ? AND shortname = ?",
                (str(entry.user.id), entry.shortname)
            )
            await self.db.commit()

    async def _lock_wishlist_shop(self, entry: WishlistEntry) -> None:
        async with self.lock:
            await self.db.execute(
                "UPDATE wishlists SET lock_shop_active = 1 WHERE user_id = ? AND shortname = ?",
                (str(entry.user.id), entry.shortname)
            )
            await self.db.commit()
        
    async def _unlock_wishlist_shop(self, entry: WishlistEntry) -> None:
        async with self.lock:
            await self.db.execute(
                "UPDATE wishlists SET lock_shop_active = 0 WHERE user_id = ? AND shortname = ?",
                (str(entry.user.id), entry.shortname)
            )
            await self.db.commit()