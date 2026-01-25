#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Popup components for user input."""

import curses
import curses.textpad
from typing import Optional, Tuple


class PopupManager:
    """Manages popup windows for user input."""

    def __init__(self, stdscr, theme):
        self.stdscr = stdscr
        self.theme = theme

        # Box drawing characters
        self.box_chars = {
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

    def text_input_popup(self, title: str, width: int = 40) -> Optional[str]:
        """Create a text input popup and return the entered text."""
        h, w = self.stdscr.getmaxyx()
        popup_h = 3
        popup_w = max(width, len(title) + 6)
        popup_y = (h - popup_h) // 2
        popup_x = (w - popup_w) // 2

        popup = curses.newwin(popup_h, popup_w, popup_y, popup_x)
        popup.bkgd(" ", self.theme.pairs["default"])
        popup.keypad(True)

        # Draw box with title
        self._draw_popup_box(popup, title)

        # Create input window
        input_win = popup.derwin(1, popup_w - 2, 1, 1)
        input_win.bkgd(" ", self.theme.pairs["highlight"])

        # Make input blocking
        self.stdscr.nodelay(0)
        curses.curs_set(1)
        popup.refresh()

        # Use simple textbox with escape support
        try:
            box = curses.textpad.Textbox(input_win)

            # Simple validator for Escape key
            def validate(ch):
                if ch == 27:  # Escape
                    return 7  # curses.BELL to terminate
                return ch

            # Edit with escape support
            result = box.edit(validate)
            text = box.gather().strip()
            return text if text else None
        except:
            return None
        finally:
            # Always restore settings
            curses.curs_set(0)
            self.stdscr.nodelay(1)

    def settings_popup(self) -> Optional[Tuple[str, str]]:
        """Create a settings popup for cluster and branch selection."""
        from features.cluster.cluster_manager import BranchManager, ClusterManager

        cluster_manager = ClusterManager()
        branch_manager = BranchManager()

        available_clusters = cluster_manager.get_available_clusters()
        available_branches = branch_manager.get_available_branches()

        current_cluster = cluster_manager.get_current_cluster()
        current_branch = branch_manager.get_current_branch()

        selected_cluster_idx = 0
        selected_branch_idx = 0

        if current_cluster in available_clusters:
            selected_cluster_idx = available_clusters.index(current_cluster)
        if current_branch in available_branches:
            selected_branch_idx = available_branches.index(current_branch)

        h, w = self.stdscr.getmaxyx()
        popup_h = min(15, h - 4)
        popup_w = min(50, w - 4)
        popup_y = (h - popup_h) // 2
        popup_x = (w - popup_w) // 2

        popup = curses.newwin(popup_h, popup_w, popup_y, popup_x)
        popup.bkgd(" ", self.theme.pairs["default"])
        popup.keypad(True)

        self.stdscr.nodelay(0)

        try:
            while True:
                self._draw_settings_popup(
                    popup,
                    available_clusters,
                    available_branches,
                    selected_cluster_idx,
                    selected_branch_idx,
                )

                key = popup.getch()

                if key in [ord("q"), 27, ord("s")]:  # Close
                    return None
                elif key == curses.KEY_UP:
                    selected_cluster_idx = max(0, selected_cluster_idx - 1)
                elif key == curses.KEY_DOWN:
                    selected_cluster_idx = min(
                        len(available_clusters) - 1, selected_cluster_idx + 1
                    )
                elif key == curses.KEY_LEFT:
                    selected_branch_idx = max(0, selected_branch_idx - 1)
                elif key == curses.KEY_RIGHT:
                    selected_branch_idx = min(
                        len(available_branches) - 1, selected_branch_idx + 1
                    )
                elif key == ord("\n"):  # Apply
                    new_cluster = available_clusters[selected_cluster_idx]
                    new_branch = available_branches[selected_branch_idx]

                    cluster_success = cluster_manager.set_cluster(new_cluster)
                    branch_success = branch_manager.set_branch(new_branch)

                    if cluster_success and branch_success:
                        return (new_cluster, new_branch)
                    else:
                        return None
        finally:
            self.stdscr.nodelay(1)

    def _draw_settings_popup(
        self, win, clusters, branches, cluster_idx, branch_idx
    ) -> None:
        """Draw settings popup content."""
        win.erase()
        self._draw_popup_box(win, "SETTINGS")

        h, w = win.getmaxyx()

        # Cluster selection
        win.addstr(2, 2, "Cluster:", self.theme.pairs["default"])
        for i, cluster in enumerate(clusters[:5]):
            if i + 3 >= h - 2:
                break
            marker = ">" if i == cluster_idx else " "
            color = (
                self.theme.pairs["highlight"]
                if i == cluster_idx
                else self.theme.pairs["default"]
            )
            line = f"{marker} {cluster}"
            if i == 0 and cluster == "auto":
                line += " (auto)"
            win.addstr(i + 3, 2, line, color)

        # Branch selection
        branch_y = 3 + len(clusters) + 1
        if branch_y < h - 3:
            win.addstr(branch_y, 2, "Branch:", self.theme.pairs["default"])
            for i, branch in enumerate(branches[:3]):
                if branch_y + 1 + i >= h - 2:
                    break
                marker = ">" if i == branch_idx else " "

                # Color branches
                if branch == "main":
                    branch_color = self.theme.pairs["success"]
                elif branch == "beta":
                    branch_color = self.theme.pairs["error"]
                else:
                    branch_color = self.theme.pairs["default"]

                color = (
                    self.theme.pairs["highlight"] if i == branch_idx else branch_color
                )
                win.addstr(branch_y + 1 + i, 2, f"{marker} {branch}", color)

        # Instructions
        instructions = "↑↓:Cluster ←→:Branch Enter:Apply Q:Close"
        if len(instructions) < w - 4:
            win.addstr(h - 2, 2, instructions, self.theme.pairs["footer"])

        win.refresh()

    def _draw_popup_box(self, win: curses.window, title: str) -> None:
        """Draw a box around the popup window."""
        try:
            h, w = win.getmaxyx()
            if h < 2 or w < 2:
                return

            # Draw corners
            win.addstr(0, 0, self.box_chars["tl"])
            win.addstr(0, w - 1, self.box_chars["tr"])
            win.addstr(h - 1, 0, self.box_chars["bl"])
            try:
                win.addstr(h - 1, w - 1, self.box_chars["br"])
            except curses.error:
                try:
                    win.insstr(h - 1, w - 1, self.box_chars["br"])
                except curses.error:
                    pass

            # Draw lines
            for x in range(1, w - 1):
                win.addstr(0, x, self.box_chars["h"])
                win.addstr(h - 1, x, self.box_chars["h"])
            for y in range(1, h - 1):
                win.addstr(y, 0, self.box_chars["v"])
                win.addstr(y, w - 1, self.box_chars["v"])

            # Draw title
            if title and w > len(title) + 4:
                win.addstr(
                    0, 2, f" {title} ", self.theme.pairs["title"] | curses.A_BOLD
                )
        except curses.error:
            pass
