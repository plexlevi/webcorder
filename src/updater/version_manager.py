"""
Version Manager for WebCorder
Handles version comparison, storage of skipped versions, and current version info
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, List, Optional
from packaging import version


class VersionManager:
    """Manages version information and user preferences for updates"""
    
    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.current_version = "1.0"  # TODO: Get from actual app version
        
    def get_current_version(self) -> str:
        """Get the current application version"""
        return self.current_version
    
    def is_newer_version(self, remote_version: str) -> bool:
        """Check if remote version is newer than current version"""
        try:
            return version.parse(remote_version) > version.parse(self.current_version)
        except Exception:
            return False
    
    def is_version_skipped(self, version_str: str) -> bool:
        """Check if a specific version has been skipped by user"""
        try:
            config = self._load_update_config()
            return version_str in config.get("skipped_versions", [])
        except Exception:
            return False
    
    def skip_version(self, version_str: str):
        """Mark a version as skipped by user"""
        try:
            config = self._load_update_config()
            skipped = config.get("skipped_versions", [])
            if version_str not in skipped:
                skipped.append(version_str)
                config["skipped_versions"] = skipped
                self._save_update_config(config)
        except Exception as e:
            print(f"Error skipping version: {e}")
    
    def get_last_check_time(self) -> Optional[float]:
        """Get timestamp of last update check"""
        try:
            config = self._load_update_config()
            return config.get("last_check_time")
        except Exception:
            return None
    
    def set_last_check_time(self, timestamp: float):
        """Set timestamp of last update check"""
        try:
            config = self._load_update_config()
            config["last_check_time"] = timestamp
            self._save_update_config(config)
        except Exception as e:
            print(f"Error setting last check time: {e}")
    
    def should_check_for_updates(self, check_interval_hours: int = 24) -> bool:
        """Check if enough time has passed since last update check"""
        import time
        last_check = self.get_last_check_time()
        if last_check is None:
            return True
        
        time_diff = time.time() - last_check
        return time_diff > (check_interval_hours * 3600)
    
    def _load_update_config(self) -> Dict:
        """Load update configuration from storage"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get("updates", {})
            return {}
        except Exception:
            return {}
    
    def _save_update_config(self, update_config: Dict):
        """Save update configuration to storage"""
        try:
            # Load existing config
            full_config = {}
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    full_config = json.load(f)
            
            # Update the updates section
            full_config["updates"] = update_config
            
            # Save back
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(full_config, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            print(f"Error saving update config: {e}")
