import sys
import os
import logging
import multiprocessing
import queue
import re
import collections

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

    def on_load(self, config, manager_service, event_bus=None):
        self.manager = manager_service
        self.event_bus = event_bus
        # We can load specific config here if needed, but the bot process will read env vars directly
        pass

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

        logger.info(f"Discord Bot process started with PID {self.process.pid}")

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
                # We could integrate this into the main app logger or a specific UI panel
                # For now, we rely on the fact that if we use a customized logging handler in the TUI,
                # we might need to forward these.
                # But for simplicity, we let the logger handle it if configured, or just ignore for now
                # to avoid duplicate logs in stdout if both print.
                # ACTUALLY: The TUI captures stdout/stderr/logging.
                # We should probably log them to the main logger with a prefix.
                level, msg = record
                if level == "INFO":
                    logger.info(f"[Discord] {msg}")
                elif level == "ERROR":
                    logger.error(f"[Discord] {msg}")
                elif level == "WARNING":
                    logger.warning(f"[Discord] {msg}")
        except queue.Empty:
            pass

        # 2. Consume Request Queue (Commands from Bot -> Manager)
        try:
            while True:
                req_type, req_data = self.request_queue.get_nowait()
                self._handle_request(req_type, req_data)
        except queue.Empty:
            pass

    def _handle_request(self, req_type, data):
        """Handle requests from the bot process."""
        if req_type == "GET_STATUS":
            # Bot wants status, we send it back
            # data is execution_id usually or just None if we use a different flow.
            # But the bot might wait for a response?
            # Creating a synchronous 'ask' across processes is complex.
            # Simplified flow: Bot asks for status -> App sends 'UPDATE_STATUS' command back with data.

            # However, for 'GET_STATUS', the bot usually needs it *now* to reply to interaction.
            # If we want to be fully async, the bot defers interaction, asks us, we process, we send back.
            # For this MVP, let's implement the 'Defer -> Ask -> Reply' flow in the bot.

            # Wait, the ManagerService has access to shm/systemd which is fast.
            # BUT we are in the main loop update() here.

            # Let's get the status
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
                success, _, err = self.manager.control_all_shards(
                    action, target_shards
                )
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
            # Execute update
            # run_updater returns Popen object?
            # manager_service.py says: return self.game_service.run_updater()
            # We should probably run this in background or just kick it off.
            # The TUI handles update logs via `_perform_update_task`.
            # Here we just kick it off.

            try:
                _ = self.manager.run_updater()
                # We can't easily capture output here without blocking or complex thread handling.
                # Let's just say it started.
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
            except Exception as e:
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
        if not self.command_queue:
            return

        # event.data is likely a list of recent messages or a single new message?
        # Based on previous code: event.data is list of all recent lines.
        # We need to filter for new lines.
        # Actually, let's look at `ui/app.py` or where the event is emitted.
        # `manager_service.get_chat_logs` returns list of str.
        # The previous bot manager kept 'previous_chat_messages' to find diffs.
        # The Event `CHAT_MESSAGE` in `ui/app.py` seems to be just a signal that update happened?
        # Let's check `_on_chat_message` in app.py. It just `request_redraw()`.
        # So the event might NOT contain the data, or it might contain the full log.
        # If it contains full log, we need a history tracking here.

        # Checking `core/background/coordinator.py` would confirm what is sent.
        # Assuming for now event.data is the list of logs.

        # Simplification: We need state to track what we already sent.
        # We can store `last_log_line` or similar.

        pass  # To be implemented fully, we need to handle the log diffing properly.
        # For now, let's assume we receive the full list and we need to simple diff.

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
            if msg not in self.last_chat_logs:
                # Check filters
                if "[Discord]" in msg:
                    continue
                if " [System Message]" in msg:
                    continue
                if " [Whisper]" in msg:
                    continue
                # Extract user?
                # Extract Name: Message using regex
                # Supported tags: [Say], [Announcement], [Death Announcement], etc.
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
                
                # Regex to match [Tag] (ID) Content
                # We target the tag after the first colon (timestamp separator)
                match = re.search(r":\s*\[(Say|.*?Announcement)\]\s*(?:\([^)]*\))?\s*(.*)", msg)
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

        self.last_chat_logs = chat_logs[-100:]  # Keep last 100

        for m in new_msgs:
            self.command_queue.put(("SEND_CHAT", m))
