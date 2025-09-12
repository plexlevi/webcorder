"""
Update Checker for WebCorder
Checks GitHub releases for new versions and manages update process
"""
from __future__ import annotations
import asyncio
try:
    import aiohttp  # type: ignore
except ImportError:
    aiohttp = None
import json
import tempfile
import subprocess
from pathlib import Path
from typing import Optional, Dict, Tuple
from urllib.parse import urlparse


class UpdateChecker:
    """Handles checking for updates from GitHub releases"""
    
    def __init__(self, repo_owner: str, repo_name: str, github_token: Optional[str] = None):
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.github_token = github_token
        self.api_base = "https://api.github.com"
        
    async def check_for_updates(self) -> Optional[Dict]:
        """
        Check for latest release on GitHub
        Returns: Dict with release info or None if no update available
        """
        if not aiohttp:
            print("aiohttp not available for update checking")
            return None
            
        try:
            latest_release = await self._get_latest_release()
            if latest_release:
                return {
                    "version": latest_release["tag_name"].lstrip("v"),
                    "name": latest_release["name"],
                    "body": latest_release["body"],
                    "download_url": self._get_installer_download_url(latest_release),
                    "published_at": latest_release["published_at"],
                    "html_url": latest_release["html_url"]
                }
            return None
        except Exception as e:
            print(f"Error checking for updates: {e}")
            return None
    
    async def _get_latest_release(self) -> Optional[Dict]:
        """Get latest release from GitHub API"""
        if not aiohttp:
            return None
            
        url = f"{self.api_base}/repos/{self.repo_owner}/{self.repo_name}/releases/latest"
        headers = {"Accept": "application/vnd.github.v3+json"}
        
        if self.github_token:
            headers["Authorization"] = f"token {self.github_token}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        print(f"GitHub API error: {response.status}")
                        return None
        except Exception as e:
            print(f"Network error checking updates: {e}")
            return None
    
    def _get_installer_download_url(self, release_data: Dict) -> Optional[str]:
        """Extract installer download URL from release assets"""
        assets = release_data.get("assets", [])
        
        # Filter out source code archives (GitHub auto-generates these)
        filtered_assets = []
        for asset in assets:
            asset_name = asset["name"].lower()
            # Skip GitHub's automatic source code archives
            if asset_name.startswith("source code") or asset_name in ["source-code.zip", "source-code.tar.gz"]:
                continue
            filtered_assets.append(asset)
        
        # Look for installer file (prioritize .exe over .zip)
        installer_patterns = [
            "WebCorder-Setup-v",
            "webcorder-setup-v", 
            "setup",
            "installer",
            ".exe"
        ]
        
        for asset in filtered_assets:
            asset_name = asset["name"].lower()
            for pattern in installer_patterns:
                if pattern.lower() in asset_name:
                    return asset["browser_download_url"]
        
        # Fallback to first NON-SOURCE asset if no installer pattern found
        for asset in filtered_assets:
            asset_name = asset["name"].lower()
            # Make sure it's not a source archive
            if not any(x in asset_name for x in ["source", ".tar.gz"]) and (".exe" in asset_name or ".zip" in asset_name):
                return asset["browser_download_url"]
        
        return None
    
    async def download_update(self, download_url: str, progress_callback=None) -> Optional[Path]:
        """
        Download update file to temporary location
        Args:
            download_url: URL to download from
            progress_callback: Optional callback for download progress
        Returns: Path to downloaded file or None if failed
        """
        if not aiohttp:
            print("aiohttp not available for downloading updates")
            return None
            
        try:
            # Create temporary file
            temp_dir = Path(tempfile.gettempdir()) / "webcorder_update"
            temp_dir.mkdir(exist_ok=True)
            
            # Get filename from URL
            parsed_url = urlparse(download_url)
            filename = Path(parsed_url.path).name
            if not filename or not filename.endswith(('.exe', '.zip')):
                filename = "webcorder_update.exe"
            
            download_path = temp_dir / filename
            
            headers = {}
            if self.github_token:
                headers["Authorization"] = f"token {self.github_token}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(download_url, headers=headers) as response:
                    if response.status == 200:
                        total_size = int(response.headers.get('content-length', 0))
                        downloaded = 0
                        
                        with open(download_path, 'wb') as f:
                            async for chunk in response.content.iter_chunked(8192):
                                f.write(chunk)
                                downloaded += len(chunk)
                                
                                if progress_callback and total_size > 0:
                                    progress = (downloaded / total_size) * 100
                                    progress_callback(progress)
                        
                        return download_path
                    else:
                        print(f"Download failed: {response.status}")
                        return None
                        
        except Exception as e:
            print(f"Error downloading update: {e}")
            return None
    
    def install_update(self, installer_path: Path, silent: bool = True) -> bool:
        """
        Install the downloaded update
        Args:
            installer_path: Path to installer file
            silent: Whether to run silent installation
        Returns: True if installation started successfully
        """
        try:
            if not installer_path.exists():
                print(f"Installer not found: {installer_path}")
                return False
            
            # Prepare installation command
            if installer_path.suffix.lower() == '.exe':
                # Run installer
                cmd = [str(installer_path)]
                if silent:
                    cmd.extend(['/SILENT', '/NORESTART'])
                
                # Start installer and exit current application
                subprocess.Popen(cmd, shell=True)
                return True
                
            elif installer_path.suffix.lower() == '.zip':
                # For portable version, could extract and replace files
                # This is more complex and might require application restart
                print("ZIP update not implemented yet")
                return False
            
            return False
            
        except Exception as e:
            print(f"Error installing update: {e}")
            return False
    
    def cleanup_temp_files(self):
        """Clean up temporary update files"""
        try:
            temp_dir = Path(tempfile.gettempdir()) / "webcorder_update"
            if temp_dir.exists():
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception as e:
            print(f"Error cleaning up temp files: {e}")
