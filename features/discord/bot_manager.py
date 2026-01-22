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


class ServerState(Enum):
    """Server state enumeration."""
    STARTING = 1
    RUNNING = 2
    STOPPING = 3
    STOPPED = 4
    RESTARTING = 5


class DiscordBotManager:
    """Manages Discord bot integration with DST Fish Manager."""

    def __init__(self, manager_service):
        """
        Initialize Discord bot manager.

        Args:
            manager_service: The main manager service instance
        """
        self.manager_service = manager_service

        # Bot configuration
        self.bot_token = os.getenv("DISCORD_BOT_TOKEN")
        self.guild_id = os.getenv("DISCORD_GUILD_ID")
        self.chat_channel_id = os.getenv("DISCORD_CHAT_CHANNEL_ID")

        if not self.bot_token:
            raise ValueError("DISCORD_BOT_TOKEN environment variable not set")

        # Bot state
        self.server_state = ServerState.STOPPED
        self.previous_chat_log_count = 0
        self.just_started = False

        # Initialize Discord client
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True

        self.client = DiscordClient(self, intents=intents)
        self.tree = app_commands.CommandTree(self.client)

        # Setup commands
        self._setup_commands()

    def _setup_commands(self):
        """Setup Discord slash commands."""
        guild = discord.Object(id=int(self.guild_id)) if self.guild_id else None

        @self.tree.command(
            name="panel",
            description="Opens the server control panel.",
            guild=guild
        )
        async def panel(interaction: discord.Interaction):
            await interaction.response.send_message(view=PanelMenu(self))

        @self.tree.command(
            name="status",
            description="Gets the server status.",
            guild=guild
        )
        async def status(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)

            shards = self.manager_service.get_shards()
            status_lines = ["**Server Status:**\n"]

            for shard in shards:
                emoji = "🟢" if shard.is_running else "🔴"
                status_lines.append(f"{emoji} **{shard.name}**: {shard.status}")

            await interaction.followup.send("\n".join(status_lines), ephemeral=True)

        @self.tree.command(
            name="announce",
            description="Send an announcement to the server.",
            guild=guild
        )
        async def announce(interaction: discord.Interaction, message: str, shard: str = "Master"):
            await interaction.response.defer(ephemeral=True)

            success, result = self.manager_service.send_chat_message(shard, f"[Discord] {message}")

            if success:
                await interaction.followup.send(f"Announcement sent to {shard}!", ephemeral=True)
            else:
                await interaction.followup.send(f"Failed to send announcement: {result}", ephemeral=True)

        @self.tree.command(
            name="players",
            description="List players on the server.",
            guild=guild
        )
        async def players(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)

            # Request status update first
            self.manager_service.request_status_update()
            await asyncio.sleep(2)  # Wait for status update

            status = self.manager_service.get_server_status()

            if status and "players" in status:
                player_list = status["players"]
                if player_list:
                    players_text = "\n".join([f"• {p}" for p in player_list])
                    await interaction.followup.send(f"**Players Online:**\n{players_text}", ephemeral=True)
                else:
                    await interaction.followup.send("No players online.", ephemeral=True)
            else:
                await interaction.followup.send("Could not retrieve player list.", ephemeral=True)

    async def start(self):
        """Start the Discord bot."""
        try:
            await self.client.start(self.bot_token)
        except Exception as e:
            raise

    async def stop(self):
        """Stop the Discord bot."""
        await self.client.close()

    def run_in_background(self):
        """Run the Discord bot in a background thread."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.start())
        except Exception as e:
            pass
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
        if self.bot_manager.guild_id:
            await self.bot_manager.tree.sync(guild=discord.Object(id=int(self.bot_manager.guild_id)))
        else:
            await self.bot_manager.tree.sync()

        self.synced = True

        if not self.added:
            self.add_view(PanelMenu(self.bot_manager))
            self.added = True

        await self.change_presence(
            activity=discord.Activity(
                name="DST Server",
                type=discord.ActivityType.watching
            )
        )

        # Start chat log monitoring
        if not self.send_chat_log.is_running():
            self.send_chat_log.start()

    async def on_message(self, message):
        """Handle incoming messages."""
        if message.author == self.user:
            return

        # Relay Discord messages to game server
        if (self.bot_manager.chat_channel_id and
            message.channel.id == int(self.bot_manager.chat_channel_id)):

            if self.bot_manager.server_state == ServerState.STOPPED:
                return

            # Remove emojis and format message
            msg = message.content
            full_message = f"[Discord] {message.author.display_name}: {msg}"

            # Send to all running shards
            shards = self.bot_manager.manager_service.get_shards()
            for shard in shards:
                if shard.is_running:
                    self.bot_manager.manager_service.send_chat_message(shard.name, full_message)

    @tasks.loop(seconds=5)
    async def send_chat_log(self):
        """Monitor and relay chat logs to Discord."""
        if not self.bot_manager.chat_channel_id:
            return

        try:
            chat_logs = self.bot_manager.manager_service.get_chat_logs(lines=100)
            current_count = len(chat_logs)

            # Handle initial startup
            if self.bot_manager.just_started:
                if self.bot_manager.previous_chat_log_count - current_count > 25:
                    return
                self.bot_manager.just_started = False

            # Send new messages
            if current_count > self.bot_manager.previous_chat_log_count:
                new_messages = chat_logs[self.bot_manager.previous_chat_log_count:]

                channel = self.get_channel(int(self.bot_manager.chat_channel_id))
                if channel:
                    for msg in new_messages:
                        # Filter out Discord messages and system messages
                        if not msg.startswith("[Discord]") and not msg.startswith("[System Message]"):
                            await channel.send(msg[:2000])  # Discord message limit

                self.bot_manager.previous_chat_log_count = current_count
        except Exception as e:
            pass


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

        await interaction.response.defer(ephemeral=True)

        shards = self.bot_manager.manager_service.get_shards()
        success, stdout, stderr = self.bot_manager.manager_service.control_all_shards("start", shards)

        if success:
            await interaction.followup.send("Server startup initiated...", ephemeral=True)
            self.bot_manager.server_state = ServerState.RUNNING
            self.bot_manager.just_started = True
            self.bot_manager.previous_chat_log_count = 0
        else:
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

        await interaction.response.defer(ephemeral=True)

        # Announce shutdown
        self.bot_manager.manager_service.send_chat_message(
            "Master", "[Discord] Server is shutting down in 5 seconds."
        )
        await asyncio.sleep(5)

        self.bot_manager.server_state = ServerState.STOPPING

        shards = self.bot_manager.manager_service.get_shards()
        success, stdout, stderr = self.bot_manager.manager_service.control_all_shards("stop", shards)

        if success:
            await interaction.followup.send("Server shutdown initiated...", ephemeral=True)
            self.bot_manager.server_state = ServerState.STOPPED
        else:
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

        await interaction.response.defer(ephemeral=True)

        # Announce restart
        self.bot_manager.manager_service.send_chat_message(
            "Master", "[Discord] Server is restarting in 5 seconds."
        )
        await asyncio.sleep(5)

        self.bot_manager.server_state = ServerState.RESTARTING

        shards = self.bot_manager.manager_service.get_shards()
        success, stdout, stderr = self.bot_manager.manager_service.control_all_shards("restart", shards)

        if success:
            await interaction.followup.send("Server restart initiated...", ephemeral=True)
            await asyncio.sleep(30)
            self.bot_manager.server_state = ServerState.RUNNING
            self.bot_manager.just_started = True
            self.bot_manager.previous_chat_log_count = 0
        else:
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

        await interaction.response.defer(ephemeral=True)

        await interaction.followup.send("Starting server update...", ephemeral=True)

        # Run updater
        success, stdout, stderr = self.bot_manager.manager_service.run_updater()

        if success:
            await interaction.followup.send("Server updated successfully!", ephemeral=True)
        else:
            await interaction.followup.send(f"Update failed: {stderr}", ephemeral=True)
