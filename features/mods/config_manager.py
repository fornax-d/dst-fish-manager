#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Advanced mod configuration management with easy interface."""

import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from utils.config import get_game_config


class ModConfigManager:
    """Advanced configuration management for DST mods."""

    def __init__(self):
        config = get_game_config()
        self.dst_dir = config["DONTSTARVE_DIR"]
        self.install_dir = config["INSTALL_DIR"]
        self.cluster_name = config["CLUSTER_NAME"]
        
        self.logger = logging.getLogger(__name__)

    def get_mod_config_options(self, workshop_id: str) -> List[Dict]:
        """
        Extract configuration options from mod's modinfo.lua.
        Returns list of configuration option dictionaries.
        """
        try:
            modinfo_path = self.install_dir / "mods" / workshop_id / "modinfo.lua"
            if not modinfo_path.exists():
                return []
            
            content = modinfo_path.read_text(encoding="utf-8", errors="ignore")
            
            # Find configuration_options block
            config_match = re.search(r'configuration_options\s*=\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}', content, re.DOTALL)
            if not config_match:
                return []
            
            config_content = config_match.group(1)
            
            # Parse individual options
            options = []
            option_pattern = r'\{\s*name\s*=\s*"([^"]+)"[^}]*\}'
            
            for match in re.finditer(option_pattern, config_content, re.DOTALL):
                option_text = match.group(0)
                option = self._parse_single_option(option_text)
                if option:
                    options.append(option)
            
            return options
            
        except Exception as e:
            self.logger.error(f"Error parsing mod config options for {workshop_id}: {e}")
            return []

    def _parse_single_option(self, option_text: str) -> Optional[Dict]:
        """Parse a single configuration option from modinfo.lua."""
        try:
            option = {}
            
            # Extract name
            name_match = re.search(r'name\s*=\s*"([^"]+)"', option_text)
            if name_match:
                option['name'] = name_match.group(1)
            
            # Extract label
            label_match = re.search(r'label\s*=\s*"([^"]+)"', option_text)
            if label_match:
                option['label'] = label_match.group(1)
            
            # Extract hover
            hover_match = re.search(r'hover\s*=\s*"([^"]+)"', option_text)
            if hover_match:
                option['hover'] = hover_match.group(1)
            
            # Extract default value
            default_match = re.search(r'default\s*=\s*([^\s,}]+)', option_text)
            if default_match:
                default_val = default_match.group(1)
                if default_val.startswith('"') and default_val.endswith('"'):
                    option['default'] = default_val[1:-1]
                elif default_val.lower() in ['true', 'false']:
                    option['default'] = default_val.lower() == 'true'
                else:
                    try:
                        option['default'] = float(default_val)
                    except ValueError:
                        option['default'] = default_val
            
            # Extract options (for dropdown/multi-select)
            options_match = re.search(r'options\s*=\s*\{([^}]*)\}', option_text, re.DOTALL)
            if options_match:
                options_content = options_match.group(1)
                option['choices'] = self._parse_option_choices(options_content)
            
            return option
            
        except Exception as e:
            self.logger.error(f"Error parsing option: {e}")
            return None

    def _parse_option_choices(self, options_text: str) -> List[Dict]:
        """Parse choices for dropdown/multi-select options."""
        choices = []
        
        # Pattern for individual choice entries
        choice_pattern = r'\{\s*description\s*=\s*"([^"]+)"[^}]*data\s*=\s*([^\s,}]+)[^}]*\}'
        
        for match in re.finditer(choice_pattern, options_text):
            choice = {
                'description': match.group(1),
                'data': match.group(2)
            }
            
            # Remove quotes from data if present
            if choice['data'].startswith('"') and choice['data'].endswith('"'):
                choice['data'] = choice['data'][1:-1]
            
            choices.append(choice)
        
        return choices

    def get_current_mod_config(self, workshop_id: str, shard_name: str = "Master") -> Dict:
        """Get current configuration values for a mod from modoverrides.lua."""
        try:
            modoverrides_path = self.dst_dir / self.cluster_name / shard_name / "modoverrides.lua"
            if not modoverrides_path.exists():
                return {}
            
            content = modoverrides_path.read_text()
            
            # Find mod configuration block
            mod_pattern = rf'\["{workshop_id}"\]\s*=\s*\{{([^}}]*)\}}'
            match = re.search(mod_pattern, content, re.DOTALL)
            
            if not match:
                return {}
            
            config_block = match.group(1)
            
            # Parse configuration_options
            config_options_match = re.search(r'configuration_options\s*=\s*\{([^}]*)\}', config_block, re.DOTALL)
            if not config_options_match:
                return {}
            
            config_text = config_options_match.group(1)
            
            # Parse key-value pairs
            config = {}
            pair_pattern = r'(\w+)\s*=\s*([^,}]+)'
            
            for pair_match in re.finditer(pair_pattern, config_text):
                key = pair_match.group(1)
                value_str = pair_match.group(2).strip()
                
                # Parse value type
                if value_str.startswith('"') and value_str.endswith('"'):
                    config[key] = value_str[1:-1]  # String
                elif value_str.lower() in ['true', 'false']:
                    config[key] = value_str.lower() == 'true'  # Boolean
                else:
                    try:
                        if '.' in value_str:
                            config[key] = float(value_str)  # Float
                        else:
                            config[key] = int(value_str)  # Integer
                    except ValueError:
                        config[key] = value_str  # Fallback to string
            
            return config
            
        except Exception as e:
            self.logger.error(f"Error reading current mod config for {workshop_id}: {e}")
            return {}

    def update_mod_config(self, workshop_id: str, config: Dict, shard_name: str = "Master") -> bool:
        """Update configuration for a mod in modoverrides.lua."""
        try:
            modoverrides_path = self.dst_dir / self.cluster_name / shard_name / "modoverrides.lua"
            
            # Create file if it doesn't exist
            if not modoverrides_path.exists():
                modoverrides_path.parent.mkdir(parents=True, exist_ok=True)
                modoverrides_path.write_text("return {\n}\n")
            
            content = modoverrides_path.read_text()
            
            # Generate new configuration_options string
            config_str = self._dict_to_lua_config(config)
            
            # Check if mod already exists
            mod_pattern = rf'\["{workshop_id}"\]\s*=\s*\{{[^}}]*\}}'
            if re.search(mod_pattern, content, re.DOTALL):
                # Update existing mod
                new_mod_entry = self._create_mod_entry(workshop_id, config_str)
                new_content = re.sub(mod_pattern, new_mod_entry, content, flags=re.DOTALL)
            else:
                # Add new mod
                new_mod_entry = self._create_mod_entry(workshop_id, config_str)
                # Find the last closing brace before the final return end
                last_brace = content.rfind("}")
                if last_brace != -1:
                    prefix = ",\n" if content[:last_brace].strip() != "return {" else "\n"
                    new_content = (
                        content[:last_brace].rstrip() + 
                        prefix + 
                        new_mod_entry + 
                        "\n" + 
                        content[last_brace:]
                    )
                else:
                    new_content = content
            
            modoverrides_path.write_text(new_content)
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating mod config for {workshop_id}: {e}")
            return False

    def _dict_to_lua_config(self, config: Dict) -> str:
        """Convert a Python dictionary to Lua configuration_options format."""
        if not config:
            return "  "
        
        config_parts = []
        for key, value in config.items():
            if isinstance(value, str):
                config_parts.append(f'                    {key}="{value}"')
            elif isinstance(value, bool):
                config_parts.append(f'                    {key}={str(value).lower()}')
            elif isinstance(value, (int, float)):
                config_parts.append(f'                    {key}={value}')
            else:
                config_parts.append(f'                    {key}="{str(value)}"')
        
        return ",\n".join(config_parts)

    def _create_mod_entry(self, workshop_id: str, config_str: str) -> str:
        """Create a complete mod entry for modoverrides.lua."""
        if config_str.strip():
            return f'  ["{workshop_id}"]={{ configuration_options={{\n{config_str}\n                  }}, enabled=true }}'
        else:
            return f'  ["{workshop_id}"]={{ configuration_options={{  }}, enabled=true }}'

    def reset_mod_to_default(self, workshop_id: str, shard_name: str = "Master") -> bool:
        """Reset a mod's configuration to default values."""
        try:
            # Get default values from modinfo.lua
            options = self.get_mod_config_options(workshop_id)
            defaults = {}
            
            for option in options:
                if 'default' in option:
                    defaults[option['name']] = option['default']
            
            # Update with defaults
            return self.update_mod_config(workshop_id, defaults, shard_name)
            
        except Exception as e:
            self.logger.error(f"Error resetting mod {workshop_id} to defaults: {e}")
            return False

    def export_mod_config(self, workshop_id: str, shard_name: str = "Master") -> Optional[Dict]:
        """Export current mod configuration as a dictionary."""
        try:
            current_config = self.get_current_mod_config(workshop_id, shard_name)
            options = self.get_mod_config_options(workshop_id)
            
            # Create export with metadata
            export_data = {
                'workshop_id': workshop_id,
                'shard_name': shard_name,
                'configuration': current_config,
                'available_options': options,
                'export_timestamp': time.time()
            }
            
            return export_data
            
        except Exception as e:
            self.logger.error(f"Error exporting mod config for {workshop_id}: {e}")
            return None

    def import_mod_config(self, workshop_id: str, config_data: Dict, shard_name: str = "Master") -> bool:
        """Import mod configuration from exported data."""
        try:
            if 'configuration' not in config_data:
                self.logger.error("Invalid import data: missing configuration")
                return False
            
            return self.update_mod_config(workshop_id, config_data['configuration'], shard_name)
            
        except Exception as e:
            self.logger.error(f"Error importing mod config for {workshop_id}: {e}")
            return False

    def get_config_summary(self, workshop_id: str, shard_name: str = "Master") -> Dict:
        """Get a summary of mod configuration status."""
        try:
            available_options = self.get_mod_config_options(workshop_id)
            current_config = self.get_current_mod_config(workshop_id, shard_name)
            
            total_options = len(available_options)
            configured_options = len(current_config)
            
            # Check if all options have default values
            defaults_used = 0
            for option in available_options:
                if 'default' in option:
                    option_name = option['name']
                    if option_name in current_config:
                        if current_config[option_name] == option['default']:
                            defaults_used += 1
            
            return {
                'total_options': total_options,
                'configured_options': configured_options,
                'defaults_used': defaults_used,
                'customized_options': configured_options - defaults_used,
                'configuration_complete': configured_options >= total_options,
                'needs_attention': configured_options < total_options
            }
            
        except Exception as e:
            self.logger.error(f"Error getting config summary for {workshop_id}: {e}")
            return {
                'total_options': 0,
                'configured_options': 0,
                'defaults_used': 0,
                'customized_options': 0,
                'configuration_complete': False,
                'needs_attention': True
            }

    def suggest_optimal_config(self, workshop_id: str) -> Dict:
        """Suggest optimal configuration based on common patterns."""
        try:
            options = self.get_mod_config_options(workshop_id)
            suggestions = {}
            
            for option in options:
                name = option.get('name', '')
                
                # Common optimization suggestions
                if 'difficulty' in name.lower():
                    suggestions[name] = 'normal'  # Balanced difficulty
                elif 'size' in name.lower() and 'world' in name.lower():
                    suggestions[name] = 'default'  # Standard world size
                elif 'season' in name.lower():
                    suggestions[name] = 'default'  # Default season settings
                elif 'rate' in name.lower() and 'spawn' in name.lower():
                    suggestions[name] = 1.0  # Normal spawn rate
                elif 'inventory' in name.lower() and 'size' in name.lower():
                    suggestions[name] = 1.2  # Slightly larger inventory
                else:
                    # Use default value if available
                    if 'default' in option:
                        suggestions[name] = option['default']
            
            return suggestions
            
        except Exception as e:
            self.logger.error(f"Error generating config suggestions for {workshop_id}: {e}")
            return {}


# Global config manager instance
mod_config_manager = ModConfigManager()