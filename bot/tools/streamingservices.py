from bot import constants
import logging
import discord
import requests

# this class handles the streaming services option in action menu dropdown
class StreamingServicesManager:
    def __init__(self):
        self.oauth_manager = constants.OAUTH_MANAGER
        pass

    def get_spotify_link(self, isrc: str):
        if not self.oauth_manager:
            raise ValueError('OAuthManager instance is required to get Spotify link.')
        
        normalized_isrc = isrc.lstrip().rstrip()

        song_url = f'https://api.spotify.com/v1/search?q=isrc%3A{normalized_isrc}&type=track&limit=1&offset=0'
        client_token = self.oauth_manager._spotify_access_token
        logging.debug(f'[GET] {song_url}')
        link = requests.get(song_url, headers={'Authorization': f'Bearer {client_token}'})

        print(link.text)

        try:
            link.raise_for_status()
        except Exception as e:
            logging.error(f'Spotify Link GET returned {link.status_code}', exc_info=e)
            return None
        
        result = link.json()
        items = result['tracks']['items']
        if len(items) > 0:
            return items[0]['external_urls'].get('spotify', None)
        
    def get_song_link_odesli(self, spotify_url: str):
        url = f"https://api.odesli.co/resolve?url={spotify_url}"
        logging.debug(f'[GET] {url}')

        odesli = requests.get(url)

        print(odesli.text)

        try:
            odesli.raise_for_status()
        except Exception as e:
            logging.error(f'Odesli Link GET returned {odesli.status_code}', exc_info=e)
            return None
        
        result = odesli.json()
        return f'https://{result["type"]}.link/s/{result["id"]}'

    async def handle_interaction(self, interaction: discord.Interaction, track_shortname: str):
        await interaction.response.defer(thinking=True, ephemeral=True)
        
        tracks = constants.get_jam_tracks(use_cache=True)
        track = discord.utils.find(lambda t: t['track']['sn'] == track_shortname, tracks)
        
        # for now, all we do is spotify and song.link
        # we can add more later
        
        # craft cv2 view
        view = discord.ui.LayoutView(timeout=None)
        container = discord.ui.Container()
        container.accent_colour = constants.ACCENT_COLOUR
        view.add_item(container)
    
        isrc = track['track'].get('isrc', None)

        if isrc:
            spotify = self.get_spotify_link(isrc=isrc)
            if not spotify:
                return

            song_dot_link = self.get_song_link_odesli(spotify)

            container.add_item(
                discord.ui.Section(
                    discord.ui.TextDisplay(
                        f"# Stream **{track['track']['tt']}** - *{track['track']['an']}*"
                    ),
                    accessory=discord.ui.Thumbnail(
                        track['track']['au']
                    )
                )
            )

            container.add_item(
                discord.ui.Separator()
            )

            actionrow = discord.ui.ActionRow(
                discord.ui.Button(
                    label="Spotify",
                    url=spotify,
                    style=discord.ButtonStyle.link
                ),
                discord.ui.Button(
                    label="Song.Link",
                    url=song_dot_link,
                    style=discord.ButtonStyle.link
                )
            )

            container.add_item(
                actionrow
            )

        else:
            container.add_item(
                discord.ui.Section(
                    discord.ui.TextDisplay(
                        f"# Stream **{track['track']['tt']}** - *{track['track']['an']}*"
                    ),
                    discord.ui.TextDisplay(
                        "Unfortunately, we don't have an ISRC. We can't find any streaming links for this track."
                    ),
                    accessory=discord.ui.Thumbnail(
                        track['track']['au']
                    )
                )
            )

        container.add_item(
            discord.ui.Separator()
        )
        container.add_item(
            discord.ui.TextDisplay(
                "-# Festival Tracker"
            )
        )
            
        await interaction.edit_original_response(view=view)
            