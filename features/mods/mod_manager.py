#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Mod management feature."""

import logging
import re
from pathlib import Path
from typing import Dict, List

from utils.config import get_game_config


class ModManager:
    """Handles parsing and editing of DST mod files."""

    def __init__(self):
        config = get_game_config()
        self.dst_dir = config["DONTSTARVE_DIR"]
        self.install_dir = config["INSTALL_DIR"]
        self.cluster_name = config["CLUSTER_NAME"]

    def get_mods_setup_path(self) -> Path:
        """Path to dedicated_server_mods_setup.lua."""
        return self.install_dir / "mods" / "dedicated_server_mods_setup.lua"

    def get_mod_overrides_path(self, shard_name: str = "Master") -> Path:
        """Path to modoverrides.lua for a specific shard."""
        return self.dst_dir / self.cluster_name / shard_name / "modoverrides.lua"

    def list_mods(self, shard_name: str = "Master") -> List[Dict]:
        """
        Parses modoverrides.lua to list known mods and their enabled status.
        Returns a list of dicts: [{'id': 'workshop-123', 'enabled': True, 'name': '...'}]
        """
        path = self.get_mod_overrides_path(shard_name)
        if not path.is_file():
            # Create default modoverrides.lua if it doesn't exist
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("return {\n}\n")
            return []

        content = path.read_text()
        mods = []

        mod_block_pattern = re.compile(
            r'\["(workshop-\d+)"\]\s*=\s*\{([^}]*)\}', re.DOTALL
        )

        for match in mod_block_pattern.finditer(content):
            mod_id = match.group(1)
            block_content = match.group(2)

            enabled_match = re.search(r"enabled\s*=\s*(true|false)", block_content)
            enabled = True
            if enabled_match:
                enabled = enabled_match.group(1) == "true"

            # Try to get the name from modinfo.lua
            name = self.get_mod_name(mod_id)

            mods.append({"id": mod_id, "enabled": enabled, "name": name})

        return mods

    def get_mod_name(self, workshop_id: str) -> str:
        """Attempts to read the mod name from its modinfo.lua file."""
        info_path = self.install_dir / "mods" / workshop_id / "modinfo.lua"
        if not info_path.is_file():
            return workshop_id  # Fallback to ID

        try:
            content = info_path.read_text(errors="ignore")
            name_match = re.search(r'name\s*=\s*"(.*?)"', content)
            if name_match:
                return name_match.group(1)
        except Exception as e:
            logging.getLogger(__name__).debug(
                "Failed to read mod info from %s: %s", 
                info_path, 
                e
            )
        return workshop_id

    def toggle_mod(
        self, workshop_id: str, enabled: bool, shard_name: str = "Master"
    ) -> bool:
        """Toggles a mod's enabled status in modoverrides.lua."""
        path = self.get_mod_overrides_path(shard_name)
        if not path.is_file():
            return False

        content = path.read_text()

        pattern = re.compile(
            rf'(\["{workshop_id}"\]\s*=\s*\{{[^}}]*enabled\s*=\s*)(true|false)',
            re.DOTALL,
        )

        new_enabled_str = "true" if enabled else "false"
        new_content, count = pattern.subn(rf"\1{new_enabled_str}", content)

        if count > 0:
            path.write_text(new_content)
            return True
        return False

    def add_mod(self, workshop_id: str, shard_name: str = "Master") -> bool:
        """
        Adds a mod to both dedicated_server_mods_setup.lua and modoverrides.lua.
        """
        # 1. Update dedicated_server_mods_setup.lua
        if not self._add_to_mods_setup(workshop_id):
            return False

        # 2. Update modoverrides.lua
        return self._add_to_mod_overrides(workshop_id, shard_name)

    def _add_to_mods_setup(self, workshop_id: str) -> bool:
        path = self.get_mods_setup_path()
        numeric_id = workshop_id.replace("workshop-", "")

        if not path.parent.exists():
            return False

        content = ""
        if path.exists():
            content = path.read_text()

        entry = f'ServerModSetup("{numeric_id}")'
        if entry in content:
            return True  # Already exists

        with path.open("a") as f:
            if content and not content.endswith("\n"):
                f.write("\n")
            f.write(entry + "\n")
        return True

    def _add_to_mod_overrides(self, workshop_id: str, shard_name: str) -> bool:
        path = self.get_mod_overrides_path(shard_name)
        if not path.exists():
            # Create a new modoverrides.lua if it doesn't exist
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("return {\n}\n")

        content = path.read_text()
        if f'["{workshop_id}"]' in content:
            return True  # Already exists

        # Add a basic entry before the final '}'
        new_entry = (
            f'  ["{workshop_id}"]={{ configuration_options={{  }}, enabled=true }}'
        )

        # Find the last closing brace
        last_brace_idx = content.rfind("}")
        if last_brace_idx == -1:
            return False

        # Check if we need a comma
        prefix = ""
        if content[:last_brace_idx].strip() != "return {":
            prefix = ",\n"
        else:
            prefix = "\n"

        new_content = (
            content[:last_brace_idx].rstrip()
            + prefix
            + new_entry
            + "\n"
            + content[last_brace_idx:]
        )
        path.write_text(new_content)
        return True
