# -*- coding: utf-8 -*-
"""
Plugin Interface Definition.
"""
from abc import ABC, abstractmethod


class IPlugin(ABC):
    """Base interface for all plugins."""

    def __init__(self):
        self.name = "Unknown Plugin"
        self.version = "0.0.0"
        self.enabled = False

    @abstractmethod
    def on_load(self, config, manager_service, event_bus=None):
        """
        Called when the plugin is loaded.
        Args:
            config: Dict or configuration object
            manager_service: Reference to the ManagerService for API access
            event_bus: Reference to the EventBus for event subscriptions
        """

    @abstractmethod
    def on_start(self):
        """Called when the plugin is started."""

    @abstractmethod
    def on_stop(self):
        """Called when the plugin is stopped."""

    @abstractmethod
    def update(self):
        """Called periodically from the main loop."""
