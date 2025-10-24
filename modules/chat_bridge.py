from __future__ import annotations

from typing import Awaitable, Callable, Dict, Optional

_SENDERS: Dict[str, Callable[[str], Awaitable[None]]] = {}


def register_sender(pc_id: str, send_func: Callable[[str], Awaitable[None]]) -> None:
    _SENDERS[pc_id] = send_func


def unregister_sender(pc_id: str) -> None:
    _SENDERS.pop(pc_id, None)


def get_sender(pc_id: Optional[str] = None) -> Optional[Callable[[str], Awaitable[None]]]:
    if pc_id and pc_id in _SENDERS:
        return _SENDERS[pc_id]
    return next(iter(_SENDERS.values()), None)

