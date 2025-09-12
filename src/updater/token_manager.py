"""
GitHub Token Security Manager
Handles secure loading of GitHub tokens from various sources
"""
import json
import os
from pathlib import Path
from typing import Optional


def load_github_token() -> Optional[str]:
    """
    Load GitHub token from secure sources in priority order:
    1. Environment variable GITHUB_TOKEN
    2. config/github_config.json file (development)
    3. Built-in production token (for releases)
    4. Return None if not found
    """
    
    # Method 1: Environment variable (most secure for production)
    token = os.environ.get('GITHUB_TOKEN')
    if token:
        return token.strip()
    
    # Method 2: Local config file (for development)
    try:
        # Config is in project root, not in src/
        config_path = Path(__file__).parent.parent.parent / "config" / "github_config.json"
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                token = config.get('github_token', '').strip()
                if token:
                    return token
    except Exception:
        pass
    
    # Method 3: Production token (built into release)
    try:
        from .production_token import PRODUCTION_GITHUB_TOKEN
        if PRODUCTION_GITHUB_TOKEN and PRODUCTION_GITHUB_TOKEN.strip():
            return PRODUCTION_GITHUB_TOKEN.strip()
    except ImportError:
        pass
    
    # No token found
    return None


def is_token_configured() -> bool:
    """Check if GitHub token is properly configured"""
    return load_github_token() is not None


def get_token_source() -> str:
    """Get information about where the token is loaded from"""
    if os.environ.get('GITHUB_TOKEN'):
        return "Environment variable GITHUB_TOKEN"
    
    # Config is in project root, not in src/
    config_path = Path(__file__).parent.parent.parent / "config" / "github_config.json"
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                if config.get('github_token', '').strip():
                    return "Local config file (config/github_config.json)"
        except Exception:
            pass
    
    # Check production token
    try:
        from .production_token import PRODUCTION_GITHUB_TOKEN
        if PRODUCTION_GITHUB_TOKEN and PRODUCTION_GITHUB_TOKEN.strip():
            return "Built-in production token"
    except ImportError:
        pass
    
    return "No token configured"
