#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Popup components for user input."""

import curses
import curses.textpad
from dataclasses import dataclass
from typing import Optional, Tuple

from features.cluster.cluster_manager import BranchManager, ClusterManager
from ui.rendering.themes import BoxChars
from utils.drawing import draw_box, get_branch_color


@dataclass
class SettingsPopupState:
    """State for the settings popup.

    Attributes:
        available_clusters: List of available cluster names
        available_branches: List of available branch names
        selected_cluster_idx: Index of currently selected cluster
        selected_branch_idx: Index of currently selected branch
    """

    available_clusters: list
    available_branches: list
    selected_cluster_idx: int
    selected_branch_idx: int

    def get_selected_cluster(self) -> str:
        """Get the currently selected cluster name."""
        if self.available_clusters and 0 <= self.selected_cluster_idx < len(
            self.available_clusters
        ):
            return self.available_clusters[self.selected_cluster_idx]
        return ""

    def get_selected_branch(self) -> str:
        """Get the currently selected branch name."""
        if self.available_branches and 0 <= self.selected_branch_idx < len(
            self.available_branches
        ):
            return self.available_branches[self.selected_branch_idx]
        return ""

    def move_cluster_selection(self, direction: int) -> None:
        """Move cluster selection by the given direction (-1 for up, 1 for down)."""
        if self.available_clusters:
            new_idx = self.selected_cluster_idx + direction
            self.selected_cluster_idx = max(
                0, min(len(self.available_clusters) - 1, new_idx)
            )

    def move_branch_selection(self, direction: int) -> None:
        """Move branch selection by the given direction (-1 for left, 1 for right)."""
        if self.available_branches:
            new_idx = self.selected_branch_idx + direction
            self.selected_branch_idx = max(
                0, min(len(self.available_branches) - 1, new_idx)
            )


