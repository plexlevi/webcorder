import os
import re
import sys
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable

TS_FMT = "%Y%m%d_%H%M%S"

# Global log callback for GUI integration
_log_callback: Optional[Callable[[str], None]] = None


def set_log_callback(callback: Callable[[str], None]) -> None:
    """Set the global log callback for GUI integration"""
    global _log_callback
    _log_callback = callback


def log_message(message: str) -> None:
    """Log a message to both console and GUI (if callback is set)"""
    print(message)
    if _log_callback:
        try:
            _log_callback(message)
        except Exception:
            pass  # Don't let GUI logging errors break the core functionality


def timestamp() -> str:
    return datetime.now().strftime(TS_FMT)


def sanitize_filename(name: str) -> str:
    return re.sub(r"[\\/:*?\"<>|]+", "_", name).strip()


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def project_root() -> Path:
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base)
    # Go up from src directory to project root
    return Path(__file__).resolve().parent.parent


def resources_dir() -> Path:
    return project_root() / "resources"


def bin_dir() -> Path:
    plat = sys.platform
    if plat.startswith("win"):
        return resources_dir() / "bin" / "win"
    if plat.startswith("linux"):
        return resources_dir() / "bin" / "linux"
    if plat == "darwin":
        return resources_dir() / "bin" / "mac"
    return resources_dir() / "bin"


def which(exe: str) -> Optional[str]:
    packaged = bin_dir() / exe
    if packaged.exists():
        return str(packaged)
    for p in os.environ.get("PATH", "").split(os.pathsep):
        candidate = Path(p) / exe
        if candidate.exists():
            return str(candidate)
    return None


_BIN = bin_dir()
if _BIN.exists():
    os.environ["PATH"] = str(_BIN) + os.pathsep + os.environ.get("PATH", "")
