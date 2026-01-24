#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Chat manager for handling game chat functionality."""

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
            # Read the entire file and get all lines
            with chat_log_path.open("r", encoding="utf-8") as f:
                all_lines = [line.strip() for line in f if line.strip()]

            if not all_lines:
                return []

            # Filter out status command responses and other non-chat messages
            # Only keep actual chat messages and important announcements
            filtered_lines = []
            for line in all_lines:
                # Keep chat messages
                if (
                    "[Say]" in line
                    or "[Join Announcement]" in line
                    or "[Leave Announcement]" in line
                ):
                    filtered_lines.append(line)
                # Filter out status command responses that might cause duplicates
                elif "c_listallplayers" in line or "c_dumpseasons" in line:
                    continue
                # Keep other potentially important messages
                else:
                    filtered_lines.append(line)

            # Return only the most recent messages
            if filtered_lines:
                return filtered_lines[-min(lines, len(filtered_lines)) :]
            else:
                return []

        except (OSError, UnicodeDecodeError) as e:
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
            # Use the same method as the old implementation to send commands
            import shlex
            import subprocess

            shell_cmd = f"echo {shlex.quote(command)} > {shlex.quote(str(fifo_path))}"
            subprocess.run(
                shell_cmd,
                shell=True,
                check=True,
                timeout=5,
                capture_output=True,
                text=True,
            )
            return True, "Command sent successfully."
        except subprocess.TimeoutExpired:
            return False, f"Timeout sending command to FIFO: {fifo_path}"
        except subprocess.CalledProcessError as e:
            return False, f"Failed to send command to FIFO: {e}"
        except Exception as e:
            return False, f"Failed to send command to FIFO: {e}"
