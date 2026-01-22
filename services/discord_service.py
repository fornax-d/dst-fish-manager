#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Discord service for running the bot in the background."""

import threading
from typing import Optional

from features.discord.bot_manager import DiscordBotManager


class DiscordService:
    """Service for managing Discord bot lifecycle."""

    def __init__(self, manager_service):
        """
        Initialize Discord service.

        Args:
            manager_service: The main manager service instance
        """
        self.manager_service = manager_service

        self.bot_manager: Optional[DiscordBotManager] = None
        self.bot_thread: Optional[threading.Thread] = None
        self.is_running = False

    def start(self):
        """Start the Discord bot in a background thread."""
        if self.is_running:
            return

        try:
            self.bot_manager = DiscordBotManager(self.manager_service)

            # Start bot in background thread
            self.bot_thread = threading.Thread(
                target=self.bot_manager.run_in_background,
                daemon=True,
                name="DiscordBot"
            )
            self.bot_thread.start()
            self.is_running = True

        except Exception as e:
            raise

    def stop(self):
        """Stop the Discord bot."""
        if not self.is_running:
            return

        try:
            if self.bot_manager:
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self.bot_manager.stop())
                loop.close()

            self.is_running = False
        except Exception as e:
            pass

    def is_enabled(self) -> bool:
        """Check if Discord integration is enabled."""
        import os
        return bool(os.getenv("DISCORD_BOT_TOKEN"))
