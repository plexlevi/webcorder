"""
Update Manager for WebCorder
Main coordinator for the update system
"""
from __future__ import annotations
import asyncio
import time
from pathlib import Path
from typing import Optional, Callable
import tkinter as tk

from .version_manager import VersionManager
from .update_checker import UpdateChecker
from .update_dialog import UpdateDialog
from .token_manager import load_github_token


class UpdateManager:
    """Main update system coordinator"""
    
    def __init__(self, config_path: Path, repo_owner: str, repo_name: str, 
                 github_token: Optional[str] = None):
        # Auto-load token if not provided
        if github_token is None:
            github_token = load_github_token()
            
        self.version_manager = VersionManager(config_path)
        self.update_checker = UpdateChecker(repo_owner, repo_name, github_token)
        self.config_path = config_path
        
    def check_for_updates_on_startup(self, parent_window, force_check: bool = False):
        """
        Check for updates when application starts
        Args:
            parent_window: Main application window
            force_check: Skip time-based checking and force immediate check
        """
        # Check if we should look for updates (time-based)
        if not force_check and not self.version_manager.should_check_for_updates():
            return
        
        # Check for updates in background
        def check_worker():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                update_info = loop.run_until_complete(self.update_checker.check_for_updates())
                if update_info:
                    parent_window.after(0, lambda: self._handle_update_available(parent_window, update_info))
                
                # Update last check time
                self.version_manager.set_last_check_time(time.time())
            except Exception as e:
                print(f"Update check failed: {e}")
            finally:
                loop.close()
        
        import threading
        threading.Thread(target=check_worker, daemon=True).start()
    
    def _handle_update_available(self, parent_window, update_info):
        """Handle when an update is available"""
        version = update_info['version']
        
        # Check if this version is newer
        if not self.version_manager.is_newer_version(version):
            return
            
        # Check if user has skipped this version
        if self.version_manager.is_version_skipped(version):
            print(f"Version {version} was skipped by user")
            return
        
        # Show update dialog
        self._show_update_dialog(parent_window, update_info)
    
    def _show_update_dialog(self, parent_window, update_info):
        """Show the update dialog to user"""
        def on_install(info, progress_callback):
            return self._install_update(info, progress_callback)
        
        def on_skip(version):
            self.version_manager.skip_version(version)
            print(f"Version {version} skipped by user")
        
        def on_dismiss():
            print("Update dismissed by user")
        
        dialog = UpdateDialog(parent_window, update_info, on_install, on_skip, on_dismiss)
        dialog.show()
    
    def _install_update(self, update_info, progress_callback) -> bool:
        """
        Download and install update
        Returns: True if successful, False otherwise
        """
        try:
            download_url = update_info.get('download_url')
            if not download_url:
                return False
            
            progress_callback(10, "Letöltés indítása...")
            
            # Download update
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            def download_progress(progress):
                # Map download progress to 10-80% of total progress
                total_progress = 10 + (progress * 0.7)
                progress_callback(total_progress, f"Letöltés: {progress:.1f}%")
            
            try:
                installer_path = loop.run_until_complete(
                    self.update_checker.download_update(download_url, download_progress)
                )
                
                if not installer_path:
                    return False
                
                progress_callback(90, "Telepítő indítása...")
                
                # Install update
                success = self.update_checker.install_update(installer_path, silent=True)
                
                if success:
                    progress_callback(100, "Telepítés sikeresen elindítva!")
                    return True
                else:
                    return False
                    
            finally:
                loop.close()
                
        except Exception as e:
            print(f"Update installation failed: {e}")
            return False
    
    def check_for_updates_manually(self, parent_window):
        """Manually check for updates (called from menu/button)"""
        self.check_for_updates_on_startup(parent_window, force_check=True)
    
    def get_current_version(self) -> str:
        """Get current application version"""
        return self.version_manager.get_current_version()
    
    def cleanup(self):
        """Clean up update system resources"""
        self.update_checker.cleanup_temp_files()
