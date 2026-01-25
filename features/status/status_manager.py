#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Status manager for handling server status operations."""

import json
import logging
import os
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from utils.config import config_manager, get_game_config


@dataclass
class ModStatus:
    """Mod status information."""
    id: str
    name: str
    enabled: bool
    loaded_in_game: bool = False
    error_count: int = 0
    last_error: Optional[str] = None
    configuration_valid: bool = True


class StatusManager:
    """Manages server status operations."""

    def __init__(self):
        self.config = get_game_config()
        self.dst_dir = self.config.get("DONTSTARVE_DIR")
        self.cluster_name = self.config.get("CLUSTER_NAME", "MyDediServer")
        self.install_dir = self.config.get("INSTALL_DIR")
        
        # Mod monitoring state
        self._mod_status_cache: Dict[str, ModStatus] = {}
        self._last_update = 0
        self._update_lock = threading.Lock()
        self.logger = logging.getLogger(__name__)

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

    def get_mod_status(self, workshop_id: str) -> Optional[ModStatus]:
        """Get status for a specific mod."""
        with self._update_lock:
            return self._mod_status_cache.get(workshop_id)

    def update_all_mod_status(self, mods_list: List[Dict]):
        """Update status for all mods in list."""
        try:
            for mod_info in mods_list:
                workshop_id = mod_info['id']
                
                if workshop_id not in self._mod_status_cache:
                    self._mod_status_cache[workshop_id] = ModStatus(
                        id=workshop_id,
                        name=mod_info.get('name', workshop_id),
                        enabled=mod_info.get('enabled', False)
                    )
                
                mod_status = self._mod_status_cache[workshop_id]
                mod_status.enabled = mod_info.get('enabled', False)
                
                # Check if mod is loaded in game logs
                mod_status.loaded_in_game = self._check_mod_loaded_in_game(workshop_id)
                
                # Validate mod configuration
                mod_status.configuration_valid = self._validate_mod_configuration(workshop_id)
                
                # Check for mod errors in logs
                mod_status.error_count, mod_status.last_error = self._check_mod_errors(workshop_id)
        
        except Exception as e:
            self.logger.error(f"Error updating mod status: {e}")

    def _check_mod_loaded_in_game(self, workshop_id: str) -> bool:
        """Check if mod is loaded by examining server logs."""
        try:
            # Check in all shard log files
            cluster_path = self.dst_dir / self.cluster_name
            
            if not cluster_path.exists():
                return False
                
            for shard_dir in cluster_path.iterdir():
                if not shard_dir.is_dir():
                    continue
                    
                log_file = shard_dir / "server_log.txt"
                if not log_file.exists():
                    continue
                
                content = log_file.read_text(encoding="utf-8", errors="ignore")
                
                # Look for mod loading messages
                patterns = [
                    rf'Loading mod:.*{workshop_id}',
                    rf'Mod.*{workshop_id}.*loaded',
                    rf'Registering mod.*{workshop_id}'
                ]
                
                for pattern in patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error checking if mod {workshop_id} is loaded: {e}")
            return False

    def _validate_mod_configuration(self, workshop_id: str) -> bool:
        """Validate mod configuration."""
        try:
            mod_overrides_path = self.dst_dir / self.cluster_name / "Master" / "modoverrides.lua"
            if not mod_overrides_path.exists():
                return True  # No overrides is valid
            
            content = mod_overrides_path.read_text(encoding="utf-8", errors="ignore")
            
            # Check if mod entry exists and has valid syntax
            mod_pattern = rf'\["{workshop_id}"\]\s*=\s*\{{([^}}]*)\}}'
            match = re.search(mod_pattern, content, re.DOTALL)
            
            if not match:
                return workshop_id not in content  # Not present is OK
            
            # Basic syntax validation
            config_content = match.group(1)
            
            # Check for balanced braces (basic check)
            open_braces = config_content.count('{')
            close_braces = config_content.count('}')
            
            return open_braces == close_braces
            
        except Exception as e:
            self.logger.error(f"Error validating mod configuration for {workshop_id}: {e}")
            return False

    def _check_mod_errors(self, workshop_id: str) -> Tuple[int, Optional[str]]:
        """Check for mod-related errors in server logs."""
        try:
            error_count = 0
            last_error = None
            
            cluster_path = self.dst_dir / self.cluster_name
            
            if not cluster_path.exists():
                return 0, None
                
            for shard_dir in cluster_path.iterdir():
                if not shard_dir.is_dir():
                    continue
                    
                log_file = shard_dir / "server_log.txt"
                if not log_file.exists():
                    continue
                
                content = log_file.read_text(encoding="utf-8", errors="ignore")
                lines = content.split('\n')
                
                # Look for recent errors (last 200 lines)
                recent_lines = lines[-200:]
                
                for line in recent_lines:
                    # Look for mod-related error patterns
                    error_patterns = [
                        rf'.*error.*{workshop_id}.*',
                        rf'.*failed.*{workshop_id}.*',
                        rf'.*{workshop_id}.*error.*',
                        rf'.*mod.*{workshop_id}.*failed.*'
                    ]
                    
                    for pattern in error_patterns:
                        if re.search(pattern, line, re.IGNORECASE):
                            error_count += 1
                            last_error = line.strip()
            
            return error_count, last_error
            
        except Exception as e:
            self.logger.error(f"Error checking mod errors for {workshop_id}: {e}")
            return 0, None

    def get_server_stats_summary(self) -> Dict:
        """Get a summary of server and mod status."""
        # Get basic server stats (reuse existing functionality)
        server_status = self.get_server_status()
        
        # Count mod status
        total_mods = len(self._mod_status_cache)
        enabled_mods = sum(1 for mod in self._mod_status_cache.values() if mod.enabled)
        loaded_mods = sum(1 for mod in self._mod_status_cache.values() if mod.loaded_in_game)
        mods_with_errors = sum(1 for mod in self._mod_status_cache.values() if mod.error_count > 0)
        
        # Get player count
        player_count = len(server_status.get("players", []))
        
        # Get season/day info
        day = server_status.get("day", "Unknown")
        season = server_status.get("season", "Unknown")
        
        return {
            "server_stats": {
                "player_count": player_count,
                "day": day,
                "season": season,
                "shard_status": server_status.get("shards", {})
            },
            "mod_summary": {
                "total_mods": total_mods,
                "enabled_mods": enabled_mods,
                "loaded_mods": loaded_mods,
                "mods_with_errors": mods_with_errors
            },
            "last_update": self._last_update
        }

    def start_monitoring(self, update_interval: int = 10):
        """Start background monitoring thread."""
        def monitor_loop():
            while True:
                try:
                    self._last_update = time.time()
                    # Server status is updated on-demand
                    time.sleep(update_interval)
                except Exception as e:
                    self.logger.error(f"Error in monitoring loop: {e}")
                    time.sleep(update_interval)
        
        monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        monitor_thread.start()
        self.logger.info(f"Started server monitoring with {update_interval}s interval")

    def get_memory_usage(self) -> float:
        """Get memory usage for DST processes."""
        try:
            import psutil
            
            total_memory = 0
            
            # Find DST processes
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmdline = ' '.join(proc.info['cmdline'] or [])
                    if 'dontstarve_dedicated_server' in cmdline:
                        total_memory += proc.info['memory_info'].rss / 1024 / 1024  # MB
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            return total_memory
            
        except ImportError:
            # psutil not available, skip memory monitoring
            return 0.0
