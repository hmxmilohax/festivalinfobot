"""
subscriptionmanager.py
----------------------
Manages the /subscriptions command UI.

Architecture: single SubscriptionManagerView with a page-rendering model.
- One discord.ui.View lives for the entire interaction lifetime.
- self._page drives which items are rendered.
- render() clears all children and rebuilds them for the current page.
- All mutable state (target channel, pending events/roles) lives on the view.

rewritten by claude!
"""

from typing import List
import discord
from discord.ext import commands

from bot import constants, database
from bot.views.suggestions import SuggestionModal

class SubscriptionManager:
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def handle_interaction(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        message = await interaction.original_response()

        if not self.bot.is_ready:
            await interaction.edit_original_response(
                embed=constants.common_error_embed(
                    "Festival Tracker is not ready yet. Please try again in a moment."
                )
            )
            return

        view = SubscriptionManagerView(self.bot, message, interaction.user)
        await view.render()


# ---------------------------------------------------------------------------
# Single-view implementation
# ---------------------------------------------------------------------------

class SubscriptionManagerView(discord.ui.View):
    """
    One view to rule them all.

    Pages
    -----
    home                  - landing; choose server or user subscription
    server                - list subscribed channels; add / unsubscribe server
    server_add            - pick a channel to subscribe
    server_channel_setup  - pick events + roles for a new channel
    server_channel_confirm- confirm and finish (includes Test button)
    server_channel_manage - manage an existing subscribed channel
    user                  - manage personal subscription events
    """

    TIMEOUT = 180  # seconds

    def __init__(
        self,
        bot: commands.Bot,
        message: discord.Message,
        user: discord.User | discord.Member,
    ):
        super().__init__(timeout=self.TIMEOUT)

        self.bot = bot
        self.message = message
        self.user = user

        # Navigation state
        self._page: str = "home"

        # Server-flow state
        self._target_channel: discord.TextChannel | None = None
        self._pending_events: list[str] = ["announcements"]
        self._pending_roles: list[discord.Role] = []
        self._test_sent: bool = False

    # ------------------------------------------------------------------
    # Core renderer – clears items and rebuilds for the current page
    # ------------------------------------------------------------------

    async def render(self):
        """Clear all children and render items for self._page, then edit the message."""
        self.clear_items()

        match self._page:
            case "home":
                embed, content = await self._build_home()
            case "server":
                embed, content = await self._build_server()
            case "server_add":
                embed, content = await self._build_server_add()
            case "server_channel_setup":
                embed, content = await self._build_server_channel_setup()
            case "server_channel_confirm":
                embed, content = await self._build_server_channel_confirm()
            case "server_channel_manage":
                embed, content = await self._build_server_channel_manage()
            case "user":
                embed, content = await self._build_user()
            case _:
                embed = constants.common_error_embed("Unknown page. Please run the command again.")
                content = {}

        await self.message.edit(embed=embed, view=self, **content)

    # ------------------------------------------------------------------
    # Timeout handler
    # ------------------------------------------------------------------

    async def on_timeout(self):
        try:
            for child in self.children:
                child.disabled = True
            await self.message.edit(view=self)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Helper: navigation shortcut
    # ------------------------------------------------------------------

    def _nav_button(self, label: str, page: str, row: int = 0, emoji=None, style=discord.ButtonStyle.secondary):
        """Create and add a button that navigates to *page* when clicked."""
        btn = discord.ui.Button(label=label, style=style, emoji=emoji, row=row)

        async def _cb(interaction: discord.Interaction):
            self._page = page
            await interaction.response.defer()
            await self.render()

        btn.callback = _cb
        self.add_item(btn)

    # ------------------------------------------------------------------
    # Page: home
    # ------------------------------------------------------------------

    async def _build_home(self):
        embed = discord.Embed(
            title="Subscription Manager",
            description="Manage your subscriptions to Festival Tracker.",
            colour=constants.ACCENT_COLOUR,
        )
        embed.add_field(
            name="",
            value="Select the type of subscription to manage.",
            inline=False,
        )

        # ── Server Subscriptions button ──────────────────────────────
        server_btn = discord.ui.Button(
            label="Server Subscriptions",
            style=discord.ButtonStyle.primary,
            emoji="🧑‍🤝‍🧑",
            row=0,
        )

        async def _server_cb(interaction: discord.Interaction):
            guild = self.message.guild
            if not guild:
                await interaction.response.send_message(
                    embed=constants.common_error_embed("You are not in a server!"),
                    ephemeral=True,
                )
                return

            try:
                member = await guild.fetch_member(interaction.user.id)
            except discord.HTTPException:
                member = None

            if not member:
                await interaction.response.send_message(
                    embed=constants.common_error_embed(
                        "We are unable to verify your permissions in this server. "
                        "You cannot manage Server Subscriptions right now."
                    ),
                    ephemeral=True,
                )
                return

            is_admin = member.guild_permissions.administrator
            is_owner = member.id in constants.BOT_OWNERS

            if not (is_admin or is_owner):
                await interaction.response.send_message(
                    embed=constants.common_error_embed(
                        "You need **Administrator** permissions to manage server subscriptions."
                    ),
                    ephemeral=True,
                )
                return

            self._page = "server"
            await interaction.response.defer()
            await self.render()

        server_btn.callback = _server_cb
        self.add_item(server_btn)

        # ── My Subscription button ───────────────────────────────────
        user_btn = discord.ui.Button(
            label="My Subscription",
            style=discord.ButtonStyle.primary,
            emoji="🧍",
            row=0,
        )

        async def _user_cb(interaction: discord.Interaction):
            self._page = "user"
            await interaction.response.defer()
            await self.render()

        user_btn.callback = _user_cb
        self.add_item(user_btn)

        # ── Problems button ──────────────────────────────────────────
        problems_btn = discord.ui.Button(
            label="Problems / Concerns?",
            emoji=constants.ERROR_EMOJI,
            style=discord.ButtonStyle.secondary,
            row=1,
        )

        async def _problems_cb(interaction: discord.Interaction):
            await interaction.response.send_modal(SuggestionModal(self.bot))

        problems_btn.callback = _problems_cb
        self.add_item(problems_btn)

        return embed, {}

    # ------------------------------------------------------------------
    # Page: server
    # ------------------------------------------------------------------

    async def _build_server(self):
        guild = self.message.guild
        embed = discord.Embed(
            title="Server Subscriptions",
            description=f"Manage the subscriptions for **{guild.name if guild else 'this server'}**",
            colour=constants.ACCENT_COLOUR,
        )

        channels_subscribed: List[database.SubscriptionChannel] = (
            await self.bot.config.subscription_guild("get_channels", guild=guild)
        )

        # Build channel list text
        channel_lines: list[str] = []
        for sub_ch in channels_subscribed:
            resolved = self.bot.get_channel(sub_ch.id)
            if resolved:
                channel_lines.append(f"<#{resolved.id}>")
            else:
                channel_lines.append(f"*(deleted channel {sub_ch.id})*")

        embed.add_field(
            name="Subscribed Channels",
            value="\n".join(channel_lines) if channel_lines else "*No channels subscribed yet.*",
            inline=False,
        )
        embed.add_field(
            name="Manage",
            value="Pick a channel from the dropdown to manage it, or use the buttons below.",
            inline=False,
        )

        # ── Back ────────────────────────────────────────────────────
        self._nav_button("Back", "home", row=0, emoji=constants.PREVIOUS_EMOJI)

        # ── Add New ─────────────────────────────────────────────────
        add_btn = discord.ui.Button(
            label="Add New",
            style=discord.ButtonStyle.success,
            emoji="➕",
            row=0,
        )

        async def _add_cb(interaction: discord.Interaction):
            self._page = "server_add"
            await interaction.response.defer()
            await self.render()

        add_btn.callback = _add_cb
        self.add_item(add_btn)

        # ── Unsubscribe Server ───────────────────────────────────────
        unsub_btn = discord.ui.Button(
            label="Unsubscribe Server",
            style=discord.ButtonStyle.danger,
            row=0,
        )

        async def _unsub_cb(interaction: discord.Interaction):
            await interaction.response.defer()
            await constants.msg_log(self.bot, f"Guild {interaction.guild.id} unsubscribed")
            await self.bot.config.subscription_guild("remove", guild=interaction.guild)
            await self.render()

        unsub_btn.callback = _unsub_cb
        self.add_item(unsub_btn)

        # ── Channel management dropdown ──────────────────────────────
        if channels_subscribed:
            options = []
            for sub_ch in channels_subscribed:
                resolved = self.bot.get_channel(sub_ch.id)
                if resolved:
                    options.append(discord.SelectOption(label=f"#{resolved.name}", value=str(sub_ch.id)))
                else:
                    options.append(
                        discord.SelectOption(
                            label=f"Deleted channel ({sub_ch.id})",
                            value=str(sub_ch.id),
                        )
                    )

            select = discord.ui.Select(
                placeholder="Manage a subscribed channel...",
                min_values=1,
                max_values=1,
                options=options,
                row=1,
            )

            async def _manage_select_cb(interaction: discord.Interaction):
                channel_id = int(select.values[0])
                channel = self.bot.get_channel(channel_id)
                if not channel:
                    await interaction.response.send_message(
                        embed=constants.common_error_embed(
                            "That channel no longer exists. It may have been deleted."
                        ),
                        ephemeral=True,
                    )
                    return
                self._target_channel = channel
                self._page = "server_channel_manage"
                await interaction.response.defer()
                await self.render()

            select.callback = _manage_select_cb
            self.add_item(select)

        return embed, {}

    # ------------------------------------------------------------------
    # Page: server_add
    # ------------------------------------------------------------------

    async def _build_server_add(self):
        guild = self.message.guild
        embed = discord.Embed(
            title="Server Subscriptions: Add New",
            description="Subscribe a channel to Festival Tracker.",
            colour=constants.ACCENT_COLOUR,
        )
        embed.add_field(
            name="Enter Channel ID",
            value=(
                "Click **Enter Channel ID** and paste the channel's ID.\n"
                "To copy a channel ID: right-click the channel then **Copy Channel ID** "
                "(Developer Mode must be on in Discord settings)."
            ),
            inline=False,
        )
        embed.add_field(
            name="Required Permissions",
            value="- View Channel\n- Send Messages\n- Embed Links\n- Attach Files",
            inline=False,
        )
        embed.add_field(name="Supported Channels", value="Text Channels, Announcement Channels", inline=False)

        # ── Back ────────────────────────────────────────────────────
        self._nav_button("Back", "server", row=0, emoji=constants.PREVIOUS_EMOJI)

        # ── Load already-subscribed IDs for validation ────────────────
        channels_subscribed: List[database.SubscriptionChannel] = (
            await self.bot.config.subscription_guild("get_channels", guild=guild)
        )
        already_subbed_ids = {sub_ch.id for sub_ch in channels_subscribed}

        # ── "Enter Channel ID" button → opens Modal ───────────────────
        enter_btn = discord.ui.Button(
            label="Enter Channel ID",
            style=discord.ButtonStyle.primary,
            emoji="🔍",
            row=0,
        )

        # Capture already_subbed_ids and guild in closure
        _already_subbed = already_subbed_ids
        _guild = guild
        _view = self

        class ChannelIDModal(discord.ui.Modal, title="Subscribe a Channel"):
            channel_id_input = discord.ui.TextInput(
                label="Channel ID",
                placeholder="e.g. 123456789012345678",
                min_length=17,
                max_length=20,
                required=True,
            )

            async def on_submit(self_modal, interaction: discord.Interaction):
                raw = self_modal.channel_id_input.value.strip()

                # Must be numeric
                if not raw.isdigit():
                    await interaction.response.send_message(
                        embed=constants.common_error_embed(
                            f"`{raw}` is not a valid channel ID. IDs are numbers only."
                        ),
                        ephemeral=True,
                    )
                    return

                cid = int(raw)

                # Resolve channel from bot cache
                channel = _view.bot.get_channel(cid)
                if not channel:
                    await interaction.response.send_message(
                        embed=constants.common_error_embed(
                            f"Channel `{cid}` could not be found. "
                            "Make sure I am a member of that server and the ID is correct."
                        ),
                        ephemeral=True,
                    )
                    return

                # Must be in this guild
                if not hasattr(channel, 'guild') or channel.guild.id != _guild.id:
                    await interaction.response.send_message(
                        embed=constants.common_error_embed(
                            "That channel is not in this server."
                        ),
                        ephemeral=True,
                    )
                    return

                # Must be text or news
                if channel.type not in (discord.ChannelType.text, discord.ChannelType.news):
                    await interaction.response.send_message(
                        embed=constants.common_error_embed(
                            "Only Text Channels and Announcement Channels can be subscribed."
                        ),
                        ephemeral=True,
                    )
                    return

                # Must not already be subscribed
                if cid in _already_subbed:
                    await interaction.response.send_message(
                        embed=constants.common_error_embed(
                            f"{channel.mention} is already subscribed to Festival Tracker."
                        ),
                        ephemeral=True,
                    )
                    return

                # Check bot permissions
                me = _guild.me
                perms: discord.Permissions = channel.permissions_for(me)
                missing = []
                if not perms.view_channel:   missing.append("View Channel")
                if not perms.send_messages:  missing.append("Send Messages")
                if not perms.embed_links:    missing.append("Embed Links")
                if not perms.attach_files:   missing.append("Attach Files")

                if missing:
                    await interaction.response.send_message(
                        embed=constants.common_error_embed(
                            f"I am missing the following permissions in {channel.mention}:\n"
                            + "\n".join(f"- {p}" for p in missing)
                        ),
                        ephemeral=True,
                    )
                    return

                # All checks passed — proceed to setup
                _view._target_channel = channel
                _view._pending_events = ["announcements"]
                _view._pending_roles = []
                _view._test_sent = False
                _view._page = "server_channel_setup"
                await interaction.response.defer()
                await _view.render()

        async def _enter_btn_cb(interaction: discord.Interaction):
            await interaction.response.send_modal(ChannelIDModal())

        enter_btn.callback = _enter_btn_cb
        self.add_item(enter_btn)

        return embed, {}

    # ------------------------------------------------------------------
    # Page: server_channel_setup
    # ------------------------------------------------------------------

    async def _build_server_channel_setup(self):
        channel = self._target_channel
        embed = discord.Embed(
            title="Server Subscriptions: Channel Setup",
            description=f"Configuring {channel.mention if channel else '*(unknown channel)*'}",
            colour=constants.ACCENT_COLOUR,
        )
        embed.add_field(
            name="Subscription Events",
            value="Choose which events to receive in this channel. Changes are saved when you click **Next**.",
            inline=False,
        )
        embed.add_field(
            name="Role Mentions",
            value="Optionally select roles to ping when a message is sent.",
            inline=False,
        )

        # ── Back ────────────────────────────────────────────────────
        self._nav_button("Back", "server_add", row=0, emoji=constants.PREVIOUS_EMOJI)

        # ── Next button ──────────────────────────────────────────────
        next_btn = discord.ui.Button(
            label="Next",
            style=discord.ButtonStyle.primary,
            emoji=constants.NEXT_EMOJI,
            row=0,
        )

        async def _next_cb(interaction: discord.Interaction):
            if not self._pending_events:
                await interaction.response.send_message(
                    embed=constants.common_error_embed(
                        "Please select at least one subscription event before continuing."
                    ),
                    ephemeral=True,
                )
                return
            # Save subscription to DB upon clicking Next
            if self._target_channel:
                await constants.msg_log(self.bot, f"Channel {self._target_channel.id} subscribed")
                await self.bot.config._channel_add(
                    self._target_channel,
                    self._pending_events,
                    [str(r.id) for r in self._pending_roles],
                )
            self._page = "server_channel_confirm"
            self._test_sent = False
            await interaction.response.defer()
            await self.render()

        next_btn.callback = _next_cb
        self.add_item(next_btn)

        # ── Events select ────────────────────────────────────────────
        all_events = database.JamTrackEvents.get_all_events()
        event_options = [
            discord.SelectOption(
                label=ev.value.english,
                description=ev.value.desc,
                value=ev.value.id,
                default=(ev.value.id in self._pending_events),
            )
            for ev in all_events
        ]

        events_select = discord.ui.Select(
            placeholder="Select subscription events...",
            min_values=1,
            max_values=len(event_options),
            options=event_options,
            row=1,
        )

        async def _events_cb(interaction: discord.Interaction):
            self._pending_events = list(events_select.values)
            await interaction.response.defer()
            await self.render()

        events_select.callback = _events_cb
        self.add_item(events_select)

        # ── Roles select (RoleSelect handles all server roles natively) ──
        role_select = discord.ui.RoleSelect(
            placeholder="Select roles to mention (optional)...",
            min_values=0,
            max_values=25,
            default_values=self._pending_roles,
            row=2,
        )

        async def _roles_cb(interaction: discord.Interaction):
            self._pending_roles = list(role_select.values)
            await interaction.response.defer()
            await self.render()

        role_select.callback = _roles_cb
        self.add_item(role_select)

        return embed, {}

    # ------------------------------------------------------------------
    # Page: server_channel_confirm
    # ------------------------------------------------------------------

    async def _build_server_channel_confirm(self):
        channel = self._target_channel

        event_names = [
            database.JamTrackEvents.get_name(e) for e in self._pending_events
        ]
        # _pending_roles now holds discord.Role objects from RoleSelect
        role_mentions = [role.mention for role in self._pending_roles]

        embed = discord.Embed(
            title="Server Subscriptions: Done!",
            description=f"{channel.mention if channel else '*(unknown)*'} has been subscribed successfully. ✅",
            colour=constants.ACCENT_COLOUR,
        )
        embed.add_field(name="Events", value=", ".join(event_names) or "*(none)*", inline=True)
        embed.add_field(
            name="Role Mentions",
            value=", ".join(role_mentions) if role_mentions else "*(none)*",
            inline=True,
        )

        # ── Test button ──────────────────────────────────────────────
        test_btn = discord.ui.Button(
            label="Send Test Message",
            style=discord.ButtonStyle.secondary,
            disabled=self._test_sent,
            row=0,
        )

        async def _test_cb(interaction: discord.Interaction):
            if channel:
                try:
                    await channel.send(
                        "This channel is now subscribed to Festival Tracker.\n*This is a test message.*"
                    )
                    self._test_sent = True
                    await interaction.response.defer()
                    await self.render()
                except discord.Forbidden:
                    await interaction.response.send_message(
                        embed=constants.common_error_embed(
                            f"I don't have permission to send messages in {channel.mention}."
                        ),
                        ephemeral=True,
                    )
            else:
                await interaction.response.send_message(
                    embed=constants.common_error_embed("Channel not found."), ephemeral=True
                )

        test_btn.callback = _test_cb
        self.add_item(test_btn)

        # ── Finish button ────────────────────────────────────────────
        finish_btn = discord.ui.Button(
            label="Back to Server Subscriptions",
            style=discord.ButtonStyle.primary,
            emoji=constants.PREVIOUS_EMOJI,
            row=0,
        )

        async def _finish_cb(interaction: discord.Interaction):
            self._page = "server"
            self._target_channel = None
            await interaction.response.defer()
            await self.render()

        finish_btn.callback = _finish_cb
        self.add_item(finish_btn)

        return embed, {}

    # ------------------------------------------------------------------
    # Page: server_channel_manage
    # ------------------------------------------------------------------

    async def _build_server_channel_manage(self):
        channel = self._target_channel
        embed = discord.Embed(
            title="Server Subscriptions — Manage Channel",
            description=f"Managing {channel.mention if channel else '*(unknown channel)*'}",
            colour=constants.ACCENT_COLOUR,
        )

        # Load current subscription data
        sub_data: database.SubscriptionChannel | None = await self.bot.config._channel(channel)

        if not sub_data:
            embed.description = f"No subscription found for {channel.mention if channel else 'that channel'}."
            self._nav_button("Back", "server", row=0, emoji=constants.PREVIOUS_EMOJI)
            return embed, {}

        current_event_names = [database.JamTrackEvents.get_name(e) for e in sub_data.events]
        embed.add_field(
            name="Current Events",
            value=", ".join(current_event_names) or "*(none)*",
            inline=False,
        )

        current_roles = []
        for rid in sub_data.roles:
            role = self.message.guild.get_role(rid) if self.message.guild else None
            current_roles.append(role.mention if role else f"*(deleted role {rid})*")
        embed.add_field(
            name="Current Role Mentions",
            value=", ".join(current_roles) if current_roles else "*(none)*",
            inline=False,
        )
        embed.add_field(
            name="",
            value="Changes to the dropdowns below are saved **immediately**.",
            inline=False,
        )

        # ── Back ────────────────────────────────────────────────────
        self._nav_button("Back", "server", row=0, emoji=constants.PREVIOUS_EMOJI)

        # ── Unsubscribe channel ──────────────────────────────────────
        unsub_btn = discord.ui.Button(
            label="Unsubscribe Channel",
            style=discord.ButtonStyle.danger,
            row=0,
        )

        async def _unsub_cb(interaction: discord.Interaction):
            await constants.msg_log(self.bot, f"Channel {channel.id} unsubscribed")
            await self.bot.config._channel_remove(channel)
            self._target_channel = None
            self._page = "server"
            await interaction.response.defer()
            await self.render()

        unsub_btn.callback = _unsub_cb
        self.add_item(unsub_btn)

        # ── Events select ────────────────────────────────────────────
        all_events = database.JamTrackEvents.get_all_events()
        event_options = [
            discord.SelectOption(
                label=ev.value.english,
                description=ev.value.desc,
                value=ev.value.id,
                default=(ev.value.id in sub_data.events),
            )
            for ev in all_events
        ]

        events_select = discord.ui.Select(
            placeholder="Change subscription events...",
            min_values=1,
            max_values=len(event_options),
            options=event_options,
            row=1,
        )

        async def _events_cb(interaction: discord.Interaction):
            new_events = list(events_select.values)
            if not new_events:
                await interaction.response.send_message(
                    embed=constants.common_error_embed("You must keep at least one subscription event selected. To unsubscribe this channel completely, click 'Unsubscribe Channel'."),
                    ephemeral=True,
                )
                return
            await self.bot.config._channel_edit_events(channel, events=new_events)
            await constants.msg_log(self.bot, f"Channel {channel.id} edited feeds to {new_events}")
            await interaction.response.send_message(
                embed=constants.common_success_embed("Event preferences saved."),
                ephemeral=True,
            )
            await self.render()

        events_select.callback = _events_cb
        self.add_item(events_select)

        # ── Roles select (RoleSelect handles all server roles natively) ──
        # Build default_values from stored role IDs as discord.Object snowflakes
        guild = channel.guild if channel else self.message.guild
        default_role_objects = [
            discord.Object(id=rid) for rid in sub_data.roles
            if (guild and guild.get_role(rid)) is not None
        ]

        role_select = discord.ui.RoleSelect(
            placeholder="Change role mentions...",
            min_values=0,
            max_values=25,
            default_values=default_role_objects,
            row=2,
        )

        async def _roles_cb(interaction: discord.Interaction):
            await self.bot.config._channel_edit_roles(
                channel,
                [discord.Object(id=r.id) for r in role_select.values],
            )
            await interaction.response.send_message(
                embed=constants.common_success_embed("Role preferences saved."),
                ephemeral=True,
            )
            await self.render()

        role_select.callback = _roles_cb
        self.add_item(role_select)

        return embed, {}

    # ------------------------------------------------------------------
    # Page: user
    # ------------------------------------------------------------------

    async def _build_user(self):
        embed = discord.Embed(
            title="My Subscription",
            description="Manage your personal Festival Tracker subscription.",
            colour=constants.ACCENT_COLOUR,
        )
        embed.add_field(
            name="How it works",
            value="Select the Jam Track events you want to be notified about via DM.",
            inline=False,
        )
        embed.add_field(
            name="Requirement",
            value="You must share at least one mutual server with Festival Tracker to receive DMs.",
            inline=False,
        )

        # ── Back ────────────────────────────────────────────────────
        self._nav_button("Back", "home", row=0, emoji=constants.PREVIOUS_EMOJI)

        # Load current user subscription
        sub_user: database.SubscriptionUser | None = await self.bot.config.subscription_user(
            "get", user=self.user
        )

        all_events = database.JamTrackEvents.get_all_events()
        subscribed_event_ids = set(sub_user.events) if sub_user else set()

        event_options = [
            discord.SelectOption(
                label=ev.value.english,
                description=ev.value.desc,
                value=ev.value.id,
                default=(ev.value.id in subscribed_event_ids),
            )
            for ev in all_events
        ]

        user_select = discord.ui.Select(
            placeholder="Select your subscription events...",
            min_values=0,
            max_values=len(event_options),
            options=event_options,
            row=1,
        )

        async def _user_select_cb(interaction: discord.Interaction):
            chosen_events = list(user_select.values)
            await self.bot.config.subscription_user("edit", user=interaction.user, events=chosen_events)

            if not sub_user:
                msg = "You have been subscribed. Changes saved!"
                await constants.msg_log(self.bot, f"User {interaction.user.id} subscribed")
            elif not chosen_events:
                msg = "You have been unsubscribed. Changes saved!"
                await constants.msg_log(self.bot, f"User {interaction.user.id} unsubscribed")
            else:
                msg = "Changes saved successfully."

            await constants.msg_log(self.bot, f"User {interaction.user.id} edited feeds to {chosen_events}")

            await interaction.response.send_message(
                embed=constants.common_success_embed(msg),
                ephemeral=True,
            )
            # Re-render so default selections reflect the new state
            await self.render()

        user_select.callback = _user_select_cb
        self.add_item(user_select)

        return embed, {}