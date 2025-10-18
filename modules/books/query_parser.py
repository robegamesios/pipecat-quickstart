from __future__ import annotations

import re
from typing import Any, Dict

from .handlers import (
    get_document_list,
    list_sections,
    show_next_section,
    show_previous_section,
    show_section,
    focus_document_by_index,
)


API_RESPONSE_TYPES = {
    "section_content": "section_content",
    "section_list": "section_list",
    "document_list": "document_list",
    "focus": "focus",
    "message": "message",
    "error": "error",
    "end": "end",
}


async def parse_document_query(query: str) -> Dict[str, Any]:
    q = (query or "").lower().strip()

    if "show" in q and ("section" in q or "chapter" in q):
        return await _handle_show_section(q)
    if "list" in q and ("section" in q or "chapter" in q):
        return await _handle_list_sections()
    if "list" in q and ("document" in q or "book" in q):
        return await _handle_list_documents()
    if "focus" in q:
        return await _handle_focus(q)
    if "next" in q and ("section" in q or "chapter" in q):
        return await _handle_next_section()
    if "previous" in q and ("section" in q or "chapter" in q):
        return await _handle_previous_section()

    return {
        "success": False,
        "type": API_RESPONSE_TYPES["error"],
        "message": (
            f"Could not understand query: '{query}'. Try 'show section 4', 'list sections', 'list documents', etc."
        ),
    }


async def _handle_show_section(q: str) -> Dict[str, Any]:
    m = re.search(r"(?:section|chapter)\s*(\d+)", q)
    if not m:
        return {"success": False, "message": "Please specify a section number, e.g., 'show section 4'"}
    n = m.group(1)
    text = await show_section(n)
    # Attempt to extract title for UI display (first line before === divider)
    title = None
    if "\n" in text:
        title = text.split("\n", 1)[0].strip()
    return {
        "success": True,
        "type": API_RESPONSE_TYPES["section_content"],
        "section_number": int(n),
        "title": title,
        "content": text.split("\n" + "=" * 60 + "\n", 1)[-1] if "=" * 60 in text else text,
        "message": f"Showing {title or f'Section {n}'}",
    }


async def _handle_list_sections() -> Dict[str, Any]:
    msg = await list_sections()
    # For the UI, provide structured sections if possible via handlers again
    # Handlers.list_sections returns formatted text; for consistency, re-fetch
    ok, _, docs = await get_document_list()
    if not ok or not docs:
        return {"success": False, "message": msg}
    # Not knowing focused id here; the UI mainly needs an array. Defer to show_section flow.
    return {"success": True, "type": API_RESPONSE_TYPES["message"], "message": msg}


async def _handle_list_documents() -> Dict[str, Any]:
    ok, message, documents = await get_document_list()
    if ok:
        return {
            "success": True,
            "type": API_RESPONSE_TYPES["document_list"],
            "documents": documents or {},
            "message": message,
        }
    return {"success": False, "message": message}


async def _handle_focus(q: str) -> Dict[str, Any]:
    m = re.search(r"(?:book|document)\s*(\d+)", q)
    if not m:
        return {
            "success": False,
            "message": "Please specify a document number, e.g., 'focus on book 1'",
        }
    idx = m.group(1)
    msg = await focus_document_by_index(idx)
    return {"success": True, "type": API_RESPONSE_TYPES["focus"], "message": msg}


async def _handle_next_section() -> Dict[str, Any]:
    text = await show_next_section()
    return {
        "success": True,
        "type": API_RESPONSE_TYPES["section_content"],
        "content": text,
        "message": "Next section",
    }


async def _handle_previous_section() -> Dict[str, Any]:
    text = await show_previous_section()
    return {
        "success": True,
        "type": API_RESPONSE_TYPES["section_content"],
        "content": text,
        "message": "Previous section",
    }

