# The action menu for the tracks command

import logging
from datetime import timezone
from datetime import datetime
from bot.database import Config, PolicyException as DbPolicyErr
import json
import re
import discord
import bot.tools.voicemessages as voicemessages
import bot.constants as constants
import base64
import io
import json

class VoteButton(discord.ui.DynamicItem[discord.ui.Button], template=r'vote:(?P<version>\d+):(?P<shortname>[a-zA-Z0-9_]+):(?P<direction>\d)'):
    def __init__(self, version: str, shortname: str, direction: int, **kwargs) -> None:
        super().__init__(
            discord.ui.Button(
                emoji="🔥" if int(direction) == 1 else "🗑️",
                custom_id=f'vote:{version}:{shortname}:{direction}',
                disabled=False,
                row=2,
                **kwargs
            )
        )
        self.version: str = version
        self.shortname: str = shortname
        self.direction: int = direction

    # This is called when the button is clicked and the custom_id matches the template.
    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match: re.Match[str], /):
        version = match['version']
        shortname = match['shortname']
        direction = int(match['direction'])
        return cls(version, shortname, direction)

    async def callback(self, interaction: discord.Interaction) -> None:
        if not constants.VOTING_IS_ENABLED:
            await interaction.response.send_message(embed=constants.common_error_embed("Voting is currently disabled."), ephemeral=True)
            return

        db: Config = interaction.client.config
        voting_action_version = '1'
        
        custom_id = self.custom_id
        action = custom_id.split(':')[0]
        vote_interaction_version = custom_id.split(':')[1]

        print(action)
        print(vote_interaction_version)
        print(voting_action_version)

        if action == "vote" and vote_interaction_version == voting_action_version:
            await interaction.response.defer(thinking=True, ephemeral=True)

            track_list = constants.get_jam_tracks(use_cache=True)
            shortname = custom_id.split(':')[2]
            track_data = discord.utils.find(lambda t: t['track']['sn'] == shortname, track_list)
            vote_direction = int(custom_id.split(':')[3])
            user = interaction.user

            chid = None
            guid = None
            if interaction.guild:
                chid = interaction.channel.id
                guid = interaction.guild.id

            within_new_until = datetime.now(tz=timezone.utc) < datetime.fromisoformat(track_data['track']['nu'])

            # check if user has voted
            try:
                vote = await db.vote('get', user, shortname)
            except DbPolicyErr as e:
                await interaction.edit_original_response(embed=constants.common_error_embed(f"{e}"))
                return

            song_fmt = f'**{track_data['track']['tt']}** - *{track_data['track']['an']}*'

            if vote is not None and vote == vote_direction:
                await interaction.edit_original_response(
                    embed=constants.common_error_embed(
                        f"You have **already** casted a **{'positive' if vote == 1 else 'negative'}** vote for {song_fmt}.\n" + 
                        "Would you like to remove your vote?"),
                    view=VoteRemovalConfirmationView(interaction, shortname, user)
                )
            else:
                # add or update vote
                # possibly dangerous but i dont wanna add a ratelimit because it drives frustration
                await db.vote('add', user, shortname, 
                    vote_direction=vote_direction,
                    vote_channel_id=chid,
                    vote_server_id=guid,
                    vote_source_window='manual',
                    vote_made_within_new_until_window=within_new_until,
                )

                await interaction.edit_original_response(embed=constants.common_success_embed(f"You have casted a **{'positive' if vote_direction == 1 else 'negative'}** vote for {song_fmt}."))

            # TEMPORARY: usage analysis
            await constants.msg_log(interaction.client, f'User {user.id} casted a **{'positive' if vote_direction == 1 else 'negative'}** vote for {shortname}')

            await update_view(interaction, shortname)
        else:
            await interaction.response.send_message('This is an old version of the button. Please run the command again.', ephemeral=True)

