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
        pass

    @abstractmethod
    def on_start(self):
        """Called when the plugin should start its main execution (e.g. background threads/processes)."""
        pass

    @abstractmethod
    def on_stop(self):
        """Called when the plugin should stop."""
        pass
    
    def update(self):
        """Optional: Called periodically by the main loop."""
        pass
