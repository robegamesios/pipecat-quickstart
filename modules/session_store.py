from __future__ import annotations

from typing import Dict, List, Optional, Tuple

"""In-memory session store keyed by client_id.

Supports two styles:
- Legacy `history` (flat user/assistant turns list)
- New summarization: rolling `summary` + recent `turns`
"""

_HISTORIES: Dict[str, List[dict]] = {}
_SUMMARY: Dict[str, str] = {}
_TURNS: Dict[str, List[dict]] = {}
_CLEARED: Dict[str, bool] = {}


def get_history(client_id: Optional[str]) -> List[dict]:
    if not client_id:
        return []
    return list(_HISTORIES.get(client_id, []))


def set_history(client_id: Optional[str], history: List[dict]) -> None:
    if not client_id:
        return
    # Store a shallow copy to avoid accidental external mutation
    _HISTORIES[client_id] = list(history or [])


def clear_history(client_id: Optional[str]) -> None:
    if not client_id:
        return
    _HISTORIES[client_id] = []
    _SUMMARY.pop(client_id, None)
    _TURNS.pop(client_id, None)
    _CLEARED[client_id] = True


def was_cleared(client_id: Optional[str]) -> bool:
    if not client_id:
        return False
    flag = _CLEARED.get(client_id, False)
    if flag:
        _CLEARED.pop(client_id, None)
    return flag


def get_session(client_id: Optional[str]) -> Tuple[str, List[dict]]:
    """Return (summary, turns) for client_id, defaults to empty."""
    if not client_id:
        return "", []
    return _SUMMARY.get(client_id, ""), list(_TURNS.get(client_id, []))


def set_session(client_id: Optional[str], summary: str, turns: List[dict]) -> None:
    if not client_id:
        return
    _SUMMARY[client_id] = str(summary or "")
    _TURNS[client_id] = list(turns or [])


def summarize_and_trim(
    client_id: Optional[str],
    all_turns: List[dict],
    *,
    keep_last: int = 30,
    summarize_chunk: int = 30,
    max_summary_chars: int = 3500,
) -> Tuple[str, List[dict]]:
    """Lightweight summarization: keep last `keep_last` turns verbatim and
    condense older turns into a rolling summary string.

    This implementation does a naive text condensation (role labels + trimmed
    single-line messages). It's intentionally simple and fast; you can swap the
    body with an LLM call later without changing callers.
    """
    if not client_id:
        return "", all_turns[-keep_last:]

    ua_turns = [t for t in all_turns if t.get("role") in ("user", "assistant")]
    if len(ua_turns) <= keep_last:
        set_session(client_id, _SUMMARY.get(client_id, ""), ua_turns)
        return _SUMMARY.get(client_id, ""), ua_turns

    # Oldest chunk to summarize (limit per pass)
    oldest = ua_turns[:-keep_last]
    if len(oldest) > summarize_chunk:
        oldest = oldest[:summarize_chunk]

    # Build condensed lines
    lines: List[str] = []
    for t in oldest:
        role_label = (str(t.get("role", "")).strip() or "unknown").title()
        content = str(t.get("content", "")).strip()
        if not content:
            continue
        content = " ".join(content.split())
        lines.append(f"{role_label}: {content}")
    piece = " \n".join(lines)

    prev = _SUMMARY.get(client_id, "")
    combined = (prev + "\n" + piece).strip() if prev else piece
    # Enforce character cap (front-truncate)
    if len(combined) > max_summary_chars:
        combined = ("... " + combined[-max_summary_chars:]).strip()

    kept = ua_turns[-keep_last:]
    set_session(client_id, combined, kept)
    return combined, kept
