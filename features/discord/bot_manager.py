#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Discord bot manager for DST Fish Manager."""

import asyncio
import os
from typing import Optional, Dict, Any
from enum import Enum

import discord
from discord import app_commands
from discord.ext import commands, tasks

from utils.logger import discord_logger


class ServerState(Enum):
    """Server state enumeration."""
    STARTING = 1
    RUNNING = 2
    STOPPING = 3
    STOPPED = 4
    RESTARTING = 5


class DiscordBotManager:
    """Manages Discord bot integration with DST Fish Manager."""

    def __init__(self, manager_service, event_bus=None):
        """
        Initialize Discord bot manager.

        Args:
            manager_service: The main manager service instance
            event_bus: Optional event bus for chat message subscription
        """
        self.manager_service = manager_service
        self.event_bus = event_bus

        # Bot configuration
        self.bot_token = os.getenv("DISCORD_BOT_TOKEN")
        self.guild_id = os.getenv("DISCORD_GUILD_ID")
        self.chat_channel_id = os.getenv("DISCORD_CHAT_CHANNEL_ID")

        discord_logger.info("Initializing Discord bot manager")

        if not self.bot_token:
            discord_logger.error("DISCORD_BOT_TOKEN environment variable not set")
            raise ValueError("DISCORD_BOT_TOKEN environment variable not set")

        if self.guild_id:
            discord_logger.info(f"Configured for guild ID: {self.guild_id}")
        if self.chat_channel_id:
            discord_logger.info(f"Chat relay channel ID: {self.chat_channel_id}")

        # Bot state
        self.server_state = ServerState.STOPPED
        self.previous_chat_messages = []
        self.chat_event_subscription_id = None

        # Initialize Discord client
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True

        self.client = DiscordClient(self, intents=intents)
        self.tree = app_commands.CommandTree(self.client)

        # Setup commands
        self._setup_commands()

        # Setup error handler for app commands
        self.tree.error(self._on_app_command_error)

    def _setup_commands(self):
        """Setup Discord slash commands."""
        discord_logger.info("Setting up Discord slash commands")
        guild = discord.Object(id=int(self.guild_id)) if self.guild_id else None
        discord_logger.info(f"Commands will be registered to: {'guild ' + self.guild_id if guild else 'globally'}")

        @self.tree.command(
            name="panel",
            description="Opens the server control panel.",
            guild=guild
        )
        async def panel(interaction: discord.Interaction):
            discord_logger.info(f"User {interaction.user} opened the panel")
            await interaction.response.send_message(view=PanelMenu(self))

        @self.tree.command(
            name="status",
            description="Gets the server status.",
            guild=guild
        )
        async def status(interaction: discord.Interaction):
            discord_logger.info(f"User {interaction.user} requested server status")
            await interaction.response.defer(ephemeral=True)

            shards = self.manager_service.get_shards()
            status_lines = ["**Server Status:**\n"]

            for shard in shards:
                emoji = "🟢" if shard.is_running else "🔴"
                status_lines.append(f"{emoji} **{shard.name}**: {shard.status}")

            discord_logger.info(f"Sending status for {len(shards)} shards")
            await interaction.followup.send("\n".join(status_lines), ephemeral=True)

        @self.tree.command(
            name="announce",
            description="Send an announcement to the server.",
            guild=guild
        )
        async def announce(interaction: discord.Interaction, message: str, shard: str = "Master"):
            discord_logger.info(f"User {interaction.user} sending announcement to {shard}: {message}")
            await interaction.response.defer(ephemeral=True)

            success, result = self.manager_service.send_chat_message(shard, f"[Discord] {message}")

            if success:
                discord_logger.info(f"Announcement sent successfully to {shard}")
                await interaction.followup.send(f"Announcement sent to {shard}!", ephemeral=True)
            else:
                discord_logger.error(f"Failed to send announcement to {shard}: {result}")
                await interaction.followup.send(f"Failed to send announcement: {result}", ephemeral=True)

        @self.tree.command(
            name="players",
            description="List players on the server.",
            guild=guild
        )
        async def players(interaction: discord.Interaction):
            discord_logger.info(f"User {interaction.user} requested player list")
            await interaction.response.defer(ephemeral=True)

            # Request status update first
            self.manager_service.request_status_update()
            await asyncio.sleep(2)  # Wait for status update

            status = self.manager_service.get_server_status()

            if status and "players" in status:
                player_list = status["players"]
                if player_list:
                    discord_logger.info(f"Found {len(player_list)} players online")
                    players_text = "\n".join([f"• {p}" for p in player_list])
                    await interaction.followup.send(f"**Players Online:**\n{players_text}", ephemeral=True)
                else:
                    discord_logger.info("No players currently online")
                    await interaction.followup.send("No players online.", ephemeral=True)
            else:
                discord_logger.warning("Could not retrieve player list from server")
                await interaction.followup.send("Could not retrieve player list.", ephemeral=True)

        discord_logger.info(f"Registered {len(self.tree.get_commands(guild=guild))} commands: {', '.join([cmd.name for cmd in self.tree.get_commands(guild=guild)])}")

    async def start(self):
        """Start the Discord bot."""
        try:
            discord_logger.info("Starting Discord bot connection")
            await self.client.start(self.bot_token)
        except Exception as e:
            discord_logger.error(f"Failed to start Discord bot: {e}")
            raise

    async def stop(self):
        """Stop the Discord bot."""
        discord_logger.info("Stopping Discord bot")
        # Unsubscribe from chat events
        if self.event_bus and self.chat_event_subscription_id:
            from core.events.bus import EventType
            self.event_bus.unsubscribe(EventType.CHAT_MESSAGE, self.chat_event_subscription_id)
        await self.client.close()

    def set_event_bus(self, event_bus):
        """Set the event bus and subscribe to chat events."""
        self.event_bus = event_bus
        if event_bus:
            from core.events.bus import EventType
            self.chat_event_subscription_id = event_bus.subscribe(EventType.CHAT_MESSAGE, self._on_chat_message_event)
            discord_logger.info("Subscribed to CHAT_MESSAGE events from TUI")

    def _on_chat_message_event(self, event):
        """Handle chat message events from the TUI's background coordinator."""
        if not self.chat_channel_id:
            return

        try:
            chat_logs = event.data
            if not chat_logs or len(chat_logs) < 2:
                return

            # Find new messages by comparing to previous state
            new_messages = []
            for msg in chat_logs:
                if msg not in self.previous_chat_messages:
                    # Filter out Discord messages to prevent echo loop
                    if not msg.startswith("[Discord]"):
                        new_messages.append(msg)

            if new_messages:
                discord_logger.info(f"Detected {len(new_messages)} new game chat message(s) to relay")
                # Schedule async send in the bot's event loop
                if self.client and self.client.is_ready():
                    import asyncio
                    asyncio.run_coroutine_threadsafe(
                        self._send_chat_to_discord(new_messages),
                        self.client.loop
                    )

            # Update previous messages (keep last 100)
            self.previous_chat_messages = chat_logs[-100:]

        except Exception as e:
            discord_logger.error(f"Error handling chat message event: {e}")

    async def _send_chat_to_discord(self, messages):
        """Send game chat messages to Discord channel."""
        try:
            channel = self.client.get_channel(int(self.chat_channel_id))
            if not channel:
                discord_logger.warning(f"Could not find Discord channel {self.chat_channel_id}")
                return

            for msg in messages:
                if msg.strip():
                    await channel.send(msg)
                    discord_logger.info(f"Sent game chat to Discord: {msg}")

        except Exception as e:
            discord_logger.error(f"Error sending chat to Discord: {e}")

    async def _on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Handle app command errors."""
        discord_logger.error(f"App command error from {interaction.user} in command '{interaction.command.name if interaction.command else 'unknown'}': {error}")
        try:
            if interaction.response.is_done():
                await interaction.followup.send(f"An error occurred: {str(error)}", ephemeral=True)
            else:
                await interaction.response.send_message(f"An error occurred: {str(error)}", ephemeral=True)
        except Exception as e:
            discord_logger.error(f"Failed to send error message: {e}")

    def run_in_background(self):
        """Run the Discord bot in a background thread."""
        discord_logger.info("Running Discord bot in background thread")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.start())
        except Exception as e:
            discord_logger.error(f"Error in Discord bot background thread: {e}")
        finally:
            loop.close()


class DiscordClient(discord.Client):
    """Custom Discord client."""

    def __init__(self, bot_manager: DiscordBotManager, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot_manager = bot_manager
        self.synced = False
        self.added = False

    async def on_ready(self):
        """Handle bot ready event."""
        discord_logger.info(f"Discord bot logged in as {self.user.name} (ID: {self.user.id})")

        try:
            if self.bot_manager.guild_id:
                discord_logger.info(f"Syncing commands to guild {self.bot_manager.guild_id}")
                synced = await self.bot_manager.tree.sync(guild=discord.Object(id=int(self.bot_manager.guild_id)))
                discord_logger.info(f"Synced {len(synced)} command(s) to guild: {[cmd.name for cmd in synced]}")
            else:
                discord_logger.info("Syncing commands globally (this may take up to 1 hour to appear)")
                synced = await self.bot_manager.tree.sync()
                discord_logger.info(f"Synced {len(synced)} command(s) globally: {[cmd.name for cmd in synced]}")

            self.synced = True
            discord_logger.info(f"Commands synced successfully. Bot is ready to receive interactions in guild {self.bot_manager.guild_id if self.bot_manager.guild_id else 'all guilds'}")
        except Exception as e:
            discord_logger.error(f"Failed to sync commands: {e}", exc_info=True)

        if not self.added:
            self.add_view(PanelMenu(self.bot_manager))
            self.added = True
            discord_logger.info("Panel menu view added")

        await self.change_presence(
            activity=discord.Activity(
                name="DST Server",
                type=discord.ActivityType.watching
            )
        )

        # Update server state based on actual running shards
        shards = self.bot_manager.manager_service.get_shards()
        running_shards = [s for s in shards if s.is_running]
        if running_shards:
            self.bot_manager.server_state = ServerState.RUNNING
            discord_logger.info(f"Server state set to RUNNING ({len(running_shards)} shard(s) active)")
        else:
            discord_logger.info("Server state remains STOPPED (no running shards)")

        # Chat relay is handled by event subscription from TUI
        if self.bot_manager.event_bus:
            discord_logger.info("Chat relay configured via event bus subscription")
        else:
            discord_logger.warning("Event bus not available - chat relay to Discord will not work until TUI connects it")

    async def on_command_error(self, interaction: discord.Interaction, error: Exception):
        """Handle command errors."""
        discord_logger.error(f"Command error from {interaction.user}: {error}")
        try:
            if interaction.response.is_done():
                await interaction.followup.send(f"Error: {error}", ephemeral=True)
            else:
                await interaction.response.send_message(f"Error: {error}", ephemeral=True)
        except:
            pass

    async def on_interaction(self, interaction: discord.Interaction):
        """Handle all interactions for debugging."""
        try:
            command_name = interaction.command.name if interaction.command else 'N/A'
            discord_logger.info(f"Received interaction from {interaction.user} (ID: {interaction.user.id}): type={interaction.type}, command={command_name}, guild={interaction.guild_id}")
        except Exception as e:
            discord_logger.error(f"Error logging interaction: {e}")

    async def on_message(self, message):
        """Handle incoming messages."""
        if message.author == self.user:
            return

        # Relay Discord messages to game server
        if (self.bot_manager.chat_channel_id and
            message.channel.id == int(self.bot_manager.chat_channel_id)):

            discord_logger.info(f"Message received in chat channel from {message.author.display_name}, server_state={self.bot_manager.server_state.name}")

            if self.bot_manager.server_state == ServerState.STOPPED:
                discord_logger.warning("Skipping message relay - server is stopped")
                return

            # Remove emojis and format message
            msg = message.content
            full_message = f"[Discord] {message.author.display_name}: {msg}"

            discord_logger.info(f"Relaying Discord message from {message.author.display_name}: {msg}")

            # Send to all running shards
            shards = self.bot_manager.manager_service.get_shards()
            relay_count = 0
            for shard in shards:
                if shard.is_running:
                    self.bot_manager.manager_service.send_chat_message(shard.name, full_message)
                    relay_count += 1

            discord_logger.info(f"Message relayed to {relay_count} running shard(s)")




class PanelMenu(discord.ui.View):
    """Discord UI panel for server control."""

    def __init__(self, bot_manager: DiscordBotManager):
        super().__init__(timeout=None)
        self.bot_manager = bot_manager
        self.cooldown = commands.CooldownMapping.from_cooldown(
            1, 5, commands.BucketType.default
        )

    @discord.ui.button(
        label="Start Server",
        style=discord.ButtonStyle.success,
        custom_id="start",
        emoji="🟢"
    )
    async def start_server(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Start the server."""
        bucket = self.cooldown.get_bucket(interaction.message)
        retry = bucket.update_rate_limit()
        if retry:
            return await interaction.response.send_message(
                "ERROR: Please do not spam commands.", ephemeral=True
            )

        discord_logger.info(f"User {interaction.user} initiated server start")
        await interaction.response.defer(ephemeral=True)

        shards = self.bot_manager.manager_service.get_shards()
        success, stdout, stderr = self.bot_manager.manager_service.control_all_shards("start", shards)

        if success:
            discord_logger.info("Server startup command executed successfully")
            await interaction.followup.send("Server startup initiated...", ephemeral=True)
            self.bot_manager.server_state = ServerState.RUNNING
            self.bot_manager.just_started = True
            self.bot_manager.previous_chat_log_count = 0
        else:
            discord_logger.error(f"Server startup failed: {stderr}")
            await interaction.followup.send(f"Failed to start server: {stderr}", ephemeral=True)

    @discord.ui.button(
        label="Stop Server",
        style=discord.ButtonStyle.danger,
        custom_id="stop",
        emoji="🔴"
    )
    async def stop_server(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Stop the server."""
        bucket = self.cooldown.get_bucket(interaction.message)
        retry = bucket.update_rate_limit()
        if retry:
            return await interaction.response.send_message(
                "ERROR: Please do not spam commands.", ephemeral=True
            )

        discord_logger.info(f"User {interaction.user} initiated server stop")
        await interaction.response.defer(ephemeral=True)

        # Announce shutdown
        discord_logger.info("Announcing server shutdown to players")
        self.bot_manager.manager_service.send_chat_message(
            "Master", "[Discord] Server is shutting down in 5 seconds."
        )
        await asyncio.sleep(5)

        self.bot_manager.server_state = ServerState.STOPPING

        shards = self.bot_manager.manager_service.get_shards()
        success, stdout, stderr = self.bot_manager.manager_service.control_all_shards("stop", shards)

        if success:
            discord_logger.info("Server shutdown command executed successfully")
            await interaction.followup.send("Server shutdown initiated...", ephemeral=True)
            self.bot_manager.server_state = ServerState.STOPPED
        else:
            discord_logger.error(f"Server shutdown failed: {stderr}")
            await interaction.followup.send(f"Failed to stop server: {stderr}", ephemeral=True)

    @discord.ui.button(
        label="Restart Server",
        style=discord.ButtonStyle.blurple,
        custom_id="restart",
        emoji="🔄"
    )
    async def restart_server(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Restart the server."""
        bucket = self.cooldown.get_bucket(interaction.message)
        retry = bucket.update_rate_limit()
        if retry:
            return await interaction.response.send_message(
                "ERROR: Please do not spam commands.", ephemeral=True
            )

        discord_logger.info(f"User {interaction.user} initiated server restart")
        await interaction.response.defer(ephemeral=True)

        # Announce restart
        discord_logger.info("Announcing server restart to players")
        self.bot_manager.manager_service.send_chat_message(
            "Master", "[Discord] Server is restarting in 5 seconds."
        )
        await asyncio.sleep(5)

        self.bot_manager.server_state = ServerState.RESTARTING

        shards = self.bot_manager.manager_service.get_shards()
        success, stdout, stderr = self.bot_manager.manager_service.control_all_shards("restart", shards)

        if success:
            discord_logger.info("Server restart command executed successfully")
            await interaction.followup.send("Server restart initiated...", ephemeral=True)
            await asyncio.sleep(30)
            self.bot_manager.server_state = ServerState.RUNNING
            self.bot_manager.just_started = True
            self.bot_manager.previous_chat_log_count = 0
        else:
            discord_logger.error(f"Server restart failed: {stderr}")
            await interaction.followup.send(f"Failed to restart server: {stderr}", ephemeral=True)

    @discord.ui.button(
        label="Update Server",
        style=discord.ButtonStyle.grey,
        custom_id="update",
        emoji="⬇️"
    )
    async def update_server(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Update the server."""
        bucket = self.cooldown.get_bucket(interaction.message)
        retry = bucket.update_rate_limit()
        if retry:
            return await interaction.response.send_message(
                "ERROR: Please do not spam commands.", ephemeral=True
            )

        discord_logger.info(f"User {interaction.user} initiated server update")
        await interaction.response.defer(ephemeral=True)

        await interaction.followup.send("Starting server update...", ephemeral=True)

        # Run updater
        success, stdout, stderr = self.bot_manager.manager_service.run_updater()

        if success:
            discord_logger.info("Server update completed successfully")
            await interaction.followup.send("Server updated successfully!", ephemeral=True)
        else:
            discord_logger.error(f"Server update failed: {stderr}")
            await interaction.followup.send(f"Update failed: {stderr}", ephemeral=True)
