# -*- coding: utf-8 -*-
# pylint: disable=broad-exception-caught
"""
Plugin Manager Implementation.
"""

import os
import importlib.util
import logging
from typing import Dict
from core.plugins.interface import IPlugin

logger = logging.getLogger(__name__)


class PluginManager:
    """Manages the discovery, loading, and lifecycle of plugins."""

    def __init__(self, manager_service, event_bus=None):
        self.manager_service = manager_service
        self.event_bus = event_bus
        self.plugins: Dict[str, IPlugin] = {}
        self.plugin_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "../../plugins")
        )

    def discover_plugins(self):
        """Scans the plugins directory for valid plugins."""
        if not os.path.exists(self.plugin_dir):
            os.makedirs(self.plugin_dir)
            return

        for item in os.listdir(self.plugin_dir):
            plugin_path = os.path.join(self.plugin_dir, item)
            if os.path.isdir(plugin_path) and os.path.exists(
                os.path.join(plugin_path, "plugin.py")
            ):
                self._load_plugin(item, os.path.join(plugin_path, "plugin.py"))

    def _load_plugin(self, plugin_name: str, file_path: str):
        """Dynamically loads a plugin module from file."""
        try:
            spec = importlib.util.spec_from_file_location(
                f"plugins.{plugin_name}", file_path
            )
            if not spec or not spec.loader:
                logger.error("Could not load spec for %s", plugin_name)
                return

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Find class implementing IPlugin
            plugin_class = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, IPlugin)
                    and attr is not IPlugin
                ):
                    plugin_class = attr
                    break

            if plugin_class:
                plugin_instance = plugin_class()
                # Initialize
                plugin_instance.on_load({}, self.manager_service, self.event_bus)
                self.plugins[plugin_name] = plugin_instance
                logger.info(
                    "Loaded plugin: %s v%s",
                    plugin_instance.name,
                    plugin_instance.version,
                )
            else:
                logger.warning("No IPlugin implementation found in %s", plugin_name)

        except Exception as e:
            logger.error("Failed to load plugin %s: %s", plugin_name, e, exc_info=True)

    def start_all(self):
        """Starts all loaded plugins."""
        for name, plugin in self.plugins.items():
            try:
                plugin.on_start()
                logger.info("Started plugin: %s", name)
            except Exception as e:
                logger.error("Error starting plugin %s: %s", name, e)

    def stop_all(self):
        """Stops all loaded plugins."""
        for name, plugin in self.plugins.items():
            try:
                plugin.on_stop()
                logger.info("Stopped plugin: %s", name)
            except Exception as e:
                logger.error("Error stopping plugin %s: %s", name, e)

    def update_all(self):
        """Updates all loaded plugins (called periodically)."""
        for plugin in self.plugins.values():
            try:
                plugin.update()
            except Exception as e:
                logger.error("Error updating plugin %s: %s", plugin.name, e)
