#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Main manager service that orchestrates all operations."""

from typing import Dict, List, Tuple

from features.chat.chat_manager import ChatManager
from features.shards.shard_manager import ShardManager
from features.status.status_manager import StatusManager
from services.game_service import GameService
from services.systemd_service import SystemDService
from utils.config import Shard, write_cluster_token


class ManagerService:
    """Orchestrates all interactions with systemd and game files."""

    def __init__(self):
        self.game_service = GameService()
        self.systemd_service = SystemDService()
        self.shard_manager = ShardManager()

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
        return ChatManager.get_chat_logs(lines)

    def run_updater(self):
        """Runs the dst-updater script."""
        return self.game_service.run_updater()

    def update_cluster_token(self, token: str) -> bool:
        """Updates the cluster token."""
        return write_cluster_token(token)

    def send_command(self, shard_name: str, command: str) -> Tuple[bool, str]:
        """Sends a command to the specified shard's console."""
        return self.game_service.send_command(shard_name, command)

    def send_chat_message(self, shard_name: str, message: str) -> Tuple[bool, str]:
        """Sends a chat message using c_announce() command."""
        return ChatManager.send_chat_message(shard_name, message)

    def rollback_shard(self, shard_name: str, count: int = 1) -> Tuple[bool, str]:
        """Rollbacks the shard."""
        return self.game_service.rollback_shard(shard_name, count)

    def save_shard(self, shard_name: str) -> Tuple[bool, str]:
        """Saves the shard."""
        return self.game_service.save_shard(shard_name)

    def reset_shard(self, shard_name: str) -> Tuple[bool, str]:
        """Resets the shard."""
        return self.game_service.reset_shard(shard_name)

    def get_server_status(self, shard_name: str = "Master") -> Dict:
        """Gets server status information."""
        return StatusManager.get_server_status(shard_name)

    def request_status_update(self, shard_name: str = "Master") -> bool:
        """Requests status update from server."""
        return StatusManager.request_status_update(shard_name)
