import re
import discord
import bot.constants as constants

class WishlistButton(discord.ui.DynamicItem[discord.ui.Button], template=r'wishlist:v(?P<version>\d+):(?P<action>\w+):(?P<id>[a-zA-Z0-9]+):(?P<user_id>\d+)'):
    def __init__(self, shortname: str, action: str, user_id: int, version: str = '1') -> None:
        super().__init__(
            discord.ui.Button(
                label='Wishlist' if action == 'add' else 'Unwishlist',
                style=discord.ButtonStyle.blurple,
                custom_id=f'wishlist:v{version}:{action}:{shortname}:{user_id}',
                emoji='🎁' if action == 'add' else '🗑️',
            )
        )
        self.shortname: str = shortname
        self.action: str = action
        self.user_id: int = user_id
        self.version: str = version

    # This is called when the button is clicked and the custom_id matches the template.
    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match: re.Match[str], /):
        shortname = match['id']
        action = match['action']
        user_id = interaction.user.id
        version = match['version']
        return cls(shortname, action, user_id, version)

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True, ephemeral=True)

        jam_tracks = constants.get_jam_tracks()
        track = discord.utils.find(lambda t: t['track']['sn'] == self.shortname, jam_tracks)
        title = track['track']['tt'] 
        artist = track['track']['an']

        user = interaction.client.get_user(self.user_id)

        if not user:
            await interaction.edit_original_response(embed=constants.common_error_embed("User not found."))
            return

        if self.version == '1':
            if self.action == 'add':

                if not await interaction.client.config._already_in_wishlist(user, self.shortname):
                    await interaction.client.config._add_to_wishlist(user, self.shortname)
                    await interaction.edit_original_response(embed=constants.common_success_embed(f"Added **{title}** - *{artist}* to your wishlist."))
                else:
                    await interaction.edit_original_response(embed=constants.common_error_embed(f"**{title}** - *{artist}* is already in your wishlist."))
            elif self.action == 'remove':

                if not await interaction.client.config._already_in_wishlist(user, self.shortname):
                    await interaction.edit_original_response(embed=constants.common_error_embed(f"**{title}** - *{artist}* is not in your wishlist."))
                else:
                    await interaction.client.config._remove_from_wishlist(user, self.shortname)
                    await interaction.edit_original_response(embed=constants.common_success_embed(f"Removed **{title}** - *{artist}* from your wishlist."))