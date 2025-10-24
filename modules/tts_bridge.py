from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Dict, Optional

# Registry of active speaker functions per WebRTC pc_id
_SPEAKERS: Dict[str, Callable[[str], Awaitable[None]]] = {}


def register_speaker(pc_id: str, speak_func: Callable[[str], Awaitable[None]]) -> None:
    _SPEAKERS[pc_id] = speak_func


def unregister_speaker(pc_id: str) -> None:
    _SPEAKERS.pop(pc_id, None)


def get_speaker(pc_id: Optional[str] = None) -> Optional[Callable[[str], Awaitable[None]]]:
    if pc_id and pc_id in _SPEAKERS:
        return _SPEAKERS[pc_id]
    # Fallback: return any available speaker (single-client use)
    return next(iter(_SPEAKERS.values()), None)

