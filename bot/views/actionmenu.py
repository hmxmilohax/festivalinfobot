# The action menu for the tracks command

import json
import re
import discord
import bot.tools.voicemessages as voicemessages
import bot.constants as constants
import base64
import io
import json

class ActionSelect(discord.ui.DynamicItem[discord.ui.Select], template=r'actionmenu:(?P<id>\d{17,20})'):
    def __init__(self, user_id: int) -> None:
        super().__init__(
            discord.ui.Select(
                placeholder='Select an action...',
                max_values=1,
                min_values=1,
                custom_id=f'actionmenu:{user_id}',
                disabled=False
            )
        )
        self.user_id: int = int(user_id)

        # likewise, each option follows the "custom id pattern"
        # they should also have versions!!!
        # e.g. {option}:{extra metadata in base64url}

    # This is called when the select is clicked and the custom_id matches the template.
    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Select, match: re.Match[str], /):
        user_id = match['id']
        return cls(user_id)

    async def callback(self, interaction: discord.Interaction) -> None:
        chosen_option = self.item.values[0]
        print(chosen_option)
        chosen_action = chosen_option.split(':')[0]
        chosen_action_version = chosen_option.split(':')[1]
        chosen_metadata = base64.urlsafe_b64decode(chosen_option.split(':')[2]).decode('utf-8')

        # block of code starts

        # WHAT THIS DOES!!
        # It finds the select menu in the view and sets the default 
        # (selected) value of the selected option to False.
        # This effectively "unselects" the option.
        # It then updates the message to reflect the change.

        # WHY THIS IS NEEDED!!
        # If we don't do this, the selected option will remain selected on the user's frontend, 
        # even though it's not selected in the backend.

        view = discord.ui.View.from_message(interaction.message)
        for child in view.children:
            if isinstance(child, discord.ui.Select) and child.custom_id == self.custom_id:
                for option in child.options:
                    option.default = False
                break
        await interaction.message.edit(view=view)
        # block of code ends

        preview_action_version = "1"
        wishlist_action_version = "3"
        streaming_action_version = "1"

        if chosen_action == 'preview' and chosen_action_version == preview_action_version:
            await interaction.response.defer(thinking=True, ephemeral=True)

            track_list = constants.get_jam_tracks()
            track = discord.utils.find(lambda t: t['track']['sn'] == chosen_metadata, track_list)

            if track is None:
                if chosen_metadata == 'imacat':
                    track = json.load(open('bot/data/Archive/imacat.json', 'r'))
                else:    
                    await interaction.edit_original_response(content='Track not found.', view=None)
                    return
            
            preview_audio_mgr = voicemessages.PreviewAudioMgr(interaction.client, track, interaction)
            await preview_audio_mgr.reply_to_interaction_message()
        elif chosen_action == 'wishlist' and chosen_action_version == wishlist_action_version:
            await interaction.response.defer(thinking=True, ephemeral=True)

            shortname = chosen_metadata.split(':')[1]
            action = chosen_metadata.split(':')[0]
            new_action_state = action

            jam_tracks = constants.get_jam_tracks()
            track = discord.utils.find(lambda t: t['track']['sn'] == shortname, jam_tracks)
            title = track['track']['tt'] 
            artist = track['track']['an']

            user = interaction.user

            if not user:
                await interaction.edit_original_response(embed=constants.common_error_embed("User not found."))
                return
            
            if action == 'add':
                if not await interaction.client.config.wishlist('check', user=user, shortname=shortname):
                    await interaction.client.config.wishlist('add', user=user, shortname=shortname)
                    await interaction.edit_original_response(embed=constants.common_success_embed(f"Added **{title}** - *{artist}* to your wishlist. Please refresh your wishlist to see changes."))
                    new_action_state = 'remove'
                else:
                    await interaction.edit_original_response(embed=constants.common_error_embed(f"**{title}** - *{artist}* is already in your wishlist."))
            elif action == 'remove':
                if not await interaction.client.config.wishlist('check', user=user, shortname=shortname):
                    await interaction.edit_original_response(embed=constants.common_error_embed(f"**{title}** - *{artist}* is not in your wishlist."))
                else:
                    await interaction.client.config.wishlist('remove', user=user, shortname=shortname)
                    await interaction.edit_original_response(embed=constants.common_success_embed(f"Removed **{title}** - *{artist}* from your wishlist. Please refresh your wishlist to see changes."))
                    new_action_state = 'add'

            new_metadata = f"{new_action_state}:{shortname}"
            # find the option and edit its value right then and there
            # only do this if the invoker of the interaction is the select's owner
            if user.id == self.user_id:
                for child in view.children:
                    if isinstance(child, discord.ui.Select) and child.custom_id == self.custom_id:
                        for option in child.options:
                            if option.value == chosen_option:
                                # also change the label because i forgot to do that
                                option.label = "Wishlist" if new_action_state == 'add' else "Unwishlist"
                                option.description = f"{'Add' if new_action_state == 'add' else 'Remove'} this Jam Track from your wishlist."
                                option.emoji = "⭐" if new_action_state == 'add' else "🗑️"
                                option.value = f"wishlist:{wishlist_action_version}:{base64.urlsafe_b64encode(new_metadata.encode('utf-8')).decode('utf-8')}"

                await interaction.message.edit(view=view)
        elif chosen_action == 'lyrics' and chosen_action_version == '1':
            # import here to avoid circular import
            from bot.commands.lyrics import LyricsHandler
            # python is weird
            lyrics_handler = LyricsHandler()
            await lyrics_handler.handle_interaction(interaction, chosen_metadata, pt='No', should_be_ephemeral=True)
        elif chosen_action == 'path' and chosen_action_version == '1':
            # import here to avoid circular import
            from bot.commands.path import PathCommandHandler
            path_command_handler = PathCommandHandler()
            # defer because path command dont do it for us
            await interaction.response.defer(thinking=True, ephemeral=True)
            await path_command_handler.handle_interaction(interaction, song=chosen_metadata, extra_args=[False, False, False, False, False])
        elif chosen_action == 'download' and chosen_action_version == '1':
            # import here to avoid circular import
            jam_tracks = constants.get_jam_tracks(use_cache=True)
            track = discord.utils.find(lambda t: t['track']['sn'] == chosen_metadata, jam_tracks)
            if track is None:
                if chosen_metadata == 'imacat':
                    track = json.load(open('bot/data/Archive/imacat.json', 'r'))
                else:
                    await interaction.response.send_message(content='Track not found.')
                    return
            file = discord.File(io.StringIO(json.dumps(track, indent=4)), f'{track["track"]["sn"]}_metadata.json')
            await interaction.response.send_message(file=file, ephemeral=True)
        elif chosen_action == 'streaming' and chosen_action_version == streaming_action_version:
            # import here to avoid circular import
            from bot.tools.streamingservices import StreamingServicesManager
            streaming_services_manager = StreamingServicesManager()
            await streaming_services_manager.handle_interaction(interaction, chosen_metadata)
        else:
            await interaction.response.send_message(content=f'Invalid action {chosen_action} v{chosen_action_version}.')