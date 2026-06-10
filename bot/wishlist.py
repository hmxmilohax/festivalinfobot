import json
import requests
import logging
import discord
from bot import constants, database
from bot.helpers import DailyCommandHandler, ShopCommandHandler
from bot.views.wishlistpersist import WishlistButton
from bot.tracks import JamTrackHandler

class AlreadyInWishlistError(Exception):
    pass

class NotInWishlistError(Exception):
    pass

class WishlistManager():
    def __init__(self, bot: discord.Client):
        self.bot = bot
        self.config: database.Config = self.bot.config
        self.daily_handler = DailyCommandHandler(self.bot)
        self.shop_handler = ShopCommandHandler(self.bot)

    async def handle_wishlists(self):
        all_wishlists: list[database.WishlistEntry] = await self.config.wishlist('get_all')
        logging.info('Processing wishlists...')
        all_tracks = constants.get_jam_tracks(use_cache=True, max_cache_age=60)
        rotation = self.daily_handler.fetch_daily_shortnames()

        for entry in all_wishlists:
            rotation_entry = discord.utils.find(lambda x: x['metadata']['track']['sn'] == entry.shortname, rotation)

            track = discord.utils.find(lambda x: x['track']['sn'] == entry.shortname, all_tracks)

            # the track is NOT in the current rotation
            if not rotation_entry:

                if entry.lock_rotation_active:
                    # the lock is active so we unlock the wishlist entry so that we can notify the user again
                    await self.config.wishlist('set_lock_status', lock_type='rotation', entry=entry, lock_status=0)

                    # we notify the user that the track is no longer in rotation
                    embed = discord.Embed(
                        title="A Jam Track from your wishlist has left rotation!",
                        colour=constants.ACCENT_COLOUR
                    )
                    embed.add_field(
                        name="", value=f"**{track['track']['tt']}** - *{track['track']['an']}* is no longer available in rotation!",
                        inline=False
                    )
                    embed.set_thumbnail(url=track['track']['au'])
                    embed.set_footer(
                        text=f"You wishlisted this item on {entry.created_at.strftime('%B %d, %Y at %H:%M:%S')}. · Festival Tracker",
                    )

                    user = self.bot.get_user(entry.user.id)
                    if user:
                        try:
                            await user.send(embed=embed)
                        except Exception as e:
                            logging.error("Cannot notify wishlist ocurrence", exc_info=e)

                # stop here
                continue

            # we already notified this user that this track is in rotation
            if entry.lock_rotation_active:
                continue

            # we now proceed to notify the user
            print(f"Track {track['track']['sn']} is in rotation, notifying user {entry.user.id}")

            # we lock the wishlist entry so that we don't notify the user again
            await self.config.wishlist('set_lock_status', lock_type='rotation', entry=entry, lock_status=1)

            embed = discord.Embed(
                title="A Jam Track from your wishlist is in rotation!",
                colour=constants.ACCENT_COLOUR
            )
            embed.add_field(
                name="", value=f"**{track['track']['tt']}** - *{track['track']['an']}* is now available in rotation.",
                inline=False
            )
            embed.set_thumbnail(url=track['track']['au'])
            embed.set_footer(
                text=f"You wishlisted this item on {entry.created_at.strftime('%B %d, %Y at %H:%M:%S')}. · Festival Tracker",
            )

            user = self.bot.get_user(entry.user.id)
            if user:
                try:
                    await user.send(embed=embed)
                except Exception as e:
                    logging.error("Cannot notify wishlist ocurrence", exc_info=e)

        # handle everything again but this time for shop












        logging.debug(f'[GET] {constants.SHOP_API}')
        headers = {
            'Authorization': self.bot.oauth_manager.session_token
        }
        response = requests.get(constants.SHOP_API, headers=headers)
        if response.status_code == 401 or response.status_code == 403:
            self.bot.oauth_manager._create_token()
            raise Exception('Please try again.')

        data = response.json()

        fortnite_api_shop_data_url = 'https://fortnite-api.com/v2/shop' # TODO: language target
        response = requests.get(fortnite_api_shop_data_url)
        marlon_data = response.json()

        storefront = discord.utils.find(lambda storefront: storefront['name'] == 'BRWeeklyStorefront', data['storefronts'])
        # open('shop_test.json', 'w').write(json.dumps(storefront, indent=4))

        shop_tracks = list(filter(lambda item: item['meta']['templateId'].startswith('SparksSong:'), storefront['catalogEntries']))
        bundles = list(filter(lambda item: item['offerType'] == 'DynamicBundle', storefront['catalogEntries']))

        for entry in all_wishlists:
            track = discord.utils.find(lambda x: x['track']['sn'] == entry.shortname, all_tracks)
            shop_entry = discord.utils.find(lambda offer: offer['meta']['templateId'] == track['track']['ti'], shop_tracks)

            bundle_with_track = None

            shop_notification_level = entry.lock_shop_active
            # LOCK LEVELS
            # 0 10 = not in bundle, not itself         10
            # 2 11 = in bundle,     not itself         11
            # 1 12 = not in bundle, itself             12
            # 3 13 = in bundle,     itself             13

            # transitions correction
            corrected_state = -1
            # I am NOT messing around
            if shop_notification_level == 0:
                corrected_state = 10
            if shop_notification_level == 2:
                corrected_state = 11
            if shop_notification_level == 1:
                corrected_state = 12
            if shop_notification_level == 3:
                corrected_state = 13

            # is this costly?
            for bundle in bundles:
                track_template_id = track['track']['ti']
                bundle_offers = bundle['dynamicBundleInfo']['bundleItems']
                for item in bundle_offers:
                    # pass
                    if item['item']['templateId'] == track_template_id:
                        bundle_with_track = bundle
                        break

            print(bundle_with_track)

            track_not_in_shop = (shop_entry is None) and (bundle_with_track is None)
            # the track is NOT in the current shop

            current_state = 10
            new_notification_level = 0
            if bundle_with_track:
                new_notification_level = 2
                current_state = 11
            if shop_entry:
                new_notification_level = 1
                current_state = 12
            if shop_entry and bundle_with_track:
                new_notification_level = 3
                current_state = 13

            if track_not_in_shop:
                if corrected_state in [11, 12, 13] and current_state == 10:
                    # the lock is active so we unlock the wishlist entry so that we can notify the user again
                    await self.config.wishlist('set_lock_status', lock_type='shop', entry=entry, lock_status=0)

                    # we notify the user that the track is no longer in shop
                    embed = discord.Embed(
                        title="A Jam Track from your wishlist has left the Item Shop!",
                        colour=constants.ACCENT_COLOUR
                    )
                    embed.add_field(
                        name="", value=f"**{track['track']['tt']}** - *{track['track']['an']}* is no longer available in the shop!",
                        inline=False
                    )
                    embed.set_thumbnail(url=track['track']['au'])
                    embed.set_footer(
                        text=f"You wishlisted this item on {entry.created_at.strftime('%B %d, %Y at %H:%M:%S')}. · Festival Tracker",
                    )

                    user = self.bot.get_user(entry.user.id)
                    if user:
                        try:
                            await user.send(embed=embed)
                        except Exception as e:
                            logging.error("Cannot notify wishlist ocurrence", exc_info=e)

                # stop here
                continue

            # we already notified this user that this track is in shop
            if current_state == corrected_state:
                continue

            # we now proceed to notify the user
            print(f"Track {track['track']['sn']} is in shop for {entry.user.id} with state {corrected_state} -> {current_state}")

            embed_title = ""
            # transition 10 -> 11
            if corrected_state == 10 and current_state == 11:
                embed_title = "A Jam Track from your wishlist is now in the Item Shop within a bundle!"

            # default transitions from 10
            if corrected_state == 10 and current_state == 12:
                embed_title = "A Jam Track from your wishlist is now in the Item Shop!"
            if corrected_state == 10 and current_state == 13:
                embed_title = "A Jam Track from your wishlist is now in the Item Shop!"

            # transitions from 11
            if corrected_state == 11 and current_state == 12:
                embed_title = "A Jam Track from your wishlist is now in the Item Shop only by itself!"
            if corrected_state == 11 and current_state == 13:
                embed_title = "A Jam Track from your wishlist is now in the Item Shop by itself!"

            # transition 12 -> 13
            if corrected_state == 12 and current_state == 13:
                embed_title = "A Jam Track from your wishlist is now in the Item Shop within a bundle!"

            # transition 13 -> 12
            if corrected_state == 13 and current_state == 12:
                embed_title = "A Jam Track from your wishlist is now in the Item Shop only by itself!"
            # transition 13 -> 11
            if corrected_state == 13 and current_state == 11:
                embed_title = "A Jam Track from your wishlist is now in the Item Shop only within a bundle!"

            # transition 12 -> 11
            if corrected_state == 12 and current_state == 11:
                embed_title = "A Jam Track from your wishlist is now in the Item Shop only within a bundle!"
            
            embed = discord.Embed(
                title=embed_title,
                colour=constants.ACCENT_COLOUR
            )
            embed.add_field(
                name="", value=f"**{track['track']['tt']}** - *{track['track']['an']}* is available in the shop.",
                inline=False
            )

            if current_state in [12, 13]:
                if shop_entry:
                    embed.add_field(
                        name="Standalone Availability",
                        value=f"Available in the Item Shop for {shop_entry['prices'][0]['regularPrice']} V-Bucks!",
                        inline=False
                    )

                    embed.add_field(
                        name="Available until",
                        value=constants.format_date(shop_entry['meta']['outDate']),
                        inline=False
                    )

                    embed.set_thumbnail(url=track['track']['au'])

            if current_state in [11, 13]:
                if bundle_with_track:
                    # cross reference bundle's offer id with the unofficial api data
                    offer_id1 = bundle_with_track['offerId']
                    unofficial_bundle = discord.utils.find(lambda x: x['offerId'] == offer_id1, marlon_data['data']['entries'])

                    bundle_price = bundle_with_track['dynamicBundleInfo']['floorPrice']
                    bundle_offers = bundle['dynamicBundleInfo']['bundleItems']
                    for item in bundle_offers:
                        bundle_price += item['regularPrice']

                    bundle_alert = ""
                    if unofficial_bundle.get('banner', None):
                        bundle_alert = f" [{unofficial_bundle['banner']['value']}]"

                    if unofficial_bundle:
                        embed.add_field(
                            name=f"Bundle: {unofficial_bundle['bundle']['name']}",
                            value=f"Price: {bundle_price} V-Bucks{bundle_alert}\n" +
                            f"**{track['track']['tt']}** - *{track['track']['an']}* and {len(bundle_offers) - 1} more items.",
                            inline=False
                        )
                        embed.add_field(
                            name="Available until",
                            value=constants.format_date(bundle_with_track['meta']['outDate']),
                            inline=False
                        )
                        embed.set_thumbnail(url=unofficial_bundle['bundle']['image'])
                    else:
                        embed.add_field(
                            name="Bundle Details",
                            value=f"We're currently unable to fetch the details for this bundle. Sorry!",
                        )

            embed.set_footer(
                text=f"You wishlisted this item on {entry.created_at.strftime('%B %d, %Y at %H:%M:%S')}. · Festival Tracker",
            )

            user = self.bot.get_user(entry.user.id)
            if user:
                try:
                    await user.send(embed=embed)
                except Exception as e:
                    logging.error("Cannot notify wishlist ocurrence", exc_info=e)

            # we lock the wishlist entry so that we don't notify the user again
            await self.config.wishlist('set_lock_status', lock_type='shop', entry=entry, lock_status=new_notification_level)

    async def handle_display(self, interaction: discord.Interaction, page = 0):
        first_time = not interaction.response.is_done()
        if first_time:
            await interaction.response.defer()

        print('trigger')
        all_tracks = constants.get_jam_tracks(use_cache=True, max_cache_age=60)

        view = discord.ui.LayoutView(timeout=60)
        
        container = discord.ui.Container(accent_colour=constants.ACCENT_COLOUR)
        view.add_item(container)

        entries = await self.config.wishlist('get', user=interaction.user)
        per_page = 5
        last_page = len(entries) // 5

        container.add_item(
            discord.ui.Section(
                discord.ui.TextDisplay(
                    "# Your Wishlist\n" + 
                    f"-# Page {page + 1} of {last_page + 1}"
                ),
                accessory=discord.ui.Thumbnail(f'attachment://{constants.KEYART_FNAME}')
            )
        )
        container.add_item(
            discord.ui.Separator()
        )

        if len(entries) == 0:
            container.add_item(
                discord.ui.TextDisplay("There's nothing to see here!\n-# Add more tracks to your wishlist and they will show up here.")
            )

        chunk_entries = entries[page * 5:(page + 1) * 5]

        for wishlist_entry in chunk_entries:
            track = discord.utils.find(lambda x: x['track']['sn'] == wishlist_entry.shortname, all_tracks)
            btn = WishlistButton(track['track']['sn'], "remove", interaction.user.id)

            container.add_item(
                discord.ui.Section(
                    discord.ui.TextDisplay(
                        f"**{track['track']['tt']}** - *{track['track']['an']}*\n" +
                        f"Added {discord.utils.format_dt(wishlist_entry.created_at, 'F')}\n-# " +
                        f"In Shop? " + (constants.SUCCESS_EMOJI if wishlist_entry.lock_shop_active else constants.ERROR_EMOJI) + " · " +
                        f"In Rotation? " + (constants.SUCCESS_EMOJI if wishlist_entry.lock_rotation_active else constants.ERROR_EMOJI)
                    ),
                    accessory=btn
                )
            )

        container.add_item(
            discord.ui.Separator()
        )

        prev_btn = discord.ui.Button(label="", emoji=constants.PREVIOUS_EMOJI, style=discord.ButtonStyle.secondary)
        async def prev(i: discord.Interaction):

            if i.user.id != interaction.user.id:
                await i.response.send_message("This is not your session. Please run the command yourself to start your own session.", ephemeral=True)
                return

            await i.response.defer()
            if page > 0:
                await self.handle_display(interaction, page - 1)

        prev_btn.callback = prev

        nxt_btn = discord.ui.Button(label="", emoji=constants.NEXT_EMOJI, style=discord.ButtonStyle.secondary)
        async def nxt(i: discord.Interaction):

            if i.user.id != interaction.user.id:
                await i.response.send_message("This is not your session. Please run the command yourself to start your own session.", ephemeral=True)
                return

            await i.response.defer()
            if page < last_page:
                await self.handle_display(interaction, page + 1)

        nxt_btn.callback = nxt

        if page == 0:
            prev_btn.disabled = True
        if page == last_page:
            nxt_btn.disabled = True

        rfr_btn = discord.ui.Button(label="", emoji='<:e541f62450f233be:1462293429437333649>', style=discord.ButtonStyle.secondary)
        async def rfr(i: discord.Interaction):

            if i.user.id != interaction.user.id:
                await i.response.send_message("This is not your session. Please run the command yourself to start your own session.", ephemeral=True)
                return

            await i.response.defer()
            await self.handle_display(interaction, page)

        rfr_btn.callback = rfr

        add_track_btn = discord.ui.Button(label="Add to Wishlist", emoji=constants.SEARCH_EMOJI)
        async def add(i: discord.Interaction):
            modal = discord.ui.Modal(title="Add to Wishlist")
            modal.add_item(discord.ui.TextInput(label="Track Search Query", placeholder="A search query: an artist, song name, or shortname."))

            async def search_add(i: discord.Interaction):
                await i.response.defer(thinking=True, ephemeral=True)
                text = modal.children[0].value
                tracks = JamTrackHandler().fuzzy_search_tracks(all_tracks, text)

                if len(tracks) == 0:
                    await i.edit_original_response(embed=constants.common_error_embed(f'No tracks were found matching \"{text}\"'))
                    return
                
                user = i.user
                shortname = tracks[0]['track']['sn']
                ftitle = tracks[0]['track']['tt']
                fartist = tracks[0]['track']['an']
                if not await self.config.wishlist('check', user=user, shortname=shortname):
                    await self.config.wishlist('add', user=user, shortname=shortname)
                    await i.edit_original_response(embed=constants.common_success_embed(f"Added **{ftitle}** - *{fartist}* to your wishlist."))
                else:
                    await i.edit_original_response(embed=constants.common_error_embed(f"**{ftitle}** - *{fartist}* is already in your wishlist."))

                if user.id == interaction.user.id:
                    await self.handle_display(interaction, page)

            modal.on_submit = search_add
            await i.response.send_modal(modal)

        add_track_btn.callback = add

        container.add_item(
            discord.ui.ActionRow(
                prev_btn, nxt_btn, rfr_btn, add_track_btn                
            )
        )

        container.add_item(
            discord.ui.Separator()
        )
        container.add_item(
            discord.ui.TextDisplay('-# Festival Tracker')
        )

        async def timeout():
            for item in view.walk_children():
                if isinstance(item, discord.ui.Button):
                    item.disabled = True

            await interaction.edit_original_response(view=view)

        view.on_timeout = timeout

        if first_time:
            await interaction.edit_original_response(view=view, attachments=[discord.File(constants.KEYART_PATH, constants.KEYART_FNAME)])
        else:
            await interaction.edit_original_response(view=view)