class PopupManager:
    """Manages popup windows for user input."""

    def __init__(self, stdscr, theme):
        self.stdscr = stdscr
        self.theme = theme

        # Box drawing characters
        self.box_chars = BoxChars.chars

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
            box.edit(validate)
            text = box.gather().strip()
            return text if text else None
        except curses.error:
            return None
        finally:
            curses.curs_set(0)
            self.stdscr.nodelay(1)

    def choice_popup(self, title: str, options: list) -> Optional[int]:
        """Create a choice popup and return the selected index."""
        h, w = self.stdscr.getmaxyx()
        popup_h = len(options) + 4
        popup_w = max(len(title) + 6, max(len(o) for o in options) + 8)
        popup_y = (h - popup_h) // 2
        popup_x = (w - popup_w) // 2

        popup = curses.newwin(popup_h, popup_w, popup_y, popup_x)
        popup.bkgd(" ", self.theme.pairs["default"])
        popup.keypad(True)

        selected_idx = 0
        self.stdscr.nodelay(0)

        try:
            while True:
                popup.erase()
                self._draw_popup_box(popup, title)
                self._draw_choice_options(popup, options, selected_idx)
                popup.refresh()
                key = popup.getch()

                if key in [ord("q"), 27]:
                    return None
                if key == ord("\n"):
                    return selected_idx
                if key == curses.KEY_UP:
                    selected_idx = max(0, selected_idx - 1)
                elif key == curses.KEY_DOWN:
                    selected_idx = min(len(options) - 1, selected_idx + 1)

        finally:
            self.stdscr.nodelay(1)

    def _draw_choice_options(self, popup, options, selected_idx):
        """Draw options for choice popup."""
        for i, option in enumerate(options):
            style = self.theme.pairs["default"]
            marker = " "
            if i == selected_idx:
                style = self.theme.pairs["highlight"]
                marker = ">"

            popup.addstr(i + 2, 2, f"{marker} {option}", style)

    def _create_popup_settings_state(
        self, cluster_manager, branch_manager
    ) -> Optional[SettingsPopupState]:
        """Create initial state for settings popup."""
        # Get available clusters and branches
        available_clusters = cluster_manager.get_available_clusters()
        available_branches = branch_manager.get_available_branches()

        if not available_clusters or not available_branches:
            return None

        # Initialize state with current selections
        current_cluster = cluster_manager.get_current_cluster()
        current_branch = branch_manager.get_current_branch()

        selected_cluster_idx = (
            available_clusters.index(current_cluster)
            if current_cluster in available_clusters
            else 0
        )
        selected_branch_idx = (
            available_branches.index(current_branch)
            if current_branch in available_branches
            else 0
        )

        return SettingsPopupState(
            available_clusters=available_clusters,
            available_branches=available_branches,
            selected_cluster_idx=selected_cluster_idx,
            selected_branch_idx=selected_branch_idx,
        )

    def settings_popup(self) -> Optional[Tuple[str, str]]:
        """Create a settings popup for cluster and branch selection.

        Returns:
            Tuple of (cluster_name, branch_name) if settings were applied successfully,
            None otherwise.
        """
        try:
            cluster_manager = ClusterManager()
            branch_manager = BranchManager()

            state = self._create_popup_settings_state(cluster_manager, branch_manager)
            if not state:
                return None

            # Calculate popup dimensions and position
            h, w = self.stdscr.getmaxyx()
            popup_h = min(15, h - 4)
            popup_w = min(50, w - 4)

            # Create popup window
            popup = curses.newwin(
                popup_h, popup_w, (h - popup_h) // 2, (w - popup_w) // 2
            )
            popup.bkgd(" ", self.theme.pairs["default"])
            popup.keypad(True)

            # Set blocking input mode
            self.stdscr.nodelay(0)

            try:
                while True:
                    self._draw_settings_popup(popup, state)

                    key = popup.getch()

                    # Handle close actions
                    if key in [ord("q"), 27, ord("s")]:
                        return None

                    # Handle cluster selection
                    if key == curses.KEY_UP:
                        state.move_cluster_selection(-1)
                    elif key == curses.KEY_DOWN:
                        state.move_cluster_selection(1)

                    # Handle branch selection
                    elif key == curses.KEY_LEFT:
                        state.move_branch_selection(-1)
                    elif key == curses.KEY_RIGHT:
                        state.move_branch_selection(1)

                    # Handle apply action
                    elif key == ord("\n"):
                        if cluster_manager.set_cluster(
                            state.get_selected_cluster()
                        ) and branch_manager.set_branch(state.get_selected_branch()):
                            return (
                                state.get_selected_cluster(),
                                state.get_selected_branch(),
                            )
                        return None
            finally:
                # Restore non-blocking input mode
                self.stdscr.nodelay(1)

        except Exception:  # pylint: disable=broad-exception-caught
            # Log error and return None to indicate failure
            # In a real application, you might want to show an error message
            return None

    def _draw_settings_popup(self, win, state: SettingsPopupState) -> None:
        """Draw settings popup content.

        Args:
            win: The curses window to draw on
            state: The current settings popup state
        """
        win.erase()
        self._draw_popup_box(win, "SETTINGS")

        h, w = win.getmaxyx()

        # Cluster selection section
        self._draw_cluster_section(win, state, h)

        # Branch selection section
        self._draw_branch_section(win, state, h)

        # Instructions section
        self._draw_instructions(win, h, w)

        win.refresh()

    def _draw_cluster_section(
        self, win, state: SettingsPopupState, max_height: int
    ) -> None:
        """Draw the cluster selection section.

        Args:
            win: The curses window to draw on
            state: The current settings popup state
            max_height: Maximum height available for drawing
        """
        win.addstr(2, 2, "Cluster:", self.theme.pairs["default"])

        # Limit the number of clusters to display and ensure we don't exceed window bounds
        display_clusters = state.available_clusters[:5]

        for i, cluster in enumerate(display_clusters):
            line_y = i + 3
            if line_y >= max_height - 2:  # Leave room for footer
                break

            marker = ">" if i == state.selected_cluster_idx else " "
            color = (
                self.theme.pairs["highlight"]
                if i == state.selected_cluster_idx
                else self.theme.pairs["default"]
            )

            line = f"{marker} {cluster}"
            if i == 0 and cluster == "auto":
                line += " (auto)"

            win.addstr(line_y, 2, line, color)

    def _draw_branch_section(
        self, win, state: SettingsPopupState, max_height: int
    ) -> None:
        """Draw the branch selection section.

        Args:
            win: The curses window to draw on
            state: The current settings popup state
            max_height: Maximum height available for drawing
        """
        # Calculate starting Y position for branch section
        cluster_count = min(
            5, len(state.available_clusters)
        )  # We display max 5 clusters
        branch_y = 3 + cluster_count + 1

        if branch_y >= max_height - 3:  # Not enough space for branches
            return

        win.addstr(branch_y, 2, "Branch:", self.theme.pairs["default"])

        # Limit the number of branches to display
        display_branches = state.available_branches[:3]

        for i, branch in enumerate(display_branches):
            line_y = branch_y + 1 + i
            if line_y >= max_height - 2:  # Leave room for footer
                break

            marker = ">" if i == state.selected_branch_idx else " "

            # Color branches based on their type
            branch_color = get_branch_color(branch, self.theme)

            color = (
                self.theme.pairs["highlight"]
                if i == state.selected_branch_idx
                else branch_color
            )

            win.addstr(line_y, 2, f"{marker} {branch}", color)

    def _draw_instructions(self, win, max_height: int, max_width: int) -> None:
        """Draw the instructions footer.

        Args:
            win: The curses window to draw on
            max_height: Maximum height available
            max_width: Maximum width available
        """
        instructions = "↑↓:Cluster ←→:Branch Enter:Apply Q:Close"

        # Only draw instructions if there's enough space
        if len(instructions) < max_width - 4:
            win.addstr(max_height - 2, 2, instructions, self.theme.pairs["footer"])

    def _draw_popup_box(self, win: curses.window, title: str) -> None:
        """Draw a box around the popup window."""
        draw_box(win, self.theme, self.box_chars, title)
