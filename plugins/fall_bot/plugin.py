"""
Fall Bot Plugin integration.

This module provides the DiscordBotPlugin class which integrates a Discord bot
into the existing ManagerService architecture.
"""

import sys
import os
import logging
import multiprocessing
import queue
import re
import collections
import time

# Validating local import for fallbot_process
# pylint: disable=import-error, wrong-import-position
try:
    from .fallbot_process import run_bot_process
except ImportError:
    # Fallback for dynamic loading where relative imports might fail
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.append(current_dir)
    from fallbot_process import run_bot_process

from core.plugins.interface import IPlugin
from core.events.bus import EventType

logger = logging.getLogger(__name__)


class DiscordBotPlugin(IPlugin):
    """Fall Bot Plugin integration."""

    # pylint: disable=too-many-instance-attributes

    def __init__(self):
        super().__init__()
        self.name = "fall.bot Integration"
        self.version = "1.0.0"
        self.process = None
        self.command_queue = None
        self.request_queue = None
        self.log_queue = None
        self.manager = None
        self.event_bus = None
        self.chat_sub_id = None
        self.last_chat_logs = []
        self.initial_sync = True
        self.sent_messages = collections.deque(maxlen=20)
        self.last_status_update = 0

    def on_load(self, config, manager_service, event_bus=None):
        self.manager = manager_service
        self.event_bus = event_bus
        # We can load specific config here if needed,
        # but the bot process will read env vars directly

    def on_start(self):
        token = os.getenv("DISCORD_BOT_TOKEN")
        if not token:
            logger.warning("DISCORD_BOT_TOKEN not set, skipping Discord Bot start.")
            return

        # Silence discord gateway logs
        logging.getLogger("discord").setLevel(logging.WARNING)

        self.command_queue = multiprocessing.Queue()
        self.request_queue = multiprocessing.Queue()
        self.log_queue = multiprocessing.Queue()

        self.process = multiprocessing.Process(
            target=run_bot_process,
            args=(token, self.command_queue, self.request_queue, self.log_queue),
            name="DiscordBotProcess",
            daemon=True,
        )
        self.process.start()

        # Subscribe to chat events
        if self.event_bus:
            self.chat_sub_id = self.event_bus.subscribe(
                EventType.CHAT_MESSAGE, self._on_chat_event
            )

        logger.info("Discord Bot process started with PID %s", self.process.pid)

    def on_stop(self):
        # Unsubscribe
        if self.event_bus and self.chat_sub_id:
            self.event_bus.unsubscribe(EventType.CHAT_MESSAGE, self.chat_sub_id)

        if self.process and self.process.is_alive():
            if self.command_queue:
                self.command_queue.put(("STOP", None))
            self.process.join(timeout=5)
            if self.process.is_alive():
                self.process.terminate()
            logger.info("Discord Bot process stopped.")

    def update(self):
        if not self.process:
            return

        # 1. Consume Log Queue
        try:
            while True:
                record = self.log_queue.get_nowait()
                level, msg = record
                if level == "INFO":
                    logger.info("[Discord] %s", msg)
                elif level == "ERROR":
                    logger.error("[Discord] %s", msg)
                elif level == "WARNING":
                    logger.warning("[Discord] %s", msg)
        except queue.Empty:
            pass

        # 1.5 Send Status Updates (Every 30s)
        current_time = time.time()
        if current_time - self.last_status_update > 30:
            self.last_status_update = current_time

            try:
                status_manager = getattr(self.manager, "status_manager", None)
                if status_manager:
                    stats = status_manager.get_server_stats_summary()
                    # stats = {'server_stats': {'player_count': ..., 'season': ...,
                    #           'day': ..., 'phase': ...}, ...}
                    server_stats = stats.get("server_stats", {})

                    self.command_queue.put(
                        (
                            "UPDATE_PRESENCE",
                            {
                                "season": server_stats.get("season"),
                                "day": server_stats.get("day"),
                                "player_count": server_stats.get("player_count"),
                                "phase": server_stats.get("shard_status", {})
                                .get("Master", {})
                                .get("phase", "Unknown"),
                            },
                        )
                    )

            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error("Error sending presence update: %s", e)

        # 2. Consume Request Queue (Commands from Bot -> Manager)
        try:
            while True:
                req_type, req_data = self.request_queue.get_nowait()
                self._handle_request(req_type, req_data)
        except queue.Empty:
            pass

    def _handle_request(self, req_type, data):
        """Handle requests from the bot process."""
        # pylint: disable=too-many-locals, too-many-branches
        if req_type == "GET_STATUS":
            shards = self.manager.get_shards()
            status_data = []
            for s in shards:
                status_data.append(
                    {"name": s.name, "is_running": s.is_running, "status": s.status}
                )

            # Send back to bot
            self.command_queue.put(
                (
                    "STATUS_RESPONSE",
                    {
                        "interaction_id": data.get("interaction_id"),
                        "shards": status_data,
                    },
                )
            )

        elif req_type == "CONTROL_SERVER":
            # data = {"action": "start", "shard": "Master", "interaction_id": ...}
            action = data.get("action")
            shard_name = data.get("shard")

            # Look up shard
            target_shards = []
            if shard_name == "All" or not shard_name:
                target_shards = self.manager.get_shards()
            else:
                # Find specific shard
                all_shards = self.manager.get_shards()
                for s in all_shards:
                    if s.name == shard_name:
                        target_shards.append(s)
                        break

            # Execute
            # This returns (success, stdout, stderr)
            # control_all_shards or control_shard
            if len(target_shards) > 1:
                success, _, err = self.manager.control_all_shards(action, target_shards)
            elif len(target_shards) == 1:
                success, _, err = self.manager.control_shard(
                    target_shards[0].name, action
                )
            else:
                success, _, err = False, "", "Shard not found"

            # Reply
            self.command_queue.put(
                (
                    "CONTROL_RESPONSE",
                    {
                        "interaction_id": data.get("interaction_id"),
                        "success": success,
                        "output": err
                        if not success
                        else "Command sent.",  # TUI usually doesn't wait for full boot
                    },
                )
            )

        elif req_type == "UPDATE_SERVER":
            try:
                _ = self.manager.run_updater()
                self.command_queue.put(
                    (
                        "CONTROL_RESPONSE",
                        {
                            "interaction_id": data.get("interaction_id"),
                            "success": True,
                            "output": "Update started. Check server logs.",
                        },
                    )
                )
            except Exception as e:  # pylint: disable=broad-exception-caught
                self.command_queue.put(
                    (
                        "CONTROL_RESPONSE",
                        {
                            "interaction_id": data.get("interaction_id"),
                            "success": False,
                            "output": f"Failed to start update: {e}",
                        },
                    )
                )

        elif req_type == "GET_PLAYERS":
            # Force update first?
            self.manager.request_status_update("Master")
            status = self.manager.get_server_status("Master")
            # {"players": ["Name", ...], ...}
            players = status.get("players", [])

            self.command_queue.put(
                (
                    "PLAYERS_RESPONSE",
                    {"interaction_id": data.get("interaction_id"), "players": players},
                )
            )

        elif req_type == "ANNOUNCE":
            # data = {"message": "...", "shard": "Master"}
            msg = data.get("message")
            shard = data.get("shard", "Master")
            self.sent_messages.append(msg)
            self.manager.send_chat_message(shard, msg)

    def _on_chat_event(self, event):
        """Handle chat message from the game."""
        # pylint: disable=too-many-branches
        if not self.command_queue:
            return

        chat_logs = event.data
        if not chat_logs or not isinstance(chat_logs, list):
            return

        if not hasattr(self, "last_chat_logs"):
            self.last_chat_logs = []

        if self.initial_sync:
            self.last_chat_logs = chat_logs[-100:]
            self.initial_sync = False
            return

        new_msgs = []
        for msg in chat_logs:
            if msg in self.last_chat_logs:
                continue

            # Check filters
            if "[Discord]" in msg:
                continue
            if " [System Message]" in msg:
                continue
            if " [Whisper]" in msg:
                continue

            tag_emojis = {
                "Say": "",
                "Announcement": "📢",
                "Join Announcement": "📥",
                "Leave Announcement": "📤",
                "Death Announcement": "💀",
                "Resurrect Announcement": "💖",
                "Skin Announcement": "🎁",
                "Vote Announcement": "🗳️",
            }

            match = re.search(
                r":\s*\[(Say|.*?Announcement)\]\s*(?:\([^)]*\))?\s*(.*)", msg
            )
            if match:
                tag = match.group(1)
                content = match.group(2).strip()

                # Check if this is an echo of a message we just sent
                if content in self.sent_messages:
                    self.sent_messages.remove(content)
                    continue

                emoji = tag_emojis.get(tag, "")

                full_msg = f"{emoji} {content}".strip() if emoji else content
                new_msgs.append(full_msg)

                # Optimization: Force status update on Join
                if tag == "Join Announcement":
                    try:
                        # Trigger game to dump status immediately
                        if hasattr(self.manager, "status_manager"):
                            self.manager.status_manager.request_status_update("Master")
                        # Reset last status update time to force bot update in next loop
                        self.last_status_update = 0
                    except Exception as e:  # pylint: disable=broad-exception-caught
                        logger.error("Failed to force status update on join: %s", e)

        self.last_chat_logs = chat_logs[-100:]  # Keep last 100

        for m in new_msgs:
            self.command_queue.put(("SEND_CHAT", m))
