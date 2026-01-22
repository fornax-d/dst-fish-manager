#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Centralized logging utility for DST Fish Manager."""

import logging
import logging.handlers
from collections import deque
from pathlib import Path
from typing import Optional, List


class InMemoryLogHandler(logging.Handler):
    """Custom log handler that stores logs in memory for TUI display."""

    def __init__(self, maxlen: int = 1000):
        """
        Initialize the in-memory log handler.

        Args:
            maxlen: Maximum number of log entries to keep in memory
        """
        super().__init__()
        self.logs = deque(maxlen=maxlen)
        # Note: Don't add an additional lock here - Handler base class already has one!

    def emit(self, record: logging.LogRecord):
        """Emit a log record."""
        try:
            msg = self.format(record)
            # Don't use a lock here - Handler.emit() is already called within acquire/release
            self.logs.append(msg)
        except Exception:
            self.handleError(record)

    def get_logs(self, lines: Optional[int] = None) -> List[str]:
        """
        Get recent log entries.

        Args:
            lines: Number of recent lines to retrieve (None for all)

        Returns:
            List of log messages
        """
        # Use the handler's lock for thread safety
        self.acquire()
        try:
            if lines is None:
                return list(self.logs)
            return list(self.logs)[-lines:]
        finally:
            self.release()

    def clear(self):
        """Clear all stored logs."""
        self.acquire()
        try:
            self.logs.clear()
        finally:
            self.release()


class DiscordBotLogger:
    """Logger specifically for Discord bot operations."""

    def __init__(self):
        """Initialize the Discord bot logger."""
        self.logger = logging.getLogger('discord_bot')
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False

        # Clear any existing handlers
        self.logger.handlers = []

        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # Create in-memory handler for TUI
        self.memory_handler = InMemoryLogHandler(maxlen=1000)
        self.memory_handler.setLevel(logging.INFO)
        self.memory_handler.setFormatter(formatter)
        self.logger.addHandler(self.memory_handler)

        # Create file handler for persistent logging
        self.log_file_path = None
        try:
            # Create logs directory if it doesn't exist
            log_dir = Path.home() / '.local' / 'share' / 'dst-fish-manager' / 'logs'
            log_dir.mkdir(parents=True, exist_ok=True)

            log_file = log_dir / 'discord_bot.log'

            # Use RotatingFileHandler to prevent log file from growing too large
            file_handler = logging.handlers.RotatingFileHandler(
                str(log_file),
                maxBytes=10 * 1024 * 1024,  # 10 MB
                backupCount=5
            )
            file_handler.setLevel(logging.INFO)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

            self.log_file_path = str(log_file)
        except Exception:
            # If file logging fails, just continue with memory logging
            pass

    def get_logger(self) -> logging.Logger:
        """Get the Discord bot logger instance."""
        return self.logger

    def get_logs(self, lines: Optional[int] = None) -> List[str]:
        """
        Get recent log entries from memory.

        Args:
            lines: Number of recent lines to retrieve (None for all)

        Returns:
            List of log messages
        """
        if self.memory_handler:
            return self.memory_handler.get_logs(lines)
        return []

    def get_log_file_path(self) -> Optional[str]:
        """Get the path to the log file."""
        return self.log_file_path

    def clear_logs(self):
        """Clear all stored in-memory logs."""
        if self.memory_handler:
            self.memory_handler.clear()

    # Convenience methods
    def info(self, message: str):
        """Log info message."""
        self.logger.info(message)

    def warning(self, message: str):
        """Log warning message."""
        self.logger.warning(message)

    def error(self, message: str):
        """Log error message."""
        self.logger.error(message)

    def debug(self, message: str):
        """Log debug message."""
        self.logger.debug(message)


# Global instance
discord_logger = DiscordBotLogger()
