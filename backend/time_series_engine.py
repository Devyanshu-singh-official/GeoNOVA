
import calendar
import math
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Any

import requests
from fastapi import APIRouter, HTTPException, Query

from nasa_power import NASA_POWER_URL, PARAMETERS

router = APIRouter()

TIMEOUT = 90

# Accumulated quantities: daily values are added over each period.
SUM_PARAMETERS = {
    "PRECTOT",
    "PRECTOTCORR",
    "ALLSKY_SFC_SW_DWN",
    "CLRSKY_SFC_SW_DWN",
    "ALLSKY_SFC_LW_DWN",
}


def parse_yyyymmdd(value: str, field: str) -> date:
    try:
        if len(value) != 8 or not value.isdigit():
            raise ValueError()
        return datetime.strptime(value, "%Y%m%d").date()
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=f"{field} must be a valid YYYYMMDD date.",
        ) from error


def clean_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(number) or number <= -998:
        return None

    return number


def period_key(day: date, frequency: str) -> str:
    if frequency == "monthly":
        return day.strftime("%Y-%m")
    if frequency == "yearly":
        return str(day.year)
    return day.isoformat()


def period_bounds(key: str, frequency: str) -> tuple[date, date]:
    if frequency == "monthly":
        year, month = map(int, key.split("-"))
        last_day = calendar.monthrange(year, month)[1]
        return date(year, month, 1), date(year, month, last_day)

    if frequency == "yearly":
        year = int(key)
        return date(year, 1, 1), date(year, 12, 31)

    day = date.fromisoformat(key)
    return day, day


def circular_mean_degrees(values: list[float]) -> float | None:
    if not values:
        return None

    radians = [math.radians(value) for value in values]
    sin_mean = sum(math.sin(value) for value in radians) / len(radians)
    cos_mean = sum(math.cos(value) for value in radians) / len(radians)

    if abs(sin_mean) < 1e-12 and abs(cos_mean) < 1e-12:
        return None

    return math.degrees(math.atan2(sin_mean, cos_mean)) % 360


def aggregate_values(
    parameter: str,
    values: list[float],
) -> float | None:
    if not values:
        return None

    if parameter in SUM_PARAMETERS:
        return sum(values)

    if parameter == "WD10M":
        return circular_mean_degrees(values)

    return sum(values) / len(values)


def build_period_keys(
    start: date,
    end: date,
    frequency: str,
) -> list[str]:
    keys = set()
    current = start

    while current <= end:
        keys.add(period_key(current, frequency))
        if frequency == "daily":
            from datetime import timedelta
            current += timedelta(days=1)
        elif frequency == "monthly":
            if current.month == 12:
                current = date(current.year + 1, 1, 1)
            else:
                current = date(current.year, current.month + 1, 1)
        else:
            current = date(current.year + 1, 1, 1)

    return sorted(keys)


def expected_days_in_period(
    key: str,
    frequency: str,
    requested_start: date,
    requested_end: date,
) -> int:
    period_start, period_end = period_bounds(key, frequency)

    clipped_start = max(period_start, requested_start)
    clipped_end = min(period_end, requested_end)

    if clipped_start > clipped_end:
        return 0

    return (clipped_end - clipped_start).days + 1


