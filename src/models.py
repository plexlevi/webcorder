from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Any


@dataclass
class Session:
    page_url: str
    resolved_url: Optional[str] = None
    rec_proc: Any = None
    elapsed_seconds: int = 0
    elapsed_running: bool = False
    tree_item_id: Optional[str] = None
    status: str = "Idle"
