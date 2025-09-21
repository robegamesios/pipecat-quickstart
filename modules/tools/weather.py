from __future__ import annotations

import httpx
from typing import Any, Dict, Literal, Optional

from loguru import logger

from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.adapters.schemas.tools_schema import ToolsSchema
from pipecat.frames.frames import TTSSpeakFrame
from pipecat.services.llm_service import FunctionCallParams


def _make_wind_fields(*, kph: Optional[float], mph: Optional[float], unit: Literal["celsius", "fahrenheit"]) -> dict:
    out: dict = {}
    try:
        if unit == "celsius":
            # Prefer KPH for metric
            if kph is None and mph is not None:
                kph = mph / 0.621371
            if kph is not None:
                out["wind_speed"] = int(round(float(kph)))
                out["wind_speed_unit"] = "kilometers per hour"
                out["wind_unit_code"] = "kph"
        else:
            # Prefer MPH for imperial
            if mph is None and kph is not None:
                mph = kph * 0.621371
            if mph is not None:
                out["wind_speed"] = int(round(float(mph)))
                out["wind_speed_unit"] = "miles per hour"
                out["wind_unit_code"] = "mph"
    except Exception:
        pass
    return out

def _as_float(x: Any) -> Optional[float]:
    try:
        return float(x) if x is not None else None
    except (TypeError, ValueError):
        return None

def _as_int(x: Any) -> Optional[int]:
    try:
        # int("45") and int(45.2) both OK; None guarded above
        return int(x) if x is not None else None
    except (TypeError, ValueError):
        return None

def _extract_current_cc(data: Dict[str, Any], unit: Literal["celsius", "fahrenheit"]) -> Dict[str, Any]:
    # current_condition is usually a list with one dict
    cc_list = data.get("current_condition") or []
    cc = cc_list[0] if isinstance(cc_list, list) and cc_list else {}

    # Description
    descs = cc.get("weatherDesc") or []
    if isinstance(descs, list) and descs and isinstance(descs[0], dict):
        desc_raw = (descs[0].get("value") or "")
    else:
        desc_raw = ""
    desc = (str(desc_raw).strip() or "Unknown")

    # Temperature (prefers temp_* then falls back to FeelsLike*)
    if unit == "celsius":
        raw_temp = cc.get("temp_C")
        if raw_temp is None:
            raw_temp = cc.get("FeelsLikeC")
        unit_label = "Celsius"
    else:
        raw_temp = cc.get("temp_F")
        if raw_temp is None:
            raw_temp = cc.get("FeelsLikeF")
        unit_label = "Fahrenheit"

    ftemp = _as_float(raw_temp)
    temp = int(round(ftemp)) if ftemp is not None else None

    out: Dict[str, Any] = {
        "conditions": desc,
        "temperature": temp,
        "temperature_unit": unit_label,
    }

    # Humidity
    hum = _as_int(cc.get("humidity"))
    if hum is not None:
        out["humidity"] = hum

    # Wind inputs (both optional; your _make_wind_fields can decide how to present)
    kph = _as_float(cc.get("windspeedKmph"))
    mph = _as_float(cc.get("windspeedMiles"))
    out.update(_make_wind_fields(kph=kph, mph=mph, unit=unit))

    return out

