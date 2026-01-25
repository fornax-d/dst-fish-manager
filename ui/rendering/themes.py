#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""UI themes and color management."""

import curses


class Theme:
    """Catppuccin Mocha theme for curses."""

    def __init__(self):
        self.colors = {}
        self._setup_colors()

    def _setup_colors(self):
        """Setup color palette."""
        if curses.can_change_color():
            # Define colors (scaled to 0-1000)
            curses.init_color(10, 117, 117, 180)  # Base (#1e1e2e)
            curses.init_color(11, 803, 839, 956)  # Text (#cdd6f4)
            curses.init_color(12, 705, 745, 996)  # Lavender (#b4befe)
            curses.init_color(13, 650, 890, 631)  # Green (#a6e3a1)
            curses.init_color(14, 952, 545, 658)  # Red (#f38ba8)
            curses.init_color(15, 976, 886, 686)  # Yellow (#f9e2af)
            curses.init_color(16, 192, 196, 266)  # Surface0 (#313244)
            curses.init_color(17, 423, 439, 525)  # Overlay0 (#6c7086)

            self.colors = {
                "bg": 10,
                "fg": 11,
                "title": 12,
                "success": 13,
                "error": 14,
                "warning": 15,
                "highlight_bg": 16,
                "border": 17,
            }
        else:
            # Fallback for terminals that don't support init_color
            self.colors = {
                "bg": curses.COLOR_BLACK,
                "fg": curses.COLOR_WHITE,
                "title": curses.COLOR_CYAN,
                "success": curses.COLOR_GREEN,
                "error": curses.COLOR_RED,
                "warning": curses.COLOR_YELLOW,
                "highlight_bg": curses.COLOR_WHITE,
                "border": curses.COLOR_BLUE,
            }

        # Initialize color pairs
        curses.init_pair(1, self.colors["fg"], self.colors["bg"])  # Default text
        curses.init_pair(2, self.colors["title"], self.colors["bg"])  # Title
        curses.init_pair(3, self.colors["success"], self.colors["bg"])  # Success
        curses.init_pair(4, self.colors["error"], self.colors["bg"])  # Error
        curses.init_pair(5, self.colors["warning"], self.colors["bg"])  # Warning
        curses.init_pair(6, self.colors["title"], self.colors["bg"])  # Border
        curses.init_pair(7, self.colors["bg"], self.colors["fg"])  # Highlight
        curses.init_pair(8, self.colors["fg"], self.colors["bg"])  # Footer

        self.pairs = {
            "default": curses.color_pair(1),
            "title": curses.color_pair(2),
            "success": curses.color_pair(3),
            "error": curses.color_pair(4),
            "warning": curses.color_pair(5),
            "border": curses.color_pair(6),
            "highlight": curses.color_pair(7),
            "footer": curses.color_pair(8),
        }


class BoxChars:
    """Box drawing characters."""

    def __init__(self):
        self.chars = {
            "tl": "╭",
            "tr": "╮",
            "bl": "╰",
            "br": "╯",
            "v": "│",
            "h": "─",
            "ml": "├",
            "mr": "┤",
            "mt": "┬",
            "mb": "┴",
        }
