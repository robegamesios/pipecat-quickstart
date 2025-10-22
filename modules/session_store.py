from __future__ import annotations

from typing import Dict, List, Optional

# In-memory session store keyed by client_id
_HISTORIES: Dict[str, List[dict]] = {}


def get_history(client_id: Optional[str]) -> List[dict]:
    if not client_id:
        return []
    return list(_HISTORIES.get(client_id, []))


def set_history(client_id: Optional[str], history: List[dict]) -> None:
    if not client_id:
        return
    # Store a shallow copy to avoid accidental external mutation
    _HISTORIES[client_id] = list(history or [])

