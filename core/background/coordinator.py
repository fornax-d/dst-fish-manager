#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Background task coordinator."""

import threading
import time
from typing import Callable

from core.events.bus import Event, EventBus, EventType
from core.state.app_state import StateManager


class BackgroundCoordinator:
    """Coordinates background tasks and periodic updates."""

    def __init__(
        self, state_manager: StateManager, event_bus: EventBus, manager_service
    ):
        self.state_manager = state_manager
        self.event_bus = event_bus
        self.manager_service = manager_service
        self._running = False
        self._background_thread = None

    def start(self) -> None:
        """Start background coordinator."""
        if self._running:
            return

        self._running = True
        self._background_thread = threading.Thread(
            target=self._background_loop, daemon=True
        )
        self._background_thread.start()

    def stop(self) -> None:
        """Stop background coordinator."""
        self._running = False
        if self._background_thread:
            self._background_thread.join(timeout=1.0)

    def run_in_background(self, func: Callable, *args, **kwargs) -> None:
        """Run a function in background thread."""

        def worker():
            self.event_bus.publish(Event(EventType.BACKGROUND_TASK_START))
            self.state_manager.set_working(True)
            try:
                func(*args, **kwargs)
                # Refresh shards after task completes
                from features.shards.shard_manager import ShardManager

                shard_manager = ShardManager()
                new_shards = shard_manager.get_shards()
                self.state_manager.update_shards(new_shards)
                self.event_bus.publish(Event(EventType.SHARD_REFRESH, new_shards))
            finally:
                self.state_manager.set_working(False)
                self.event_bus.publish(Event(EventType.BACKGROUND_TASK_END))

        threading.Thread(target=worker, daemon=True).start()

    def _background_loop(self) -> None:
        """Main background loop for periodic updates."""
        while self._running:
            current_time = time.time()
            state = self.state_manager.state

            # Periodic shard refresh (every 2 seconds)
            if current_time - state.last_refresh_time > 2.0:
                if (
                    not state.ui_state.log_viewer_active
                    and not state.ui_state.mods_viewer_active
                ):
                    from features.shards.shard_manager import ShardManager

                    shard_manager = ShardManager()
                    new_shards = shard_manager.get_shards()
                    self.state_manager.update_shards(new_shards)

                    # Check master offline status
                    master = next((s for s in new_shards if s.name == "Master"), None)
                    if master and master.is_running:
                        state.master_offline_count = 0
                    else:
                        state.master_offline_count += 1
                        if state.master_offline_count >= 3:
                            self.state_manager.update_server_status(
                                {
                                    "season": "---",
                                    "day": "---",
                                    "days_left": "---",
                                    "phase": "---",
                                    "players": [],
                                }
                            )

                    self.event_bus.publish(Event(EventType.SHARD_REFRESH, new_shards))
                    self.state_manager.update_timing(last_refresh_time=current_time)
                    self.state_manager.request_redraw()

            # Server status refresh (every 5 seconds)
            if current_time - state.last_status_refresh_time > 5.0:
                from features.status.status_manager import StatusManager

                new_status = StatusManager.get_server_status()
                shards = self.state_manager.get_shards_copy()
                master = next((s for s in shards if s.name == "Master"), None)
                if master and master.is_running:
                    self.state_manager.update_server_status(new_status)
                    self.event_bus.publish(
                        Event(EventType.SERVER_STATUS_UPDATE, new_status)
                    )
                self.state_manager.update_timing(last_status_refresh_time=current_time)
                self.state_manager.request_redraw()

            # Status poll request (every 15 seconds)
            if current_time - state.last_status_poll_time > 15.0:
                if not state.ui_state.log_viewer_active and not state.is_working:
                    from features.status.status_manager import StatusManager

                    StatusManager.request_status_update()
                self.state_manager.update_timing(last_status_poll_time=current_time)

            # Chat logs refresh (every 5 seconds)
            if current_time - state.last_chat_read_time > 5.0:
                from features.chat.chat_manager import ChatManager

                chat_logs = ChatManager.get_chat_logs(50)
                state.ui_state.cached_chat_logs = chat_logs
                self.event_bus.publish(Event(EventType.CHAT_MESSAGE, chat_logs))
                self.state_manager.update_timing(last_chat_read_time=current_time)

            time.sleep(0.1)
