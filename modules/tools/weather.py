from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, Literal, Optional, Tuple

import httpx
from loguru import logger
from dotenv import load_dotenv

from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.adapters.schemas.tools_schema import ToolsSchema
from pipecat.frames.frames import TTSSpeakFrame
from pipecat.services.llm_service import FunctionCallParams

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------

load_dotenv(override=True)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "").strip()

GOOGLE_WEATHER_URL_CURRENT = "https://weather.googleapis.com/v1/currentConditions:lookup"
GOOGLE_WEATHER_URL_HOURLY  = "https://weather.googleapis.com/v1/forecast/hours:lookup"
GOOGLE_WEATHER_URL_DAILY   = "https://weather.googleapis.com/v1/forecast/days:lookup"
GOOGLE_GEOCODE_URL         = "https://maps.googleapis.com/maps/api/geocode/json"

# -----------------------------------------------------------------------------
# Utilities
# -----------------------------------------------------------------------------

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
            if kph is None and mph is not None:
                kph = mph / 0.621371
            if kph is not None:
                out["wind_speed"] = int(round(float(kph)))
                out["wind_speed_unit"] = "kilometers per hour"
                out["wind_unit_code"] = "kph"
        else:
            if mph is None and kph is not None:
                mph = kph * 0.621371
            if mph is not None:
                out["wind_speed"] = int(round(float(mph)))
                out["wind_speed_unit"] = "miles per hour"
                out["wind_unit_code"] = "mph"
    except Exception as e:
        logger.debug("wind parse failed: %s", e)
    return out

def _weekday_name_to_index(name: str) -> Optional[int]:
    """Return 0..6 (Mon..Sun) for weekday name, else None."""
    name = name.strip().lower()
    days = ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]
    for i, d in enumerate(days):
        if name.startswith(d[:3]) or name == d:
            return i
    return None

def _parse_when(when: Optional[str]) -> tuple[int, Optional[str], str]:
    """
    Return (day_index, part_of_day, label).
    Supports 'now', 'today', 'tomorrow', 'day after', 'next hour',
    parts of day (morning/afternoon/evening/night), and weekday names.
    """
    if not when:
        return 0, None, "now"
    w = when.lower().strip()
    if w in ("now", "current", "right now"):
        return 0, None, "now"

    # Day index via common phrases
    day_index = 0
    if "tomorrow" in w:
        day_index = 1
    elif "day after" in w or "in 2 days" in w:
        day_index = 2
    elif "today" in w:
        day_index = 0
    else:
        # Weekday handling (relative to today)
        tgt = _weekday_name_to_index(w)
        if tgt is not None:
            today = datetime.now().weekday()  # 0=Mon
            delta = (tgt - today) % 7
            day_index = delta

    part: Optional[str] = None
    if "next hour" in w or ("hour" in w and "next" in w):
        part = "hour"
    elif any(p in w for p in ["morning", "am"]):
        part = "morning"
    elif any(p in w for p in ["afternoon", "noon", "pm"]):
        part = "afternoon"
    elif any(p in w for p in ["evening", "sunset"]):
        part = "evening"
    elif any(p in w for p in ["night", "tonight"]):
        part = "night"

    logger.debug("parse_when(%r) → day_index=%s part=%r label=%r", when, day_index, part, w)
    return day_index, part, w

# -----------------------------------------------------------------------------
# Google clients
# -----------------------------------------------------------------------------

async def _geocode_place(place: str) -> tuple[Optional[float], Optional[float], Optional[str]]:
    if not GOOGLE_API_KEY:
        raise RuntimeError("GOOGLE_API_KEY is not set in the environment")

    params = {"address": place, "key": GOOGLE_API_KEY}
    logger.info("GEOCODE → %s | params=%r", GOOGLE_GEOCODE_URL, params)
    async with httpx.AsyncClient(timeout=8.0) as client:
        r = await client.get(GOOGLE_GEOCODE_URL, params=params)
        logger.debug("GEOCODE status=%s", r.status_code)
        r.raise_for_status()
        data = r.json()
    status = data.get("status")
    logger.debug("GEOCODE body.status=%r results_count=%s", status, len(data.get("results") or []))
    if status != "OK" or not data.get("results"):
        logger.warning("Geocoding failed for %r; status=%r", place, status)
        return None, None, None
    res0 = data["results"][0]
    loc = res0["geometry"]["location"]
    lat, lng = float(loc["lat"]), float(loc["lng"])
    formatted = res0.get("formatted_address")
    logger.info("Geocoded %r → (%s,%s) %r", place, lat, lng, formatted)
    return lat, lng, formatted

async def _google_weather_call(url: str, *, lat: float, lng: float) -> Dict[str, Any]:
    if not GOOGLE_API_KEY:
        raise RuntimeError("GOOGLE_API_KEY is not set in the environment")

    params = {
        "key": GOOGLE_API_KEY,
        "location.latitude": lat,
        "location.longitude": lng,
    }
    logger.info("WEATHER GET → %s params=%r", url, params)
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(url, params=params)
        logger.debug("WEATHER status=%s", r.status_code)
        if r.status_code != 200:
            logger.warning("Weather HTTP error: %s - %s", r.status_code, r.text[:800])
        r.raise_for_status()
        return r.json()

# -----------------------------------------------------------------------------
# Extractors
# -----------------------------------------------------------------------------

def _c_to_unit(c: Optional[float], unit: Literal["celsius", "fahrenheit"]) -> Optional[int]:
    if c is None:
        return None
    return int(round((c * 9.0 / 5.0) + 32.0)) if unit == "fahrenheit" else int(round(c))

def _extract_from_google_current(
    data: Dict[str, Any],
    unit: Literal["celsius", "fahrenheit"],
) -> Dict[str, Any]:
    # Temperatures (C) - try common shapes
    temp_c = _as_float(((data.get("temperature") or {}).get("degrees") or (data.get("temperature") or {}).get("value")))
    feels_c = _as_float(((data.get("feelsLikeTemperature") or {}).get("degrees") or (data.get("feelsLikeTemperature") or {}).get("value")))
    if feels_c is None:
        feels_c = temp_c

    desc = (
        ((data.get("weatherCondition") or {}).get("description") or {}).get("text")
        or (data.get("weatherCondition") or {}).get("text")
        or "Unknown"
    )
    desc = str(desc).strip() or "Unknown"

    hum = _as_int(data.get("relativeHumidity"))

    wind = data.get("wind") or {}
    kph = _as_float(((wind.get("speed") or {}).get("value")))
    mph = None

    out: Dict[str, Any] = {
        "conditions": desc,
        "temperature": _c_to_unit(temp_c, unit),
        "temperature_unit": "Fahrenheit" if unit == "fahrenheit" else "Celsius",
    }
    if hum is not None:
        out["humidity"] = hum
    out.update(_make_wind_fields(kph=kph, mph=mph, unit=unit))

    out["is_daytime"] = bool(data.get("isDaytime", False))
    tz = (data.get("timeZone") or {}).get("id")
    if tz:
        out["time_zone"] = tz

    logger.debug("PARSED current → %r", out)
    return out

def _extract_from_google_daily(
    data: Dict[str, Any],
    *,
    day_index: int,
    unit: Literal["celsius", "fahrenheit"],
) -> Optional[Dict[str, Any]]:
    # The days array name varies; try multiple
    days = (
        data.get("days")
        or data.get("dailyForecasts")
        or data.get("forecasts")
        or []
    )
    if not isinstance(days, list) or not days or day_index >= len(days):
        return None

    d = days[day_index]
    # Temperature fields (C)
    hi_c = _as_float(((d.get("temperatureMax") or {}).get("degrees") or (d.get("temperatureMax") or {}).get("value") or d.get("maxTemperature")))
    lo_c = _as_float(((d.get("temperatureMin") or {}).get("degrees") or (d.get("temperatureMin") or {}).get("value") or d.get("minTemperature")))

    desc = (
        (d.get("weatherCondition") or {}).get("text")
        or ((d.get("weatherCondition") or {}).get("description") or {}).get("text")
        or d.get("conditions")
        or "Unknown"
    )
    desc = str(desc).strip() or "Unknown"

    out: Dict[str, Any] = {
        "conditions": desc,
        "temperature_unit": "Fahrenheit" if unit == "fahrenheit" else "Celsius",
    }
    hi = _c_to_unit(hi_c, unit)
    lo = _c_to_unit(lo_c, unit)
    if hi is not None:
        out["high_temperature"] = hi
    if lo is not None:
        out["low_temperature"] = lo

    # Optional precip chance (percent) — try a few shapes
    precip_pct = (
        _as_int(((d.get("precipitation") or {}).get("chance")))
        or _as_int(d.get("precipitationChance"))
        or _as_int(d.get("precipitationChancePercent"))
    )
    if precip_pct is not None:
        out["chance_of_rain_pct"] = precip_pct

    logger.debug("PARSED daily[%s] → %r", day_index, out)
    return out

def _extract_from_google_hourly(
    data: Dict[str, Any],
    *,
    unit: Literal["celsius", "fahrenheit"],
    pick: Literal["hour", "morning", "afternoon", "evening", "night", None],
) -> Optional[Dict[str, Any]]:
    # The hours array name varies; try multiple
    hours = data.get("hours") or data.get("hourlyForecasts") or []
    if not isinstance(hours, list) or not hours:
        return None

    def hour_in_range(hh: int, rng: tuple[int, int]) -> bool:
        return rng[0] <= hh <= rng[1]

    chosen = None
    for h in hours:
        ts = str(h.get("forecastStartTime") or h.get("startTime") or "")
        hh = None
        if len(ts) >= 13 and ts[11:13].isdigit():
            try:
                hh = int(ts[11:13])
            except ValueError:
                hh = None

        if pick == "hour":
            chosen = hours[0]
            break
        elif hh is not None:
            if pick == "morning"    and hour_in_range(hh, (6, 10)):  chosen = h; break
            if pick == "afternoon"  and hour_in_range(hh, (11, 15)): chosen = h; break
            if pick == "evening"    and hour_in_range(hh, (16, 19)): chosen = h; break
            if pick == "night"      and (hour_in_range(hh, (20, 23)) or hour_in_range(hh, (0, 2))): chosen = h; break

    if chosen is None:
        chosen = hours[min(len(hours)//2, len(hours)-1)]

    temp_c = _as_float(((chosen.get("temperature") or {}).get("degrees") or (chosen.get("temperature") or {}).get("value") or chosen.get("temperatureCelsius")))
    desc = (
        ((chosen.get("weatherCondition") or {}).get("text"))
        or ((chosen.get("weatherCondition") or {}).get("description") or {}).get("text")
        or chosen.get("conditions")
        or "Unknown"
    )
    desc = str(desc).strip() or "Unknown"

    wind = chosen.get("wind") or {}
    kph = _as_float(((wind.get("speed") or {}).get("value") or wind.get("speedKph")))
    mph = None

    # Optional precip chance (percent)
    precip_pct = (
        _as_int(((chosen.get("precipitation") or {}).get("chance")))
        or _as_int(chosen.get("precipitationChance"))
        or _as_int(chosen.get("precipitationChancePercent"))
    )

    out: Dict[str, Any] = {
        "conditions": desc,
        "temperature": _c_to_unit(temp_c, unit),
        "temperature_unit": "Fahrenheit" if unit == "fahrenheit" else "Celsius",
    }
    out.update(_make_wind_fields(kph=kph, mph=mph, unit=unit))
    if precip_pct is not None:
        out["chance_of_rain_pct"] = precip_pct

    logger.debug("PARSED hourly pick=%r → %r", pick, out)
    return out

# -----------------------------------------------------------------------------
# Tool handler
# -----------------------------------------------------------------------------

async def fetch_weather(params: FunctionCallParams) -> None:
    """
    Expects:
      - location: str  e.g., "San Francisco, CA"
      - format: "celsius" | "fahrenheit"
      - when: Optional[str] like 'now', 'next hour', 'today afternoon', 'tomorrow morning', 'Tuesday'
    """
    args = params.arguments or {}
    location = str(args.get("location", "")).strip()
    unit: Literal["celsius", "fahrenheit"] = args.get("format", "fahrenheit")  # type: ignore
    when: Optional[str] = args.get("when")

    logger.info("TOOL fetch_weather args: location=%r unit=%r when=%r", location, unit, when)

    if not location:
        await params.result_callback({"error": "missing_location"})
        return

    if not GOOGLE_API_KEY:
        logger.error("GOOGLE_API_KEY missing")
        await params.result_callback({
            "error": "missing_google_api_key",
            "message": "GOOGLE_API_KEY is not set in the environment."
        })
        return

    try:
        await params.llm.push_frame(TTSSpeakFrame("Let me check on that."))
    except Exception as e:
        logger.debug("TTSSpeakFrame push failed (non-fatal): %s", e)

    try:
        lat, lng, resolved = await _geocode_place(location)
        if lat is None or lng is None:
            await params.result_callback({
                "error": "geocode_failed",
                "location": location,
            })
            return

        # Always get current (fast + helps with context/fallbacks)
        current_payload = await _google_weather_call(GOOGLE_WEATHER_URL_CURRENT, lat=lat, lng=lng)
        current = _extract_from_google_current(current_payload, unit=unit)

        day_index, part, label = _parse_when(when)

        if when and label != "now":
            result: Dict[str, Any] = {
                "location": location,
                "resolved_location": resolved or location,
                "format": unit,
                "when": label,
            }

            # Hourly for “next hour” / parts of day (today/tomorrow)
            hourly_added = False
            if part in ("hour", "morning", "afternoon", "evening", "night") and day_index in (0, 1):
                try:
                    hourly_payload = await _google_weather_call(GOOGLE_WEATHER_URL_HOURLY, lat=lat, lng=lng)
                    hourly_pick = _extract_from_google_hourly(
                        hourly_payload,
                        unit=unit,
                        pick="hour" if part == "hour" else part,
                    )
                    if hourly_pick:
                        result.update(hourly_pick)
                        hourly_added = True
                except httpx.HTTPStatusError as e:
                    logger.warning("Hourly forecast unavailable (%s); skipping hourly data", e.response.status_code)
                    result["note_hourly"] = "hourly_unavailable"

            # Daily bounds for requested day
            try:
                daily_payload = await _google_weather_call(GOOGLE_WEATHER_URL_DAILY, lat=lat, lng=lng)
                daily = _extract_from_google_daily(daily_payload, day_index=day_index, unit=unit)
                if daily:
                    # If we already added hourly, keep its conditions/temp, but add daily hi/lo
                    for k, v in daily.items():
                        if k in ("conditions", "temperature") and hourly_added:
                            continue
                        result[k] = v
                else:
                    result["note_daily"] = "daily_not_available"
            except httpx.HTTPStatusError as e:
                logger.warning("Daily forecast unavailable (%s); skipping daily data", e.response.status_code)
                result["note_daily"] = "daily_unavailable"

            # If nothing forecastful made it in, fall back to current
            if "temperature" not in result and "high_temperature" not in result and "low_temperature" not in result:
                result.update(current)
                result["note"] = "forecast_unavailable_fallback_to_current"

            await params.result_callback(result)
            return

        # “now”
        result = {
            "location": location,
            "resolved_location": resolved or location,
            "format": unit,
            "when": "now",
            **current,
        }
        await params.result_callback(result)

    except httpx.HTTPStatusError as e:
        text = e.response.text[:500] if e.response is not None else ""
        code = e.response.status_code if e.response is not None else "?"
        logger.warning("Google Weather HTTP error: %s - %s", code, text)
        await params.result_callback({
            "error": "weather_fetch_failed",
            "message": f"HTTP {code}",
            "location": location,
        })
    except Exception as e:
        logger.warning("Weather fetch failed: %s", e)
        await params.result_callback({
            "error": "weather_fetch_failed",
            "location": location,
        })

# -----------------------------------------------------------------------------
# Tool registration
# -----------------------------------------------------------------------------

def create_weather_tools() -> ToolsSchema:
    weather_function = FunctionSchema(
        name="get_current_weather",
        description="Get the weather: current, and forecast if 'when' is not now",
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
                "description": "Optional: when to check, e.g. 'now', 'next hour', 'today afternoon', 'tomorrow morning', 'Tuesday'.",
            },
        },
        required=["location", "format"],
    )
    return ToolsSchema(standard_tools=[weather_function])

def register_weather_tool(llm):
    llm.register_function("get_current_weather", fetch_weather)
