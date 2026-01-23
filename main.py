#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Entry point for the refactored DST Manager."""

import curses
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Load environment variables from .env file
from services.manager_service import ManagerService  # noqa: E402
from ui.app import main  # noqa: E402
from utils.env_loader import load_env_file  # noqa: E402

load_env_file()

if __name__ == "__main__":
    # Initialize manager service
    manager_service = ManagerService()

    try:
        # Run the TUI application
        curses.wrapper(lambda stdscr: main(stdscr, manager_service))
    except KeyboardInterrupt:
        pass
    finally:
        # Stop Discord bot on exit
        manager_service.stop_discord_bot()
