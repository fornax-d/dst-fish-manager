#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Main TUI application."""

import curses
import signal
import time

from core.background.coordinator import BackgroundCoordinator
from core.events.bus import Event, EventBus, EventType
from core.plugins.manager import PluginManager
from core.state.app_state import ServerStatus, StateManager
from features.mods.mod_manager import ModManager
from features.shards.shard_manager import ShardManager
from services.manager_service import ManagerService
from ui.input.handler import InputHandler
from ui.rendering.renderer import Renderer


class TUIApp:  # pylint: disable=too-many-instance-attributes, too-few-public-methods
    """Main TUI application class."""

    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.state_manager = StateManager()
        self.event_bus = EventBus()

        self.mod_manager = ModManager()
        self.status_manager = self.mod_manager.status_manager

        self.manager_service = ManagerService(self.status_manager)

        self.shard_manager = ShardManager()
        self.plugin_manager = PluginManager(self.manager_service, self.event_bus)

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

        # Start server status monitoring
        self.status_manager.start_monitoring(update_interval=10)

        self.background_coordinator = BackgroundCoordinator(
            self.state_manager,
            self.event_bus,
            self.manager_service,
            self.status_manager,
            self.plugin_manager,
        )

        # Setup callbacks
        self._setup_callbacks()

        # Setup event subscriptions
        self._setup_event_subscriptions()

        # Initialize curses
        self._setup_curses()

        # Start background coordinator
        self.background_coordinator.start()

        # Initialize and start plugins
        self.plugin_manager.discover_plugins()
        self.plugin_manager.start_all()

        # Register signal handler for resize
        signal.signal(signal.SIGWINCH, self._handle_sigwinch)

    def _handle_sigwinch(self, _signum, _frame):
        """Handle window resize signal."""
        # This will unblock getch and cause the loop to iterate
        try:
            curses.endwin()
            self.state_manager.request_redraw()
        except Exception:  # pylint: disable=broad-exception-caught
            pass

    def _setup_curses(self) -> None:
        """Setup curses settings."""
        curses.curs_set(0)
        # Use timeout instead of nodelay to reduce CPU usage and handle signals better
        self.stdscr.timeout(100)

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
            "validate_mod", self._validate_selected_mod
        )
        self.input_handler.register_action_callback("fix_mod", self._fix_selected_mod)
        self.input_handler.register_action_callback(
            "show_stats", self._show_server_stats
        )
        self.input_handler.register_action_callback("resize", self._handle_resize)
        self.input_handler.register_action_callback("toggle_mod", self._toggle_mod)
        self.input_handler.register_action_callback("add_mod", self._prompt_add_mod)

    def _open_settings(self) -> None:
        """Open settings popup."""
        # This will be handled by the settings popup in input handler

    def _setup_event_subscriptions(self) -> None:
        """Setup event bus subscriptions."""
        self.event_bus.subscribe(EventType.SHARD_REFRESH, self._on_shard_refresh)
        self.event_bus.subscribe(EventType.SERVER_STATUS_UPDATE, self._on_status_update)
        self.event_bus.subscribe(EventType.CHAT_MESSAGE, self._on_chat_message)
        self.event_bus.subscribe(EventType.EXIT_REQUESTED, self._on_exit_requested)

    def run(self) -> None:
        """Main application loop."""
        running = True
        status_update_counter = 0

        # Initial shard loading
        self.background_coordinator.run_in_background(lambda: None)

        while running:
            current_time = time.time()
            state = self.state_manager.state

            # Process input
            if self.input_handler.process_input(self.stdscr):
                running = False
                continue

            # Periodic status update for WORLD STATUS panel
            status_update_counter += 1
            if status_update_counter >= 50:  # Update every ~5 seconds
                # Update server status
                status_dict = self.status_manager.get_server_status()

                self.state_manager.state.server_status = ServerStatus(
                    season=status_dict.get("season", "Unknown"),
                    day=status_dict.get("day", "Unknown"),
                    days_left=status_dict.get("days_left", "Unknown"),
                    phase=status_dict.get("phase", "Unknown"),
                    players=status_dict.get("players", []),
                    memory_usage=self.status_manager.get_memory_usage(),
                )

                # Update shards status
                shards = self.shard_manager.get_shards()
                self.state_manager.update_shards(shards)

                status_update_counter = 0

            # Draw if needed (at most 30 FPS)
            if state.ui_state.need_redraw and (
                current_time - state.timing_state.last_draw_time > 0.033
            ):
                try:
                    self.renderer.render()
                except curses.error:
                    pass
                except Exception:  # pylint: disable=broad-exception-caught
                    # Log error but keep running
                    pass

                self.state_manager.clear_redraw_flag()
                self.state_manager.update_timing(last_draw_time=current_time)

        # Cleanup
        self.background_coordinator.stop()
        self.plugin_manager.stop_all()

    def _execute_action(self) -> None:
        """Execute the selected action."""
        state = self.state_manager.state

        if state.ui_state.is_working:
            return

        if state.ui_state.selection_state.selected_global_action_idx != -1:
            # Global action
            actions = [
                "start",
                "stop",
                "enable",
                "disable",
                "restart",
                "update",
                "token",
            ]
            action = actions[state.ui_state.selection_state.selected_global_action_idx]

            if action == "update":
                self._handle_update()
            elif action == "token":
                self._handle_token()
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

            shard = shards[state.ui_state.selection_state.selected_shard_idx]
            actions = ["start", "stop", "restart", "actions", "logs"]
            action = actions[state.ui_state.selection_state.selected_action_idx]

            if action == "logs":
                self._handle_logs(shard.name)
            elif action == "actions":
                self._handle_shard_actions(shard.name)
            else:
                self.background_coordinator.run_in_background(
                    self.manager_service.control_shard, shard.name, action
                )

    def _handle_shard_actions(self, shard_name: str) -> None:
        """Handle shard advanced actions."""
        options = ["Rollback (1 day)", "Force Save", "Regenerate World"]
        selection = self.renderer.popup_manager.choice_popup("Shard Actions", options)

        if selection is None:
            return

        if selection == 0:  # Rollback
            self.background_coordinator.run_in_background(
                self.manager_service.rollback_shard, shard_name, 1
            )
        elif selection == 1:  # Save
            self.background_coordinator.run_in_background(
                self.manager_service.save_shard, shard_name
            )
        elif selection == 2:  # Regenerate
            # Confirm regeneration
            confirm = self.renderer.popup_manager.choice_popup(
                f"Regenerate {shard_name}?", ["No, cancel", "Yes, DESTROY and reset"]
            )
            if confirm == 1:
                self.background_coordinator.run_in_background(
                    self.manager_service.reset_shard, shard_name
                )

    def _toggle_enable(self) -> None:
        """Toggle shard enable state."""
        state = self.state_manager.state

        if (
            state.ui_state.is_working
            or state.ui_state.selection_state.selected_global_action_idx != -1
        ):
            return

        shards = self.state_manager.get_shards_copy()
        if not shards:
            return

        shard = shards[state.ui_state.selection_state.selected_shard_idx]
        action = "disable" if shard.is_enabled else "enable"
        self.background_coordinator.run_in_background(
            self.manager_service.control_shard, shard.name, action
        )

    def _prompt_chat(self) -> None:
        """Prompt for chat message."""
        message = self.renderer.popup_manager.text_input_popup("Chat:", width=60)
        if message:
            success, _ = self.manager_service.send_chat_message(
                "Master", f"[SSH God] {message}"
            )
            if not success:
                # Could show error popup here
                pass

    def _open_mods(self) -> None:
        """Open mods viewer with enhanced status."""
        # Start auto-refresh for mods
        self.mod_manager.start_auto_refresh(interval=30)

        # Get mods with enhanced status
        mods = self.mod_manager.list_mods_with_status("Master")
        self.state_manager.state.ui_state.mods = mods
        self.state_manager.state.ui_state.viewer_state.mods_viewer_active = True
        self.state_manager.state.ui_state.selection_state.selected_mod_idx = 0

    def _handle_resize(self) -> None:
        """Handle terminal resize."""
        if hasattr(curses, "update_lines_cols"):
            curses.update_lines_cols()

        self.stdscr.clear()
        self.stdscr.refresh()
        self.renderer.window_manager.create_layout()
        self.state_manager.request_redraw()

    def _toggle_mod(self) -> None:
        """Toggle mod enabled state."""
        state = self.state_manager.state
        if not state.ui_state.mods:
            return

        mod = state.ui_state.mods[state.ui_state.selection_state.selected_mod_idx]
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
                self.state_manager.state.ui_state.mods = (
                    self.mod_manager.list_mods_with_status("Master")
                )

    def _validate_selected_mod(self) -> None:
        """Validate selected mod configuration."""
        state = self.state_manager.state
        if not state.ui_state.mods:
            return

        mod = state.ui_state.mods[state.ui_state.selection_state.selected_mod_idx]
        validation = self.mod_manager.validate_mod_configuration(mod["id"], "Master")

        # Show validation results in log
        log_content = [f"=== Validation for {mod.get('name', mod['id'])} ==="]

        if validation["valid"]:
            log_content.append("✅ Configuration is valid")
        else:
            log_content.append("❌ Configuration has issues:")
            for error in validation["errors"]:
                log_content.append(f"   • {error}")

        if validation["warnings"]:
            log_content.append("⚠️ Warnings:")
            for warning in validation["warnings"]:
                log_content.append(f"   • {warning}")

        if validation["suggestions"]:
            log_content.append("💡 Suggestions:")
            for suggestion in validation["suggestions"]:
                log_content.append(f"   • {suggestion}")

        self.state_manager.state.ui_state.viewer_state.log_content = log_content
        self.state_manager.state.ui_state.viewer_state.log_viewer_active = True
        self.state_manager.state.ui_state.viewer_state.log_scroll_pos = 0

    def _fix_selected_mod(self) -> None:
        """Fix common issues for selected mod."""
        state = self.state_manager.state
        if not state.ui_state.mods:
            return

        mod = state.ui_state.mods[state.ui_state.selection_state.selected_mod_idx]
        fix_result = self.mod_manager.fix_common_mod_issues(mod["id"], "Master")

        # Show fix results in log
        log_content = [f"=== Fix attempt for {mod.get('name', mod['id'])} ==="]

        if fix_result["success"]:
            log_content.append("✅ Fixed successfully!")
            if fix_result["fixed"]:
                log_content.append("Fixed issues:")
                for fix in fix_result["fixed"]:
                    log_content.append(f"   • {fix}")
        else:
            log_content.append("❌ Some issues remain:")
            for issue in fix_result["remaining_issues"]:
                log_content.append(f"   • {issue}")

        # Refresh mods list
        self.state_manager.state.ui_state.mods = self.mod_manager.list_mods_with_status(
            "Master"
        )

        self.state_manager.state.ui_state.viewer_state.log_content = log_content
        self.state_manager.state.ui_state.viewer_state.log_viewer_active = True
        self.state_manager.state.ui_state.viewer_state.log_scroll_pos = 0

    def _show_server_stats(self) -> None:
        """Show server and mod statistics."""
        summary = self.mod_manager.get_server_stats_summary()

        # Format server stats for display
        mod_summary = summary["mod_summary"]
        log_content = ["=== Mod Summary ==="]
        log_content.append(f"📦 Total mods: {mod_summary['total_mods']}")
        log_content.append(f"✅ Enabled: {mod_summary['enabled_mods']}")
        log_content.append(f"🎮 Loaded in game: {mod_summary['loaded_mods']}")
        log_content.append(f"❌ With errors: {mod_summary['mods_with_errors']}")

        self.state_manager.state.ui_state.viewer_state.log_content = log_content
        self.state_manager.state.ui_state.viewer_state.log_viewer_active = True
        self.state_manager.state.ui_state.viewer_state.log_scroll_pos = 0

    def _handle_update(self) -> None:
        """Handle server update."""
        self.state_manager.state.ui_state.viewer_state.log_content = [
            "--- Starting Update ---"
        ]
        self.state_manager.state.ui_state.viewer_state.log_viewer_active = True
        self.state_manager.state.ui_state.viewer_state.log_scroll_pos = 0

        self.background_coordinator.run_in_background(self._perform_update_task)

    def _perform_update_task(self) -> None:
        """Background task for performing update."""
        try:
            proc = self.manager_service.run_updater()
            if proc.stdout:
                for line in proc.stdout:
                    self._process_update_line(line)

            proc.wait()
            self.state_manager.state.ui_state.viewer_state.log_content.append(
                "--- Update Complete ---"
            )
        except Exception as e:  # pylint: disable=broad-exception-caught
            self.state_manager.state.ui_state.viewer_state.log_content.append(
                f"Error during update: {e}"
            )

    def _handle_token(self) -> None:
        """Handle cluster token update."""
        token = self.renderer.popup_manager.text_input_popup(
            "Enter Cluster Token", width=60
        )
        if token:
            if self.manager_service.update_cluster_token(token):
                # Show success message in log (or popup)
                self.state_manager.state.ui_state.viewer_state.log_content = [
                    "Checking server status...",
                    "Cluster token updated successfully!",
                ]
                self.state_manager.state.ui_state.viewer_state.log_viewer_active = True
                self.state_manager.state.ui_state.viewer_state.log_scroll_pos = 0
            else:
                self.state_manager.state.ui_state.viewer_state.log_content = [
                    "Checking server status...",
                    "Failed to update cluster token.",
                ]
                self.state_manager.state.ui_state.viewer_state.log_viewer_active = True
                self.state_manager.state.ui_state.viewer_state.log_scroll_pos = 0

    def _process_update_line(self, line: str) -> None:
        """Process a single line of output from the updater."""
        clean_line = line.strip()
        if not clean_line:
            return

        self.state_manager.state.ui_state.viewer_state.log_content.append(clean_line)
        # Auto-scroll to follow logs
        right_pane = self.renderer.window_manager.get_window("right_pane")
        if right_pane:
            lh, _ = right_pane.getmaxyx()
            if len(self.state_manager.state.ui_state.viewer_state.log_content) > lh - 2:
                self.state_manager.state.ui_state.viewer_state.log_scroll_pos = len(
                    self.state_manager.state.ui_state.viewer_state.log_content
                ) - (lh - 2)

    def _handle_logs(self, shard_name: str) -> None:
        """Handle viewing logs."""
        log_content = self.manager_service.get_logs(shard_name, lines=200).split("\n")
        self.state_manager.state.ui_state.viewer_state.log_content = log_content
        self.state_manager.state.ui_state.viewer_state.log_viewer_active = True
        self.state_manager.state.ui_state.viewer_state.log_scroll_pos = 0

    def _on_shard_refresh(self, _event: Event) -> None:
        """Handle shard refresh event."""
        # Refresh shards from ShardManager and update state
        shards = self.shard_manager.get_shards()
        self.state_manager.update_shards(shards)
        self.state_manager.request_redraw()

    def _on_status_update(self, _event: Event) -> None:
        """Handle server status update event."""
        # Update server status in state from StatusManager
        status_dict = self.status_manager.get_server_status()

        self.state_manager.state.server_status = ServerStatus(
            season=status_dict.get("season", "Unknown"),
            day=status_dict.get("day", "Unknown"),
            days_left=status_dict.get("days_left", "Unknown"),
            phase=status_dict.get("phase", "Unknown"),
            players=status_dict.get("players", []),
            memory_usage=self.status_manager.get_memory_usage(),
        )
        self.state_manager.request_redraw()

    def _on_chat_message(self, _event: Event) -> None:
        """Handle chat message event."""
        self.state_manager.request_redraw()

    def _on_exit_requested(self, event: Event) -> None:
        """Handle exit requested event."""
        # This will be handled in the main loop


def main(stdscr):
    """Main entry point."""
    try:
        app = TUIApp(stdscr)
        app.run()
    except Exception as e:  # pylint: disable=broad-exception-caught
        # Cleanup and show error
        curses.endwin()
        print(f"An error occurred: {e}")
