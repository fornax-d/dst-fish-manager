#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Discord bot manager for DST Fish Manager - Refactored version."""

import asyncio

from core.events.bus import EventType
from features.discord.bot_client import DiscordBotClient
from features.discord.commands.panel_commands import PanelCommands
from features.discord.commands.status_commands import StatusCommands
from features.discord.handlers.error_handlers import ErrorHandlers
from utils.logger import discord_logger


class FallBotManager:
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
        self.sent_messages = set()  # Track sent message IDs to prevent duplicates

        # Initialize bot client
        self.client = DiscordBotClient(self.event_bus)

        # Initialize command handlers
        self.panel_commands = PanelCommands(manager_service)
        self.status_commands = StatusCommands(manager_service)

        # Setup bot
        self._setup_commands()
        self._setup_error_handlers()
        self._setup_event_handlers()

    def _setup_commands(self):
        """Setup bot slash commands."""
        discord_logger.info("Setting up Discord slash commands")

        guild = self.client.get_guild_object()
        guild_info = f"guild {self.client.guild_id}" if guild else "globally"
        discord_logger.info(f"Commands will be registered to: {guild_info}")

        # Register commands
        self.panel_commands.register_commands(self.client.tree, guild)
        self.status_commands.register_commands(self.client.tree, guild)

    def _setup_error_handlers(self):
        """Setup error handlers."""
        discord_logger.info("Setting up error handlers")
        ErrorHandlers.setup_error_handlers(self.client.tree)
        ErrorHandlers.setup_client_handlers(self.client)

    def _setup_event_handlers(self):
        """Setup event handlers."""
        # Event subscriptions are now handled in set_event_bus method only
        pass

    def is_enabled(self) -> bool:
        """Check if Discord bot is properly configured."""
        return self.client.is_enabled()

    async def start(self):
        """Start the Discord bot manager.

        Initializes the bot client and starts listening for events.
        """
        if not self.client.is_enabled():
            discord_logger.warning("Discord bot not configured, skipping startup")
            return

        try:
            discord_logger.info("Starting Discord bot manager")
            await self.client.start()
        except Exception as e:  # pylint: disable=broad-exception-caught
            # Catch all exceptions to ensure proper error logging and cleanup
            discord_logger.error(f"Failed to start Discord bot manager: {e}")
            raise

    async def stop(self):
        """Stop the Discord bot."""
        try:
            discord_logger.info("Stopping Discord bot manager")
            await self.client.stop()
        except Exception as e:  # pylint: disable=broad-exception-caught
            # Catch all exceptions to ensure proper error logging
            discord_logger.error(f"Error stopping Discord bot manager: {e}")

    async def send_message(self, message: str):
        """Send a message to the configured chat channel."""
        channel = self.client.get_chat_channel()
        if not channel or not hasattr(channel, "send"):
            discord_logger.warning("No valid chat channel configured, skipping message")
            return

        try:
            await channel.send(message)
        except Exception as e:  # pylint: disable=broad-exception-caught
            # Catch all exceptions to ensure proper error logging
            discord_logger.error(f"Error sending message to Discord: {e}")

    def set_event_bus(self, event_bus):
        """Set the event bus and setup subscriptions."""
        self.event_bus = event_bus
        if self.event_bus:
            self._setup_event_subscriptions()
            discord_logger.debug(
                f"Event bus set for Discord bot manager with {len(self.event_bus._subscribers)} subscriptions"
            )

    def _setup_event_subscriptions(self):
        """Setup event subscriptions for chat messages."""
        if self.event_bus:
            # Subscribe to chat message events
            self.event_bus.subscribe(EventType.CHAT_MESSAGE, self._handle_chat_message)

    def _handle_chat_message(self, event):
        """Handle chat message events to prevent duplicate sending."""
        chat_logs = event.data
        discord_logger.info(
            f"Received chat event with {len(chat_logs) if isinstance(chat_logs, list) else 0} messages"
        )

        if chat_logs and isinstance(chat_logs, list):
            # Process all messages but filter out duplicates and non-chat entries
            for log_entry in chat_logs:
                discord_logger.debug(f"Processing chat entry: {log_entry}")
                if isinstance(log_entry, str):
                    # Skip empty messages
                    if not log_entry.strip():
                        continue

                    # Skip Discord messages coming back to avoid loops
                    if "[Discord]" in log_entry:
                        discord_logger.debug("Skipping Discord message to avoid loop")
                        continue

                    # Skip system messages
                    if log_entry.startswith("[System Message]"):
                        continue

                    # Process chat messages
                    # Format 1: [Say] message or [Whisper] message (from game chat)
                    # Format 2: [HH:MM:SS]: [Announcement] message (from coordinator)
                    # Format 3: [HH:MM:SS]: [Join Announcement] message (player join)
                    # Format 4: Simple message (from UI)
                    is_chat_message = (
                        log_entry.startswith("[Say]")
                        or log_entry.startswith("[Whisper]")
                        or "[Announcement]" in log_entry
                        or "[Join Announcement]" in log_entry
                        or "[Leave Announcement]" in log_entry
                        or "[Death Announcement]" in log_entry
                        or (
                            not log_entry.startswith("[") and len(log_entry.strip()) > 0
                        )
                    )

                    if is_chat_message:
                        discord_logger.info(f"Processing chat message: {log_entry}")
                        # Create unique ID using full content to ensure uniqueness
                        message_id = hash(log_entry.strip())
                        if message_id not in self.sent_messages:
                            discord_logger.info(
                                f"New message detected (not in sent_messages)"
                            )
                            self.sent_messages.add(message_id)

                            # Clean up old message IDs to prevent memory growth
                            if len(self.sent_messages) > 100:
                                self.sent_messages = set(list(self.sent_messages)[-50:])

                            # Message from game, forward to Discord (keep original format)
                            discord_logger.info(
                                f"Calling _forward_message_to_discord with: {log_entry}"
                            )
                            # Schedule async send in the bot's event loop
                            if self.client and self.client.client.is_ready():
                                import asyncio

                                asyncio.run_coroutine_threadsafe(
                                    self._forward_message_to_discord(log_entry),
                                    self.client.client.loop,
                                )
                        else:
                            discord_logger.info(
                                f"Skipping duplicate message: {log_entry}"
                            )
                    else:
                        discord_logger.info(f"Skipping non-chat message: {log_entry}")

    async def _forward_message_to_discord(self, message):
        """Forward chat message to Discord if chat channel is configured."""
        try:
            chat_channel = self.client.get_chat_channel()
            if chat_channel and hasattr(chat_channel, "send"):
                discord_logger.info(f"Forwarding message to Discord: {message}")
                # Send message to Discord chat channel
                await chat_channel.send(message)
                discord_logger.info(f"Successfully sent message to Discord: {message}")
            else:
                discord_logger.warning(
                    "Cannot forward message to Discord: no valid chat channel"
                )
        except Exception as e:  # pylint: disable=broad-exception-caught
            # Catch all exceptions to ensure proper error logging
            discord_logger.error(
                f"Error forwarding message to Discord: {e}", exc_info=True
            )

    def _forward_message_to_game(self, message):
        """Forward Discord message to game if appropriate."""
        try:
            # Send message to game via manager service
            success, error = self.manager_service.send_chat_message("Master", message)
            if not success:
                discord_logger.warning(f"Failed to send message to game: {error}")
        except Exception as e:  # pylint: disable=broad-exception-caught
            # Catch all exceptions to ensure proper error logging
            discord_logger.warning(f"Error forwarding message to game: {e}")
