#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Main TUI application."""

import curses
import subprocess
import time

from core.background.coordinator import BackgroundCoordinator
from core.events.bus import Event, EventBus, EventType
from core.state.app_state import StateManager
from features.mods.mod_manager import ModManager
from services.manager_service import ManagerService
from ui.input.handler import InputHandler
from ui.rendering.renderer import Renderer
from utils.logger import discord_logger


class TUIApp:
    """Main TUI application class."""

    def __init__(self, stdscr, manager_service=None):
        self.stdscr = stdscr
        self.state_manager = StateManager()
        self.event_bus = EventBus()
        self.manager_service = manager_service or ManagerService()
        self.mod_manager = ModManager()

        # Setup UI components
        self.renderer = Renderer(stdscr, self.state_manager)

        # Setup input handler after renderer is created
        self.input_handler = InputHandler(
            self.state_manager,
            self.event_bus,
            self.renderer.theme,
            self.renderer.popup_manager,
        )

        # Set back-reference for input handler to access app
        self.input_handler._app = self

        # Link renderer to app for settings access
        self.renderer._app = self

        self.background_coordinator = BackgroundCoordinator(
            self.state_manager, self.event_bus, self.manager_service
        )

        # Setup callbacks
        self._setup_callbacks()

        # Setup event subscriptions
        self._setup_event_subscriptions()

        # Initialize curses
        self._setup_curses()

        # Start background coordinator
        self.background_coordinator.start()

    def _setup_curses(self) -> None:
        """Setup curses settings."""
        curses.curs_set(0)
        self.stdscr.nodelay(1)

    def _setup_callbacks(self) -> None:
        """Setup input handler callbacks."""
        self.input_handler.register_action_callback(
            "execute_action", self._execute_action
        )
        self.input_handler.register_action_callback(
            "toggle_enable", self._toggle_enable
        )
        self.input_handler.register_action_callback("prompt_chat", self._prompt_chat)
        self.input_handler.register_action_callback("open_mods", self._open_mods)
        self.input_handler.register_action_callback(
            "open_discord_logs", self._open_discord_logs
        )
        self.input_handler.register_action_callback("resize", self._handle_resize)
        self.input_handler.register_action_callback("toggle_mod", self._toggle_mod)
        self.input_handler.register_action_callback("add_mod", self._prompt_add_mod)
        self.input_handler.register_action_callback(
            "toggle_discord", self._toggle_discord_bot
        )

    def _setup_event_subscriptions(self) -> None:
        """Setup event bus subscriptions."""
        self.event_bus.subscribe(EventType.SHARD_REFRESH, self._on_shard_refresh)
        self.event_bus.subscribe(EventType.SERVER_STATUS_UPDATE, self._on_status_update)
        self.event_bus.subscribe(EventType.CHAT_MESSAGE, self._on_chat_message)
        self.event_bus.subscribe(EventType.EXIT_REQUESTED, self._on_exit_requested)

    def run(self) -> None:
        """Main application loop."""
        running = True

        # Start Discord bot in background if enabled (after UI is created)
        try:
            if self.manager_service.discord_service.is_enabled():
                # Connect event bus to Discord bot BEFORE starting it
                self.manager_service.discord_service.set_event_bus(self.event_bus)
                self.manager_service.start_discord_bot()
            else:
                # Log or handle the case where Discord is not enabled
                pass
        except AttributeError:
            # Discord service not available or not properly initialized
            pass

        # Initial shard loading
        self.background_coordinator.run_in_background(lambda: None)

        while running:
            current_time = time.time()
            state = self.state_manager.state

            # Process input
            if self.input_handler.process_input(self.stdscr):
                running = False
                continue

            # Draw if needed (at most 30 FPS)
            if state.need_redraw and (current_time - state.last_draw_time > 0.033):
                self.renderer.render()
                self.state_manager.clear_redraw_flag()
                self.state_manager.update_timing(last_draw_time=current_time)

            # Small sleep to prevent 100% CPU
            time.sleep(0.01)

        # Cleanup
        self.background_coordinator.stop()

    def _execute_action(self) -> None:
        """Execute the selected action."""
        state = self.state_manager.state

        if state.is_working:
            return

        if state.ui_state.selected_global_action_idx != -1:
            # Global action
            actions = ["start", "stop", "enable", "disable", "restart", "update"]
            action = actions[state.ui_state.selected_global_action_idx]

            if action == "update":
                self._handle_update()
            else:
                shards = self.state_manager.get_shards_copy()
                self.background_coordinator.run_in_background(
                    self.manager_service.control_all_shards, action, shards
                )
        else:
            # Shard action
            shards = self.state_manager.get_shards_copy()
            if not shards:
                return

            shard = shards[state.ui_state.selected_shard_idx]
            actions = ["start", "stop", "restart", "logs"]
            action = actions[state.ui_state.selected_action_idx]

            if action == "logs":
                self._handle_logs(shard.name)
            else:
                self.background_coordinator.run_in_background(
                    self.manager_service.control_shard, shard.name, action
                )

    def _toggle_enable(self) -> None:
        """Toggle shard enable state."""
        state = self.state_manager.state

        if state.is_working or state.ui_state.selected_global_action_idx != -1:
            return

        shards = self.state_manager.get_shards_copy()
        if not shards:
            return

        shard = shards[state.ui_state.selected_shard_idx]
        action = "disable" if shard.is_enabled else "enable"
        self.background_coordinator.run_in_background(
            self.manager_service.control_shard, shard.name, action
        )

    def _prompt_chat(self) -> None:
        """Prompt for chat message."""
        message = self.renderer.popup_manager.text_input_popup("Chat:", width=60)
        if message:
            # Send message to game and publish event for Discord forwarding
            success, _ = self.manager_service.send_chat_message("Master", message)
            if success:
                # Note: Chat messages are now handled by the coordinator
                # which reads from the game chat log file.
                # No need to publish separately from UI.
                discord_logger.info(f"Chat message sent to game: {message}")
            else:
                # Could show error popup here
                pass

    def _open_mods(self) -> None:
        """Open mods viewer."""
        mods = self.mod_manager.list_mods("Master")
        self.state_manager.state.ui_state.mods = mods
        self.state_manager.state.ui_state.mods_viewer_active = True
        self.state_manager.state.ui_state.selected_mod_idx = 0

    def _set_log_viewer(
        self,
        log_content: list,
        is_discord: bool = False,
        scroll_to_bottom: bool = False,
    ) -> None:
        """Set log viewer content and activate it.

        Args:
            log_content: List of log lines to display
            is_discord: True if Discord logs, False for system logs
            scroll_to_bottom: If True, scroll to show most recent logs
        """
        # Use the existing method from discord_logger to avoid code duplication
        if is_discord:
            log_content = discord_logger.get_log_file_content(max_lines=500)
        elif not log_content:
            log_content = ["No log content available"]

        self.state_manager.state.ui_state.log_content = log_content
        self.state_manager.state.ui_state.discord_logs_viewer_active = is_discord
        self.state_manager.state.ui_state.log_viewer_active = not is_discord

        if scroll_to_bottom:
            self.state_manager.state.ui_state.log_scroll_pos = max(
                0, len(log_content) - 20
            )
        else:
            self.state_manager.state.ui_state.log_scroll_pos = 0

    def _open_discord_logs(self) -> None:
        """Open Discord bot logs viewer."""
        try:
            log_content = discord_logger.get_log_file_content(max_lines=500)
        except (ImportError, AttributeError):
            log_content = ["Discord logging not available"]

        self._set_log_viewer(log_content, is_discord=True, scroll_to_bottom=True)

    def _handle_resize(self) -> None:
        """Handle terminal resize."""
        self.stdscr.clear()
        self.renderer.window_manager.create_layout()

    def _toggle_discord_bot(self) -> None:
        """Toggle Discord bot on/off via F10."""
        try:
            discord_service = self.manager_service.discord_service

            if discord_service.is_running:
                discord_service.stop()
                self._set_log_viewer(
                    ["--- Discord Bot Stopped ---"],
                    is_discord=False,
                    scroll_to_bottom=True,
                )
            else:
                discord_service.start()
                self._set_log_viewer(
                    ["--- Discord Bot Started ---"],
                    is_discord=False,
                    scroll_to_bottom=True,
                )
        except AttributeError:
            self._set_log_viewer(
                ["--- Discord Service Not Available ---"],
                is_discord=False,
                scroll_to_bottom=True,
            )
        except (RuntimeError, OSError) as e:
            self._set_log_viewer(
                [f"--- Error Toggling Discord Bot: {e} ---"],
                is_discord=False,
                scroll_to_bottom=True,
            )

    def _toggle_mod(self) -> None:
        """Toggle mod enabled state."""
        state = self.state_manager.state
        if not state.ui_state.mods:
            return

        mod = state.ui_state.mods[state.ui_state.selected_mod_idx]
        new_state = not mod["enabled"]
        if self.mod_manager.toggle_mod(mod["id"], new_state, "Master"):
            mod["enabled"] = new_state
            # Refresh mods list
            state.ui_state.mods = self.mod_manager.list_mods("Master")

    def _prompt_add_mod(self) -> None:
        """Prompt for mod ID to add."""
        mod_id = self.renderer.popup_manager.text_input_popup("Enter Workshop ID")
        if mod_id:
            # Handle both raw ID and workshop- prefix
            if not mod_id.startswith("workshop-"):
                mod_id = f"workshop-{mod_id}"

            if self.mod_manager.add_mod(mod_id, "Master"):
                # Refresh mods list
                self.state_manager.state.ui_state.mods = self.mod_manager.list_mods(
                    "Master"
                )

    def _handle_update(self) -> None:
        """Handle server update."""
        self._set_log_viewer(["--- Starting Update ---"], is_discord=False)

        def update_worker():
            try:
                proc = self.manager_service.run_updater()
                if proc.stdout:
                    for line in proc.stdout:
                        clean_line = line.strip()
                        if clean_line:
                            self.state_manager.state.ui_state.log_content.append(
                                clean_line
                            )
                            # Auto-scroll to follow logs
                            right_pane = self.renderer.window_manager.get_window(
                                "right_pane"
                            )
                            if right_pane:
                                lh, _ = right_pane.getmaxyx()
                                if (
                                    len(self.state_manager.state.ui_state.log_content)
                                    > lh - 2
                                ):
                                    self.state_manager.state.ui_state.log_scroll_pos = (
                                        len(
                                            self.state_manager.state.ui_state.log_content
                                        )
                                        - (lh - 2)
                                    )
                proc.wait()
                self.state_manager.state.ui_state.log_content.append(
                    "--- Update Complete ---"
                )
            except (OSError, subprocess.SubprocessError) as e:
                self.state_manager.state.ui_state.log_content.append(
                    f"Error during update: {e}"
                )

        self.background_coordinator.run_in_background(update_worker)

    def _handle_logs(self, shard_name: str) -> None:
        """Handle viewing logs."""
        log_content = self.manager_service.get_logs(shard_name, lines=200).split("\n")
        self._set_log_viewer(log_content, is_discord=False)

    def _on_shard_refresh(self, _event: Event) -> None:
        """Handle shard refresh event."""
        self.state_manager.request_redraw()

    def _on_status_update(self, _event: Event) -> None:
        """Handle server status update event."""
        self.state_manager.request_redraw()

    def _on_chat_message(self, event: Event) -> None:
        """Handle chat message event."""
        chat_logs = event.data
        if chat_logs and isinstance(chat_logs, list):
            # The coordinator already handles deduplication and adds new messages
            # to state.ui_state.cached_chat_logs, so we don't need to add them again here
            # Just request a redraw to show the updated chat logs
            pass
        self.state_manager.request_redraw()

    def _on_exit_requested(self, _event: Event) -> None:
        """Handle exit requested event."""
        # This will be handled in the main loop
        pass  # noqa: W0107


def main(stdscr, manager_service=None):
    """Main entry point."""
    try:
        app = TUIApp(stdscr, manager_service)
        app.run()
    except (KeyboardInterrupt, SystemExit):
        pass
