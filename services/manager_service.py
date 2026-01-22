#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Main manager service that orchestrates all operations."""

from typing import List, Tuple, Dict

from services.game_service import GameService
from services.systemd_service import SystemDService
from features.shards.shard_manager import ShardManager
from utils.config import Shard


class ManagerService:
    """Orchestrates all interactions with systemd and game files."""

    def __init__(self):
        self.game_service = GameService()
        self.systemd_service = SystemDService()
        self.shard_manager = ShardManager()

        # Discord service (lazy initialization)
        self._discord_service = None

    def get_shards(self) -> List[Shard]:
        """
        Reads desired shards from the config file and gets their current status.
        """
        return self.shard_manager.get_shards()

    def control_shard(self, shard_name: str, action: str) -> Tuple[bool, str, str]:
        """
        Controls a single shard through systemd.
        Returns: (success, stdout, stderr)
        """
        return self.shard_manager.control_shard(shard_name, action)

    def control_all_shards(
        self, action: str, shard_list: List[Shard]
    ) -> Tuple[bool, str, str]:
        """
        Controls all shards in the list.
        Returns: (success, stdout, stderr)
        """
        return self.shard_manager.control_all_shards(action, shard_list)

    def get_logs(self, shard_name: str, lines: int = 50) -> str:
        """Gets the latest journalctl logs for a shard."""
        return self.shard_manager.get_logs(shard_name, lines)

    def sync_shards(self) -> None:
        """
        Synchronizes systemd units with shards.conf.
        """
        self.shard_manager.sync_shards()

    def get_chat_logs(self, lines: int = 50) -> List[str]:
        """Gets the latest chat messages from the game chat log."""
        from features.chat.chat_manager import ChatManager

        return ChatManager.get_chat_logs(lines)

    def run_updater(self):
        """Runs the dst-updater script."""
        return self.game_service.run_updater()

    def send_command(self, shard_name: str, command: str) -> Tuple[bool, str]:
        """Sends a command to the specified shard's console."""
        return self.game_service.send_command(shard_name, command)

    def send_chat_message(self, shard_name: str, message: str) -> Tuple[bool, str]:
        """Sends a chat message using c_announce() command."""
        from features.chat.chat_manager import ChatManager

        return ChatManager.send_chat_message(shard_name, message)

    def get_server_status(self, shard_name: str = "Master") -> Dict:
        """Gets server status information."""
        from features.status.status_manager import StatusManager

        return StatusManager.get_server_status(shard_name)

    def request_status_update(self, shard_name: str = "Master") -> bool:
        """Requests status update from server."""
        from features.status.status_manager import StatusManager

        return StatusManager.request_status_update(shard_name)

    @property
    def discord_service(self):
        """Lazy initialization of Discord service."""
        if self._discord_service is None:
            from services.discord_service import DiscordService
            self._discord_service = DiscordService(self)
        return self._discord_service

    def start_discord_bot(self):
        """Start the Discord bot if enabled."""
        if self.discord_service.is_enabled():
            self.discord_service.start()

    def stop_discord_bot(self):
        """Stop the Discord bot."""
        if self._discord_service:
            self.discord_service.stop()