@router.get("/api/nasa/power/timeseries")
def generate_power_timeseries(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    start_date: str = Query(..., description="YYYYMMDD"),
    end_date: str = Query(..., description="YYYYMMDD"),
    parameters: str = Query(
        default="T2M,PRECTOTCORR,RH2M",
        min_length=2,
        max_length=500,
    ),
    frequency: str = Query(
        default="monthly",
        pattern="^(daily|monthly|yearly)$",
    ),
    community: str = Query(
        default="AG",
        pattern="^(AG|RE|SB)$",
    ),
    minimum_coverage: float = Query(
        default=0.80,
        ge=0.0,
        le=1.0,
    ),
):
    start = parse_yyyymmdd(start_date, "start_date")
    end = parse_yyyymmdd(end_date, "end_date")
    today = datetime.now(timezone.utc).date()

    if start > end:
        raise HTTPException(
            status_code=422,
            detail="start_date must be on or before end_date.",
        )

    if start < date(1981, 1, 1):
        raise HTTPException(
            status_code=422,
            detail="NASA POWER daily coverage begins on 1981-01-01.",
        )

    if end > today:
        raise HTTPException(
            status_code=422,
            detail="end_date cannot be in the future.",
        )

    selected = list(dict.fromkeys(
        item.strip().upper()
        for item in parameters.split(",")
        if item.strip()
    ))

    if not selected:
        raise HTTPException(
            status_code=422,
            detail="At least one parameter is required.",
        )

    if len(selected) > 20:
        raise HTTPException(
            status_code=422,
            detail="A maximum of 20 parameters is allowed.",
        )

    unsupported = [
        item for item in selected
        if item not in PARAMETERS
    ]

    if unsupported:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Unsupported NASA POWER parameters.",
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
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()

    except requests.Timeout as error:
        raise HTTPException(
            status_code=504,
            detail="NASA POWER timed out while building the time series.",
        ) from error

    except requests.RequestException as error:
        status = getattr(
            getattr(error, "response", None),
            "status_code",
            None,
        )
        raise HTTPException(
            status_code=502,
            detail={
                "message": "NASA POWER data retrieval failed.",
                "upstream_status": status,
                "reason": str(error),
            },
        ) from error

    except ValueError as error:
        raise HTTPException(
            status_code=502,
            detail="NASA POWER returned invalid JSON.",
        ) from error

    raw_parameters = (
        payload.get("properties", {}).get("parameter", {})
        if isinstance(payload, dict)
        else {}
    )

    if not isinstance(raw_parameters, dict) or not raw_parameters:
        raise HTTPException(
            status_code=502,
            detail={
                "message": "NASA POWER returned no parameter observations.",
                "upstream_messages": (
                    payload.get("messages", [])
                    if isinstance(payload, dict)
                    else []
                ),
            },
        )

    # Convert upstream parameter dictionaries into date-indexed records.
    daily_by_date: dict[str, dict[str, float | None]] = {}

    all_dates = sorted({
        observation_date
        for parameter_values in raw_parameters.values()
        if isinstance(parameter_values, dict)
        for observation_date in parameter_values.keys()
    })

    for observation_date in all_dates:
        try:
            parsed_date = datetime.strptime(
                observation_date,
                "%Y%m%d",
            ).date()
        except (TypeError, ValueError):
            continue

        if parsed_date < start or parsed_date > end:
            continue

        daily_by_date[observation_date] = {}

        for parameter in selected:
            values = raw_parameters.get(parameter) or {}
            daily_by_date[observation_date][parameter] = clean_number(
                values.get(observation_date)
            )

    period_keys = build_period_keys(start, end, frequency)

    grouped: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )

    for observation_date, record in daily_by_date.items():
        day = datetime.strptime(observation_date, "%Y%m%d").date()
        key = period_key(day, frequency)

        for parameter in selected:
            value = record.get(parameter)
            if value is not None:
                grouped[key][parameter].append(value)

    output_series = []
    total_expected = 0
    total_valid = 0
    total_missing = 0

    for key in period_keys:
        expected = expected_days_in_period(
            key,
            frequency,
            start,
            end,
        )

        if expected <= 0:
            continue

        period_values = grouped.get(key, {})
        result_record: dict[str, Any] = {
            "date": key,
            "expected_days": expected,
            "parameters": {},
        }

        period_valid = 0
        period_missing = 0

        for parameter in selected:
            values = period_values.get(parameter, [])
            valid_days = len(values)
            missing_days = max(0, expected - valid_days)
            coverage = valid_days / expected if expected else 0.0

            aggregated = aggregate_values(parameter, values)

            # Do not publish a partial period value below the threshold.
            publish_value = (
                aggregated
                if coverage >= minimum_coverage
                else None
            )

            result_record["parameters"][parameter] = {
                "value": publish_value,
                "unit": PARAMETERS[parameter]["unit"],
                "valid_days": valid_days,
                "missing_days": missing_days,
                "coverage": round(coverage, 4),
                "aggregation": (
                    "sum"
                    if parameter in SUM_PARAMETERS
                    else "circular_mean"
                    if parameter == "WD10M"
                    else "mean"
                ),
                "below_coverage_threshold": (
                    coverage < minimum_coverage
                ),
            }

            period_valid += valid_days
            period_missing += missing_days

        result_record["quality"] = {
            "valid_parameter_days": period_valid,
            "missing_parameter_days": period_missing,
        }

        total_expected += expected * len(selected)
        total_valid += period_valid
        total_missing += period_missing

        output_series.append(result_record)

    overall_coverage = (
        total_valid / total_expected
        if total_expected
        else 0.0
    )

    return {
        "project": "GeoNOVA",
        "engine": "Historical Time-Series Engine",
        "engine_version": "1.0.0",
        "source": {
            "name": "NASA POWER",
            "product": "Daily Point",
            "url": NASA_POWER_URL,
            "time_standard": "UTC",
        },
        "spatial": {
            "mode": "single_point",
            "latitude": latitude,
            "longitude": longitude,
            "notice": (
                "This result represents a NASA POWER grid point, "
                "not an area-wide regional average."
            ),
        },
        "temporal": {
            "requested_start": start.isoformat(),
            "requested_end": end.isoformat(),
            "frequency": frequency,
            "daily_source_resolution": True,
            "output_periods": len(output_series),
        },
        "configuration": {
            "community": community,
            "parameters": selected,
            "minimum_coverage": minimum_coverage,
        },
        "quality": {
            "expected_parameter_days": total_expected,
            "valid_parameter_days": total_valid,
            "missing_parameter_days": total_missing,
            "overall_coverage": round(overall_coverage, 4),
            "missing_values_interpolated": False,
            "low_coverage_values_suppressed": True,
        },
        "series": output_series,
        "methodology": {
            "mean": "Arithmetic mean of available daily values.",
            "sum": "Sum of available daily accumulated quantities.",
            "circular_mean": (
                "Circular mean for wind direction, avoiding "
                "incorrect arithmetic averaging across 0/360 degrees."
            ),
            "coverage": (
                "Valid daily observations divided by expected calendar "
                "days within each requested period."
            ),
            "limitations": [
                "A period below the coverage threshold returns null.",
                "Missing observations are not interpolated.",
                "Monthly and yearly values are derived from daily values.",
                "This endpoint currently analyzes one coordinate at a time.",
            ],
        },
        "upstream_messages": payload.get("messages"),
    }
