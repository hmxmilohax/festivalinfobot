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

                    available_setlists[f"setlist_{setlist_idx}"] = normalised + [active_until_date]

        containers: list[discord.ui.Container] = []
        img_bytes = []

        def _sort_key(item):
            key = item[0]
            parts = key.rsplit('_', 1)
            if len(parts) == 2 and parts[1].isdigit():
                return int(parts[1])
            return key

        available_setlists = dict(sorted(available_setlists.items(), key=_sort_key))

        for setlist_id, setlist_data in available_setlists.items():
            container = discord.ui.Container()

            shortnames = setlist_data[:-1]
            active_until_date = setlist_data[-1]

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
                if not track_info:
                    track_info = {'track': {'tt': shortname, 'an': '[Song Not Found]', 'dn': 0, 'au': 'https://festivaltracker.org/assets/img/no_album_art.png'}}

                songsstr += f"- **{track_info['track']['tt']}** - *{track_info['track']['an']}*\n"
                length_secs += track_info['track']['dn']
                auurls.append(track_info['track']['au'])

            minutes = length_secs // 60
            seconds = length_secs % 60
            length = f"{minutes}m {seconds}s"

            td = discord.ui.TextDisplay(f"{len(shortnames)} songs · {length}\n{songsstr}Ends {discord.utils.format_dt(active_until_date, 'R')}")
            container.add_item(td)

            all_imgs = []
            for url in auurls:
                r = requests.get(url)
                img = Image.open(io.BytesIO(r.content)).convert("RGBA").resize((512, 512))
                all_imgs.append(img)

            grid_w, grid_h = 512 * 2, 512 * 2
            bg = Image.open("bot/data/Logo/Festival_Tracker_Fuser_sat.png").convert("RGBA")
            bg = bg.resize((grid_w, grid_h))
            bg = bg.filter(ImageFilter.GaussianBlur(radius=75))
            bg = ImageEnhance.Brightness(bg).enhance(0.4)
            grid = bg

            if len(all_imgs) <= 4:
                # normal
                imgs = list(all_imgs)
                while len(imgs) < 4:
                    imgs.append(Image.new("RGBA", (512, 512), (0, 0, 0, 0)))
                positions = [(0, 0), (512, 0), (0, 512), (512, 512)]
                for img, pos in zip(imgs, positions):
                    grid.paste(img, pos, img)
            else:
                # mini 4x4 in last grid slot
                first_three = all_imgs[:3]
                for img, pos in zip(first_three, [(0, 0), (512, 0), (0, 512)]):
                    grid.paste(img, pos, img)
                overflow = all_imgs[3:7]
                mini_positions = [(512, 512), (768, 512), (512, 768), (768, 768)]
                for img, mini_pos in zip(overflow, mini_positions):
                    mini = img.resize((256, 256))
                    grid.paste(mini, mini_pos, mini)

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