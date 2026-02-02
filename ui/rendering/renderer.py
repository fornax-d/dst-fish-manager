#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Main renderer for the TUI."""

import curses
from typing import TYPE_CHECKING, Optional

from core.state.app_state import StateManager
from ui.components.popups import PopupManager
from ui.components.windows import WindowManager
from ui.rendering.themes import BoxChars, Theme
from utils.helpers import truncate_string

if TYPE_CHECKING:
    from ui.app import TUIApp


class Renderer:  # pylint: disable=too-few-public-methods
    """Main renderer for the TUI application."""

    def __init__(self, stdscr, state_manager: StateManager):
        self.stdscr = stdscr
        self.state_manager = state_manager
        self.theme = Theme()
        self.box_chars = BoxChars()

        self.window_manager = WindowManager(stdscr)
        self.window_manager.setup_theme(self.theme, self.box_chars)
        self.popup_manager = PopupManager(stdscr, self.theme)

        self.window_manager.create_layout()

        # Store reference to app for settings access
        self._app: Optional["TUIApp"] = None

    def render(self) -> None:
        """Main render method."""

        # Check minimum terminal size safely
        try:
            h, w = self.stdscr.getmaxyx()
        except curses.error:
            return

        # If detached or invalid size, skip rendering
        if h <= 0 or w <= 0:
            return

        if h < 12 or w < 40:
            self._render_too_small()
            return

        # Set background for main screen
        self.stdscr.bkgd(" ", self.theme.pairs["default"])

        # Clear all windows
        self._clear_all_windows()

        # Render components
        self._render_header(w)
        self._render_status()
        self._render_shards()
        self._render_global_controls()
        self._render_right_pane()
        self._render_footer(h, w)

        # Refresh all
        self.window_manager.refresh_all()

    def _draw_mods_box(self, win) -> None:
        """Draw mods management box with proper borders."""
        self.window_manager.draw_box(win, "MODS MANAGEMENT")

    def _draw_logs_box(self, win, title: str) -> None:
        """Draw logs box with proper borders."""
        self.window_manager.draw_box(win, title)

    def _render_too_small(self) -> None:
        """Render message when terminal is too small."""
        h, w = self.stdscr.getmaxyx()
        self.stdscr.clear()
        self.stdscr.bkgd(" ", self.theme.pairs["default"])
        msg = "Terminal too small"
        start_x = (w - len(msg)) // 2
        start_y = h // 2
        if start_y >= 0 and start_x >= 0 and start_x + len(msg) < w:
            self.stdscr.addstr(start_y, start_x, msg, self.theme.pairs["error"])
        self.stdscr.refresh()

    def _clear_all_windows(self) -> None:
        """Clear all windows."""
        self.stdscr.erase()
        for win in self.window_manager.windows.values():
            if win:
                win.erase()

    def _render_header(self, w: int) -> None:
        """Render the header."""
        state = self.state_manager.state
        title = "DST FISH MANAGER"
        if state.ui_state.is_working:
            title += " [WAITING...]"

        # Clear header line with background color
        try:
            self.stdscr.move(0, 0)
            self.stdscr.clrtoeol()
            self.stdscr.bkgd(" ", self.theme.pairs["default"])
            self.stdscr.addstr(0, 0, " " * w, self.theme.pairs["default"])
        except curses.error:
            pass

        start_x = (w - len(title)) // 2
        if start_x > 0 and start_x + len(title) < w and w > len(title):
            self.stdscr.addstr(
                0, start_x, title, self.theme.pairs["title"] | curses.A_BOLD
            )

    SEASON_EMOJIS = {
        "autumn": "🍂",
        "winter": "❄️",
        "spring": "🌱",
        "summer": "☀️",
    }
    PHASE_EMOJIS = {
        "day": "☀️",
        "dusk": "🌆",
        "night": "🌙",
    }

    def _render_status(self) -> None:
        """Render server status window."""
        win = self.window_manager.get_window("status")
        if not win:
            return

        self.window_manager.draw_box(win, "WORLD STATUS")

        h, w = win.getmaxyx()
        if h < 3 or w < 10:
            return

        state = self.state_manager.state
        status = state.server_status

        # Clear content area with proper width
        for y in range(1, h - 1):
            try:
                win.addstr(y, 1, " " * (w - 2), self.theme.pairs["default"])
            except curses.error:
                pass

        try:
            season = status.season
            phase = status.phase

            s_emoji = self.SEASON_EMOJIS.get(season.lower(), "❓")
            p_emoji = self.PHASE_EMOJIS.get(phase.lower(), "❓")

            # Line 1: Season: Emoji | Day: ...
            line1 = f"Season: {s_emoji} | Day: {status.day}"
            if w > len(line1) + 4:
                line1 += f" ({status.days_left} left)"

            # Line 2: Phase: Emoji | Players: X
            line2 = f"Phase: {p_emoji} | Players: {len(status.players)}"

            win.addstr(1, 2, truncate_string(line1, w - 4), self.theme.pairs["default"])
            if h >= 3:
                win.addstr(
                    2, 2, truncate_string(line2, w - 4), self.theme.pairs["default"]
                )

            # List players starting from line 3
            if h > 4:
                self._render_player_list(win, status.players, (3, h, w))

        except curses.error:
            pass

    def _render_player_list(self, win, players, layout_info) -> None:
        """Render list of players in status window."""
        if not players:
            return

        start_y, h, w = layout_info
        max_players_to_show = h - 4
        for i, p in enumerate(players):
            if i < max_players_to_show - 1 or (
                i == max_players_to_show - 1 and len(players) == max_players_to_show
            ):
                p_line = f"  {p['name']} - {p['char']}"
                try:
                    win.addstr(
                        start_y + i,
                        2,
                        truncate_string(p_line, w - 4),
                        self.theme.pairs["default"],
                    )
                except curses.error:
                    pass
            else:
                remaining = len(players) - i
                try:
                    win.addstr(
                        start_y + i,
                        2,
                        f"  ... and {remaining} more",
                        self.theme.pairs["default"],
                    )
                except curses.error:
                    pass
                break

    def _render_shards(self) -> None:
        """Render shards window."""
        win = self.window_manager.get_window("shards")
        if not win:
            return

        self.window_manager.draw_box(win, "SHARDS")

        state = self.state_manager.state
        shards = self.state_manager.get_shards_copy()

        wh, ww = win.getmaxyx()
        if not shards:
            if ww > 20:
                win.addstr(1, 2, "Loading shards...", self.theme.pairs["title"])
            return

        for i, shard in enumerate(shards):
            try:
                if i >= wh - 2:
                    break

                marker = (
                    ">"
                    if (
                        i == state.ui_state.selection_state.selected_shard_idx
                        and state.ui_state.selection_state.selected_global_action_idx
                        == -1
                    )
                    else " "
                )
                win.addstr(i + 1, 1, marker, self.theme.pairs["title"])

                if ww < 14:
                    continue

                display_name = truncate_string(shard.name, 10)
                win.addstr(i + 1, 2, display_name)

                # Status
                status_color = (
                    self.theme.pairs["success"]
                    if shard.is_running
                    else self.theme.pairs["error"]
                )
                status_icon = "●" if shard.is_running else "○"
                win.addstr(i + 1, 13, status_icon, status_color)

                self._render_shard_controls(win, i, ww, state)

            except curses.error:
                pass

    def _render_shard_controls(self, win, shard_idx: int, ww: int, state) -> None:
        """Render shard control buttons."""
        actions = ["🚀 Start", "🛑 Stop", "🔄 Restart", "⚡ Actions", "📜 Logs"]

        for j, label in enumerate(actions):
            btn_col = 14 + j * 11
            if btn_col + len(label) + 3 >= ww:
                break

            style = self.theme.pairs["default"]
            if (
                shard_idx == state.ui_state.selection_state.selected_shard_idx
                and j == state.ui_state.selection_state.selected_action_idx
                and state.ui_state.selection_state.selected_global_action_idx == -1
            ):
                style = self.theme.pairs["highlight"]

            try:
                win.addstr(shard_idx + 1, btn_col, f" {label} ", style)
            except curses.error:
                pass

    def _render_global_controls(self) -> None:
        """Render cluster management window."""
        win = self.window_manager.get_window("global")
        if not win:
            return

        self.window_manager.draw_box(win, "CLUSTER MANAGEMENT")

        state = self.state_manager.state
        gl_actions = [
            ("Start", 3),  # success green
            ("Stop", 4),  # error red
            ("Enable", 3),  # success green
            ("Disable", 4),  # error red
            ("Restart", 5),  # warning yellow
            ("Update", 2),  # title cyan
            ("Token", 2),  # title cyan
        ]

        for i, (label, color_num) in enumerate(gl_actions):
            try:
                gh, gw = win.getmaxyx()
                row = 1 + (i // 2)
                col = 2 + (i % 2) * 19

                if row >= gh - 1 or col + len(label) + 2 >= gw:
                    continue

                # Map color pair numbers to theme names
                color_map = {
                    2: "title",
                    3: "success",
                    4: "error",
                    5: "warning",
                    6: "border",
                }
                theme_color = color_map.get(color_num, "default")
                style = self.theme.pairs[theme_color]
                if i == state.ui_state.selection_state.selected_global_action_idx:
                    style = self.theme.pairs["highlight"]

                marker = (
                    ">"
                    if i == state.ui_state.selection_state.selected_global_action_idx
                    else " "
                )
                win.addstr(row, col, f"{marker}{label}", style)
            except curses.error:
                pass

    def _render_right_pane(self) -> None:
        """Render right pane (logs/mods/chat)."""
        win = self.window_manager.get_window("right_pane")
        if not win:
            return

        state = self.state_manager.state

        if state.ui_state.viewer_state.mods_viewer_active:
            self._draw_mods_box(win)
            self._render_mods(win)
        else:
            right_pane_title = (
                "LOGS" if state.ui_state.viewer_state.log_viewer_active else "CHAT LOGS"
            )
            self._draw_logs_box(win, right_pane_title)
            self._render_logs_pane(win)

    def _render_mods(self, win) -> None:
        """Render mods list."""
        state = self.state_manager.state
        mods = state.ui_state.mods

        for i, mod in enumerate(mods):
            try:
                wh, ww = win.getmaxyx()
                if i >= wh - 2:
                    break

                marker = (
                    ">" if i == state.ui_state.selection_state.selected_mod_idx else " "
                )
                win.addstr(i + 1, 1, marker, self.theme.pairs["title"])

                # Status - enhanced with mod status colors
                status_color = self._get_mod_status_color(mod)
                status_text = self._get_mod_status_text(mod)
                win.addstr(i + 1, 3, status_text, status_color)

                # Mod Name/ID
                display_name = mod.get("name", mod["id"])
                win.addstr(i + 1, 14, truncate_string(display_name, ww - 16))

                if i == state.ui_state.selection_state.selected_mod_idx:
                    win.chgat(i + 1, 1, ww - 2, self.theme.pairs["highlight"])

            except curses.error:
                pass

    def _get_mod_status_color(self, mod) -> int:
        """Get color for mod status based on new status fields."""
        if mod.get("error_count", 0) > 0:
            return self.theme.pairs["error"]  # Red for errors
        if not mod.get("configuration_valid", True):
            return self.theme.pairs["warning"]  # Yellow for config issues
        if mod.get("loaded_in_game", False) and mod.get("enabled", False):
            return self.theme.pairs["success"]  # Green for loaded and enabled
        if mod.get("enabled", False) and not mod.get("loaded_in_game", False):
            return self.theme.pairs["info"]  # Cyan for enabled but not loaded

        return self.theme.pairs["default"]  # Default for disabled

    def _get_mod_status_text(self, mod) -> str:
        """Get status text for mod."""
        if mod.get("error_count", 0) > 0:
            error_count = mod["error_count"]
            return f"[ERROR:{error_count}] "
        if not mod.get("configuration_valid", True):
            return "[CONFIG] "
        if mod.get("loaded_in_game", False) and mod.get("enabled", False):
            return "[LOADED] "
        if mod.get("enabled", False):
            return "[ENABLED] "

        return "[DISABLED] "

    def _render_logs_pane(self, win) -> None:
        """Render logs or chat pane."""
        state = self.state_manager.state

        if state.ui_state.viewer_state.log_viewer_active:
            lh, lw_box = win.getmaxyx()
            for i in range(1, lh - 1):
                idx = state.ui_state.viewer_state.log_scroll_pos + i - 1
                if idx < len(state.ui_state.viewer_state.log_content) and lw_box > 2:
                    try:
                        line = state.ui_state.viewer_state.log_content[idx]
                        win.addstr(i, 1, truncate_string(line, lw_box - 2))
                    except curses.error:
                        pass
        else:
            chat_logs = state.ui_state.cached_chat_logs
            lh, lw_box = win.getmaxyx()
            available_width = lw_box - 2

            if chat_logs and len(chat_logs) > 1 and available_width > 0:
                display_lines = (
                    chat_logs[-(lh - 2) :] if len(chat_logs) >= (lh - 2) else chat_logs
                )
                for i, line in enumerate(display_lines):
                    try:
                        y = i + 1
                        if line and len(line) > available_width:
                            line = truncate_string(line, available_width - 3) + "..."
                        win.addstr(y, 1, line, self.theme.pairs["default"])
                    except curses.error:
                        pass
            else:
                self._render_ascii_art(win)

    def _render_ascii_art(self, win) -> None:
        """Render ASCII art when no chat is available."""
        ascii_art = [
            "                    .                             ",
            "         .--. .--+*****=.                         ",
            "        -%#-:===:.. .:-+*=: .....   ..:-:         ",
            "          :++:.:#*:    .+++:.::.  .-====.    ..   ",
            "  .     .++=.:%@%.     :++++::    .---===.  .==:  ",
            " .=:.. -***-.         .+**+*:-=:   ...::-=-=---:  ",
            "  :+:-:=-+*+=..   ..-=+**++*=*=+=:.     ....:::.  ",
            "   :==::-=:-++======+******=-=+*+=*+++-=:         ",
            "   .::--+**=:=-.::=-:::----:==---:.:..            ",
            "      . ...::--==----===-:...:::---:.             ",
            "                             .:-----.            ",
        ]

        lh, lw_box = win.getmaxyx()
        available_width = lw_box - 2

        if lh > len(ascii_art) + 2 and available_width > 50:
            try:
                start_y = (lh - len(ascii_art)) // 2
                start_x = 1 + (available_width - 50) // 2
                for i, line in enumerate(ascii_art):
                    if start_y + i < lh - 1 and start_x + 50 < lw_box:
                        win.addstr(
                            start_y + i, start_x, line, self.theme.pairs["footer"]
                        )
            except curses.error:
                pass
        else:
            info_msg = "Game chat will appear here"
            if lh > 2 and lw_box > len(info_msg) + 2:
                try:
                    start_y = lh // 2
                    start_x = 1 + (available_width - len(info_msg)) // 2
                    win.addstr(start_y, start_x, info_msg, self.theme.pairs["footer"])
                except curses.error:
                    pass

    def _render_footer(self, h: int, w: int) -> None:
        """Render the footer."""
        state = self.state_manager.state

        if state.ui_state.viewer_state.mods_viewer_active:
            footer = " ARROWS:NAV | ENTER:TOGGLE | A:ADD | M:BACK | Q:EXIT "
        else:
            footer = (
                " ARROWS:NAV | ENTER:TOGGLE | S:SETTINGS | M:MODS | C:CHAT | Q:EXIT "
            )

        # Clear footer line with background color (only 1 line - h-1)
        try:
            self.stdscr.move(h - 1, 0)
            self.stdscr.clrtoeol()
            self.stdscr.addstr(h - 1, 0, " " * w, self.theme.pairs["footer"])
        except curses.error:
            pass

        if h > 0 and w > len(footer) + 2:
            self.stdscr.addstr(h - 1, 1, footer, self.theme.pairs["footer"])

        # Render RAM usage in footer
        try:
            ram_val = state.server_status.memory_usage
            ram_str = f"RAM: {ram_val:.0f} MB "
            if w > len(footer) + len(ram_str) + 4:
                self.stdscr.addstr(
                    h - 1, w - len(ram_str) - 1, ram_str, self.theme.pairs["footer"]
                )
        except curses.error:
            pass
