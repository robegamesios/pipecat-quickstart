from __future__ import annotations

import httpx
from typing import Literal

from loguru import logger

from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.adapters.schemas.tools_schema import ToolsSchema
from pipecat.frames.frames import TTSSpeakFrame
from pipecat.services.llm_service import FunctionCallParams


async def fetch_weather(params: FunctionCallParams) -> None:
    """Fetch current weather using wttr.in and return it to the LLM.

    Expects `params.arguments` to contain:
    - location: str (e.g., "San Francisco, CA")
    - format: "celsius" | "fahrenheit"
    """
    args = params.arguments or {}
    location = str(args.get("location", "")).strip()
    unit: Literal["celsius", "fahrenheit"] = args.get("format", "fahrenheit")  # type: ignore

    if not location:
        await params.result_callback({"error": "missing_location"})
        return

    try:
        await params.llm.push_frame(TTSSpeakFrame("Let me check on that."))
    except Exception:
        pass

    url = f"https://wttr.in/{location}?format=j1"
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning(f"Weather fetch failed for {location}: {e}")
        await params.result_callback({
            "error": "weather_fetch_failed",
            "message": "Could not fetch weather at this time.",
            "location": location,
        })
        return

    try:
        cc = (data.get("current_condition") or [{}])[0]
        descs = cc.get("weatherDesc") or []
        desc = (descs[0].get("value") if descs else "").strip() or "Unknown"
        if unit == "celsius":
            temperature = float(cc.get("temp_C") or cc.get("FeelsLikeC"))
        else:
            temperature = float(cc.get("temp_F") or cc.get("FeelsLikeF"))

        humidity = int(cc.get("humidity")) if cc.get("humidity") is not None else None
        wind_kph = (
            float(cc.get("windspeedKmph")) if cc.get("windspeedKmph") is not None else None
        )

        result = {
            "location": location,
            "format": unit,
            "conditions": desc,
            "temperature": temperature,
        }
        if humidity is not None:
            result["humidity"] = humidity
        if wind_kph is not None:
            result["wind_kph"] = wind_kph
        await params.result_callback(result)
    except Exception as e:
        logger.warning(f"Weather parse failed for {location}: {e}")
        await params.result_callback({
            "error": "weather_parse_failed",
            "location": location,
        })


def create_weather_tools() -> ToolsSchema:
    """Create a ToolsSchema describing the `get_current_weather` tool."""
    weather_function = FunctionSchema(
        name="get_current_weather",
        description="Get the current weather",
        properties={
            "location": {
                "type": "string",
                "description": "The city and state, e.g. San Francisco, CA",
            },
            "format": {
                "type": "string",
                "enum": ["celsius", "fahrenheit"],
                "description": "The temperature unit to use. Infer this from the user's location.",
            },
        },
        required=["location", "format"],
    )
    return ToolsSchema(standard_tools=[weather_function])


def register_weather_tool(llm):
    """Register the weather tool handler with the given LLM service."""
    llm.register_function("get_current_weather", fetch_weather)
