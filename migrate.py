import aiosqlite
import json
import os
import asyncio

DATABASE_FILE = "subscriptions.db"
CHANNELS_FILE = "channels.json"

lock = asyncio.Lock()

async def setup_database():
    results = []
    results.append("Database connection created.")
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS channel_subscriptions (
                channel_id TEXT PRIMARY KEY,
                guild_id TEXT,
                events TEXT,
                roles TEXT
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS user_subscriptions (
                user_id TEXT PRIMARY KEY,
                events TEXT
            )
            """
        )
        await db.commit()
    return results

async def load_data():
    if not os.path.exists(CHANNELS_FILE):
        print(f"File {CHANNELS_FILE} not found.")
        return {}, [], ["Channels.json file not found."]

    with open(CHANNELS_FILE, "r") as f:
        data = json.load(f)

    results = ["Channels.json file read."]
    return data.get("channels", []), data.get("users", []), results

async def populate_channel_subscriptions(channels, bot, results):
    async with aiosqlite.connect(DATABASE_FILE) as db:
        async with lock:
            for channel in channels:
                channel_id = str(channel.get("id"))
                events = ",".join(channel.get("events", []))
                roles = ",".join([str(id) for id in channel.get("roles", [])])

                # Attempt to fetch the guild_id using the bot
                try:
                    discord_channel = bot.get_channel(int(channel_id))
                    guild_id = str(discord_channel.guild.id) if discord_channel and discord_channel.guild else None
                    if guild_id:
                        results.append(f"Channel {channel_id} with events {events} and roles {roles} guild {guild_id} added to channel_subscriptions.")
                    else:
                        results.append(f"Channel {channel_id} with events {events} and roles {roles} failed to get guild_id.")
                except Exception as e:
                    results.append(f"Channel {channel_id} with events {events} and roles {roles} failed to get guild_id due to error: {e}")
                    guild_id = None

                await db.execute(
                    """
                    INSERT OR REPLACE INTO channel_subscriptions (channel_id, guild_id, events, roles)
                    VALUES (?, ?, ?, ?)
                    """,
                    (channel_id, guild_id, events, roles),
                )
            await db.commit()

async def populate_user_subscriptions(users, results):
    async with aiosqlite.connect(DATABASE_FILE) as db:
        async with lock:
            for user in users:
                user_id = str(user.get("id"))
                events = ",".join(user.get("events", []))

                await db.execute(
                    """
                    INSERT OR REPLACE INTO user_subscriptions (user_id, events)
                    VALUES (?, ?)
                    """,
                    (user_id, events),
                )
                results.append(f"User {user_id} with events {events} added to user_subscriptions.")
            await db.commit()

async def main(bot):
    results = await setup_database()
    channels, users, load_results = await load_data()
    results.extend(load_results)

    if channels:
        await populate_channel_subscriptions(channels, bot, results)
    else:
        results.append("No channels found to populate.")

    if users:
        await populate_user_subscriptions(users, results)
    else:
        results.append("No users found to populate.")

    return results