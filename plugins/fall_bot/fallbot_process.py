# -*- coding: utf-8 -*-
"""
Isolated fall.bot Process.
This file is imported ONLY by the child process.
"""

import asyncio
import os
import queue
import time

import discord
from discord import app_commands

# Global reference for the client to access queues
BOT_QUEUES = None


class ControlPanel(discord.ui.View):
    def __init__(self, request_queue):
        super().__init__(timeout=None)
        self.request_queue = request_queue

    @discord.ui.button(
        label="Start All",
        style=discord.ButtonStyle.success,
        emoji="🟢",
        custom_id="panel_start",
    )
    async def start_server(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()
        # Simplified: We don't track interaction ID for completion on buttons for now
        # OR we could ephemeral reply "Command Sent"
        self.request_queue.put(
            (
                "CONTROL_SERVER",
                {"action": "start", "shard": "All", "interaction_id": interaction.id},
            )
        )
        await interaction.followup.send("Start command sent.", ephemeral=True)

    @discord.ui.button(
        label="Stop All",
        style=discord.ButtonStyle.danger,
        emoji="🔴",
        custom_id="panel_stop",
    )
    async def stop_server(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()
        self.request_queue.put(
            ("ANNOUNCE", {"message": "Server shutting down in 5 seconds..."})
        )
        # The referenced implementation did sleep in the thread. We can't easily sleep here without blocking?
        # Actually async sleep is fine.
        await asyncio.sleep(5)
        self.request_queue.put(
            (
                "CONTROL_SERVER",
                {"action": "stop", "shard": "All", "interaction_id": interaction.id},
            )
        )
        await interaction.followup.send("Stop command sent.", ephemeral=True)

    @discord.ui.button(
        label="Restart All",
        style=discord.ButtonStyle.primary,
        emoji="🔄",
        custom_id="panel_restart",
    )
    async def restart_server(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()
        self.request_queue.put(
            ("ANNOUNCE", {"message": "Server restarting in 5 seconds..."})
        )
        await asyncio.sleep(5)
        self.request_queue.put(
            (
                "CONTROL_SERVER",
                {"action": "restart", "shard": "All", "interaction_id": interaction.id},
            )
        )
        await interaction.followup.send("Restart command sent.", ephemeral=True)

    @discord.ui.button(
        label="Update Server",
        style=discord.ButtonStyle.secondary,
        emoji="⬇️",
        custom_id="panel_update",
    )
    async def update_server(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()
        self.request_queue.put(("UPDATE_SERVER", {"interaction_id": interaction.id}))
        await interaction.followup.send("Update command sent.", ephemeral=True)


class FishBotClient(discord.Client):
    def __init__(self, command_queue, request_queue, log_queue, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.command_queue = command_queue
        self.request_queue = request_queue
        self.log_queue = log_queue
        self.tree = app_commands.CommandTree(self)
        self.chat_channel_id = os.getenv("DISCORD_CHAT_CHANNEL_ID")

        # Dictionary to store pending interactions to reply to later
        # Key: interaction_id, Value: Interaction Object
        self.pending_interactions = {}

    async def on_ready(self):
        self.log(f"Logged in as {self.user} (ID: {self.user.id})")
        # Global sync (might take time) or Guild sync
        guild_id = os.getenv("DISCORD_GUILD_ID")
        if guild_id:
            guild = discord.Object(id=int(guild_id))
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

    def log(self, msg, level="INFO"):
        try:
            self.log_queue.put((level, msg))
        except:
            pass

    async def queue_listener(self):
        """Polls the command queue for messages from the TUI."""
        while not self.is_closed():
            try:
                # Non-blocking get
                while not self.command_queue.empty():
                    cmd_type, data = self.command_queue.get_nowait()

                    if cmd_type == "STOP":
                        self.log("Received STOP command. Closing bot.")
                        await self.close()
                        return

                    elif cmd_type == "STATUS_RESPONSE":
                        # data = {"interaction_id": ..., "shards": [...]}
                        iid = data.get("interaction_id")
                        if iid in self.pending_interactions:
                            interaction = self.pending_interactions.pop(iid)
                            shards = data.get("shards", [])

                            # Build embed or message
                            msg = "**Server Status:**\n"
                            for s in shards:
                                icon = "🟢" if s["is_running"] else "🔴"
                                msg += f"{icon} **{s['name']}**: {s['status']}\n"

                            try:
                                await interaction.followup.send(msg)
                            except Exception as e:
                                self.log(
                                    f"Failed to send status followup: {e}", "ERROR"
                                )

                    elif cmd_type == "CONTROL_RESPONSE":
                        # data = {"interaction_id": ..., "success": bool, "output": str}
                        iid = data.get("interaction_id")
                        if iid in self.pending_interactions:
                            interaction = self.pending_interactions.pop(iid)
                            success = data.get("success")
                            output = data.get("output", "")

                            icon = "✅" if success else "❌"
                            try:
                                await interaction.followup.send(
                                    f"{icon} Result: {output}"
                                )
                            except:
                                pass

                    elif cmd_type == "UPDATE_RESPONSE":
                        # data = {"interaction_id": ..., "success": ..., "output": ...}
                        # We might want to notify channel?
                        pass

                    elif cmd_type == "PLAYERS_RESPONSE":
                        # data = {"interaction_id": ..., "players": [...]}
                        iid = data.get("interaction_id")
                        if iid in self.pending_interactions:
                            interaction = self.pending_interactions.pop(iid)
                            players = data.get("players", [])

                            if players:
                                msg = "**Online Players:**\n" + "\n".join(
                                    [f"• {p}" for p in players]
                                )
                            else:
                                msg = "No players online."

                            try:
                                await interaction.followup.send(msg)
                            except:
                                pass

                    elif cmd_type == "SEND_CHAT":
                        # data = "User: Message"
                        if self.chat_channel_id:
                            try:
                                channel = self.get_channel(int(self.chat_channel_id))
                                if channel:
                                    await channel.send(data)
                            except Exception as e:
                                self.log(f"Failed to send chat: {e}", "ERROR")

                await asyncio.sleep(0.5)
            except Exception as e:
                self.log(f"Error in queue listener: {e}", "ERROR")
                await asyncio.sleep(1)


def run_bot_process(token, command_queue, request_queue, log_queue):
    """Entry point for the separate process."""

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
        client.run(token)
    except Exception as e:
        log_queue.put(("ERROR", f"Bot crashed: {e}"))