def _extract_period_forecast(
    data: dict, *, day_index: int, part_of_day: Optional[str], unit: Literal["celsius", "fahrenheit"]
) -> Optional[dict]:
    weather = data.get("weather") or []
    if not weather or day_index >= len(weather):
        return None
    day = weather[day_index]
    hourly = day.get("hourly") or []

    # Map parts of day to wttr.in 3-hour buckets
    targets = {
        "morning": ["600", "900"],
        "afternoon": ["1200", "1500"],
        "evening": ["1800"],
        "night": ["2100", "0"],
        None: ["1200"],  # default to noon snapshot if no part specified
    }
    wanted = targets.get(part_of_day, targets[None])

    # Pick the first matching bucket present; otherwise take the middle bucket
    pick = None
    by_time = {str(h.get("time")): h for h in hourly}
    for t in wanted:
        if t in by_time:
            pick = by_time[t]
            break
    if pick is None and hourly:
        pick = hourly[min(len(hourly) // 2, len(hourly) - 1)]
    if pick is None:
        return None

    descs = pick.get("weatherDesc") or []
    desc = (descs[0].get("value") if descs else "").strip() or "Unknown"
    temp_key = "tempC" if unit == "celsius" else "tempF"
    try:
        temp = float(pick.get(temp_key))
    except Exception:
        temp = None

    out = {
        "conditions": desc,
        "temperature_unit": "Celsius" if unit == "celsius" else "Fahrenheit",
    }
    if temp is not None:
        out["temperature"] = int(round(temp))
    # Wind speed in words, selecting mph/kph based on unit
    wind_kph_val = pick.get("windspeedKmph")
    wind_miles_val = pick.get("windspeedMiles")
    try:
        kph = float(wind_kph_val) if wind_kph_val is not None else None
    except Exception:
        kph = None
    try:
        mph = float(wind_miles_val) if wind_miles_val is not None else None
    except Exception:
        mph = None
    out.update(_make_wind_fields(kph=kph, mph=mph, unit=unit))
    if pick.get("chanceofrain") is not None:
        try:
            out["chance_of_rain_pct"] = int(pick.get("chanceofrain"))
        except Exception:
            pass
    return out


def _parse_when(when: Optional[str]) -> tuple[int, Optional[str], str]:
    """Return (day_index, part_of_day, label) from a human-ish 'when' string.

    Supported examples: 'now', 'today', 'tomorrow', 'tomorrow morning',
    'tonight', 'this evening', 'tomorrow night'. Defaults to current conditions.
    """
    if not when:
        return 0, None, "now"
    w = when.lower().strip()
    if w in ("now", "current", "right now"):
        return 0, None, "now"
    day_index = 0
    part: Optional[str] = None
    if "tomorrow" in w:
        day_index = 1
    elif "day after" in w or "in 2 days" in w:
        day_index = 2
    elif "today" in w:
        day_index = 0

    if any(p in w for p in ["morning", "am"]):
        part = "morning"
    elif any(p in w for p in ["afternoon", "pm"]):
        part = "afternoon"
    elif any(p in w for p in ["evening", "sunset"]):
        part = "evening"
    elif any(p in w for p in ["night", "tonight"]):
        part = "night"
    return day_index, part, w


async def fetch_weather(params: FunctionCallParams) -> None:
    """Fetch current weather using wttr.in and return it to the LLM.

    Expects `params.arguments` to contain:
    - location: str (e.g., "San Francisco, CA")
    - format: "celsius" | "fahrenheit"
    """
    args = params.arguments or {}
    location = str(args.get("location", "")).strip()
    unit: Literal["celsius", "fahrenheit"] = args.get("format", "fahrenheit")  # type: ignore
    when: Optional[str] = args.get("when")

    if not location:
        await params.result_callback({"error": "missing_location"})
        return

    try:
        await params.llm.push_frame(TTSSpeakFrame("Let me check on that."))
    except Exception:
        pass

    url = f"https://wttr.in/{location}?format=j1"
    logger.info(
        f"tools.weather: location='{location}' format='{unit}' when='{when or 'now'}'"
    )
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
        day_index, part, label = _parse_when(when)
        if when and label != "now":
            snap = _extract_period_forecast(data, day_index=day_index, part_of_day=part, unit=unit)
            if snap is None:
                # Fall back to current
                snap = _extract_current_cc(data, unit)
                snap["note"] = "forecast_unavailable_fallback_to_current"
            result = {"location": location, "format": unit, "when": label, **snap}
        else:
            snap = _extract_current_cc(data, unit)
            result = {"location": location, "format": unit, "when": "now", **snap}

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
            "when": {
                "type": "string",
                "description": "Optional: when to check, e.g. 'now', 'tomorrow morning', 'tonight'.",
            },
        },
        required=["location", "format"],
    )
    return ToolsSchema(standard_tools=[weather_function])


def register_weather_tool(llm):
    """Register the weather tool handler with the given LLM service."""
    llm.register_function("get_current_weather", fetch_weather)
