#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Window management for UI components."""

import curses
from typing import Optional


class WindowManager:
    """Manages window layout and creation."""

    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.windows = {}
        self.theme = None
        self.box_chars = None

    def setup_theme(self, theme, box_chars):
        """Setup theme and box characters."""
        self.theme = theme
        self.box_chars = box_chars

    def create_layout(self) -> None:
        """Create the main window layout."""
        try:
            # Clear old windows
            self._clear_old_windows()

            h, w = self.stdscr.getmaxyx()
            target_lw = int(w * 0.45) if w > 120 else w // 2
            lw = max(58, target_lw) if w > 80 else w // 2

            available_h = h - 2  # Reserve space for header and footer

            # Divide left side into 3 equal parts
            part_h = available_h // 3
            status_h = part_h
            shards_h = part_h
            global_h = available_h - status_h - shards_h

            status_y = 1
            shards_y = status_y + status_h
            global_y = shards_y + shards_h

            # Create windows
            self.windows["status"] = curses.newwin(
                max(1, status_h), max(1, lw), status_y, 0
            )
            self.windows["shards"] = curses.newwin(
                max(1, shards_h), max(1, lw), shards_y, 0
            )
            self.windows["global"] = curses.newwin(
                max(1, global_h), max(1, lw), global_y, 0
            )

            self.windows["right_pane"] = curses.newwin(
                max(1, available_h), max(1, w - lw), 1, lw
            )

            # Set backgrounds
            if self.theme:
                for win in self.windows.values():
                    win.bkgd(" ", self.theme.pairs["default"])

        except curses.error:
            pass

    def _clear_old_windows(self) -> None:
        """Clear old windows to prevent memory leakage."""
        for win in self.windows.values():
            if win:
                try:
                    win.erase()
                    win.clear()
                    del win
                except curses.error:
                    pass
        self.windows.clear()

    def get_window(self, name: str) -> Optional[curses.window]:
        """Get a window by name."""
        return self.windows.get(name)

    def draw_box(self, win: curses.window, title: str = "") -> None:
        """Draw a themed box with title on a window."""
        if not self.theme or not self.box_chars:
            return

        try:
            h, w = win.getmaxyx()
            if h < 2 or w < 2:
                return

            win.attron(self.theme.pairs["border"])

            # Corners
            win.addstr(0, 0, self.box_chars.chars["tl"])
            win.addstr(0, w - 1, self.box_chars.chars["tr"])
            win.addstr(h - 1, 0, self.box_chars.chars["bl"])
            try:
                win.addstr(h - 1, w - 1, self.box_chars.chars["br"])
            except curses.error:
                try:
                    win.insstr(h - 1, w - 1, self.box_chars.chars["br"])
                except curses.error:
                    pass

            # Lines
            for x in range(1, w - 1):
                win.addstr(0, x, self.box_chars.chars["h"])
                win.addstr(h - 1, x, self.box_chars.chars["h"])
            for y in range(1, h - 1):
                win.addstr(y, 0, self.box_chars.chars["v"])
                win.addstr(y, w - 1, self.box_chars.chars["v"])
            win.attroff(self.theme.pairs["border"])

            if title and w > len(title) + 4:
                win.addstr(
                    0, 2, f" {title} ", self.theme.pairs["title"] | curses.A_BOLD
                )
        except curses.error:
            pass

    def refresh_all(self) -> None:
        """Refresh all windows."""
        try:
            self.stdscr.noutrefresh()
            for win in self.windows.values():
                if win:
                    win.touchwin()
                    win.noutrefresh()
            curses.doupdate()
        except curses.error:
            pass
