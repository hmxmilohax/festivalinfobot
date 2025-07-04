import discord
from bot import config, constants
from bot.helpers import DailyCommandHandler, ShopCommandHandler

class AlreadyInWishlistError(Exception):
    pass

class NotInWishlistError(Exception):
    pass

class WishlistManager():
    def __init__(self, bot: discord.Client):
        self.bot = bot
        self.config: config.Config = self.bot.config
        self.daily_handler = DailyCommandHandler(self.bot)
        self.shop_handler = ShopCommandHandler(self.bot)

    async def handle_wishlists(self):
        all_wishlists: list[config.WishlistEntry] = await self.config._get_all_wishlists()
        rotation = self.daily_handler.fetch_daily_shortnames()
        all_tracks = constants.get_jam_tracks()

        for entry in all_wishlists:
            rotation_entry = discord.utils.find(lambda x: x['shortname'] == entry.shortname, rotation)

            track = discord.utils.find(lambda x: x['track']['sn'] == entry.shortname, all_tracks)

            # the track is NOT in the current rotation
            if not rotation_entry:

                if entry.lock_rotation_active:
                    # the lock is active so we unlock the wishlist entry so that we can notify the user again
                    await self.config._unlock_wishlist_rotation(entry=entry)

                    # we notify the user that the track is no longer in rotation
                    # TODO

                # stop here
                continue

            # we already notified this user that this track is in rotation
            if entry.lock_rotation_active:
                continue

            # we now proceed to notify the user
            print(f"Track {track['track']['sn']} is in rotation, notifying user {entry.user.id}")

            # we lock the wishlist entry so that we don't notify the user again
            await self.config._lock_wishlist_rotation(entry=entry)

        # handle everything again but this time for shop
        shop_tracks = self.shop_handler.fetch_shop_tracks()

        for entry in all_wishlists:
            track = discord.utils.find(lambda x: x['track']['sn'] == entry.shortname, all_tracks)
            shop_entry = discord.utils.find(lambda offer: offer['meta']['templateId'] == track['track']['ti'], shop_tracks)

            # the track is NOT in the current shop
            if not shop_entry:

                if entry.lock_shop_active:
                    # the lock is active so we unlock the wishlist entry so that we can notify the user again
                    await self.config._unlock_wishlist_shop(entry=entry)

                    # we notify the user that the track is no longer in shop
                    # TODO

                # stop here
                continue

            # we already notified this user that this track is in shop
            if entry.lock_shop_active:
                continue

            # we now proceed to notify the user
            print(f"Track {track['track']['sn']} is in shop, notifying user {entry.user.id}")

            # we lock the wishlist entry so that we don't notify the user again
            await self.config._lock_wishlist_shop(entry=entry)