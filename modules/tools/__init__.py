from __future__ import annotations

# Re-export common helpers
from .weather import create_weather_tools as create_weather_tools
from .weather import register_weather_tool as register_weather_tool
from .google_search import (
    create_google_search_tools,
    register_google_search_tool,
)
from pipecat.adapters.schemas.tools_schema import ToolsSchema


def create_all_tools() -> ToolsSchema:
    """Combine all tool schemas into a single ToolsSchema.

    Currently merges weather + google search tools.
    """
    w = create_weather_tools()
    g = create_google_search_tools()
    # Merge by concatenating standard tool schemas
    return ToolsSchema(standard_tools=[*w.standard_tools, *g.standard_tools])

__all__ = [
    "create_weather_tools",
    "register_weather_tool",
    "create_google_search_tools",
    "register_google_search_tool",
    "create_all_tools",
]
