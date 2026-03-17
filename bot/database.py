from datetime import datetime
import enum
from typing import List

import aiosqlite
import discord
import asyncio

import os
import base64

from typing import overload, Literal
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
    Announcements = JamTrackEvent('announcements', 'Announcements', desc='Important Festival Tracker announcements and bugfixes. (Recommended)')

    def get_all_events(): # type: ignore
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
    def __init__(self, user: discord.Object, shortname: str, created_at: datetime, lock_rotation_active: bool = False, lock_shop_active: bool = False) -> None:
        self.user = user
        self.shortname = shortname
        self.created_at = created_at
        self.lock_rotation_active = lock_rotation_active
        self.lock_shop_active = lock_shop_active

class Config:
    def __init__(self) -> None:
        self.channels: list[SubscriptionChannel] = []
        self.users: list[SubscriptionUser] = []
        self.db: aiosqlite.Connection
        # jolly good golly im NOT getting errors now, you silly wonkie toots!
        self.lock = asyncio.Lock()

    async def initialize(self) -> None:
        self.db = await aiosqlite.connect('festivaltracker.db')
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

            # tokens are encoded in base64 after being encrypted with AES-256-GCM
            await self.db.execute('''
                CREATE TABLE IF NOT EXISTS profiles (
                    user_id TEXT PRIMARY KEY
                );
            ''')

            # agreements
            await self.db.execute('''
                CREATE TABLE IF NOT EXISTS agreements (
                    user_id TEXT PRIMARY KEY,
                    privacy_policy_accepted INTEGER DEFAULT 0,
                    privacy_policy_version TEXT,
                    terms_of_service_accepted INTEGER DEFAULT 0,
                    terms_of_service_version TEXT
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

    async def _channel(self, channel: discord.TextChannel) -> SubscriptionChannel | None:
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

    @overload
    async def subscription_guild(self, operation: Literal['get_channels'], guild: discord.Guild) -> list[SubscriptionChannel]: ...

    @overload
    async def subscription_guild(self, operation: Literal['remove'], guild: discord.Guild) -> None: ...

    async def subscription_guild(self, operation: Literal['get_channels', 'remove'], guild: discord.Guild) -> list[SubscriptionChannel] | None:
        async with self.lock:
            if operation == 'get_channels':
                async with self.db.execute("SELECT channel_id, events, roles FROM channel_subscriptions WHERE guild_id = ?", (str(guild.id),)) as cursor:
                    rows = await cursor.fetchall()
                    channels = []
                    for row in rows:
                        channel_id, events_str, roles_str = row
                        events = events_str.split(',') 
                        roles = [int(role_id) for role_id in roles_str.split(',') if len(role_id) > 0] if roles_str else []
                        channels.append(SubscriptionChannel(int(channel_id), events, roles)) 
                    return channels 
            elif operation == 'remove':
                await self.db.execute(
                    "DELETE FROM channel_subscriptions WHERE guild_id = ?",
                    (str(guild.id),)
                )
                await self.db.commit()
            return None

    @overload
    async def subscription_user(self, operation: Literal['get'], user: discord.User | discord.Object) -> SubscriptionUser | None: ...

    @overload
    async def subscription_user(self, operation: Literal['edit'], user: discord.User | discord.Object, events: list[str]) -> None: ...

    async def subscription_user(self, operation: Literal['get', 'edit'], user: discord.User | discord.Object, **kwargs) -> SubscriptionUser | None:
        async with self.lock:
            if operation == 'get':
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
            elif operation == 'edit':
                events = kwargs.get('events', [])
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
            return None

    @overload
    async def subscription_global(self, operation: Literal['get_all_channels']) -> list[SubscriptionChannel]: ...

    @overload
    async def subscription_global(self, operation: Literal['get_all_users']) -> list[SubscriptionUser]: ...

    @overload
    async def subscription_global(self, operation: Literal['delete_channels_with_query'], query: str) -> None: ...

    @overload
    async def subscription_global(self, operation: Literal['delete_users_with_query'], query: str) -> None: ...

    async def subscription_global(self, operation: Literal['get_all_channels', 'get_all_users', 'delete_channels_with_query', 'delete_users_with_query'], **kwargs) -> list[SubscriptionChannel] | list[SubscriptionUser] | None:
        async with self.lock:
            if operation == 'get_all_channels':
                channels = []
                async with self.db.execute("SELECT channel_id, events, roles FROM channel_subscriptions") as cursor:
                    rows = await cursor.fetchall()
                    for row in rows:
                        channel_id, events_str, roles_str = row
                        events = events_str.split(',') 
                        roles = [int(role_id) for role_id in roles_str.split(',') if len(role_id) > 0] if roles_str else []
                        channels.append(SubscriptionChannel(int(channel_id), events, roles))
                    return channels 
            elif operation == 'get_all_users':
                users = []
                async with self.db.execute("SELECT user_id, events FROM user_subscriptions") as cursor:
                    rows = await cursor.fetchall()
                    for row in rows:
                        user_id, events_str = row
                        events = events_str.split(',')
                        users.append(SubscriptionUser(int(user_id), events))
                    return users
            elif operation == 'delete_channels_with_query':
                query = kwargs.get('query')
                if query is not None:
                    await self.db.execute(f"DELETE FROM channel_subscriptions {query}")
                    await self.db.commit()
            elif operation == 'delete_users_with_query':
                query = kwargs.get('query')
                if query is not None:
                    await self.db.execute(f"DELETE FROM user_subscriptions {query}")
                    await self.db.commit()
            return None

    async def get_all(self) -> list[SubscriptionObject]:
        channels: list[SubscriptionObject] = []
        text_channels = await self.subscription_global('get_all_channels')
        for c in text_channels:
            channels.append(c)

        user_channels = await self.subscription_global('get_all_users')
        for u in user_channels:
            channels.append(u)

        return channels

    @overload
    async def wishlist(self, operation: Literal['add', 'remove', 'check'], user: discord.User | discord.Object, shortname: str) -> bool | None: ...

    @overload
    async def wishlist(self, operation: Literal['get'], user: discord.User | discord.Object) -> list[WishlistEntry]: ...

    @overload
    async def wishlist(self, operation: Literal['get_all']) -> list[WishlistEntry]: ...

    @overload
    async def wishlist(self, operation: Literal['set_lock_status'], lock_type: Literal['shop', 'rotation'], entry: WishlistEntry, lock_status: bool) -> None: ...

    async def wishlist(self, operation: Literal['add', 'remove', 'check', 'get', 'get_all', 'set_lock_status'], **kwargs) -> list[WishlistEntry] | bool | None:
        async with self.lock:
            if operation == 'add':
                user = kwargs.get('user')
                shortname = kwargs.get('shortname')
                if user and shortname:
                    await self.db.execute(
                        "INSERT OR REPLACE INTO wishlists (user_id, shortname, created_at, lock_rotation_active, lock_shop_active) VALUES (?, ?, ?, ?, ?)",
                        (str(user.id), shortname, datetime.now().isoformat(), 0, 0)
                    )
                    await self.db.commit()
            elif operation == 'remove':
                user = kwargs.get('user')
                shortname = kwargs.get('shortname')
                if user and shortname:
                    await self.db.execute(
                        "DELETE FROM wishlists WHERE user_id = ? AND shortname = ?",
                        (str(user.id), shortname)
                    )
                    await self.db.commit()
            elif operation == 'check':
                user = kwargs.get('user')
                shortname = kwargs.get('shortname')
                if user and shortname:
                    async with self.db.execute(
                        "SELECT 1 FROM wishlists WHERE user_id = ? AND shortname = ?",
                        (str(user.id), shortname)
                    ) as cursor:
                        row = await cursor.fetchone()
                        return row is not None
                return False
            elif operation == 'get':
                user = kwargs.get('user')
                if user:
                    async with self.db.execute(
                        "SELECT shortname, created_at, lock_rotation_active, lock_shop_active FROM wishlists WHERE user_id = ?",
                        (str(user.id),)
                    ) as cursor:
                        rows = await cursor.fetchall()
                        return [
                            WishlistEntry(
                                discord.Object(id=user.id),
                                row[0],
                                datetime.fromisoformat(row[1]),
                                bool(row[2]),
                                bool(row[3])
                            )
                            for row in rows
                        ] if rows else []
                return []
            elif operation == 'get_all':
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
            elif operation == 'set_lock_status':
                lock_type = kwargs.get('lock_type')
                entry = kwargs.get('entry')
                lock_status = kwargs.get('lock_status')
                if lock_type and entry and lock_status is not None:
                    column = f"lock_{lock_type}_active"
                    await self.db.execute(
                        f"UPDATE wishlists SET {column} = ? WHERE user_id = ? AND shortname = ?",
                        (1 if lock_status else 0, str(entry.user.id), entry.shortname)
                    )
                    await self.db.commit()
            return None

    @overload
    async def profile(self, operation: Literal['create'], user_id: int) -> None: ...

    async def profile(self, operation: Literal['create'], user_id: int, **kwargs) -> None:
        async with self.lock:
            if operation == 'create':
                await self.db.execute(
                    "INSERT OR IGNORE INTO profiles (user_id) VALUES (?)",
                    (str(user_id),)
                )
                await self.db.commit()

    @overload
    async def agreement(self, operation: Literal['get'], user: discord.User | discord.Object | str) -> dict | None: ...

    @overload
    async def agreement(self, operation: Literal['update'], user: discord.User | discord.Object | str, agreement_type: str, agreement_version: str, agreement_accepted: bool) -> None: ...

    async def agreement(self, operation: Literal['get', 'update'], user: discord.User | discord.Object | str, **kwargs) -> dict | None:
        async with self.lock:
            user_id = user if isinstance(user, str) else str(user.id)
            if operation == 'get':
                async with self.db.execute(
                    "SELECT privacy_policy_accepted, privacy_policy_version, terms_of_service_accepted, terms_of_service_version FROM agreements WHERE user_id = ?",
                    (user_id,)
                ) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        return {
                            "privacy_policy_accepted": bool(row[0]),
                            "privacy_policy_version": row[1],
                            "terms_of_service_accepted": bool(row[2]),
                            "terms_of_service_version": row[3]
                        }
                    return None
            elif operation == 'update':
                agreement_type = kwargs.get('agreement_type')
                agreement_version = kwargs.get('agreement_version')
                agreement_accepted = kwargs.get('agreement_accepted')

                if agreement_type and agreement_version and agreement_accepted is not None:
                    await self.db.execute("INSERT OR IGNORE INTO agreements (user_id) VALUES (?)", (user_id,))
                    
                    if agreement_type == 'privacy_policy':
                        await self.db.execute(
                            "UPDATE agreements SET privacy_policy_accepted = ?, privacy_policy_version = ? WHERE user_id = ?",
                            (1 if agreement_accepted else 0, agreement_version, user_id)
                        )
                    elif agreement_type == 'terms_of_service':
                        await self.db.execute(
                            "UPDATE agreements SET terms_of_service_accepted = ?, terms_of_service_version = ? WHERE user_id = ?",
                            (1 if agreement_accepted else 0, agreement_version, user_id)
                        )
                    await self.db.commit()
            return None