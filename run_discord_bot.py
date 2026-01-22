#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Standalone Discord bot runner.

This script runs only the Discord bot without the TUI.
Useful for running on headless servers or as a systemd service.

Usage:
    python run_discord_bot.py

    Or as a service:
    Create /etc/systemd/system/dst-discord-bot.service
"""

import sys
import os
import signal
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Load environment variables
from utils.env_loader import load_env_file
load_env_file()

# Import services
from services.manager_service import ManagerService

# Global manager instance for signal handling
manager_service = None
running = True


def signal_handler(signum, frame):
    """Handle shutdown signals."""
    global running
    running = False


def main():
    """Main entry point for standalone Discord bot."""
    global manager_service, running

    # Check if Discord token is configured
    if not os.getenv("DISCORD_BOT_TOKEN"):
        return 1

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Initialize manager service
        manager_service = ManagerService()

        # Start Discord bot
        manager_service.start_discord_bot()

        if not manager_service.discord_service.is_running:
            return 1

        # Keep running until interrupted
        while running:
            time.sleep(1)

    except Exception as e:
        return 1
    finally:
        # Cleanup
        if manager_service:
            manager_service.stop_discord_bot()

    return 0


if __name__ == "__main__":
    sys.exit(main())
