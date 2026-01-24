#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Status manager for handling server status operations."""

import os
import re
import time
from pathlib import Path
from typing import Dict, Optional

from utils.config import get_game_config


class StatusManager:
    """Manages server status operations."""

    @staticmethod
    def _get_default_status() -> Dict:
        """Get default status structure."""
        return {
            "season": "Unknown",
            "day": "Unknown",
            "days_left": "Unknown",
            "phase": "Unknown",
            "players": [],
            "shards": {},
        }

    @staticmethod
    def _parse_shard_log(log_path: Path) -> Dict:
        """Parse individual shard log file for status information."""
        shard_status = {}

        if not log_path.exists():
            return {"error": f"Log file not found: {log_path}"}

        try:
            # Read only the last 32KB of the log file for better performance
            # and to focus on the most recent information
            with open(log_path, "rb") as f:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                f.seek(max(0, size - 32768), os.SEEK_SET)
                content = f.read().decode("utf-8", errors="ignore")

            # Parse Season and Day from c_dumpseasons() - using approach from old implementation
            season_matches = re.findall(
                r"(?:\[Season\] Season:\s*|:\s*)(\w+)\s*(\d+)\s*(?:,\s*Remaining:|\s*->)\s*(\d+)\s*days?",
                content,
            )
            if season_matches:
                s_name, s_elapsed, s_rem = season_matches[-1]
                shard_status["season"] = s_name.capitalize()
                shard_status["day"] = str(int(s_elapsed) + 1)
                shard_status["days_left"] = s_rem
            else:
                # Fallback to simpler patterns if c_dumpseasons output not found
                season_patterns = [
                    r"^(autumn|spring|summer|winter) \d+ -> \d+ days \(\d+ %\) cycle",
                    r"World \d+ is now in (\w+)",
                    r"Season: (\w+)",
                    r"Current season: (\w+)",
                    r"Setting season to (\w+)",
                    r"\[Shard\] Season: (\w+)",
                    r"Season is now (\w+)",
                    r"Season changed to (\w+)",
                ]
                for pattern in season_patterns:
                    season_match = re.search(
                        pattern, content, re.MULTILINE | re.IGNORECASE
                    )
                    if season_match:
                        shard_status["season"] = season_match.group(1).capitalize()
                        break

            # Parse Day from explicit poll or natural World State logs
            if shard_status.get("day") == "Unknown":
                day_matches = re.findall(
                    r"(?:Current day:|\[World State\] day:)\s*(\d+)", content
                )
                if day_matches:
                    last_match = day_matches[-1]
                    if f"Current day: {last_match}" in content:
                        shard_status["day"] = last_match
                    else:
                        shard_status["day"] = str(int(last_match) + 1)

            # Parse days left if not already set by c_dumpseasons
            if shard_status.get("days_left") == "Unknown":
                days_left_patterns = [
                    r"^(autumn|spring|summer|winter) \d+ -> (\d+) days \(\d+ %\) cycle",
                    r"Days left in season: (\d+)",
                    r"Season days remaining: (\d+)",
                    r"Days until season change: (\d+)",
                    r"Season will end in (\d+) days",
                    r"(\d+) days left in this season",
                ]
                for pattern in days_left_patterns:
                    days_left_match = re.search(
                        pattern, content, re.MULTILINE | re.IGNORECASE
                    )
                    if days_left_match:
                        if pattern.startswith("^(autumn|spring|summer|winter)"):
                            shard_status["days_left"] = int(days_left_match.group(2))
                        else:
                            shard_status["days_left"] = int(days_left_match.group(1))
                        break

            # Extract phase information - multiple patterns
            phase_patterns = [
                r"Current phase: (\w+)",
                r"Clock phase: (\w+)",
                r"Phase: (\w+)",
            ]
            for pattern in phase_patterns:
                phase_match = re.search(pattern, content)
                if phase_match:
                    shard_status["phase"] = phase_match.group(1)
                    break

            # Extract players - focus on recent activity and listallplayers output
            _ = []
            _ = set()
            all_players = {}  # Track all players across shards using KU_ID as key

            # Pattern for c_listallplayers output - look for actual player list
            # After c_listallplayers() command, server outputs player data

            # Parse Players using the approach from the old implementation
            # Split content by "All players:" marker to find the player list section
            dumps = content.split("All players:")
            last_dump = dumps[-1] if dumps else content

            # Try multiple patterns to find players
            player_matches = []

            # Pattern 1: [id] (KU_id) name <char>
            pattern1_matches = re.findall(
                r"\[(\d+)\]\s+\((KU_[\w-]+)\)\s+(.*?)\s+<(.*?)>", last_dump
            )
            if pattern1_matches:
                for match in pattern1_matches:
                    player_matches.append((match[1], match[2], match[3]))

            # Pattern 2: [id] (KU_id) name <char> (alternative format)
            pattern2_matches = re.findall(
                r"\[(\d+)\]\s+\((KU_[\w-]+)\)\s+(.*?)\s+<([^>]+)>", last_dump
            )
            if pattern2_matches:
                for match in pattern2_matches:
                    player_matches.append((match[1], match[2], match[3]))

            # Pattern 3: (KU_id) name <char> (without [id] prefix)
            pattern3_matches = re.findall(
                r"\s+\((KU_[\w-]+)\)\s+(.*?)\s+<(.*?)>", last_dump
            )
            if pattern3_matches:
                for match in pattern3_matches:
                    player_matches.append(match)

            shard_players = {}
            if player_matches:
                for ku_id, name, char in player_matches:
                    # Use KU_ID as key to avoid duplicates and ensure uniqueness
                    shard_players[ku_id] = {"name": name, "char": char}
                    all_players[ku_id] = {"name": name, "char": char}

            shard_status["players"] = list(shard_players.values())

        except (OSError, ValueError, KeyError) as e:
            shard_status["error"] = f"Error parsing shard log: {e}"

        return shard_status

    @staticmethod
    def get_server_status(shard_name: Optional[str] = None) -> Dict:
        """Get server status for specified shard or all shards."""
        from utils.config import read_desired_shards  # noqa: C0415

        config = get_game_config()
        cluster_name = config.get("CLUSTER_NAME", "MyDediServer")
        dst_dir = config.get("DONTSTARVE_DIR")

        # Get all shards if none specified
        if shard_name is None:
            shard_names = read_desired_shards()
        else:
            shard_names = [shard_name]

        # Initialize with default values
        combined_status = StatusManager._get_default_status()
        all_players = {}  # Track all players across shards using KU_ID as key

        for current_shard in shard_names:
            log_path = dst_dir / cluster_name / current_shard / "server_log.txt"

            if not log_path.exists():
                combined_status["shards"][current_shard] = {
                    "error": f"Log file not found for shard '{current_shard}'",
                    "players": [],
                }
                continue

            # Parse shard status using helper method
            shard_status = StatusManager._parse_shard_log(log_path)

            # Update combined status with valid shard data
            if "error" not in shard_status:
                for key in ["season", "day", "phase"]:
                    if shard_status.get(key, "Unknown") != "Unknown":
                        combined_status[key] = shard_status[key]

                # Merge players from each shard
                for player in shard_status.get("players", []):
                    all_players[player["name"]] = player

            combined_status["shards"][current_shard] = shard_status

        # Combine all players from all shards
        combined_status["players"] = list(all_players.values())

        return combined_status

    @staticmethod
    def request_status_update(shard_name: Optional[str] = None) -> bool:
        """Sends Lua commands to the server to dump current status into the logs."""
        from features.chat.chat_manager import ChatManager  # noqa: C0415
        from utils.config import read_desired_shards  # noqa: C0415

        # Get all shards if none specified
        if shard_name is None:
            shard_names = read_desired_shards()
        else:
            shard_names = [shard_name]

        commands = [
            "c_dumpseasons()",
            'print("Current day: " .. (TheWorld.components.worldstate.data.cycles + 1))',
            'print("Current phase: " .. TheWorld.components.worldstate.data.phase)',
            "c_listallplayers()",
        ]

        overall_success = True

        for current_shard in shard_names:
            for cmd in commands:
                s, _ = ChatManager.send_command(current_shard, cmd)
                if not s:
                    overall_success = False
                # Increased delay to give server more time to process commands
                time.sleep(1.0)

        return overall_success
