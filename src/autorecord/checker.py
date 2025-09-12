from __future__ import annotations

from typing import Callable, Optional, Tuple

from src.media import resolve_with_browser


def resolve_page_url(page_url: str, log: Optional[Callable[[str], None]] = None) -> Optional[str]:
    """Resolve a page URL to a direct stream URL using browser method."""
    page_url = (page_url or "").strip()
    if not page_url:
        return None
    if log:
        log(f"Resolving: {page_url}")
    
    # Use browser method - reliable and works on all streaming sites
    res = None
    if log:
        log("Using headless browser with cache clearing...")
    try:
        res = resolve_with_browser(page_url, force_fresh=True)
    except Exception as e:
        if log:
            log(f"Browser error: {e}")
        res = None
    
    if not res:
        if log:
            log("No stream present on the URL now")
        return None
    if log:
        log(f"Resolved stream: {res.url}")
    return res.url


def check_session_status(
    page_url: str,
    resolved_url: Optional[str] = None,
    log: Optional[Callable[[str], None]] = None,
) -> Tuple[Optional[str], str]:
    """Presence-only check: if resolving yields a URL, mark Live; else No stream."""
    url = resolved_url or resolve_page_url(page_url, log=log)
    return (url, "Live") if url else (None, "No stream")
