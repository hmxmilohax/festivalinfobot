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
        all_wishlists: list[database.WishlistEntry] = await self.config._get_all_wishlists()
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
                    await self.config._unlock_wishlist_rotation(entry=entry)

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
            await self.config._lock_wishlist_rotation(entry=entry)

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
            if entry.lock_shop_active:
                continue

            # we now proceed to notify the user
            print(f"Track {track['track']['sn']} is in shop, notifying user {entry.user.id}")
            embed = discord.Embed(
                title="A Jam Track from your wishlist is in the Item Shop!",
                colour=constants.ACCENT_COLOUR
            )
            embed.add_field(
                name="", value=f"**{track['track']['tt']}** - *{track['track']['an']}* is now available in the shop.",
                inline=False
            )
            embed.add_field(
                name="Available until",
                value=constants.format_date(shop_entry['meta']['outDate'])
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

            # we lock the wishlist entry so that we don't notify the user again
            await self.config._lock_wishlist_shop(entry=entry)

    async def handle_display(self, interaction: discord.Interaction, page = 0):
        first_time = not interaction.response.is_done()
        if first_time:
            await interaction.response.defer()

        print('trigger')
        all_tracks = constants.get_jam_tracks(use_cache=True, max_cache_age=60)

        view = discord.ui.LayoutView(timeout=60)
        
        container = discord.ui.Container(accent_colour=constants.ACCENT_COLOUR)
        view.add_item(container)

        entries = await self.config._get_wishlist_of_user(interaction.user)
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
                if not await self.config._already_in_wishlist(user, shortname):
                    await self.config._add_to_wishlist(user, shortname)
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