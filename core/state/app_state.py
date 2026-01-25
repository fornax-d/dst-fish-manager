#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Application state management."""

from dataclasses import dataclass, field
from typing import List, Dict, Any
import threading

from utils.config import Shard


@dataclass
class ServerStatus:
    """Server status information."""

    season: str = "---"
    day: str = "---"
    days_left: str = "---"
    phase: str = "---"
    players: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class UIState:
    """UI-specific state."""

    selected_shard_idx: int = 0
    selected_mod_idx: int = 0
    selected_action_idx: int = 0
    selected_global_action_idx: int = -1  # -1 means not selected
    log_viewer_active: bool = False
    mods_viewer_active: bool = False
    log_content: List[str] = field(default_factory=list)
    log_scroll_pos: int = 0
    mods: List[Dict[str, Any]] = field(default_factory=list)
    cached_chat_logs: List[str] = field(default_factory=list)


@dataclass
class AppState:
    """Main application state."""

    shards: List[Shard] = field(default_factory=list)
    server_status: ServerStatus = field(default_factory=ServerStatus)
    ui_state: UIState = field(default_factory=UIState)
    is_working: bool = False
    need_redraw: bool = True
    shards_lock: threading.Lock = field(default_factory=threading.Lock)

    # Timing state
    last_refresh_time: float = 0.0
    last_status_refresh_time: float = 0.0
    last_chat_read_time: float = 0.0
    last_draw_time: float = 0.0
    last_status_poll_time: float = 0.0

    # Master offline counter
    master_offline_count: int = 0


class StateManager:
    """Manages application state with thread safety."""

    def __init__(self):
        self._state = AppState()

    @property
    def state(self) -> AppState:
        """Get current state (read-only)."""
        return self._state

    def update_shards(self, shards: List[Shard]) -> None:
        """Update shards list thread-safely."""
        with self._state.shards_lock:
            self._state.shards = shards

    def get_shards_copy(self) -> List[Shard]:
        """Get a thread-safe copy of shards."""
        with self._state.shards_lock:
            return list(self._state.shards)

    def update_server_status(self, status: Dict[str, Any]) -> None:
        """Update server status."""
        for key, value in status.items():
            if hasattr(self._state.server_status, key):
                setattr(self._state.server_status, key, value)

    def set_working(self, is_working: bool) -> None:
        """Set working state."""
        self._state.is_working = is_working

    def request_redraw(self) -> None:
        """Request UI redraw."""
        self._state.need_redraw = True

    def clear_redraw_flag(self) -> None:
        """Clear redraw flag."""
        self._state.need_redraw = False

    def update_timing(self, **kwargs) -> None:
        """Update timing values."""
        for key, value in kwargs.items():
            if hasattr(self._state, key):
                setattr(self._state, key, value)
