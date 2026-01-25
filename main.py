#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Entry point for the refactored DST Manager."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import application main function (requires path to be set first)
from ui.app import main  # noqa: E402

if __name__ == "__main__":
    import curses

    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        pass
