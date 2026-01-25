#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Game service for communication with DST server."""

import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from utils.config import HOME_DIR


class GameService:
    """Handles communication with DST game server."""

    @staticmethod
    def get_chat_logs(lines: int = 50) -> List[str]:
        """Gets the latest chat messages from the game chat log."""
        from features.chat.chat_manager import ChatManager

        return ChatManager.get_chat_logs(lines)

    @staticmethod
    def run_updater() -> subprocess.Popen:
        """Runs the dst-updater script."""
        possible_paths = [
            Path(__file__).parent.parent.parent / ".local" / "bin" / "dst-updater",
            HOME_DIR / ".local" / "bin" / "dst-updater",
        ]

        updater_path = None
        for p in possible_paths:
            if p.is_file() and os.access(p, os.X_OK):
                updater_path = p
                break

        if not updater_path:
            raise FileNotFoundError(
                f"Updater script not found in any of: {possible_paths}"
            )

        return subprocess.Popen(
            [str(updater_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

    @staticmethod
    def send_command(shard_name: str, command: str) -> Tuple[bool, str]:
        """Sends a command to the specified shard's console."""
        from features.chat.chat_manager import ChatManager

        return ChatManager.send_command(shard_name, command)

    @staticmethod
    def send_chat_message(shard_name: str, message: str) -> Tuple[bool, str]:
        """Sends a chat message using c_announce() command."""
        from features.chat.chat_manager import ChatManager

        return ChatManager.send_chat_message(shard_name, message)

    @staticmethod
    def request_status_update(shard_name: Optional[str] = None) -> bool:
        """Sends Lua commands to the server to dump current status into the logs."""
        from features.status.status_manager import StatusManager

        return StatusManager.request_status_update(shard_name)

    @staticmethod
    def get_server_status(shard_name: Optional[str] = None) -> Dict:
        from features.status.status_manager import StatusManager

        return StatusManager.get_server_status(shard_name)
