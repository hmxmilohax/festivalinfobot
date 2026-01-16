import json
import re
import discord
import bot.tools.voicemessages as voicemessages
import bot.constants as constants

class PreviewButton(discord.ui.DynamicItem[discord.ui.Button], template=r'persistent_preview:sn:(?P<id>[a-zA-Z0-9_]+)'):
    def __init__(self, shortname: str) -> None:
        super().__init__(
            discord.ui.Button(
                label='Preview',
                style=discord.ButtonStyle.blurple,
                custom_id=f'persistent_preview:sn:{shortname}',
                emoji='🔊',
                disabled=True
            )
        )
        self.shortname: str = shortname

    # This is called when the button is clicked and the custom_id matches the template.
    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match: re.Match[str], /):
        shortname = match['id']
        return cls(shortname)

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True, ephemeral=True)

        track_list = constants.get_jam_tracks()
        track = discord.utils.find(lambda t: t['track']['sn'] == self.shortname, track_list)

        if track is None:
            if self.shortname == 'imacat':
                track = json.load(open('bot/data/Archive/imacat.json', 'r'))
            else:    
                await interaction.edit_original_response(content='Track not found.', view=None)
                return
        
        preview_audio_mgr = voicemessages.PreviewAudioMgr(interaction.client, track, interaction)
        await preview_audio_mgr.reply_to_interaction_message()
