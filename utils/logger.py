#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Global logging configuration."""

import logging
import sys
from pathlib import Path

# Log file path
LOG_FILE = Path(__file__).parent.parent / "log.txt"


def setup_logging():
    """Setup global logging configuration."""
    # Configure root logger
    logging.basicConfig(
        level=logging.ERROR,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
            # We don't add StreamHandler here because it would interfere with Curses UI
        ],
    )

    # Setup global exception handler
    sys.excepthook = handle_exception


def handle_exception(exc_type, exc_value, exc_traceback):
    """Handle uncaught exceptions."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logging.critical(
        "Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback)
    )
