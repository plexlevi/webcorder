#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
🎯 SIMPLIFIED HYBRID RESOLVER
Uses HybridStreamExtractor for fast and compatible stream resolution
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict, Any
from urllib.parse import urlparse

from src.utils import log_message
from .stream_extractor import HybridStreamExtractor


@dataclass
class ResolveResult:
    """Result object for stream resolution"""
    url: str
    protocol: str = "unknown"
    meta: Optional[Dict[str, Any]] = None
    headers: Optional[Dict[str, str]] = None


def _is_valid_stream_url(url: str) -> bool:
    """Validate that URL is actually a stream, not an image or other format"""
    url_lower = url.lower()
    
    # Skip image URLs
    image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']
    for ext in image_extensions:
        if ext in url_lower:
            return False
    
    # Skip image CDN domains
    image_domains = ['jpeg.live.', 'jpg.live.', 'png.live.', 'img.', 'image.', 'thumb.', 'preview.']
    for domain in image_domains:
        if domain in url_lower:
            return False
    
    # Only accept known streaming formats
    streaming_indicators = ['.m3u8', '.mp4', '.flv', '.webm', '.mkv', 'playlist', 'master', 'stream']
    return any(indicator in url_lower for indicator in streaming_indicators)


def _extract_title_from_url(url: str) -> str:
    """Extract a simple title from URL"""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.replace('www.', '').replace('.com', '')
        path_parts = [p for p in parsed.path.split('/') if p and p != 'room']
        
        if path_parts:
            title = f"{domain} - {path_parts[-1]}"
        else:
            title = domain
            
        return title
    except:
        return "Live Stream"


def resolve_page_url(page_url: str) -> Optional[ResolveResult]:
    """Main URL resolver using HybridStreamExtractor."""
    log_message(f"[HYBRID_RESOLVER] Starting resolution for: {page_url}")

    try:
        extractor = HybridStreamExtractor()
        try:
            log_message(f"[HYBRID_RESOLVER] Extracting stream URL...")
            stream_url = extractor.extract_stream_url(page_url)

            if stream_url and stream_url != page_url:
                # Validate that this is actually a stream URL, not an image
                if not _is_valid_stream_url(stream_url):
                    log_message(f"[HYBRID_RESOLVER] Invalid stream URL (appears to be image): {stream_url[:100]}...")
                    return None
                
                # Determine protocol from URL
                protocol = "m3u8" if ".m3u8" in stream_url else "unknown"
                
                # Get title from URL
                title = _extract_title_from_url(page_url)

                log_message(f"[HYBRID_RESOLVER] Successfully extracted stream URL: {stream_url[:100]}...")
                log_message(f"[HYBRID_RESOLVER] Protocol: {protocol}, Title: {title}")

                return ResolveResult(
                    url=stream_url,
                    protocol=protocol,
                    meta={"title": title, "source": "hybrid_extractor"}
                )
            else:
                log_message(f"[HYBRID_RESOLVER] No stream URL found")
                return None
        
        finally:
            extractor.cleanup()

    except Exception as e:
        log_message(f"[HYBRID_RESOLVER] Error: {e}")
        return None


# Backward compatibility functions
def extract_video_url(url: str) -> Optional[str]:
    """Simple URL extraction - backward compatibility"""
    result = resolve_page_url(url)
    return result.url if result else None


def extract_video_title(url: str) -> Optional[str]:
    """Extract video title - backward compatibility"""
    result = resolve_page_url(url)
    return result.meta.get("title") if result and result.meta else None


def extract_video_url_and_title(url: str) -> tuple[Optional[str], Optional[str]]:
    """Extract both URL and title - backward compatibility"""
    result = resolve_page_url(url)
    if result:
        return result.url, result.meta.get("title") if result.meta else None
    return None, None


def resolve_with_browser(url: str) -> Optional[str]:
    """Legacy function for backward compatibility"""
    return extract_video_url(url)
