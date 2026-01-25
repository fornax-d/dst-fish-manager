#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Mod management feature."""

import logging
import re
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional

from utils.config import get_game_config
from ..status.status_manager import StatusManager
from .config_manager import mod_config_manager


class ModManager:
    """Handles parsing and editing of DST mod files."""

    def __init__(self):
        config = get_game_config()
        self.dst_dir = config["DONTSTARVE_DIR"]
        self.install_dir = config["INSTALL_DIR"]
        self.cluster_name = config["CLUSTER_NAME"]
        
        # Auto-refresh state
        self._auto_refresh_enabled = False
        self._refresh_interval = 30  # seconds
        self._refresh_thread = None
        self._stop_refresh = threading.Event()
        self._last_mod_list = []
        self._last_update = 0
        
        self.logger = logging.getLogger(__name__)
        
        # Status manager integration
        self.status_manager = StatusManager()

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

    def list_mods_with_status(self, shard_name: str = "Master", force_refresh: bool = False) -> List[Dict]:
        """
        Enhanced version of list_mods that includes real-time status information.
        Returns a list of dicts with additional status fields.
        """
        mods = self.list_mods(shard_name)
        
        # Update status manager with current mods
        self.status_manager.update_all_mod_status(mods)
        
        # Enhance mod info with status data
        for mod in mods:
            mod_status = self.status_manager.get_mod_status(mod['id'])
            if mod_status:
                mod.update({
                    'loaded_in_game': mod_status.loaded_in_game,
                    'error_count': mod_status.error_count,
                    'last_error': mod_status.last_error,
                    'configuration_valid': mod_status.configuration_valid,
                    'status_color': self._get_status_color(mod_status)
                })
            else:
                mod.update({
                    'loaded_in_game': False,
                    'error_count': 0,
                    'last_error': None,
                    'configuration_valid': True,
                    'status_color': 'white'
                })
        
        self._last_mod_list = mods
        self._last_update = time.time()
        return mods

    def _get_status_color(self, mod_status) -> str:
        """Get color code for mod status display."""
        if mod_status.error_count > 0:
            return 'red'
        elif not mod_status.configuration_valid:
            return 'yellow'
        elif mod_status.loaded_in_game and mod_status.enabled:
            return 'green'
        elif mod_status.enabled and not mod_status.loaded_in_game:
            return 'cyan'
        else:
            return 'white'

    def start_auto_refresh(self, interval: int = 30):
        """Start automatic refreshing of mod status."""
        if self._auto_refresh_enabled:
            return
        
        # Start the underlying status manager monitoring
        self.status_manager.start_monitoring(interval)
        
        self._refresh_interval = interval
        self._auto_refresh_enabled = True
        self._stop_refresh.clear()
        
        def refresh_loop():
            while not self._stop_refresh.wait(self._refresh_interval):
                try:
                    if self._last_mod_list:  # Only refresh if we have mods to monitor
                        self.list_mods_with_status(force_refresh=True)
                        self.logger.debug(f"Auto-refreshed mod status for {len(self._last_mod_list)} mods")
                except Exception as e:
                    self.logger.error(f"Error in auto-refresh loop: {e}")
        
        self._refresh_thread = threading.Thread(target=refresh_loop, daemon=True)
        self._refresh_thread.start()
        self.logger.info(f"Started auto-refresh with {interval}s interval")

    def stop_auto_refresh(self):
        """Stop automatic refreshing of mod status."""
        if not self._auto_refresh_enabled:
            return
        
        self._auto_refresh_enabled = False
        self._stop_refresh.set()
        
        if self._refresh_thread and self._refresh_thread.is_alive():
            self._refresh_thread.join(timeout=2)
        
        self.logger.info("Stopped auto-refresh")

    def get_server_stats_summary(self) -> Dict:
        """Get server statistics summary."""
        return self.status_manager.get_server_stats_summary()

    def get_mod_health_report(self) -> Dict:
        """Get comprehensive mod health report."""
        if not self._last_mod_list:
            self.list_mods_with_status()
        
        healthy_mods = []
        problematic_mods = []
        disabled_mods = []
        
        for mod in self._last_mod_list:
            if mod['error_count'] > 0 or not mod['configuration_valid']:
                problematic_mods.append(mod)
            elif mod['enabled'] and mod['loaded_in_game']:
                healthy_mods.append(mod)
            elif not mod['enabled']:
                disabled_mods.append(mod)
        
        return {
            'total_mods': len(self._last_mod_list),
            'healthy_mods': len(healthy_mods),
            'problematic_mods': len(problematic_mods),
            'disabled_mods': len(disabled_mods),
            'healthy_mods_list': healthy_mods,
            'problematic_mods_list': problematic_mods,
            'disabled_mods_list': disabled_mods,
            'last_update': self._last_update
        }

    def refresh_mod_status(self, workshop_id: Optional[str] = None):
        """Force refresh status for specific mod or all mods."""
        if workshop_id:
            # Refresh specific mod
            mods = [mod for mod in self._last_mod_list if mod['id'] == workshop_id]
            if mods:
                self.status_manager.update_all_mod_status(mods)
        else:
            # Refresh all mods
            self.list_mods_with_status(force_refresh=True)

    def validate_mod_configuration(self, workshop_id: str, shard_name: str = "Master") -> Dict:
        """
        Comprehensive validation of mod configuration.
        Returns detailed validation results.
        """
        validation_result = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'suggestions': []
        }
        
        try:
            # Check modoverrides.lua syntax
            path = self.get_mod_overrides_path(shard_name)
            if not path.exists():
                validation_result['warnings'].append("modoverrides.lua does not exist")
                return validation_result
            
            content = path.read_text()
            
            # Basic Lua syntax validation
            lua_errors = self._validate_lua_syntax(content)
            validation_result['errors'].extend(lua_errors)
            
            # Mod-specific configuration validation
            mod_config_errors = self._validate_mod_specific_config(workshop_id, content)
            validation_result['errors'].extend(mod_config_errors['errors'])
            validation_result['warnings'].extend(mod_config_errors['warnings'])
            validation_result['suggestions'].extend(mod_config_errors['suggestions'])
            
            # Check modinfo.lua for configuration options
            modinfo_validation = self._validate_against_modinfo(workshop_id)
            validation_result['warnings'].extend(modinfo_validation['warnings'])
            validation_result['suggestions'].extend(modinfo_validation['suggestions'])
            
            # Set overall validity
            validation_result['valid'] = len(validation_result['errors']) == 0
            
        except Exception as e:
            validation_result['valid'] = False
            validation_result['errors'].append(f"Validation failed: {str(e)}")
        
        return validation_result

    def _validate_lua_syntax(self, content: str) -> List[str]:
        """Basic Lua syntax validation for modoverrides.lua."""
        errors = []
        
        # Check for balanced braces
        open_braces = content.count('{')
        close_braces = content.count('}')
        if open_braces != close_braces:
            errors.append(f"Unbalanced braces: {open_braces} open, {close_braces} close")
        
        # Check for balanced brackets
        open_brackets = content.count('[')
        close_brackets = content.count(']')
        if open_brackets != close_brackets:
            errors.append(f"Unbalanced brackets: {open_brackets} open, {close_brackets} close")
        
        # Check for common syntax errors
        if 'return' not in content.split('\n')[0].lower():
            errors.append("modoverrides.lua should start with 'return {'")
        
        # Check for trailing commas
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.endswith(',}') or stripped.endswith(',,}'):
                errors.append(f"Line {i}: Invalid syntax near closing brace")
        
        return errors

    def _validate_mod_specific_config(self, workshop_id: str, content: str) -> Dict:
        """Validate configuration for a specific mod."""
        result = {'errors': [], 'warnings': [], 'suggestions': []}
        
        # Find mod configuration block
        mod_pattern = rf'\["{workshop_id}"\]\s*=\s*\{{([^}}]*)\}}'
        match = re.search(mod_pattern, content, re.DOTALL)
        
        if not match:
            result['warnings'].append(f"Mod {workshop_id} not found in modoverrides.lua")
            return result
        
        config_block = match.group(1)
        
        # Check for required fields
        if 'enabled' not in config_block:
            result['errors'].append(f"Mod {workshop_id}: Missing 'enabled' field")
        elif re.search(r'enabled\s*=\s*(true|false)', config_block) is None:
            result['errors'].append(f"Mod {workshop_id}: Invalid 'enabled' value")
        
        # Check for empty configuration_options
        if 'configuration_options' in config_block:
            if re.search(r'configuration_options\s*=\s*\{\s*\}', config_block):
                result['suggestions'].append(f"Mod {workshop_id}: Empty configuration_options")
        
        # Check for common typos
        common_typos = ['configuraton_options', 'configration_options', 'enable', 'enbaled']
        for typo in common_typos:
            if typo in config_block:
                result['errors'].append(f"Mod {workshop_id}: Possible typo '{typo}'")
        
        return result

    def _validate_against_modinfo(self, workshop_id: str) -> Dict:
        """Validate configuration against mod's modinfo.lua."""
        result = {'warnings': [], 'suggestions': []}
        
        try:
            modinfo_path = self.install_dir / "mods" / workshop_id / "modinfo.lua"
            if not modinfo_path.exists():
                result['warnings'].append(f"Mod {workshop_id}: modinfo.lua not found")
                return result
            
            content = modinfo_path.read_text(encoding="utf-8", errors="ignore")
            
            # Extract configuration options from modinfo
            config_options_match = re.search(r'configuration_options\s*=\s*\{([^}]+)\}', content, re.DOTALL)
            if not config_options_match:
                # Mod has no configurable options
                return result
            
            # This is a simplified validation - in a full implementation,
            # we would parse configuration_options and validate against
            # actual configuration in modoverrides.lua
            result['suggestions'].append(
                f"Mod {workshop_id}: Has configurable options - ensure they are properly set"
            )
            
        except Exception as e:
            result['warnings'].append(f"Could not validate against modinfo: {str(e)}")
        
        return result

    def fix_common_mod_issues(self, workshop_id: str, shard_name: str = "Master") -> Dict:
        """
        Attempt to automatically fix common mod configuration issues.
        Returns what was fixed and any remaining issues.
        """
        fix_result = {
            'fixed': [],
            'remaining_issues': [],
            'success': False
        }
        
        try:
            validation = self.validate_mod_configuration(workshop_id, shard_name)
            
            # Fix missing enabled field
            for error in validation['errors']:
                if "Missing 'enabled' field" in error:
                    if self._add_enabled_field(workshop_id, shard_name):
                        fix_result['fixed'].append("Added missing 'enabled' field")
                    else:
                        fix_result['remaining_issues'].append(error)
            
            # Fix syntax errors
            for error in validation['errors']:
                if "Unbalanced" in error:
                    if self._fix_balancing_issue(workshop_id, shard_name):
                        fix_result['fixed'].append("Fixed balancing issue")
                    else:
                        fix_result['remaining_issues'].append(error)
            
            # Re-validate after fixes
            final_validation = self.validate_mod_configuration(workshop_id, shard_name)
            fix_result['remaining_issues'].extend(final_validation['errors'])
            fix_result['success'] = len(final_validation['errors']) == 0
            
        except Exception as e:
            fix_result['remaining_issues'].append(f"Fix attempt failed: {str(e)}")
        
        return fix_result

    def _add_enabled_field(self, workshop_id: str, shard_name: str) -> bool:
        """Add enabled=true to mod configuration."""
        try:
            path = self.get_mod_overrides_path(shard_name)
            content = path.read_text()
            
            # Find mod block and add enabled field
            mod_pattern = r'(\["' + workshop_id + r'"\]\s*=\s*\{)([^}]*)(\})'
            match = re.search(mod_pattern, content, re.DOTALL)
            
            if match:
                prefix = match.group(1)
                config_content = match.group(2)
                suffix = match.group(3)
                
                # Add enabled field if not present
                if 'enabled' not in config_content:
                    new_config = config_content.rstrip()
                    if new_config and not new_config.endswith(','):
                        new_config += ',\n'
                    new_config += '                    enabled=true'
                    
                    new_content = content.replace(match.group(0), prefix + new_config + suffix)
                    path.write_text(new_content)
                    return True
            
            return False
            
        except Exception:
            return False

    def _fix_balancing_issue(self, workshop_id: str, shard_name: str) -> bool:
        """Attempt to fix brace/bracket balancing issues."""
        try:
            path = self.get_mod_overrides_path(shard_name)
            content = path.read_text()
            
            # Count and fix braces
            open_braces = content.count('{')
            close_braces = content.count('}')
            
            if open_braces > close_braces:
                # Add missing closing braces
                missing = open_braces - close_braces
                content += '\n' + '}' * missing
                path.write_text(content)
                return True
            else:
                return False
            
        except Exception:
            return False

    def get_mod_configuration_options(self, workshop_id: str) -> List[Dict]:
        """Get available configuration options for a mod."""
        return mod_config_manager.get_mod_config_options(workshop_id)

    def get_mod_current_config(self, workshop_id: str, shard_name: str = "Master") -> Dict:
        """Get current configuration values for a mod."""
        return mod_config_manager.get_current_mod_config(workshop_id, shard_name)

    def update_mod_configuration(self, workshop_id: str, config: Dict, shard_name: str = "Master") -> bool:
        """Update configuration for a mod."""
        return mod_config_manager.update_mod_config(workshop_id, config, shard_name)

    def reset_mod_to_default(self, workshop_id: str, shard_name: str = "Master") -> bool:
        """Reset a mod's configuration to default values."""
        return mod_config_manager.reset_mod_to_default(workshop_id, shard_name)

    def get_mod_config_summary(self, workshop_id: str, shard_name: str = "Master") -> Dict:
        """Get a summary of mod configuration status."""
        return mod_config_manager.get_config_summary(workshop_id, shard_name)

    def suggest_optimal_config(self, workshop_id: str) -> Dict:
        """Suggest optimal configuration for a mod."""
        return mod_config_manager.suggest_optimal_config(workshop_id)

    def export_mod_config(self, workshop_id: str, shard_name: str = "Master") -> Optional[Dict]:
        """Export current mod configuration."""
        return mod_config_manager.export_mod_config(workshop_id, shard_name)

    def import_mod_config(self, workshop_id: str, config_data: Dict, shard_name: str = "Master") -> bool:
        """Import mod configuration."""
        return mod_config_manager.import_mod_config(workshop_id, config_data, shard_name)