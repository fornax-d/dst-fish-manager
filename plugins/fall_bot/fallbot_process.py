# -*- coding: utf-8 -*-
"""
Isolated fall.bot Process.
This file is imported ONLY by the child process.
"""

import asyncio
import os
import queue
# pylint: disable=import-error
import discord
from discord import app_commands

# Global reference for the client to access queues
BOT_QUEUES = None


class ControlPanel(discord.ui.View):
    """Interactive Control Panel for Server Management."""

    def __init__(self, request_queue):
        super().__init__(timeout=None)
        self.request_queue = request_queue

    @discord.ui.button(label="Start All", style=discord.ButtonStyle.success, emoji="🟢", custom_id="panel_start")
    async def start_server(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle Start All button."""
        # pylint: disable=unused-argument
        await interaction.response.defer()
        self.request_queue.put(("CONTROL_SERVER", {
            "action": "start",
            "shard": "All",
            "interaction_id": interaction.id
        }))
        await interaction.followup.send("Start command sent.", ephemeral=True)

    @discord.ui.button(label="Stop All", style=discord.ButtonStyle.danger, emoji="🔴", custom_id="panel_stop")
    async def stop_server(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle Stop All button."""
        # pylint: disable=unused-argument
        await interaction.response.defer()
        self.request_queue.put(("ANNOUNCE", {"message": "Server shutting down in 5 seconds..."}))
        await asyncio.sleep(5)
        self.request_queue.put(("CONTROL_SERVER", {
            "action": "stop",
            "shard": "All",
            "interaction_id": interaction.id
        }))
        await interaction.followup.send("Stop command sent.", ephemeral=True)

    @discord.ui.button(label="Restart All", style=discord.ButtonStyle.primary, emoji="🔄", custom_id="panel_restart")
    async def restart_server(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle Restart All button."""
        # pylint: disable=unused-argument
        await interaction.response.defer()
        self.request_queue.put(("ANNOUNCE", {"message": "Server restarting in 5 seconds..."}))
        await asyncio.sleep(5)
        self.request_queue.put(("CONTROL_SERVER", {
            "action": "restart",
            "shard": "All",
            "interaction_id": interaction.id
        }))
        await interaction.followup.send("Restart command sent.", ephemeral=True)

    @discord.ui.button(label="Update Server", style=discord.ButtonStyle.secondary, emoji="⬇️", custom_id="panel_update")
    async def update_server(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle Update Server button."""
        # pylint: disable=unused-argument
        await interaction.response.defer()
        self.request_queue.put(("UPDATE_SERVER", {
            "interaction_id": interaction.id
        }))
        await interaction.followup.send("Update command sent.", ephemeral=True)


class FishBotClient(discord.Client):
    """Custom Discord Client for the Fish Manager Bot."""

    def __init__(self, command_queue, request_queue, log_queue, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.command_queue = command_queue
        self.request_queue = request_queue
        self.log_queue = log_queue
        self.tree = app_commands.CommandTree(self)
        self.chat_channel_id = os.getenv("DISCORD_CHAT_CHANNEL_ID")
        self.pending_interactions = {}
        self.added = False  # Track if view is added

    def log(self, message, level="INFO"):
        """Log a message to the shared log queue."""
        try:
            self.log_queue.put((level, message))
        except: # pylint: disable=bare-except
            pass

    async def setup_hook(self):
        """Setup hook to sync commands and start the queue listener."""
        guild_id_str = os.getenv("DISCORD_GUILD_ID")
        if guild_id_str:
            guild_id = int(guild_id_str)
            guild = discord.Object(id=guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            self.log(f"Synced commands to guild {guild_id}")
        else:
            await self.tree.sync()
            self.log("Synced commands (Global)")

        if not self.added:
            self.add_view(ControlPanel(self.request_queue))
            self.added = True

        # Start the queue listener
        self.loop.create_task(self.queue_listener())

    async def on_ready(self):
        """Called when bot is ready."""
        self.log(f"Logged in as {self.user} (ID: {self.user.id})")

    async def on_message(self, message):
        """Handle incoming messages from Discord."""
        # Ignore own messages
        if message.author == self.user:
            return

        # Check channel
        if self.chat_channel_id and str(message.channel.id) == str(self.chat_channel_id):
            # Relay to game
            # Format: User: Message
            display_name = message.author.display_name
            content = message.clean_content
            self.request_queue.put(("ANNOUNCE", {
                "message": f"{display_name}: {content}"
            }))

    async def queue_listener(self):
        """Listen for commands from the main process."""
        self.log("Queue listener started")

        handlers = {
            "STOP": self._handle_stop,
            "STATUS_RESPONSE": self._handle_status_response,
            "CONTROL_RESPONSE": self._handle_control_response,
            "UPDATE_RESPONSE": self._handle_update_response,
            "PLAYERS_RESPONSE": self._handle_players_response,
            "SEND_CHAT": self._handle_send_chat,
        }

        while not self.is_closed():
            try:
                # Non-blocking get
                while not self.command_queue.empty():
                    cmd_type, data = self.command_queue.get_nowait()

                    handler = handlers.get(cmd_type)
                    if handler:
                        await handler(data)
                    else:
                        self.log(f"Unknown command type: {cmd_type}", "WARNING")

                await asyncio.sleep(0.5)
            except Exception as e: # pylint: disable=broad-exception-caught
                self.log(f"Error in queue listener: {e}", "ERROR")
                await asyncio.sleep(1)

    async def _handle_stop(self, _):
        """Handle STOP command."""
        self.log("Received STOP command. Closing bot.")
        await self.close()

    async def _handle_status_response(self, data):
        """Handle STATUS_RESPONSE command."""
        # data = {"interaction_id": ..., "shards": [...]}
        iid = data.get("interaction_id")
        if iid in self.pending_interactions:
            interaction = self.pending_interactions.pop(iid)
            shards = data.get("shards", [])

            embed = discord.Embed(title="Server Status", color=discord.Color.blue())
            for s in shards:
                status_icon = "🟢" if s['is_running'] else "🔴"
                embed.add_field(
                    name=f"{status_icon} {s['name']}",
                    value=f"Status: {s['status']}",
                    inline=False
                )

            try:
                await interaction.followup.send(embed=embed)
            except Exception: # pylint: disable=broad-exception-caught
                pass

    async def _handle_control_response(self, data):
        """Handle CONTROL_RESPONSE command."""
        # data = {"interaction_id": ..., "success": ..., "output": ...}
        iid = data.get("interaction_id")
        if iid in self.pending_interactions:
            interaction = self.pending_interactions.pop(iid)
            success = data.get("success")
            output = data.get("output")

            icon = "✅" if success else "❌"
            try:
                await interaction.followup.send(f"{icon} Result: {output}")
            except Exception: # pylint: disable=broad-exception-caught
                pass

    async def _handle_update_response(self, _):
        """Handle UPDATE_RESPONSE command."""
        # Not fully implemented
        pass

    async def _handle_players_response(self, data):
        """Handle PLAYERS_RESPONSE command."""
        iid = data.get("interaction_id")
        if iid in self.pending_interactions:
            interaction = self.pending_interactions.pop(iid)
            players = data.get("players", [])

            if players:
                msg = "**Online Players:**\n" + "\n".join([f"• {p}" for p in players])
            else:
                msg = "No players online."

            try:
                await interaction.followup.send(msg)
            except Exception: # pylint: disable=broad-exception-caught
                pass

    async def _handle_send_chat(self, data):
        """Handle SEND_CHAT command."""
        # data = "User: Message"
        if self.chat_channel_id:
            try:
                channel = self.get_channel(int(self.chat_channel_id))
                if channel:
                    await channel.send(data)
            except Exception as e: # pylint: disable=broad-exception-caught
                self.log(f"Failed to send chat: {e}", "ERROR")


def run_bot_process(token, command_queue, request_queue, log_queue):
    """Entry point for the separate process."""
    # Silence discord gateway logs
    import logging
    logging.getLogger("discord").setLevel(logging.WARNING)

    # Setup intents
    intents = discord.Intents.default()
    intents.message_content = True  # If we want to read chat

    client = FishBotClient(command_queue, request_queue, log_queue, intents=intents)

    # --- DEFINE COMMANDS ---
    @client.tree.command(name="status", description="Get Server Status")
    async def status(interaction: discord.Interaction):
        await interaction.response.defer()
        # Store interaction to reply later
        client.pending_interactions[interaction.id] = interaction
        # Request status from TUI
        request_queue.put(("GET_STATUS", {"interaction_id": interaction.id}))

    @client.tree.command(name="start", description="Start a shard (or all)")
    @app_commands.describe(shard="Shard name or 'All'")
    async def start_server(interaction: discord.Interaction, shard: str = "Master"):
        await interaction.response.defer()
        client.pending_interactions[interaction.id] = interaction
        request_queue.put(
            (
                "CONTROL_SERVER",
                {"action": "start", "shard": shard, "interaction_id": interaction.id},
            )
        )

    @client.tree.command(name="stop", description="Stop a shard (or all)")
    @app_commands.describe(shard="Shard name or 'All'")
    async def stop_server(interaction: discord.Interaction, shard: str = "Master"):
        await interaction.response.defer()
        client.pending_interactions[interaction.id] = interaction
        request_queue.put(
            (
                "CONTROL_SERVER",
                {"action": "stop", "shard": shard, "interaction_id": interaction.id},
            )
        )

    @client.tree.command(name="announce", description="Send Message to Server")
    async def announce(interaction: discord.Interaction, message: str):
        request_queue.put(("ANNOUNCE", {"message": message}))
        await interaction.response.send_message(f"Sent: {message}", ephemeral=True)

    @client.tree.command(name="players", description="List Players")
    async def players(interaction: discord.Interaction):
        await interaction.response.defer()
        client.pending_interactions[interaction.id] = interaction
        request_queue.put(("GET_PLAYERS", {"interaction_id": interaction.id}))

    @client.tree.command(name="panel", description="Show Server Control Panel")
    async def panel(interaction: discord.Interaction):
        await interaction.response.send_message(
            "Server Controls:", view=ControlPanel(request_queue)
        )

    # --- RUN ---
    try:
        client.run(token, log_handler=None)
    except Exception as e: # pylint: disable=broad-exception-caught
        log_queue.put(("ERROR", f"Bot crashed: {e}"))
