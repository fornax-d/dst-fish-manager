#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Settings UI component for cluster and branch management with proper boxes and colors."""

import curses

from features.cluster.cluster_manager import BranchManager, ClusterManager


class SettingsUI:
    """UI for managing clusters and branches with proper boxes and colors."""

    def __init__(self, state_manager, event_bus, theme, popup_manager):
        self.state_manager = state_manager
        self.event_bus = event_bus
        self.theme = theme
        self.popup_manager = popup_manager

        self.cluster_manager = ClusterManager()
        self.branch_manager = BranchManager()

        self.available_clusters = []
        self.available_branches = []
        self.selected_cluster_idx = 0
        self.selected_branch_idx = 0
        self.active = False

    def activate(self) -> None:
        """Activate settings UI."""
        self.available_clusters = self.cluster_manager.get_available_clusters()
        self.available_branches = self.branch_manager.get_available_branches()

        current_cluster = self.cluster_manager.get_current_cluster()
        current_branch = self.branch_manager.get_current_branch()

        if current_cluster in self.available_clusters:
            self.selected_cluster_idx = self.available_clusters.index(current_cluster)

        if current_branch in self.available_branches:
            self.selected_branch_idx = self.available_branches.index(current_branch)

        self.active = True

    def handle_input(self, key: int) -> bool:
        """Handle input for settings UI."""
        if key in [ord("q"), 27, ord("s")]:  # q, Esc, or s to close
            self.active = False
            return True

        elif key == curses.KEY_UP:
            if self.selected_cluster_idx > 0:
                self.selected_cluster_idx -= 1

        elif key == curses.KEY_DOWN:
            if self.selected_cluster_idx < len(self.available_clusters) - 1:
                self.selected_cluster_idx += 1

        elif key == curses.KEY_LEFT:
            if self.selected_branch_idx > 0:
                self.selected_branch_idx -= 1

        elif key == curses.KEY_RIGHT:
            if self.selected_branch_idx < len(self.available_branches) - 1:
                self.selected_branch_idx += 1

        elif key == ord("\n"):
            self._apply_settings()

        return False

    def render(self, win) -> None:
        """Render settings UI with proper boxes and colored branches."""
        if not self.active:
            return

        h, w = win.getmaxyx()
        if h < 10 or w < 40:
            return

        # Clear window
        win.erase()

        # Draw box and title
        self._draw_box(win, "SETTINGS")

        # Use Catppuccin box characters
        box_chars = {
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

        # Cluster selection
        cluster_label = "Cluster:"
        win.addstr(2, 2, cluster_label, self.theme.pairs["default"])

        y_offset = 3
        for i, cluster in enumerate(self.available_clusters):
            if i + y_offset >= h - 2:
                break

            marker = ">" if i == self.selected_cluster_idx else " "
            color = (
                self.theme.pairs["highlight"]
                if i == self.selected_cluster_idx
                else self.theme.pairs["default"]
            )

            line = f"{marker} {cluster}"
            if i == 0 and cluster == "auto":
                line += " (auto-detect)"

            win.addstr(i + y_offset, 2, line, color)

        # Add horizontal separator
        cluster_count = len(self.available_clusters)
        separator_y = y_offset + cluster_count + 1
        if separator_y < h - 2:
            win.addstr(separator_y, 1, box_chars["ml"])
            win.addstr(separator_y, w - 1, box_chars["mr"])
            for x in range(2, w - 1):
                win.addstr(separator_y, x, box_chars["h"])

        # Branch selection
        branch_label = "Branch:"
        branch_y = y_offset + cluster_count + 3
        win.addstr(branch_y, 2, branch_label, self.theme.pairs["default"])

        for i, branch in enumerate(self.available_branches):
            if branch_y + 1 + i >= h - 2:
                break

            marker = ">" if i == self.selected_branch_idx else " "

            # Color branches based on stability
            if branch == "main":
                branch_color = self.theme.pairs["success"]  # Green for stable
            elif branch == "beta":
                branch_color = self.theme.pairs["error"]  # Red for beta/unstable
            else:
                branch_color = self.theme.pairs["default"]

            color = (
                self.theme.pairs["highlight"]
                if i == self.selected_branch_idx
                else branch_color
            )

            line = f"{marker} {branch}"
            win.addstr(branch_y + 1 + i, 2, line, color)

        # Instructions
        instructions = (
            "↑↓: Select cluster | ←→: Select branch | Enter: Apply | S/Q: Close"
        )
        if len(instructions) < w - 4:
            win.addstr(h - 2, 2, instructions, self.theme.pairs["footer"])

    def _draw_box(self, win, title: str) -> None:
        """Draw a themed box with title on a window."""
        try:
            h, w = win.getmaxyx()
            if h < 2 or w < 2:
                return

            win.attron(self.theme.pairs["border"])

            # Use Catppuccin box characters (same as main app)
            box_chars = {
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

            # Corners
            win.addstr(0, 0, box_chars["tl"])
            win.addstr(0, w - 1, box_chars["tr"])
            win.addstr(h - 1, 0, box_chars["bl"])
            win.addstr(h - 1, w - 1, box_chars["br"])

            # Lines
            for x in range(1, w - 1):
                win.addstr(0, x, box_chars["h"])
                win.addstr(h - 1, x, box_chars["h"])
            for y in range(1, h - 1):
                win.addstr(y, 0, box_chars["v"])
                win.addstr(y, w - 1, box_chars["v"])

            win.attroff(self.theme.pairs["border"])

            if title and w > len(title) + 4:
                win.addstr(
                    0, 2, f" {title} ", self.theme.pairs["title"] | curses.A_BOLD
                )
        except curses.error:
            pass

    def _apply_settings(self) -> None:
        """Apply selected settings."""
        if self.selected_cluster_idx < len(self.available_clusters):
            new_cluster = self.available_clusters[self.selected_cluster_idx]
            success = self.cluster_manager.set_cluster(new_cluster)
            if not success:
                self._show_error("Failed to set cluster")

        if self.selected_branch_idx < len(self.available_branches):
            new_branch = self.available_branches[self.selected_branch_idx]
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
        pass
