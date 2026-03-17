from datetime import datetime, timezone
import json
import logging
import discord
import requests
from PIL import Image
import io
import bot.constants as constants
from bot.views.setlists_views import SetlistView
from PIL import ImageFilter, ImageEnhance

class SetlistHandler():
    def __init__(self, bot):
        self.bot = bot

    async def handle_interaction(self, interaction: discord.Interaction):
        # await interaction.response.send_message("Setlist feature is under development.")

        await interaction.response.defer()

        logging.debug(f'[GET] {constants.DAILY_API}')
        headers = {
            'Authorization': self.bot.oauth_manager.session_token
        }
        response = requests.get(constants.DAILY_API, headers=headers)
        data = response.json()

        print(data)
        # open('debug_daily.json', 'w').write(json.dumps(data, indent=4))

        track_list = constants.get_jam_tracks(use_cache=True)

        available_setlists = {}

        channels = data.get('channels', {})
        client_events_data = channels.get('client-events', {})
        states = client_events_data.get('states', [])

        current_time = datetime.now(timezone.utc)
        
        valid_states = [state for state in states if datetime.fromisoformat(state['validFrom'].replace('Z', '+00:00')) <= current_time]
        valid_states.sort(key=lambda x: datetime.fromisoformat(x['validFrom'].replace('Z', '+00:00')), reverse=True)

        if not valid_states:
            raise ValueError("No valid states found")

        active_events = valid_states[0].get('activeEvents', [])
        for event in active_events:
            event_type = event.get('eventType', '')
            active_since = event.get('activeSince', '')
            active_until = event.get('activeUntil', '')

            active_since_date = datetime.fromisoformat(active_since.replace('Z', '+00:00')) if active_since else None
            active_until_date = datetime.fromisoformat(active_until.replace('Z', '+00:00')) if active_until else None

            if event_type.startswith('Sparks_CuratedSetlist') and active_since_date and active_until_date:
                if active_since_date <= current_time <= active_until_date:
                    setlist_meta = event_type.split(':')[0]
                    setlist_class = setlist_meta.split(',')[0]
                    setlist_idx = int(setlist_class.split('_')[-1])
                    
                    setlist_values = event_type.split(':')[1]
                    setlist_songs: list[str] = setlist_values.split(',')
                    normalised = [song.lstrip().rstrip() for song in setlist_songs]

                    available_setlists[f"setlist_{setlist_idx}"] = normalised

        containers: list[discord.ui.Container] = []
        img_bytes = []

        def _sort_key(item):
            key = item[0]
            parts = key.rsplit('_', 1)
            if len(parts) == 2 and parts[1].isdigit():
                return int(parts[1])
            return key

        available_setlists = dict(sorted(available_setlists.items(), key=_sort_key))

        for setlist_id, shortnames in available_setlists.items():
            container = discord.ui.Container()

            setlist_names = ['Daily Vibes', 'Spotlight', 'Festival Selects']
            idx = int(setlist_id.split('_')[-1]) - 1
            if idx > len(setlist_names) - 1:
                setlist_title = f"Setlist {idx + 1}"
            else:
                setlist_title = setlist_names[idx]

            container.add_item(discord.ui.TextDisplay(f"# {setlist_title}"))

            songsstr = ''
            length_secs = 0
            auurls = []

            for shortname in shortnames:
                track_info = discord.utils.find(lambda t: t['track']['sn'] == shortname, track_list)

                songsstr += f"- **{track_info['track']['tt']}** - *{track_info['track']['an']}*\n"
                length_secs += track_info['track']['dn']
                auurls.append(track_info['track']['au'])

            minutes = length_secs // 60
            seconds = length_secs % 60
            length = f"{minutes}m {seconds}s"

            td = discord.ui.TextDisplay(f"{len(shortnames)} songs · {length}\n{songsstr}")
            container.add_item(td)

            imgs = []
            for url in auurls[:4]:
                r = requests.get(url)
                img = Image.open(io.BytesIO(r.content)).convert("RGBA")
                imgs.append(img)

            while len(imgs) < 4:
                imgs.append(Image.new("RGBA", (512, 512), (0, 0, 0, 0)))

            grid_w, grid_h = 512 * 2, 512 * 2
            bg = Image.open("bot/data/Logo/Festival_Tracker_Fuser_sat.png").convert("RGBA")
            bg = bg.resize((grid_w, grid_h))
            bg = bg.filter(ImageFilter.GaussianBlur(radius=75))
            bg = ImageEnhance.Brightness(bg).enhance(0.4)
            grid = bg

            positions = [(0, 0), (512, 0), (0, 512), (512, 512)]
            for img, pos in zip(imgs, positions):
                grid.paste(img, pos, img)

            img_bytes_io = io.BytesIO()
            grid.save(img_bytes_io, format="PNG")
            grid_image_bytes = img_bytes_io.getvalue()

            container.add_item(discord.ui.MediaGallery(
                discord.MediaGalleryItem(f"attachment://{setlist_id}.png")
            ))
            container.accent_colour = constants.ACCENT_COLOUR

            container.add_item(discord.ui.Separator())
            container.add_item(discord.ui.TextDisplay(f"-# Festival Tracker"))

            img_bytes.append( (f"{setlist_id}.png", grid_image_bytes) )

            containers.append(container)

        view = SetlistView(containers=containers, user_id=interaction.user.id)
        view.update_components()

        msg = await interaction.followup.send(view=view, files=[discord.File(io.BytesIO(img_data), filename=img_name) for img_name, img_data in img_bytes], wait=True)
        view.message = msg

