#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Event system for decoupled communication."""

import logging
import threading
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List


class EventType(Enum):
    """Application event types."""

    SHARD_REFRESH = "shard_refresh"
    SERVER_STATUS_UPDATE = "server_status_update"
    CHAT_MESSAGE = "chat_message"
    LOG_UPDATE = "log_update"
    MOD_LIST_UPDATE = "mod_list_update"
    BACKGROUND_TASK_START = "background_task_start"
    BACKGROUND_TASK_END = "background_task_end"
    USER_ACTION = "user_action"
    EXIT_REQUESTED = "exit_requested"


@dataclass
class Event:
    """Application event."""

    type: EventType
    data: Any = None
    timestamp: Any = None


class EventBus:
    """Simple event bus for decoupled communication."""

    def __init__(self):
        self._subscribers: Dict[EventType, List[Callable]] = {}
        self._lock = threading.Lock()

    def subscribe(self, event_type: EventType, callback: Callable) -> None:
        """Subscribe to an event type."""
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: EventType, callback: Callable) -> None:
        """Unsubscribe from an event type."""
        with self._lock:
            if event_type in self._subscribers:
                try:
                    self._subscribers[event_type].remove(callback)
                except ValueError:
                    pass

    def publish(self, event: Event) -> None:
        """Publish an event to all subscribers."""
        with self._lock:
            subscribers = self._subscribers.get(event.type, [])

        for callback in subscribers:
            try:
                callback(event)
            except Exception as e:  # pylint: disable=broad-exception-caught
                # Broad exception catch is intentional here - we don't want one
                # subscriber's exception to break the entire event system
                logging.getLogger(__name__).warning(
                    "Event subscriber %s raised exception: %s", callback.__name__, e
                )


# Global event bus instance
event_bus = EventBus()
