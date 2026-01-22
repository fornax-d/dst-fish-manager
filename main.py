#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Entry point for the refactored DST Manager."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Load environment variables from .env file
from utils.env_loader import load_env_file
load_env_file()

# Import and run the application
from ui.app import main
from services.manager_service import ManagerService

if __name__ == "__main__":
    import curses

    # Initialize manager service
    manager_service = ManagerService()

    try:
        # Start Discord bot in background if enabled
        if manager_service.discord_service.is_enabled():
            manager_service.start_discord_bot()
        else:
            print("Discord bot is not enabled (no token found)")

        # Run the TUI application
        curses.wrapper(lambda stdscr: main(stdscr, manager_service))
    except KeyboardInterrupt:
        pass
    finally:
        # Stop Discord bot on exit
        manager_service.stop_discord_bot()