class SetlistViewActionRow(discord.ui.ActionRow):
    def __init__(self, page, total, user_id):
        super().__init__()

        self.current_page = page
        self.total_pages = total
        self.user_id = user_id

        self.prev = PreviousButton(style=discord.ButtonStyle.secondary, emoji=constants.PREVIOUS_EMOJI, disabled=not (self.current_page > 0), user_id=self.user_id)
        self.next = NextButton(style=discord.ButtonStyle.secondary, emoji=constants.NEXT_EMOJI, disabled=not (self.current_page < self.total_pages - 1), user_id=self.user_id)
        self.wishlist = discord.ui.Button(style=discord.ButtonStyle.secondary, label="Wishlist Songs", emoji="🎁")
        self.wishlist.callback = self.wishlist_callback

        self.add_item(self.prev)
        self.add_item(self.next)
        self.add_item(self.wishlist)

    async def wishlist_callback(self, interaction: discord.Interaction):
        view: SetlistView = self.view
        container_data = view.container_data[view.current_page]
        shortnames = container_data['songs_shortnames']

        await interaction.response.defer(thinking=True, ephemeral=True)

        return

        user = interaction.client.get_user(self.user_id)

        if not user:
            await interaction.response.send_message("User not found.", ephemeral=True)
            return

        added_tracks = []
        already_in_wishlist = []

        for shortname in shortnames:
            if not await interaction.client.config.wishlist('check', user=user, shortname=shortname):
                await interaction.client.config.wishlist('add', user=user, shortname=shortname)
                added_tracks.append(shortname)
            else:
                already_in_wishlist.append(shortname)

        jam_tracks = constants.get_jam_tracks()
        def get_track_info(sn):
            return discord.utils.find(lambda t: t['track']['sn'] == sn, jam_tracks)

        embed = discord.Embed(title="Wishlist Update", color=constants.EMBED_COLOR_SUCCESS)

        if added_tracks:
            added_lines = []
            for sn in added_tracks:
                track_info = get_track_info(sn)
                added_lines.append(f"**{track_info['track']['tt']}** - *{track_info['track']['an']}*")
            embed.add_field(name="Added to Wishlist:", value="\n".join(added_lines), inline=False)

        if already_in_wishlist:
            already_lines = []
            for sn in already_in_wishlist:
                track_info = get_track_info(sn)
                already_lines.append(f"**{track_info['track']['tt']}** - *{track_info['track']['an']}*")
            embed.add_field(name="Already in Wishlist:", value="\n".join(already_lines), inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

class SetlistView(discord.ui.LayoutView):
    def __init__(self, containers, user_id):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.current_page = 0
        self.message : discord.Message

        self.container_data = containers

        self.total_pages = len(containers)
        self.action_row = None

        logging.info(self.total_pages)

    def update_components(self):
        """
        returns the attachments for the page
        """
        self.clear_items()

        container_data = self.container_data[self.current_page]

        container = discord.ui.Container()
        container.add_item(discord.ui.TextDisplay(f"# {container_data['setlist_name']}"))
        container.add_item(discord.ui.TextDisplay(f"-# Setlist {self.current_page + 1} of {self.total_pages}"))
        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay(f"{len(container_data['songs'].splitlines())} songs · {container_data['length']}\n{container_data['songs']}"))
        container.add_item(discord.ui.MediaGallery(
            discord.MediaGalleryItem(container_data['attachment_url'])
        ))

        container.add_item(discord.ui.Separator())

        self.action_row = SetlistViewActionRow(self.current_page, self.total_pages, self.user_id)
        container.add_item(self.action_row)

        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay(f"-# Festival Tracker"))

        self.add_item(container)

    async def on_timeout(self):
        try:
            if self.action_row:
                for item in self.action_row.children:
                    item.disabled = True
                await self.message.edit(view=self)
        except discord.NotFound:
            logging.warning("Message was not found when trying to edit after timeout.")
        except Exception as e:
            logging.error(f"An error occurred during on_timeout: {e}, {type(e)}, {self.message}")

class PreviousButton(discord.ui.Button):
    def __init__(self, *args, **kwargs):
        self.user_id = kwargs.pop('user_id')
        super().__init__(*args, **kwargs)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your session. Please run the command yourself to start your own session.", ephemeral=True)
            return
        view: SetlistView = self.view
        view.current_page -= 1
        
        view.update_components()

        await interaction.response.edit_message(view=view)

class NextButton(discord.ui.Button):
    def __init__(self, *args, **kwargs):
        self.user_id = kwargs.pop('user_id')
        super().__init__(*args, **kwargs)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your session. Please run the command yourself to start your own session.", ephemeral=True)
            return
        view: SetlistView = self.view
        view.current_page += 1
        view.update_components()

        await interaction.response.edit_message(view=view)
