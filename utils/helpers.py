#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Common utility functions."""


def truncate_string(text: str, max_length: int, suffix: str = "...") -> str:
    """Truncate string to max_length with suffix."""
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix
