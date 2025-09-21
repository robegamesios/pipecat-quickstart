from __future__ import annotations

import re
from datetime import datetime, timedelta
import httpx
from typing import Any, Dict, Literal, Optional, Tuple

from loguru import logger

from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.adapters.schemas.tools_schema import ToolsSchema
from pipecat.frames.frames import TTSSpeakFrame
from pipecat.services.llm_service import FunctionCallParams


# -----------------------------
# Utilities
# -----------------------------

def _as_float(x: Any) -> Optional[float]:
    try:
        return float(x) if x is not None else None
    except (TypeError, ValueError):
        return None

def _as_int(x: Any) -> Optional[int]:
    try:
        return int(x) if x is not None else None
    except (TypeError, ValueError):
        return None


def _make_wind_fields(
    *,
    kph: Optional[float],
    mph: Optional[float],
    unit: Literal["celsius", "fahrenheit"],
) -> dict:
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
        # Keep wind fields optional on bad/missing data
        pass
    return out


def _day_hi_lo(day: Dict[str, Any], unit: Literal["celsius", "fahrenheit"]) -> Tuple[Optional[int], Optional[int]]:
    """Return (high, low) int temps for the given daily block."""
    if unit == "celsius":
        hi = _as_float(day.get("maxtempC"))
        lo = _as_float(day.get("mintempC"))
    else:
        hi = _as_float(day.get("maxtempF"))
        lo = _as_float(day.get("mintempF"))
    hi_i = int(round(hi)) if hi is not None else None
    lo_i = int(round(lo)) if lo is not None else None
    return hi_i, lo_i


# -----------------------------
# Current conditions + period forecast
# -----------------------------

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

    # Temperature (prefer temp_* then fall back to FeelsLike*)
    if unit == "celsius":
        raw_temp = cc.get("temp_C") or cc.get("FeelsLikeC")
        unit_label = "Celsius"
    else:
        raw_temp = cc.get("temp_F") or cc.get("FeelsLikeF")
        unit_label = "Fahrenheit"

    ftemp = _as_float(raw_temp)
    temp = int(round(ftemp)) if ftemp is not None else None

    out: Dict[str, Any] = {
        "conditions": desc,
        "temperature": temp,
        "temperature_unit": unit_label,
    }

    # Humidity (optional)
    hum = _as_int(cc.get("humidity"))
    if hum is not None:
        out["humidity"] = hum

    # Wind (optional)
    kph = _as_float(cc.get("windspeedKmph"))
    mph = _as_float(cc.get("windspeedMiles"))
    out.update(_make_wind_fields(kph=kph, mph=mph, unit=unit))

    # Daily high/low from today's daily block, if available
    weather_days = data.get("weather") or []
    if isinstance(weather_days, list) and weather_days:
        hi, lo = _day_hi_lo(weather_days[0], unit)
        if hi is not None:
            out["high_temperature"] = hi
        if lo is not None:
            out["low_temperature"] = lo

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
        "noon": ["1200"],
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

    # Conditions
    descs = pick.get("weatherDesc") or []
    desc_raw = (descs[0].get("value") if descs and isinstance(descs[0], dict) else "") or ""
    desc = (str(desc_raw).strip() or "Unknown")

    # Temperature snapshot at that time
    temp_key = "tempC" if unit == "celsius" else "tempF"
    temp_float = _as_float(pick.get(temp_key))
    temp_int = int(round(temp_float)) if temp_float is not None else None

    out: Dict[str, Any] = {
        "conditions": desc,
        "temperature_unit": "Celsius" if unit == "celsius" else "Fahrenheit",
    }
    if temp_int is not None:
        out["temperature"] = temp_int

    # Daily high/low for that day
    hi, lo = _day_hi_lo(day, unit)
    if hi is not None:
        out["high_temperature"] = hi
    if lo is not None:
        out["low_temperature"] = lo

    # Wind (optional)
    kph = _as_float(pick.get("windspeedKmph"))
    mph = _as_float(pick.get("windspeedMiles"))
    out.update(_make_wind_fields(kph=kph, mph=mph, unit=unit))

    # Chance of rain (optional)
    rain = _as_int(pick.get("chanceofrain"))
    if rain is not None:
        out["chance_of_rain_pct"] = rain

    return out


# -----------------------------
# When parsing
# -----------------------------

_WEEKDAY_ALIASES = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3, "thur": 3, "thurs": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}

_NOON_PAT = re.compile(r"\b(noon|midday|12\s*(?:pm|p\.m\.|p|))\b", re.IGNORECASE)
_MORNING_PAT = re.compile(r"\b(morning|am|a\.m\.)\b", re.IGNORECASE)
_AFTERNOON_PAT = re.compile(r"\b(afternoon|pm|p\.m\.)\b", re.IGNORECASE)
_EVENING_PAT = re.compile(r"\b(evening|sunset|dusk)\b", re.IGNORECASE)
_NIGHT_PAT = re.compile(r"\b(night|tonight|overnight|late)\b", re.IGNORECASE)

def _next_weekday_delta(target_wd: int, *, base: Optional[datetime] = None, force_next: bool = False) -> int:
    """Days until the next target weekday (0=Mon..6=Sun).
    If force_next is True and today==target, return 7.
    """
    base = base or datetime.now()
    today = base.weekday()
    delta = (target_wd - today) % 7
    if delta == 0 and force_next:
        delta = 7
    return delta

