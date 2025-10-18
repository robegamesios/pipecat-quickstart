from __future__ import annotations

import os
import urllib.parse
from typing import Optional

import httpx
from loguru import logger

from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.adapters.schemas.tools_schema import ToolsSchema
from pipecat.services.llm_service import FunctionCallParams


API_URL = "https://www.googleapis.com/customsearch/v1"


async def google_search(params: FunctionCallParams) -> None:
    """Search the web with Google Custom Search and return top results.

    Expected arguments in params.arguments:
      - query: The search query string.
      - max_results: Optional int (1-10). Default 5.
      - date_restrict: Optional string like "d1", "w1", "m1" to restrict results.
      - safe: Optional "off" | "active".
      - gl: Optional country code for region bias (e.g., "us").
      - hl: Optional interface language (e.g., "en").
    """
    args = params.arguments or {}
    query = str(args.get("query", "")).strip()
    if not query:
        await params.result_callback({"error": "missing_query"})
        return

    max_results = int(args.get("max_results", 5) or 5)
    # Google API caps at 10 per request
    max_results = max(1, min(10, max_results))
    date_restrict: Optional[str] = args.get("date_restrict")
    safe: Optional[str] = args.get("safe")
    gl: Optional[str] = args.get("gl")
    hl: Optional[str] = args.get("hl")

    # Prefer standard names, accept legacy aliases for convenience
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE_SEARCH_API_KEY")
    cx = os.getenv("GOOGLE_CSE_ID") or os.getenv("GOOGLE_CX")
    if not api_key or not cx:
        logger.warning("Missing GOOGLE_API_KEY and/or GOOGLE_CSE_ID")
        await params.result_callback({
            "error": "missing_credentials",
            "message": "Google search is not configured. Set GOOGLE_API_KEY and GOOGLE_CSE_ID.",
        })
        return

    q = {
        "key": api_key,
        "cx": cx,
        "q": query,
        "num": max_results,
    }
    if date_restrict:
        q["dateRestrict"] = date_restrict
    if safe in ("off", "active"):
        q["safe"] = safe
    if gl:
        q["gl"] = gl
    if hl:
        q["hl"] = hl

    url = f"{API_URL}?{urllib.parse.urlencode(q)}"

    logger.info(
        f"tools.google_search: query='{query}' max_results={max_results} date_restrict={date_restrict} safe={safe} gl={gl} hl={hl}"
    )

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.error(f"Google search failed: {e}")
        await params.result_callback({"error": "search_failed", "message": str(e)})
        return

    items = data.get("items") or []
    results = []
    for it in items:
        results.append(
            {
                "title": it.get("title"),
                # omit full URL to discourage the model from speaking links
                "snippet": it.get("snippet"),
                "source": it.get("displayLink"),
            }
        )

    payload = {
        "query": query,
        "results": results,
        "total_estimated": data.get("searchInformation", {}).get("totalResults"),
        "search_time": data.get("searchInformation", {}).get("searchTime"),
    }
    await params.result_callback(payload)


def create_google_search_tools() -> ToolsSchema:
    """Return a ToolsSchema defining the google_search function."""
    schema = FunctionSchema(
        name="google_search",
        description="Search the web using Google Custom Search (top results).",
        properties={
            "query": {
                "type": "string",
                "description": "Search query",
            },
            "max_results": {
                "type": "integer",
                "minimum": 1,
                "maximum": 10,
                "description": "Maximum number of results (1-10). Default 5.",
            },
            "date_restrict": {
                "type": "string",
                "description": "Optional time restriction: d1, w1, m1, etc.",
            },
            "safe": {
                "type": "string",
                "enum": ["off", "active"],
                "description": "Safe search mode.",
            },
            "gl": {
                "type": "string",
                "description": "Region/country bias, e.g., 'us'",
            },
            "hl": {
                "type": "string",
                "description": "Interface language, e.g., 'en'",
            },
        },
        required=["query"],
    )
    return ToolsSchema(standard_tools=[schema])


def register_google_search_tool(llm):
    """Register the google_search function handler with the LLM service."""
    llm.register_function("google_search", google_search)
