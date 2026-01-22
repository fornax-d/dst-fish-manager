#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Status manager for handling server status operations."""

import os
import re
import time
from typing import Dict, Optional

from utils.config import get_game_config


class StatusManager:
    """Manages server status operations."""

    @staticmethod
    def get_server_status(shard_name: Optional[str] = None) -> Dict:
        from utils.config import read_desired_shards

        config = get_game_config()
        cluster_name = config.get("CLUSTER_NAME", "MyDediServer")
        dst_dir = config.get("DONTSTARVE_DIR")

        # Get all shards if none specified
        if shard_name is None:
            shard_names = read_desired_shards()
        else:
            shard_names = [shard_name]

        # Initialize with default values
        combined_status = {
            "season": "Unknown",
            "day": "Unknown",
            "days_left": "Unknown",
            "phase": "Unknown",
            "players": [],
            "shards": {},
        }

        all_players = {}

        for current_shard in shard_names:
            log_path = dst_dir / cluster_name / current_shard / "server_log.txt"

            if not log_path.exists():
                combined_status["shards"][current_shard] = {
                    "error": f"Log file not found for shard '{current_shard}'",
                    "players": []
                }
                continue

            try:
                with log_path.open("rb") as f:
                    f.seek(0, os.SEEK_END)
                    size = f.tell()
                    f.seek(max(0, size - 32768), os.SEEK_SET)
                    content = f.read().decode("utf-8", errors="ignore")

                shard_status = {
                    "season": "Unknown",
                    "day": "Unknown",
                    "days_left": "Unknown",
                    "phase": "Unknown",
                    "players": []
                }

                # Parse Season and Day from c_dumpseasons()
                season_matches = re.findall(
                    r"(?:\[Season\] Season:\s*|:\s*)(\w+)\s*(\d+)\s*(?:,\s*Remaining:|\s*->)\s*(\d+)\s*days?",
                    content,
                )
                if season_matches:
                    s_name, s_elapsed, s_rem = season_matches[-1]
                    shard_status["season"] = s_name.capitalize()
                    shard_status["day"] = str(int(s_elapsed) + 1)
                    shard_status["days_left"] = s_rem

                # Parse Day from explicit poll or natural World State logs
                day_matches = re.findall(
                    r"(?:Current day:|\[World State\] day:)\s*(\d+)", content
                )
                if day_matches:
                    last_match = day_matches[-1]
                    if f"Current day: {last_match}" in content:
                        shard_status["day"] = last_match
                    else:
                        shard_status["day"] = str(int(last_match) + 1)

                # Parse Phase
                phase_matches = re.findall(
                    r"(?:Current phase:|\[World State\] phase:)\s*(\w+)", content
                )
                if phase_matches:
                    shard_status["phase"] = phase_matches[-1].capitalize()

                # Parse Players
                dumps = content.split("All players:")
                last_dump = dumps[-1] if dumps else content

                player_matches = re.findall(
                    r"\[\d+\]\s+\((KU_[\w-]+)\)\s+(.*?)\s+<(.*?)>", last_dump
                )
                shard_players = {}
                if player_matches:
                    for ku_id, name, char in player_matches:
                        shard_players[ku_id] = {"name": name, "char": char}
                        all_players[ku_id] = {"name": name, "char": char}

                shard_status["players"] = list(shard_players.values())
                combined_status["shards"][current_shard] = shard_status

                # Update main status with data from Master shard if available
                if current_shard == "Master":
                    combined_status.update({
                        "season": shard_status["season"],
                        "day": shard_status["day"],
                        "days_left": shard_status["days_left"],
                        "phase": shard_status["phase"]
                    })

            except Exception as e:
                combined_status["shards"][current_shard] = {
                    "error": f"Error reading shard '{current_shard}': {e}",
                    "players": []
                }

        # Combine all players from all shards
        combined_status["players"] = list(all_players.values())

        return combined_status

    @staticmethod
    def request_status_update(shard_name: Optional[str] = None) -> bool:
        """Sends Lua commands to the server to dump current status into the logs."""
        from utils.config import read_desired_shards
        from features.chat.chat_manager import ChatManager

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
                time.sleep(0.5)

        return overall_success
