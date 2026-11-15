
from datetime import date, datetime, timezone
from typing import Any
import re

import requests
from fastapi import APIRouter, HTTPException, Query

router = APIRouter()

NASA_POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
REQUEST_TIMEOUT = 60
EARLIEST_DATE = date(1981, 1, 1)

# Supported daily parameters exposed by this GeoNOVA endpoint.
PARAMETERS = {
    "T2M": {"name": "Air Temperature at 2 Meters", "unit": "°C"},
    "T2M_MAX": {"name": "Maximum Air Temperature at 2 Meters", "unit": "°C"},
    "T2M_MIN": {"name": "Minimum Air Temperature at 2 Meters", "unit": "°C"},
    "T2MDEW": {"name": "Dew/Frost Point at 2 Meters", "unit": "°C"},
    "T2MWET": {"name": "Wet Bulb Temperature at 2 Meters", "unit": "°C"},
    "T2M_RANGE": {"name": "Temperature Range at 2 Meters", "unit": "°C"},
    "RH2M": {"name": "Relative Humidity at 2 Meters", "unit": "%"},
    "PRECTOTCORR": {"name": "Corrected Precipitation", "unit": "mm/day"},
    "PRECTOT": {"name": "Precipitation", "unit": "mm/day"},
    "WS10M": {"name": "Wind Speed at 10 Meters", "unit": "m/s"},
    "WS10M_MAX": {"name": "Maximum Wind Speed at 10 Meters", "unit": "m/s"},
    "WS10M_MIN": {"name": "Minimum Wind Speed at 10 Meters", "unit": "m/s"},
    "WD10M": {"name": "Wind Direction at 10 Meters", "unit": "degrees"},
    "ALLSKY_SFC_SW_DWN": {
        "name": "All Sky Surface Shortwave Downward Irradiance",
        "unit": "kW-hr/m²/day",
    },
    "CLRSKY_SFC_SW_DWN": {
        "name": "Clear Sky Surface Shortwave Downward Irradiance",
        "unit": "kW-hr/m²/day",
    },
    "ALLSKY_SFC_LW_DWN": {
        "name": "All Sky Surface Longwave Downward Irradiance",
        "unit": "kW-hr/m²/day",
    },
    "PS": {"name": "Surface Pressure", "unit": "kPa"},
    "QV2M": {"name": "Specific Humidity at 2 Meters", "unit": "g/kg"},
}


def parse_date(value: str, field_name: str) -> date:
    if not re.fullmatch(r"\d{8}", value):
        raise HTTPException(
            status_code=422,
            detail=f"{field_name} must use YYYYMMDD format.",
        )

    try:
        return datetime.strptime(value, "%Y%m%d").date()
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=f"{field_name} is not a valid calendar date.",
        ) from error


def normalize_value(value: Any) -> float | None:
    if value is None:
        return None

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    # NASA POWER uses -999 as its missing-data fill value.
    if number <= -998:
        return None

    return number


@router.get("/api/nasa/power/parameters")
def get_power_parameters():
    return {
        "source": "NASA POWER",
        "product": "Daily Point",
        "available_parameters": [
            {
                "id": parameter_id,
                **metadata,
            }
            for parameter_id, metadata in PARAMETERS.items()
        ],
        "maximum_parameters_per_request": 20,
        "historical_coverage_start": "1981-01-01",
        "temporal_resolution": "Daily",
    }


