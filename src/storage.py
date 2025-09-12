from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, List, Union


def _cfg_dir() -> Path:
    """Get the config directory in the program's own folder"""
    # Go up to the project root, then to config directory
    d = Path(__file__).parent.parent / "config"
    try:
        d.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return d


def config_path() -> Path:
    """Path to the unified config file"""
    return _cfg_dir() / "webcorder_data.json"


def models_path() -> Path:
    """Path to the unified config file (same as config_path for backward compatibility)"""
    return config_path()


def settings_path() -> Path:
    """Path to the unified config file (same as config_path for backward compatibility)"""
    return config_path()


def _load_unified_data() -> Dict:
    """Load all data from the unified config file"""
    p = config_path()
    if not p.exists():
        return {"models": {}, "settings": {}}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        # Migrate old format: if 'urls' exists but 'models' is empty, convert urls to models
        if "urls" in data and data.get("urls") and not data.get("models"):
            models = {}
            for url in data["urls"]:
                models[url] = {
                    "url": url,
                    "autorecord": False,
                    "created_at": None
                }
            data["models"] = models
            # Remove the old urls key
            del data["urls"]
            # Save the migrated data
            _save_unified_data(data)
        # Ensure models key exists
        if "models" not in data:
            data["models"] = {}
        # Ensure settings key exists  
        if "settings" not in data:
            data["settings"] = {}
        # Remove urls key if it still exists (cleanup)
        if "urls" in data:
            del data["urls"]
        return data
    except Exception:
        return {"models": {}, "settings": {}}


def _save_unified_data(data: Dict) -> None:
    """Save all data to the unified config file"""
    try:
        config_path().write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def load_urls() -> List[str]:
    """Load URLs from models data (backward compatibility)"""
    data = _load_unified_data()
    models = data.get("models", {})
    return list(models.keys())


def save_urls(url_list: List[str]) -> None:
    """Save URLs as models (backward compatibility)"""
    data = _load_unified_data()
    models = data.get("models", {})
    
    # Create models for new URLs that don't exist yet
    for url in url_list:
        if url not in models:
            models[url] = {
                "url": url,
                "autorecord": False,
                "created_at": None
            }
    
    # Remove models that are no longer in the URL list
    urls_to_remove = [url for url in models.keys() if url not in url_list]
    for url in urls_to_remove:
        del models[url]
    
    data["models"] = models
    _save_unified_data(data)


def load_settings() -> Dict:
    data = _load_unified_data()
    return data.get("settings", {})


def save_settings(settings: Dict) -> None:
    data = _load_unified_data()
    data["settings"] = settings
    _save_unified_data(data)


def load_models() -> Dict[str, Dict]:
    """Load models with their autorecord status from unified config"""
    data = _load_unified_data()
    return data.get("models", {})


def save_models(models: Dict[str, Dict]) -> None:
    """Save models with their autorecord status to unified config"""
    data = _load_unified_data()
    data["models"] = models
    _save_unified_data(data)


def add_model(url: str, autorecord: bool = False) -> None:
    """Add a new model or update existing one"""
    models = load_models()
    from datetime import datetime
    models[url] = {
        "url": url,
        "autorecord": autorecord,
        "created_at": datetime.now().isoformat()
    }
    save_models(models)


def update_model_autorecord(url: str, autorecord: bool) -> None:
    """Update autorecord status for a specific model"""
    models = load_models()
    if url in models:
        models[url]["autorecord"] = autorecord
        save_models(models)


def remove_model(url: str) -> None:
    """Remove a model from storage"""
    models = load_models()
    if url in models:
        del models[url]
        save_models(models)