class UpdateVotesButton(discord.ui.DynamicItem[discord.ui.Button], template=r'votes_upt:(?P<version>\d+):(?P<shortname>[a-zA-Z0-9_]+)'):
    def __init__(self, version: str, shortname: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=f'Update',
                emoji="🔄",
                custom_id=f'votes_upt:{version}:{shortname}',
                disabled=False,
                row=2
            )
        )
        self.version: str = version
        self.shortname: str = shortname

    @classmethod
    async def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match: re.Match[str], /):
        version = match['version']
        shortname = match['shortname']
        return cls(version, shortname)

    async def callback(self, interaction: discord.Interaction) -> None:
        if not constants.VOTING_IS_ENABLED:
            await interaction.response.send_message(embed=constants.common_error_embed("Voting is currently disabled."), ephemeral=True)
            return

        db: Config = interaction.client.config
        user_id = interaction.user.id
        current_time = datetime.now(timezone.utc)

        # rate limit: 10 second cooldown
        if user_id in db.voting_update_last_usage_per_user_dict:
            last_usage = db.voting_update_last_usage_per_user_dict[user_id]
            if (current_time - last_usage).total_seconds() < 10:
                time_remaining = 10 - int((current_time - last_usage).total_seconds())
                await interaction.response.send_message(
                    embed=constants.common_error_embed(f"Please wait **{time_remaining} seconds** before updating votes again."), 
                    ephemeral=True
                )
                return

        await interaction.response.defer(ephemeral=True, thinking=True)
        db.voting_update_last_usage_per_user_dict[user_id] = current_time

        # TEMPORARY: usage analysis
        await constants.msg_log(interaction.client, f'User {user_id} updated votes')

        await update_view(interaction, self.shortname)
        await interaction.edit_original_response(embed=constants.common_success_embed("Votes updated successfully."))

async def update_view(interaction: discord.Interaction, shortname: str):
    db: Config = interaction.client.config

    vote_counts = await db.get_vote_counts(shortname)

    print(f'{shortname} {vote_counts}')

    view = discord.ui.View.from_message(interaction.message)
    for child in view.children:
        if isinstance(child, discord.ui.Button):
            # were gonna update both buttons here.
            child_cid = child.custom_id
            if child_cid:
                button_action = child_cid.split(':')[0]
                if button_action == 'vote':
                    child_shortname = child_cid.split(':')[2]
                    if child_shortname == shortname:
                        child_vote_direction = int(child_cid.split(':')[3])
                        count = vote_counts['upvotes'] if child_vote_direction == 1 else vote_counts['downvotes']
                        child.label = f"{count}"
                    else:
                        logging.warning(f"update_view: button shortname {child_shortname} does not match track shortname {shortname}")

    await interaction.message.edit(view=view)

class VoteRemovalConfirmationView(discord.ui.View):
    def __init__(self, original_interaction: discord.Interaction, shortname: str, user: discord.User) -> None:
        super().__init__(timeout=60)
        self.original_interaction = original_interaction
        self.shortname = shortname
        self.user = user

    @discord.ui.button(
        label="Remove",
        style=discord.ButtonStyle.danger,
    )
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not constants.VOTING_IS_ENABLED:
            await interaction.response.send_message(embed=constants.common_error_embed("Voting is currently disabled."), ephemeral=True)
            return

        # Remove the vote from database
        await interaction.response.defer()

        db: Config = interaction.client.config
        try:
            await db.vote('remove', self.user, self.shortname)
        except DbPolicyErr as e:
            await interaction.edit_original_response(embed=constants.common_error_embed(f"{e}"))
            return

        # TEMPORARY: usage analysis
        await constants.msg_log(interaction.client, f'User {self.user.id} removed vote for {self.shortname}')

        await update_view(self.original_interaction, self.shortname)
        await self.original_interaction.edit_original_response(embed=constants.common_success_embed("Vote removed successfully."), view=None)

        self.stop()

    @discord.ui.button(
        label="Don't Remove",
        style=discord.ButtonStyle.secondary
    )
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        # Edit using this button interaction to acknowledge it and avoid "Interaction Failed" errors
        await self.original_interaction.edit_original_response(embed=constants.common_error_embed("Vote removal cancelled."), view=None)
        self.stop()

    async def on_timeout(self) -> None:
        try:
            # If the user doesn't respond in 60s, clean up the original ephemeral message
            await self.original_interaction.edit_original_response(
                embed=constants.common_error_embed("Vote removal timed out."), 
                view=None
            )
        except Exception:
            pass