def _parse_when(when: Optional[str]) -> tuple[int, Optional[str], str]:
    """Return (day_index, part_of_day, label) from a human-ish 'when' string.

    Now supports:
      - 'now', 'today', 'tomorrow', 'day after tomorrow'
      - day-of-week: 'Tuesday', 'next Friday', 'Fri morning', etc.
      - 'noon', 'around 12', '12 pm', plus morning/afternoon/evening/night
    """
    if not when:
        return 0, None, "now"
    w = when.lower().strip()

    # Fast paths
    if w in ("now", "current", "right now"):
        return 0, None, "now"

    # Baseline day_index and part
    day_index = 0
    part: Optional[str] = None

    # Relative words
    if "day after" in w or "in 2 days" in w:
        day_index = 2
    elif "tomorrow" in w:
        day_index = 1
    elif "today" in w:
        day_index = 0

    # Day-of-week handling, including "next <weekday>"
    force_next = "next " in w  # crude but effective
    # Find any weekday token
    tokens = re.findall(r"(mon(?:day)?|tue(?:s|sday)?|wed(?:nesday)?|thu(?:r|rs|rsday)?|fri(?:day)?|sat(?:urday)?|sun(?:day)?)", w, re.IGNORECASE)
    if tokens:
        # Use the first match; map to weekday index
        wd_token = tokens[0].lower()
        for k, idx in _WEEKDAY_ALIASES.items():
            if wd_token.startswith(k):
                day_index = _next_weekday_delta(idx, force_next=force_next)
                break

    # Part-of-day / time parsing
    if _NOON_PAT.search(w) or "around 12" in w or "12pm" in w or "12 pm" in w or "12 p.m." in w:
        part = "noon"
    elif _MORNING_PAT.search(w):
        part = "morning"
    elif _AFTERNOON_PAT.search(w):
        # Prefer 'noon' if they used '12' without 'am'
        if "12" in w:
            part = "noon"
        else:
            part = "afternoon"
    elif _EVENING_PAT.search(w):
        part = "evening"
    elif _NIGHT_PAT.search(w):
        part = "night"

    # If they said "tonight", make sure day_index is today
    if "tonight" in w:
        day_index = 0
        part = "night"

    # Compose a friendly label we can echo back
    label = w
    return day_index, part, label


# -----------------------------
# Tool handler
# -----------------------------

async def fetch_weather(params: FunctionCallParams) -> None:
    """Fetch current weather using wttr.in and return it to the LLM.

    Expects `params.arguments` to contain:
    - location: str (e.g., "San Francisco, CA")
    - format: "celsius" | "fahrenheit"
    - when: Optional[str] like 'now', 'tomorrow morning', 'tuesday noon'
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
    logger.info("tools.weather: location='%s' format='%s' when='%s'", location, unit, when or "now")
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

    # Best-effort "resolved_location" from wttr JSON (falls back to input)
    resolved_location = None
    try:
        nearest = (data.get("nearest_area") or [])
        if nearest and isinstance(nearest, list):
            area = nearest[0]
            name_val = ((area.get("areaName") or [{}])[0].get("value") or "").strip()
            region_val = ((area.get("region") or [{}])[0].get("value") or "").strip()
            country_val = ((area.get("country") or [{}])[0].get("value") or "").strip()
            resolved_location = ", ".join([p for p in [name_val, region_val, country_val] if p])
    except Exception:
        resolved_location = None

    try:
        day_index, part, label = _parse_when(when)
        # If a specific time/weekday was asked, use period forecast; else current conditions
        if when and label != "now":
            snap = _extract_period_forecast(data, day_index=day_index, part_of_day=part, unit=unit)
            if snap is None:
                # Fall back to current if out of range (wttr j1 usually gives 3 days)
                snap = _extract_current_cc(data, unit)
                snap["note"] = "forecast_unavailable_fallback_to_current"
            result = {
                "location": location,
                "resolved_location": resolved_location or location,
                "format": unit,
                "when": label,
                **snap,
            }
        else:
            snap = _extract_current_cc(data, unit)
            result = {
                "location": location,
                "resolved_location": resolved_location or location,
                "format": unit,
                "when": "now",
                **snap,
            }

        logger.info(
            "WTTR resolved %r → %s",
            location,
            result.get("resolved_location", location),
        )
        await params.result_callback(result)
    except Exception as e:
        logger.warning(f"Weather parse failed for {location}: {e}")
        await params.result_callback({
            "error": "weather_parse_failed",
            "location": location,
        })


# -----------------------------
# Tool registration
# -----------------------------

def create_weather_tools() -> ToolsSchema:
    """Create a ToolsSchema describing the `get_current_weather` tool."""
    weather_function = FunctionSchema(
        name="get_current_weather",
        description="Get the current weather or a simple forecast snapshot",
        properties={
            "location": {
                "type": "string",
                "description": "City and state or place name, e.g. 'San Francisco, CA' or 'Vallejo'",
            },
            "format": {
                "type": "string",
                "enum": ["celsius", "fahrenheit"],
                "description": "Temperature unit to use. Infer from the user's locale/preferences.",
            },
            "when": {
                "type": "string",
                "description": "Optional: when to check, e.g. 'now', 'tomorrow morning', 'Tuesday noon', 'tonight'.",
            },
        },
        required=["location", "format"],
    )
    return ToolsSchema(standard_tools=[weather_function])


def register_weather_tool(llm):
    """Register the weather tool handler with the given LLM service."""
    llm.register_function("get_current_weather", fetch_weather)
