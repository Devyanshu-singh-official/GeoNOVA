
from datetime import date, datetime, timedelta

import requests
from fastapi import APIRouter, HTTPException, Query

router = APIRouter()

NASA_POWER_URL = (
    "https://power.larc.nasa.gov/api/temporal/daily/point"
)

# NASA POWER daily parameters.
# Units are taken from the NASA POWER parameter definitions.
DOMAIN_PARAMETERS = {
    "temperature": {
        "community": "AG",
        "parameters": {
            "T2M": {"label": "Air Temperature", "unit": "°C"},
            "T2M_MAX": {"label": "Maximum Air Temperature", "unit": "°C"},
            "T2M_MIN": {"label": "Minimum Air Temperature", "unit": "°C"},
        },
    },
    "water": {
        "community": "AG",
        "parameters": {
            "PRECTOTCORR": {
                "label": "Corrected Precipitation",
                "unit": "mm/day",
            },
            "RH2M": {
                "label": "Relative Humidity",
                "unit": "%",
            },
        },
    },
    "soil": {
        "community": "AG",
        "parameters": {
            "GWETTOP": {
                "label": "Surface Soil Wetness",
                "unit": "fraction",
            },
            "GWETROOT": {
                "label": "Root Zone Soil Wetness",
                "unit": "fraction",
            },
            "GWETPROF": {
                "label": "Profile Soil Wetness",
                "unit": "fraction",
            },
        },
    },
    "atmosphere": {
        "community": "SB",
        "parameters": {
            "RH2M": {
                "label": "Relative Humidity",
                "unit": "%",
            },
            "WS10M": {
                "label": "Wind Speed at 10m",
                "unit": "m/s",
            },
            "PS": {
                "label": "Surface Pressure",
                "unit": "kPa",
            },
        },
    },
    "climate-carbon": {
        "community": "AG",
        "parameters": {
            "T2M": {
                "label": "Air Temperature",
                "unit": "°C",
            },
            "PRECTOTCORR": {
                "label": "Corrected Precipitation",
                "unit": "mm/day",
            },
            "RH2M": {
                "label": "Relative Humidity",
                "unit": "%",
            },
        },
    },
}


def parse_power_date(value: str, field_name: str) -> date:
    try:
        return datetime.strptime(value, "%Y%m%d").date()
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} must use YYYYMMDD format.",
        )


def clean_value(value):
    if value is None:
        return None

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    if number in (-999, -999.0):
        return None

    return number


@router.get("/api/science/observations/{domain_id}")
def get_science_observations(
    domain_id: str,
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    start_date: str | None = None,
    end_date: str | None = None,
):
    configuration = DOMAIN_PARAMETERS.get(domain_id)

    if configuration is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Observation API is not configured for this domain. "
                "Use the scientific dataset catalogue instead."
            ),
        )

    today = date.today()
    default_end = today - timedelta(days=3)
    default_start = default_end - timedelta(days=30)

    start = (
        parse_power_date(start_date, "start_date")
        if start_date
        else default_start
    )

    end = (
        parse_power_date(end_date, "end_date")
        if end_date
        else default_end
    )

    if start > end:
        raise HTTPException(
            status_code=400,
            detail="start_date must not be later than end_date.",
        )

    if end > today:
        raise HTTPException(
            status_code=400,
            detail="Future dates are not supported.",
        )

    if (end - start).days > 1825:
        raise HTTPException(
            status_code=400,
            detail="Maximum supported date range is five years.",
        )

    parameters = configuration["parameters"]

    request_params = {
        "parameters": ",".join(parameters.keys()),
        "community": configuration["community"],
        "longitude": longitude,
        "latitude": latitude,
        "start": start.strftime("%Y%m%d"),
        "end": end.strftime("%Y%m%d"),
        "format": "JSON",
    }

    try:
        response = requests.get(
            NASA_POWER_URL,
            params=request_params,
            timeout=35,
        )
        response.raise_for_status()
        payload = response.json()

    except requests.Timeout:
        raise HTTPException(
            status_code=504,
            detail="NASA POWER request timed out. Try again later.",
        )

    except requests.RequestException as error:
        raise HTTPException(
            status_code=502,
            detail=f"NASA POWER request failed: {str(error)}",
        )

    except ValueError:
        raise HTTPException(
            status_code=502,
            detail="NASA POWER returned an invalid JSON response.",
        )

    properties = (
        payload.get("properties", {})
        .get("parameter", {})
    )

    if not properties:
        raise HTTPException(
            status_code=502,
            detail="NASA POWER returned no observation parameters.",
        )

    dates = set()

    for values in properties.values():
        if isinstance(values, dict):
            dates.update(values.keys())

        observations = []

    for observation_date in sorted(dates):
        row = {"date": observation_date}

        for parameter_code in parameters:
            values = properties.get(parameter_code, {})
            raw_value = values.get(observation_date)

            row[parameter_code] = clean_value(raw_value)

        if latitude is not None and longitude is not None:
            row["lat"] = latitude
            row["lon"] = longitude

        observations.append(row)

    parameter_metadata = {}

    for code, details in parameters.items():
        parameter_metadata[code] = {
            "label": details["label"],
            "unit": details["unit"],
        }

    return {
        "domain_id": domain_id,
        "source": {
            "name": "NASA POWER",
            "url": "https://power.larc.nasa.gov/",
            "type": "Gridded meteorological and solar data service",
        },
        "metadata": {
            "community": configuration["community"],
            "parameters": parameter_metadata,
            "temporal_resolution": "Daily",
            "spatial_interpretation": (
                "NASA POWER point estimate at the requested coordinates; "
                "not a ground-station measurement."
            ),
            "quality_notice": (
                "Values may be provisional, missing, or revised. "
                "Check the NASA POWER documentation and parameter metadata "
                "before scientific interpretation."
            ),
        },
        "coordinates": {
            "latitude": latitude,
            "longitude": longitude,
        },
        "time_range": {
            "start": start.isoformat(),
            "end": end.isoformat(),
        },
        "count": len(observations),
        "observations": observations,
    }

