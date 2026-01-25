#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Configuration management with cluster and branch switching."""

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

# --- Configuration ---
HOME_DIR = Path.home()
UNIT_PREFIX = "dontstarve@"
UNIT_SUFFIX = ".service"


def _find_config_file():
    paths = [
        HOME_DIR / ".config" / "dontstarve" / "config",
        Path(__file__).parent.parent.parent / ".config" / "dontstarve" / "config",
    ]
    for p in paths:
        if p.is_file():
            return p
    return None


GAME_CONFIG_FILE = _find_config_file()
CONFIG_DIR = (
    GAME_CONFIG_FILE.parent if GAME_CONFIG_FILE else HOME_DIR / ".config" / "dontstarve"
)
SHARDS_FILE = CONFIG_DIR / "shards.conf"


class ConfigManager:
    """Manages configuration with runtime modifications."""

    def __init__(self):
        self._config_cache = {}
        self._config_file_path = None

    def read_config(self) -> Dict[str, str]:
        """Read configuration from file."""
        config = {}
        if GAME_CONFIG_FILE and GAME_CONFIG_FILE.is_file():
            self._config_file_path = GAME_CONFIG_FILE
            with GAME_CONFIG_FILE.open("r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    match = re.match(r'^\s*([^#\s=]+)\s*=\s*"?([^"]*)"?', line)
                    if match:
                        key, value = match.groups()
                        config[key] = os.path.expandvars(value)
        else:
            # Create default config
            self._config_file_path = GAME_CONFIG_FILE or (
                HOME_DIR / ".config" / "dontstarve" / "config"
            )
            config = self._get_default_config()
            self.write_config(config)

        self._config_cache = config
        return config

    def write_config(self, config: Dict[str, str]) -> bool:
        """Write configuration to file."""
        try:
            if not self._config_file_path:
                self._config_file_path = GAME_CONFIG_FILE or (
                    HOME_DIR / ".config" / "dontstarve" / "config"
                )

            # Ensure directory exists
            self._config_file_path.parent.mkdir(parents=True, exist_ok=True)

            # Write configuration
            with self._config_file_path.open("w") as f:
                f.write("# DST Manager Configuration\n")
                f.write("# Cluster name (set to 'auto' to auto-detect clusters):\n")
                f.write(f'CLUSTER_NAME="{config.get("CLUSTER_NAME", "auto")}"\n\n')

                f.write("# Steam branch to use (main, beta):\n")
                f.write(f'BRANCH="{config.get("BRANCH", "main")}"\n\n')

                f.write("# DST install directory:\n")
                f.write('INSTALL_DIR="$HOME/dontstarvetogether_dedicated_server"\n\n')

                f.write("# SteamCMD directory:\n")
                f.write('STEAMCMD_DIR="$HOME/steamcmd"\n\n')

                f.write("# Game saves directories:\n")
                f.write('DONTSTARVE_DIR="$HOME/.klei/DoNotStarveTogether"\n')
                f.write(
                    'DONTSTARVE_BETA_DIR="$HOME/.klei/DoNotStarveTogetherBetaBranch"\n\n'
                )
                f.write("# Current shard list (one per line):\n")
                f.write("# Master\n# Caves\n# Islands\n# Volcano\n")

            self._config_cache = config
            return True
        except Exception as e:
            import sys

            print(f"Error writing config: {e}", file=sys.stderr)
            return False

    def update_config_value(self, key: str, value: str) -> bool:
        """Update a single configuration value."""
        config = self.read_config()
        config[key] = value
        return self.write_config(config)

    def _get_default_config(self) -> Dict[str, str]:
        """Get default configuration."""
        return {
            "CLUSTER_NAME": "auto",
            "BRANCH": "main",
            "INSTALL_DIR": "$HOME/dontstarvetogether_dedicated_server",
            "STEAMCMD_DIR": "$HOME/steamcmd",
            "DONTSTARVE_DIR": "$HOME/.klei/DoNotStarveTogether",
            "DONTSTARVE_BETA_DIR": "$HOME/.klei/DoNotStarveTogetherBetaBranch",
        }

    def get_available_clusters(self) -> List[str]:
        """Get list of available clusters."""
        config = self.read_config()
        dst_dir = Path(
            os.path.expandvars(
                config.get("DONTSTARVE_DIR", "$HOME/.klei/DoNotStarveTogether")
            )
        ).expanduser()

        if not dst_dir.exists():
            return []

        clusters = []

        # First check for dedicated server clusters (flat structure)
        for item in dst_dir.iterdir():
            if item.is_dir() and (item / "cluster.ini").exists():
                # Check if this looks like a dedicated server (has Master shard)
                master_path = item / "Master"
                if master_path.exists() and (master_path / "server.ini").exists():
                    clusters.append(item.name)

        # Then check numeric ID subdirectories (client clusters - usually ignore for servers)
        if not clusters:  # Only check client clusters if no server clusters found
            for item in dst_dir.iterdir():
                if item.is_dir() and item.name.isdigit():
                    for subitem in item.iterdir():
                        if subitem.is_dir() and (subitem / "cluster.ini").exists():
                            master_path = subitem / "Master"
                            if (
                                master_path.exists()
                                and (master_path / "server.ini").exists()
                            ):
                                clusters.append(subitem.name)

        return sorted(set(clusters))

    def auto_detect_cluster(self) -> str:
        """Auto-detect first available cluster with proper shard structure."""
        config = self.read_config()
        dst_dir = Path(
            os.path.expandvars(
                config.get("DONTSTARVE_DIR", "$HOME/.klei/DoNotStarveTogether")
            )
        ).expanduser()

        # For remote servers, use a default cluster name if shards are configured
        shards = read_desired_shards()
        if shards:
            return "MyDediServer"  # Standard cluster name for dedicated servers

        # First try direct cluster directories (dedicated server structure)
        if dst_dir.exists():
            for item in dst_dir.iterdir():
                if item.is_dir() and (item / "cluster.ini").exists():
                    # Check if it has proper shard structure (Master shard with server.ini)
                    master_path = item / "Master" / "server.ini"
                    if master_path.exists():
                        return item.name

        # Fallback to default
        return "MyDediServer"

    def get_available_branches(self) -> List[str]:
        """Get list of available branches."""
        return ["main", "beta"]


# Global config manager
config_manager = ConfigManager()


class Shard:
    """Represents a single server shard."""

    def __init__(self, name: str):
        self.name = name
        self.is_running = False
        self.is_enabled = False

    @property
    def unit_name(self) -> str:
        """The full systemd unit name."""
        return f"{UNIT_PREFIX}{self.name}{UNIT_SUFFIX}"

    def __repr__(self) -> str:
        return (
            f"Shard({self.name}, running={self.is_running}, enabled={self.is_enabled})"
        )


@lru_cache(maxsize=1)
def get_game_config() -> Dict[str, Any]:
    """Reads and caches the game config file."""
    config = config_manager.read_config()

    # Convert results to Path objects
    dst_dir = config.get("DONTSTARVE_DIR")
    if dst_dir:
        dst_dir = Path(dst_dir).expanduser()
    else:
        # Check common locations
        p1 = HOME_DIR / ".klei" / "DoNotStarveTogether"
        p2 = HOME_DIR / "DoNotStarveTogether"
        dst_dir = p1 if p1.is_dir() else p2 if p2.is_dir() else p1

    # Installation directory
    install_dir = config.get("INSTALL_DIR")
    if install_dir:
        install_dir = Path(install_dir).expanduser()
    else:
        install_dir = HOME_DIR / "dontstarvetogether_dedicated_server"

    # Handle auto cluster detection
    cluster_name = config.get("CLUSTER_NAME", "MyDediServer")
    if cluster_name == "auto":
        cluster_name = config_manager.auto_detect_cluster()
        # If still auto, it means no valid cluster found - use default
        if cluster_name == "auto":
            cluster_name = "MyDediServer"

    return {
        "DONTSTARVE_DIR": dst_dir,
        "INSTALL_DIR": install_dir,
        "CLUSTER_NAME": cluster_name,
        "BRANCH": config.get("BRANCH", "main"),
    }


def read_desired_shards() -> List[str]:
    """Reads shard names from the shards.conf file."""
    if not SHARDS_FILE.is_file():
        return []
    with SHARDS_FILE.open("r") as f:
        lines = f.readlines()
    return [
        line.strip()
        for line in lines
        if line.strip() and not line.strip().startswith("#")
    ]
