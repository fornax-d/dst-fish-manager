#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""SystemD service for managing DST shards."""

import subprocess
from typing import List, Set, Tuple

from utils.config import UNIT_PREFIX, UNIT_SUFFIX


class SystemDService:
    """Handles all SystemD operations for DST shards."""

    @staticmethod
    def _run_systemctl_command(args: list[str]) -> Tuple[bool, str, str]:
        """Runs a systemctl command and returns success, stdout, and stderr."""
        try:
            process = subprocess.run(
                ["systemctl", "--user", *args],
                capture_output=True,
                text=True,
                check=False,
            )
            return (
                process.returncode == 0,
                process.stdout.strip(),
                process.stderr.strip(),
            )
        except FileNotFoundError:
            return False, "", "systemctl command not found."

    @classmethod
    def get_systemd_instances(cls, command: str, state_filter: str) -> Set[str]:
        """
        Helper to get a set of shard names from systemd commands.
        Args:
            command: The systemctl command to run (e.g., "list-units").
            state_filter: The state to look for (e.g., "active", "enabled").
        """
        args = [command, "--no-legend", f"{UNIT_PREFIX}*.service"]
        if command == "list-units":
            args.extend(["--state", state_filter])

        success, stdout, _ = cls._run_systemctl_command(args)
        if not success:
            return set()

        instances = set()
        for line in stdout.splitlines():
            parts = line.split()
            if not parts:
                continue

            unit_file = parts[0]
            # For list-unit-files, the state is in the second column
            if command == "list-unit-files" and len(parts) > 1:
                unit_state = parts[1]
                if unit_state != state_filter:
                    continue

            # Extract shard name from 'dontstarve@SHARD.service'
            if unit_file.startswith(UNIT_PREFIX) and unit_file.endswith(UNIT_SUFFIX):
                shard_name = unit_file.removeprefix(UNIT_PREFIX).removesuffix(
                    UNIT_SUFFIX
                )
                if shard_name:
                    instances.add(shard_name)
        return instances

    @classmethod
    def control_shard(cls, shard_name: str, action: str) -> Tuple[bool, str, str]:
        """
        Controls a single shard.
        Actions: "start", "stop", "enable", "disable", "restart"
        """
        return cls.control_all_shards(action, [shard_name])

    @classmethod
    def control_all_shards(
        cls, action: str, shard_list: List[str]
    ) -> Tuple[bool, str, str]:
        """
        Controls all shards in the list in a single batch.
        Actions: "start", "stop", "restart", "enable", "disable"
        Returns: (success, stdout, stderr)
        """
        if not shard_list:
            return True, "", ""

        unit_names = [f"{UNIT_PREFIX}{name}{UNIT_SUFFIX}" for name in shard_list]
        return cls._run_systemctl_command([action] + unit_names)

    @classmethod
    def get_logs(cls, shard_name: str, lines: int = 50) -> str:
        """Gets the latest journalctl logs for a shard."""
        unit_name = f"{UNIT_PREFIX}{shard_name}{UNIT_SUFFIX}"
        try:
            process = subprocess.run(
                [
                    "journalctl",
                    "--user",
                    "-u",
                    unit_name,
                    "-n",
                    str(lines),
                    "--no-pager",
                    "-o",
                    "cat",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            return (
                process.stdout.strip()
                if process.returncode == 0
                else process.stderr.strip()
            )
        except FileNotFoundError:
            return "journalctl command not found."

    @classmethod
    def sync_shards_and_target(cls, desired_shards: set[str]) -> None:
        """
        Synchronizes systemd units with a set of desired shards.
        Enables and starts desired shards, disables and stops others.
        """
        enabled_names = cls.get_systemd_instances("list-unit-files", "enabled")
        running_names = cls.get_systemd_instances("list-units", "active")

        # Enable and start desired shards (batching is more efficient)
        if desired_shards:
            list_to_enable = list(desired_shards)
            cls.control_all_shards("enable", list_to_enable)
            cls.control_all_shards("start", list_to_enable)

        # Disable and stop shards not in the desired list
        all_managed_names = enabled_names.union(running_names)
        to_remove = [name for name in all_managed_names if name not in desired_shards]
        if to_remove:
            cls.control_all_shards("stop", to_remove)
            cls.control_all_shards("disable", to_remove)

        # Ensure the main target is enabled and started
        cls._run_systemctl_command(["enable", "--now", "dontstarve.target"])
