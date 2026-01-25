#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Common utility functions."""

import time
from typing import Any, Dict


def debounce(last_called: float, delay: float) -> bool:
    """Check if enough time has passed for debounced operation."""
    return time.time() - last_called > delay


def safe_get(dictionary: Dict[str, Any], key: str, default: Any = None) -> Any:
    """Safely get value from dictionary with default."""
    return dictionary.get(key, default)


def truncate_string(text: str, max_length: int, suffix: str = "...") -> str:
    """Truncate string to max_length with suffix."""
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix
