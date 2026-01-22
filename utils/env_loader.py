#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Environment variable loader utility."""

import os
from pathlib import Path


def load_env_file(env_file: str = ".env") -> None:
    """
    Load environment variables from a .env file.

    Args:
        env_file: Path to the .env file (relative to project root)
    """
    project_root = Path(__file__).parent.parent
    env_path = project_root / env_file

    if not env_path.exists():
        return

    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue

            # Parse KEY=VALUE format
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()

                # Remove quotes if present
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]

                # Set environment variable
                os.environ[key] = value


# Auto-load on import
load_env_file()
