#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Input handler with settings support."""

import curses
from typing import TYPE_CHECKING, Optional

from core.events.bus import Event, EventBus, EventType
from core.state.app_state import StateManager

if TYPE_CHECKING:
    from ui.app import TUIApp


class InputHandler:
    """Input handler with settings support."""

    def __init__(
        self, state_manager: StateManager, event_bus: EventBus, theme, popup_manager
    ):
        self.state_manager = state_manager
        self.event_bus = event_bus
        self.theme = theme
        self.popup_manager = popup_manager

        self.action_callbacks = {}
        self._app: Optional["TUIApp"] = None  # Back-reference to app
        self._setup_keymap()

    def _setup_keymap(self):
        """Setup key mappings."""
        self.keymap = {
            # Navigation
            curses.KEY_UP: self._handle_up,
            curses.KEY_DOWN: self._handle_down,
            curses.KEY_LEFT: self._handle_left,
            curses.KEY_RIGHT: self._handle_right,
            # Actions
            ord("\n"): self._handle_enter,
            ord("e"): self._handle_enable,
            ord("c"): self._handle_chat,
            ord("m"): self._handle_mods,
            ord("v"): self._handle_validate,
            ord("f"): self._handle_fix,
            ord("s"): self._handle_settings,
            ord("i"): self._handle_stats,
            ord("q"): self._handle_quit,
            27: self._handle_quit,  # Esc
            # Special
            curses.KEY_RESIZE: self._handle_resize,
        }

    def register_action_callback(self, action: str, callback) -> None:
        """Register a callback for an action."""
        self.action_callbacks[action] = callback

    def process_input(self, stdscr) -> bool:
        """
        Process all pending input.
        Returns True if exit requested, False otherwise.
        """
        state = self.state_manager.state

        while True:
            try:
                key = stdscr.getch()
            except curses.error:
                key = -1

            if key == -1:
                break

            self.state_manager.request_redraw()

            # Handle special modes
            if state.ui_state.viewer_state.log_viewer_active:
                if self._handle_log_viewer_input(key):
                    continue
            elif state.ui_state.viewer_state.mods_viewer_active:
                if self._handle_mods_input(key):
                    continue

            # Handle normal input
            handler = self.keymap.get(key)
            if handler:
                should_exit = handler(stdscr, key)
                if should_exit:
                    return True

        return False

    def _handle_up(self, _stdscr, _key) -> bool:
        """Handle up arrow key."""
        state = self.state_manager.state
        if state.ui_state.selection_state.selected_global_action_idx != -1:
            # From GLOBAL to SHARDS
            if state.ui_state.selection_state.selected_global_action_idx < 2:
                state.ui_state.selection_state.selected_global_action_idx = -1
            else:
                state.ui_state.selection_state.selected_global_action_idx -= 2
        else:
            state.ui_state.selection_state.selected_shard_idx = max(
                0, state.ui_state.selection_state.selected_shard_idx - 1
            )
        return False

    def _handle_down(self, _stdscr, _key) -> bool:
        """Handle down arrow key."""
        state = self.state_manager.state
        shards = self.state_manager.get_shards_copy()

        if state.ui_state.selection_state.selected_global_action_idx != -1:
            if state.ui_state.selection_state.selected_global_action_idx >= 4:
                pass  # Last row, nowhere to go
            else:
                state.ui_state.selection_state.selected_global_action_idx += 2
        elif (
            shards
            and state.ui_state.selection_state.selected_shard_idx == len(shards) - 1
        ):
            # From SHARDS to GLOBAL
            state.ui_state.selection_state.selected_global_action_idx = 0
        elif shards:
            state.ui_state.selection_state.selected_shard_idx += 1
        return False

    def _handle_left(self, _stdscr, _key) -> bool:
        """Handle left arrow key."""
        state = self.state_manager.state
        if state.ui_state.selection_state.selected_global_action_idx != -1:
            state.ui_state.selection_state.selected_global_action_idx = (
                state.ui_state.selection_state.selected_global_action_idx - 1
            ) % 7
        else:
            state.ui_state.selection_state.selected_action_idx = (
                state.ui_state.selection_state.selected_action_idx - 1
            ) % 5
        return False

    def _handle_right(self, _stdscr, _key) -> bool:
        """Handle right arrow key."""
        state = self.state_manager.state
        if state.ui_state.selection_state.selected_global_action_idx != -1:
            state.ui_state.selection_state.selected_global_action_idx = (
                state.ui_state.selection_state.selected_global_action_idx + 1
            ) % 7
        else:
            state.ui_state.selection_state.selected_action_idx = (
                state.ui_state.selection_state.selected_action_idx + 1
            ) % 5
        return False

    def _handle_enter(self, _stdscr, _key) -> bool:
        """Handle Enter key."""
        callback = self.action_callbacks.get("execute_action")
        if callback:
            callback()
        return False

    def _handle_enable(self, _stdscr, _key) -> bool:
        """Handle 'e' key for enable/disable."""
        callback = self.action_callbacks.get("toggle_enable")
        if callback:
            callback()
        return False

    def _handle_chat(self, _stdscr, _key) -> bool:
        """Handle 'c' key for chat."""
        callback = self.action_callbacks.get("prompt_chat")
        if callback:
            callback()
        return False

    def _handle_mods(self, _stdscr, _key) -> bool:
        """Handle 'm' key for mods."""
        callback = self.action_callbacks.get("open_mods")
        if callback:
            callback()
        return False

    def _handle_stats(self, _stdscr, _key) -> bool:
        """Handle 'i' key for statistics."""
        callback = self.action_callbacks.get("show_stats")
        if callback:
            callback()
        return False

    def _handle_settings(self, _stdscr, _key) -> bool:
        """Handle 's' key for settings."""
        result = self.popup_manager.settings_popup()
        if result:
            # Settings were applied successfully
            pass
        return False  # Don't consume the key - let normal processing continue

    def _handle_validate(self, _stdscr, _key) -> bool:
        """Handle 'v' key for mod validation."""
        callback = self.action_callbacks.get("validate_mod")
        if callback:
            callback()
        return False

    def _handle_fix(self, _stdscr, _key) -> bool:
        """Handle 'f' key for fixing mods."""
        callback = self.action_callbacks.get("fix_mod")
        if callback:
            callback()
        return False

    def _handle_quit(self, _stdscr, _key) -> bool:
        """Handle quit keys."""
        state = self.state_manager.state
        if state.ui_state.viewer_state.log_viewer_active:
            state.ui_state.viewer_state.log_viewer_active = False
        elif state.ui_state.viewer_state.mods_viewer_active:
            state.ui_state.viewer_state.mods_viewer_active = False

        else:
            self.event_bus.publish(Event(EventType.EXIT_REQUESTED))
            return True
        return False

    def _handle_resize(self, _stdscr, _key) -> bool:
        """Handle terminal resize."""
        callback = self.action_callbacks.get("resize")
        if callback:
            callback()
        return False

    def _handle_log_viewer_input(self, key) -> bool:
        """Handle input in log viewer mode."""
        state = self.state_manager.state
        if key == curses.KEY_DOWN:
            max_scroll = max(0, len(state.ui_state.viewer_state.log_content) - 1)
            state.ui_state.viewer_state.log_scroll_pos = min(
                max_scroll, state.ui_state.viewer_state.log_scroll_pos + 1
            )
            return True
        if key == curses.KEY_UP:
            state.ui_state.viewer_state.log_scroll_pos = max(
                0, state.ui_state.viewer_state.log_scroll_pos - 1
            )
            return True
        if key == curses.KEY_LEFT:
            state.ui_state.viewer_state.log_viewer_active = False
            return True
        return False

    def _handle_mods_input(self, key) -> bool:
        """Handle input in mods viewer mode."""
        state = self.state_manager.state
        if key == curses.KEY_UP:
            state.ui_state.selection_state.selected_mod_idx = max(
                0, state.ui_state.selection_state.selected_mod_idx - 1
            )
            return True
        if key == curses.KEY_DOWN:
            if state.ui_state.mods:
                state.ui_state.selection_state.selected_mod_idx = min(
                    len(state.ui_state.mods) - 1,
                    state.ui_state.selection_state.selected_mod_idx + 1,
                )
            return True
        if key == ord("\n"):
            callback = self.action_callbacks.get("toggle_mod")
            if callback:
                callback()
            return True
        if key == ord("a"):
            callback = self.action_callbacks.get("add_mod")
            if callback:
                callback()
            return True
        if key in [ord("q"), 27, ord("m"), curses.KEY_LEFT]:
            state.ui_state.viewer_state.mods_viewer_active = False
            return True
        return False