@router.get("/api/nasa/power/daily")
def get_power_daily(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    start_date: str = Query(..., description="YYYYMMDD"),
    end_date: str = Query(..., description="YYYYMMDD"),
    parameters: str = Query(
        default="T2M,PRECTOTCORR,RH2M",
        min_length=2,
        max_length=500,
    ),
    community: str = Query(default="AG", pattern="^(AG|RE|SB)$"),
):
    start = parse_date(start_date, "start_date")
    end = parse_date(end_date, "end_date")
    today = datetime.now(timezone.utc).date()

    if start < EARLIEST_DATE:
        raise HTTPException(
            status_code=422,
            detail="NASA POWER daily data coverage begins on 1981-01-01.",
        )

    if end > today:
        raise HTTPException(
            status_code=422,
            detail="end_date cannot be in the future.",
        )

    if start > end:
        raise HTTPException(
            status_code=422,
            detail="start_date must be on or before end_date.",
        )

    selected = list(dict.fromkeys(
        item.strip().upper()
        for item in parameters.split(",")
        if item.strip()
    ))

    if not selected:
        raise HTTPException(
            status_code=422,
            detail="Select at least one parameter.",
        )

    if len(selected) > 20:
        raise HTTPException(
            status_code=422,
            detail="A maximum of 20 parameters can be requested.",
        )

    unsupported = [item for item in selected if item not in PARAMETERS]
    if unsupported:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Unsupported parameter identifiers.",
                "unsupported": unsupported,
                "available": list(PARAMETERS.keys()),
            },
        )

    request_params = {
        "parameters": ",".join(selected),
        "community": community,
        "longitude": longitude,
        "latitude": latitude,
        "start": start.strftime("%Y%m%d"),
        "end": end.strftime("%Y%m%d"),
        "format": "JSON",
        "time-standard": "UTC",
    }

    try:
        response = requests.get(
            NASA_POWER_URL,
            params=request_params,
            headers={"Accept": "application/json"},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()

    except requests.Timeout as error:
        raise HTTPException(
            status_code=504,
            detail="NASA POWER request timed out. Try a shorter date range.",
        ) from error

    except requests.RequestException as error:
        raise HTTPException(
            status_code=502,
            detail={
                "message": "NASA POWER could not be reached.",
                "reason": str(error),
            },
        ) from error

    except ValueError as error:
        raise HTTPException(
            status_code=502,
            detail="NASA POWER returned invalid JSON.",
        ) from error

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=502,
            detail="NASA POWER returned an unexpected response.",
        )

    properties = payload.get("properties") or {}
    raw_parameters = properties.get("parameter") or {}

    if not isinstance(raw_parameters, dict) or not raw_parameters:
        messages = payload.get("messages") or []
        raise HTTPException(
            status_code=502,
            detail={
                "message": "NASA POWER returned no usable parameter observations.",
                "upstream_messages": messages,
            },
        )

    # Convert parameter -> date dictionaries into date -> parameter records.
    dates = sorted({
        observation_date
        for values in raw_parameters.values()
        if isinstance(values, dict)
        for observation_date in values
    })

    series = []
    missing_count = 0
    valid_count = 0

    for observation_date in dates:
        record = {"date": observation_date}

        for parameter_id in selected:
            values = raw_parameters.get(parameter_id) or {}
            value = normalize_value(values.get(observation_date))

            record[parameter_id] = value

            if value is None:
                missing_count += 1
            else:
                valid_count += 1

        series.append(record)

    if not series:
        raise HTTPException(
            status_code=502,
            detail="NASA POWER returned an empty time series.",
        )

    metadata = {
        parameter_id: PARAMETERS[parameter_id]
        for parameter_id in selected
    }

    return {
        "source": "NASA POWER",
        "provider": "NASA Langley Research Center",
        "product": "Daily Point",
        "upstream_url": NASA_POWER_URL,
        "coordinates": {
            "latitude": latitude,
            "longitude": longitude,
        },
        "requested_period": {
            "start": start.isoformat(),
            "end": end.isoformat(),
        },
        "actual_period": {
            "start": series[0]["date"],
            "end": series[-1]["date"],
        },
        "community": community,
        "time_standard": "UTC",
        "temporal_resolution": "daily",
        "parameters": metadata,
        "total_observations": len(series),
        "valid_values": valid_count,
        "missing_values": missing_count,
        "series": series,
        "quality_notice": (
            "NASA POWER analysis-ready gridded meteorological and solar data. "
            "These are not raw satellite swath observations or direct station measurements. "
            "Missing values are represented as null."
        ),
        "upstream_header": payload.get("header"),
        "upstream_messages": payload.get("messages"),
    }
