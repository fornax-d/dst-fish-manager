#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Drawing utility functions for the UI."""

import curses
from typing import Dict


def draw_box(
    win: curses.window, theme, box_chars: Dict[str, str], title: str = ""
) -> None:
    """Draw a themed box with title on a window."""
    if not theme or not box_chars:
        return

    try:
        h, w = win.getmaxyx()
        if h < 2 or w < 2:
            return

        win.attron(theme.pairs["border"])

        # Corners
        win.addstr(0, 0, box_chars["tl"])
        win.addstr(0, w - 1, box_chars["tr"])
        win.addstr(h - 1, 0, box_chars["bl"])
        try:
            win.addstr(h - 1, w - 1, box_chars["br"])
        except curses.error:
            try:
                win.insstr(h - 1, w - 1, box_chars["br"])
            except curses.error:
                pass

        # Lines
        for x in range(1, w - 1):
            win.addstr(0, x, box_chars["h"])
            win.addstr(h - 1, x, box_chars["h"])
        for y in range(1, h - 1):
            win.addstr(y, 0, box_chars["v"])
            win.addstr(y, w - 1, box_chars["v"])
        win.attroff(theme.pairs["border"])

        if title and w > len(title) + 4:
            win.addstr(0, 2, f" {title} ", theme.pairs["title"] | curses.A_BOLD)
    except curses.error:
        pass


def get_branch_color(branch: str, theme):
    """Get the color for a branch."""
    if branch == "main":
        return theme.pairs["success"]
    if branch == "beta":
        return theme.pairs["error"]
    return theme.pairs["default"]
