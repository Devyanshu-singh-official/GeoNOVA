
from collections import defaultdict
from datetime import datetime, date, timezone
from math import isfinite
from statistics import mean

from fastapi import APIRouter, HTTPException, Query

from science_observations import get_science_observations


router = APIRouter()


def parse_observation_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y%m%d").date()
    except (ValueError, TypeError):
        raise ValueError(f"Invalid NASA POWER observation date: {value}")


def calculate_linear_trend(points):
    """
    Calculate ordinary least-squares slope using equally spaced
    monthly observations.

    The returned slope is expressed per year.
    This is descriptive, not a statistical significance test.
    """
    valid_points = [
        point for point in points
        if point["value"] is not None
    ]

    if len(valid_points) < 2:
        return {
            "slope_per_year": None,
            "direction": "insufficient_data",
            "monthly_points_used": len(valid_points),
        }

    x_values = list(range(len(valid_points)))
    y_values = [point["value"] for point in valid_points]

    x_mean = mean(x_values)
    y_mean = mean(y_values)

    denominator = sum(
        (x - x_mean) ** 2 for x in x_values
    )

    if denominator == 0:
        slope_per_month = 0.0
    else:
        numerator = sum(
            (x - x_mean) * (y - y_mean)
            for x, y in zip(x_values, y_values)
        )
        slope_per_month = numerator / denominator

    slope_per_year = slope_per_month * 12

    if abs(slope_per_year) < 0.000001:
        direction = "approximately_stable"
    elif slope_per_year > 0:
        direction = "increasing"
    else:
        direction = "decreasing"

    return {
        "slope_per_year": round(slope_per_year, 6),
        "direction": direction,
        "monthly_points_used": len(valid_points),
    }


def build_monthly_series(observations, parameter_metadata):
    grouped = defaultdict(lambda: defaultdict(list))
    missing = defaultdict(int)

    for row in observations:
        raw_date = row.get("date")

        if not raw_date:
            continue

        try:
            observation_date = parse_observation_date(raw_date)
        except ValueError:
            continue

        month_key = observation_date.strftime("%Y-%m")

        for parameter_code in parameter_metadata:
            value = row.get(parameter_code)

            if (
                isinstance(value, (int, float))
                and isfinite(value)
            ):
                grouped[parameter_code][month_key].append(
                    float(value)
                )
            else:
                missing[parameter_code] += 1

    output = {}

    for parameter_code, metadata in parameter_metadata.items():
        monthly_values = grouped[parameter_code]

        all_months = sorted(monthly_values.keys())

        raw_series = []

        for month in all_months:
            values = monthly_values[month]

            if not values:
                continue

            raw_series.append({
                "month": month,
                "value": round(mean(values), 4),
                "valid_days": len(values),
            })

        period_mean = (
            mean(point["value"] for point in raw_series)
            if raw_series
            else None
        )

        series = []

        for point in raw_series:
            anomaly = (
                point["value"] - period_mean
                if period_mean is not None
                else None
            )

            series.append({
                **point,
                "anomaly": (
                    round(anomaly, 4)
                    if anomaly is not None
                    else None
                ),
            })

        trend = calculate_linear_trend(series)

        output[parameter_code] = {
            "label": metadata.get("label", parameter_code),
            "unit": metadata.get("unit", "unknown"),
            "aggregation": "Monthly mean of available daily values",
            "period_mean": (
                round(period_mean, 4)
                if period_mean is not None
                else None
            ),
            "trend": trend,
            "missing_daily_values": missing[parameter_code],
            "monthly_observations": len(series),
            "series": series,
        }

    return output


@router.get("/api/science/trends/status")
def historical_trends_status():
    return {
        "service": "GeoNOVA Historical Trends Engine",
        "version": "0.1.0",
        "status": "operational",
        "source": "NASA POWER daily observations",
        "maximum_period_years": 5,
        "analysis": [
            "monthly aggregation",
            "period-relative anomalies",
            "descriptive linear trend estimates",
            "data coverage",
        ],
        "statistical_significance_testing": False,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/api/science/trends/{domain_id}")
def get_historical_trends(
    domain_id: str,
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    start_date: str | None = None,
    end_date: str | None = None,
):
    """
    Retrieve daily NASA POWER observations and calculate
    monthly time-series summaries and descriptive trends.
    """

    try:
        observation_data = get_science_observations(
            domain_id=domain_id,
            latitude=latitude,
            longitude=longitude,
            start_date=start_date,
            end_date=end_date,
        )

    except HTTPException:
        raise

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Historical observation processing failed.",
        )

    observations = observation_data.get("observations", [])
    metadata = observation_data.get("metadata", {})
    parameter_metadata = metadata.get("parameters", {})

    if not parameter_metadata:
        raise HTTPException(
            status_code=502,
            detail="No parameter metadata was returned by NASA POWER.",
        )

    if not observations:
        raise HTTPException(
            status_code=404,
            detail="No daily observations were returned for this period.",
        )

    monthly_results = build_monthly_series(
        observations,
        parameter_metadata,
    )

    return {
        "status": "trend_analysis_completed",
        "domain_id": domain_id,
        "source": observation_data.get("source"),
        "coordinates": observation_data.get("coordinates"),
        "time_range": observation_data.get("time_range"),
        "daily_observation_count": len(observations),
        "monthly_results": monthly_results,
        "methodology": {
            "aggregation": (
                "Arithmetic mean of available daily values within each month."
            ),
            "anomaly_baseline": (
                "Mean of the available monthly means within the selected period."
            ),
            "trend_method": (
                "Ordinary least-squares linear regression over consecutive "
                "available monthly observations."
            ),
            "trend_unit": "Parameter units per year",
            "significance_test": False,
        },
        "limitations": [
            "NASA POWER point estimates are gridded estimates, not ground-station measurements.",
            "Monthly values are calculated from available daily observations.",
            "Missing days can affect monthly averages.",
            "Anomalies are relative to the selected date range, not a standard climate normal.",
            "Linear trend estimates do not establish causation or statistical significance.",
            "A short observation period should not be interpreted as a long-term climate trend.",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
