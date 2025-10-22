from __future__ import annotations

from typing import Awaitable, Callable, Dict, Optional

_INTERRUPTERS: Dict[str, Callable[[], Awaitable[None]]] = {}


def register_interrupter(pc_id: str, interrupter: Callable[[], Awaitable[None]]) -> None:
    """Register an async callable that, when awaited, interrupts the active pipeline."""
    _INTERRUPTERS[pc_id] = interrupter


def unregister_interrupter(pc_id: str) -> None:
    _INTERRUPTERS.pop(pc_id, None)


def get_interrupter(pc_id: Optional[str] = None) -> Optional[Callable[[], Awaitable[None]]]:
    if pc_id and pc_id in _INTERRUPTERS:
        return _INTERRUPTERS[pc_id]
    # Single-session fallback: return any registered interrupter
    return next(iter(_INTERRUPTERS.values()), None)

