from __future__ import annotations

from .ffmpeg import ensure_ffmpeg, run_ffprobe
from .recorder import build_output_path, record_stream, spawn_record_process
from .stream_extractor import HybridStreamExtractor
from .resolver import resolve_page_url, ResolveResult, extract_video_url, extract_video_title

# Import VLC player
try:
    from .vlc_player import create_vlc_player, is_vlc_available, VLCVideoPlayer  # type: ignore
    VLC_AVAILABLE = True
except ImportError:
    VLC_AVAILABLE = False
    
    def create_vlc_player(canvas):  # type: ignore
        return None
    
    def is_vlc_available():  # type: ignore
        return False
    
    class VLCVideoPlayer:  # type: ignore
        pass

def resolve_with_browser(page_url: str, force_fresh: bool = True, user_agent: str | None = None) -> ResolveResult | None:
    """URL feloldás a selenium_stream_extractor használatával - backward compatibility"""
    try:
        # Use the new resolver
        return resolve_page_url(page_url)
    except Exception:
        return None

__all__ = [
    'ensure_ffmpeg',
    'run_ffprobe',
    'build_output_path',
    'record_stream',
    'spawn_record_process',
    'resolve_with_browser',
    'resolve_page_url',
    'ResolveResult',
    'HybridStreamExtractor',
    'extract_video_url',
    'extract_video_title',
    'create_vlc_player',
    'is_vlc_available',
    'VLCVideoPlayer'
]
