#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Entry point for the refactored DST Manager."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import application main function (requires path to be set first)
from ui.app import main  # noqa: E402,C0413  # pylint: disable=wrong-import-position

if __name__ == "__main__":
    import curses
    from utils.logger import setup_logging
    from utils.config import load_env_keys

    # Load Discord keys
    load_env_keys()

    # Setup logging
    setup_logging()

    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        pass
    except Exception as e:  # pylint: disable=broad-exception-caught
        # Also catch exceptions that bubble up from curses wrapper
        import logging

        logging.critical("Fatal error", exc_info=True)
        print(f"Fatal error occurred: {e}")
        print("Check log.txt for details.")
