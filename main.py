#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Entry point for the refactored DST Manager."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import and run the application
from ui.app import main

if __name__ == "__main__":
    import curses

    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        pass
