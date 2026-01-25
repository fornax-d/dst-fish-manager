#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Settings UI component for cluster and branch management with proper boxes and colors."""

import curses
from dataclasses import dataclass, field
from typing import List

from features.cluster.cluster_manager import BranchManager, ClusterManager
from ui.rendering.themes import BoxChars
from utils.drawing import draw_box, get_branch_color


@dataclass
class SettingsState:  # pylint: disable=too-few-public-methods
    """State for settings UI."""

    available_clusters: List[str] = field(default_factory=list)
    available_branches: List[str] = field(default_factory=list)
    selected_cluster_idx: int = 0
    selected_branch_idx: int = 0
    active: bool = False


class SettingsUI:
    """UI for managing clusters and branches with proper boxes and colors."""

    def __init__(self, state_manager, event_bus, theme, popup_manager):
        self.state_manager = state_manager
        self.event_bus = event_bus
        self.theme = theme
        self.popup_manager = popup_manager

        self.cluster_manager = ClusterManager()
        self.branch_manager = BranchManager()

        self.state = SettingsState()

    def activate(self) -> None:
        """Activate settings UI."""
        self.state.available_clusters = self.cluster_manager.get_available_clusters()
        self.state.available_branches = self.branch_manager.get_available_branches()

        current_cluster = self.cluster_manager.get_current_cluster()
        current_branch = self.branch_manager.get_current_branch()

        if current_cluster in self.state.available_clusters:
            self.state.selected_cluster_idx = self.state.available_clusters.index(
                current_cluster
            )

        if current_branch in self.state.available_branches:
            self.state.selected_branch_idx = self.state.available_branches.index(
                current_branch
            )

        self.state.active = True

    def handle_input(self, key: int) -> bool:
        """Handle input for settings UI."""
        if key in [ord("q"), 27, ord("s")]:  # q, Esc, or s to close
            self.state.active = False
            return True

        if key == curses.KEY_UP:
            if self.state.selected_cluster_idx > 0:
                self.state.selected_cluster_idx -= 1

        elif key == curses.KEY_DOWN:
            if self.state.selected_cluster_idx < len(self.state.available_clusters) - 1:
                self.state.selected_cluster_idx += 1

        elif key == curses.KEY_LEFT:
            if self.state.selected_branch_idx > 0:
                self.state.selected_branch_idx -= 1

        elif key == curses.KEY_RIGHT:
            if self.state.selected_branch_idx < len(self.state.available_branches) - 1:
                self.state.selected_branch_idx += 1

        elif key == ord("\n"):
            self._apply_settings()

        return False

    def render(self, win) -> None:
        """Render settings UI with proper boxes and colored branches."""
        if not self.state.active:
            return

        h, w = win.getmaxyx()
        if h < 10 or w < 40:
            return

        # Clear window
        win.erase()

        # Draw box and title
        self._draw_box(win, "SETTINGS")

        # Calculations for layout
        y_offset = 3
        cluster_count = len(self.state.available_clusters)

        # Render sections
        self._render_clusters(win, y_offset, h)
        self._draw_separator(win, y_offset + cluster_count + 1, h, w)
        self._render_branches(win, y_offset + cluster_count + 3, h)

        # Instructions
        instructions = (
            "↑↓: Select cluster | ←→: Select branch | Enter: Apply | S/Q: Close"
        )
        if len(instructions) < w - 4:
            win.addstr(h - 2, 2, instructions, self.theme.pairs["footer"])

    def _render_clusters(self, win, start_y: int, h: int) -> None:
        """Render cluster selection section."""
        cluster_label = "Cluster:"
        win.addstr(start_y - 1, 2, cluster_label, self.theme.pairs["default"])

        for i, cluster in enumerate(self.state.available_clusters):
            if i + start_y >= h - 2:
                break

            marker = ">" if i == self.state.selected_cluster_idx else " "
            color = (
                self.theme.pairs["highlight"]
                if i == self.state.selected_cluster_idx
                else self.theme.pairs["default"]
            )

            line = f"{marker} {cluster}"
            if i == 0 and cluster == "auto":
                line += " (auto-detect)"

            win.addstr(i + start_y, 2, line, color)

    def _draw_separator(self, win, y: int, h: int, w: int) -> None:
        """Draw horizontal separator."""
        if y < h - 2:
            win.addstr(y, 1, BoxChars.chars["ml"])
            win.addstr(y, w - 1, BoxChars.chars["mr"])
            for x in range(2, w - 1):
                win.addstr(y, x, BoxChars.chars["h"])

    def _render_branches(self, win, start_y: int, h: int) -> None:
        """Render branch selection section."""
        branch_label = "Branch:"
        win.addstr(start_y - 1, 2, branch_label, self.theme.pairs["default"])

        for i, branch in enumerate(self.state.available_branches):
            if start_y + 1 + i >= h - 2:
                break

            marker = ">" if i == self.state.selected_branch_idx else " "

            # Color branches based on stability
            branch_color = get_branch_color(branch, self.theme)

            color = (
                self.theme.pairs["highlight"]
                if i == self.state.selected_branch_idx
                else branch_color
            )

            line = f"{marker} {branch}"
            win.addstr(start_y + i, 2, line, color)

    def _draw_box(self, win, title: str) -> None:
        """Draw a themed box with title on a window."""
        draw_box(win, self.theme, BoxChars.chars, title)

    def _apply_settings(self) -> None:
        """Apply selected settings."""
        if self.state.selected_cluster_idx < len(self.state.available_clusters):
            new_cluster = self.state.available_clusters[self.state.selected_cluster_idx]
            success = self.cluster_manager.set_cluster(new_cluster)
            if not success:
                self._show_error("Failed to set cluster")

        if self.state.selected_branch_idx < len(self.state.available_branches):
            new_branch = self.state.available_branches[self.state.selected_branch_idx]
            success = self.branch_manager.set_branch(new_branch)
            if not success:
                self._show_error("Failed to set branch")

        # Show success message
        self._show_success("Settings applied successfully")

    def _show_success(self, message: str) -> None:
        """Show success message popup."""
        self._show_popup(message, self.theme.pairs["success"])

    def _show_error(self, message: str) -> None:
        """Show error message popup."""
        self._show_popup(message, self.theme.pairs["error"])

    def _show_popup(self, message: str, color_pair) -> None:
        """Show a temporary popup message."""
        # For now, just print to screen - in real implementation would show popup
