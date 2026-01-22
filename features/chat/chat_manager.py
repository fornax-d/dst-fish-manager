#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Chat manager for handling game chat functionality."""

import collections
import subprocess
import shlex
from typing import List

from utils.config import HOME_DIR, config_manager, get_game_config


class ChatManager:
    """Manages game chat functionality."""

    @staticmethod
    def get_chat_logs(lines: int = 50) -> List[str]:
        """Gets the latest chat messages from the game chat log."""
        config = get_game_config()
        cluster_name = config.get("CLUSTER_NAME", "MyDediServer")
        dst_dir = config.get("DONTSTARVE_DIR")

        chat_log_path = dst_dir / cluster_name / "Master" / "server_chat_log.txt"

        if not chat_log_path.exists():
            available_clusters = config_manager.get_available_clusters()
            return [
                f"Chat log file not found at {chat_log_path}.",
                f"Available clusters: {', '.join(available_clusters) if available_clusters else 'None'}",
                f"Using cluster: {cluster_name}",
                "Make sure the server is running and the cluster directory exists.",
            ]

        try:
            with chat_log_path.open("r") as f:
                last_lines = collections.deque(f, maxlen=lines)
            if last_lines:
                return [line.strip() for line in last_lines]
            else:
                return ["No chat messages yet."]
        except Exception as e:
            return [f"Error reading chat log: {e}"]

    @staticmethod
    def send_chat_message(shard_name: str, message: str) -> tuple[bool, str]:
        """Sends a chat message using c_announce() command."""
        if shard_name != "Master":
            return False, "Chat messages can only be sent to the 'Master' shard."

        command = f'c_announce("{message}")'
        return ChatManager.send_command(shard_name, command)

    @staticmethod
    def send_system_message(shard_name: str, message: str) -> tuple[bool, str]:
        """Sends a chat message using TheNet:SystemMessage command."""
        if shard_name != "Master":
            return False, "Chat messages can only be sent to the 'Master' shard."

        command = f'TheNet:SystemMessage("{message}")'
        return ChatManager.send_command(shard_name, command)


    @staticmethod
    def send_command(shard_name: str, command: str) -> tuple[bool, str]:
        """Sends a command to the specified shard's console."""
        # Allow commands to all shards (not just Master) for status polling

        fifo_path = HOME_DIR / ".cache" / "dontstarve" / f"dst-{shard_name}.fifo"
        if not fifo_path.exists():
            return False, f"FIFO for shard '{shard_name}' not found at {fifo_path}"

        try:
            echo_cmd = ["echo", command]
            with open(fifo_path, "w") as fifo:
                subprocess.run(echo_cmd, stdout=fifo, check=True, timeout=5)
            return True, "Command sent successfully."
        except Exception as e:
            return False, f"Failed to send command to FIFO: {e}"
