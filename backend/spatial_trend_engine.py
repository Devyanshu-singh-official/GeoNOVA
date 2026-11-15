
from datetime import date
from math import erf, sqrt, isfinite
from statistics import median
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(
    prefix="/api/science/spatial-trends",
    tags=["Spatial Trend Intelligence"],
)

MAX_CELLS = 500
MAX_OBSERVATIONS_PER_CELL = 2000
MIN_OBSERVATIONS = 8


class SpatialObservation(BaseModel):
    date: date
    value: Optional[float] = None


class SpatialCell(BaseModel):
    cell_id: str = Field(min_length=1, max_length=100)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    observations: list[SpatialObservation]


class SpatialTrendRequest(BaseModel):
    variable: str = Field(default="unspecified", max_length=100)
    unit: str = Field(default="unspecified", max_length=50)
    cells: list[SpatialCell] = Field(min_length=1, max_length=MAX_CELLS)
    significance_level: float = Field(default=0.05, gt=0, lt=1)


def normal_cdf(z: float) -> float:
    return 0.5 * (1 + erf(z / sqrt(2)))


def two_sided_p(z: float) -> float:
    return max(0.0, min(1.0, 2 * (1 - normal_cdf(abs(z)))))


def decimal_year(d: date) -> float:
    start = date(d.year, 1, 1)
    end = date(d.year + 1, 1, 1)
    return d.year + (d - start).days / (end - start).days


def mann_kendall(values: list[float]) -> dict:
    n = len(values)

    score = 0
    for i in range(n):
        for j in range(i + 1, n):
            difference = values[j] - values[i]
            if difference > 0:
                score += 1
            elif difference < 0:
                score -= 1

    variance = n * (n - 1) * (2 * n + 5) / 18.0

    counts = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1

    for count in counts.values():
        if count > 1:
            variance -= (
                count * (count - 1) * (2 * count + 5) / 18.0
            )

    if variance <= 0 or score == 0:
        z = 0.0
    elif score > 0:
        z = (score - 1) / sqrt(variance)
    else:
        z = (score + 1) / sqrt(variance)

    return {
        "s": score,
        "variance": max(0.0, variance),
        "z": z,
        "p_value": two_sided_p(z),
    }


def calculate_sen_slope(
    dates: list[date],
    values: list[float],
) -> Optional[float]:
    slopes = []

    years = [decimal_year(d) for d in dates]

    for i in range(len(values)):
        for j in range(i + 1, len(values)):
            elapsed = years[j] - years[i]

            if elapsed > 0:
                slopes.append(
                    (values[j] - values[i]) / elapsed
                )

    return median(slopes) if slopes else None


def analyze_cell(
    cell: SpatialCell,
    significance_level: float,
) -> dict:
    if len(cell.observations) > MAX_OBSERVATIONS_PER_CELL:
        raise HTTPException(
            status_code=413,
            detail=(
                f"Cell {cell.cell_id} exceeds "
                f"{MAX_OBSERVATIONS_PER_CELL} observations."
            ),
        )

    ordered = sorted(
        cell.observations,
        key=lambda item: item.date,
    )

    seen_dates = set()
    valid = []

    for observation in ordered:
        if observation.date in seen_dates:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Duplicate date in cell {cell.cell_id}: "
                    f"{observation.date}"
                ),
            )

        seen_dates.add(observation.date)

        if observation.value is None:
            continue

        value = float(observation.value)

        if not isfinite(value):
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Non-finite observation in cell "
                    f"{cell.cell_id}."
                ),
            )

        valid.append((observation.date, value))

    dates = [item[0] for item in valid]
    values = [item[1] for item in valid]

    base = {
        "cell_id": cell.cell_id,
        "latitude": cell.latitude,
        "longitude": cell.longitude,
        "input_observations": len(ordered),
        "valid_observations": len(valid),
        "missing_observations": len(ordered) - len(valid),
    }

    if len(valid) < MIN_OBSERVATIONS:
        return {
            **base,
            "available": False,
            "reason": (
                f"At least {MIN_OBSERVATIONS} valid observations "
                "are required."
            ),
            "trend": "insufficient_data",
            "sen_slope_per_year": None,
            "p_value": None,
            "significant": None,
        }

    mk = mann_kendall(values)
    slope = calculate_sen_slope(dates, values)

    p_value = mk["p_value"]
    significant = p_value < significance_level

    if significant and mk["s"] > 0:
        trend = "significant_increase"
    elif significant and mk["s"] < 0:
        trend = "significant_decrease"
    elif slope is not None and slope > 0:
        trend = "non_significant_increase"
    elif slope is not None and slope < 0:
        trend = "non_significant_decrease"
    else:
        trend = "no_detected_trend"

    return {
        **base,
        "available": True,
        "trend": trend,
        "sen_slope_per_year": (
            round(slope, 10) if slope is not None else None
        ),
        "mann_kendall_s": mk["s"],
        "mann_kendall_z": round(mk["z"], 6),
        "p_value": round(p_value, 8),
        "significant": significant,
        "significance_level": significance_level,
        "first_observation": dates[0].isoformat(),
        "last_observation": dates[-1].isoformat(),
    }


@router.post("/analyze")
def analyze_spatial_trends(request: SpatialTrendRequest):
    cell_ids = [cell.cell_id for cell in request.cells]

    if len(cell_ids) != len(set(cell_ids)):
        raise HTTPException(
            status_code=422,
            detail="Each cell_id must be unique.",
        )

    results = [
        analyze_cell(cell, request.significance_level)
        for cell in request.cells
    ]

    counts = {
        "significant_increase": 0,
        "significant_decrease": 0,
        "non_significant_increase": 0,
        "non_significant_decrease": 0,
        "no_detected_trend": 0,
        "insufficient_data": 0,
    }

    features = []

    for result in results:
        trend = result["trend"]
        counts[trend] = counts.get(trend, 0) + 1

        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [
                    result["longitude"],
                    result["latitude"],
                ],
            },
            "properties": result,
        })

    available_slopes = [
        result["sen_slope_per_year"]
        for result in results
        if result["sen_slope_per_year"] is not None
    ]

    return {
        "status": "success",
        "variable": request.variable,
        "unit": request.unit,
        "method": "Mann-Kendall and Sen's slope",
        "significance_level": request.significance_level,
        "spatial_summary": {
            "total_cells": len(results),
            "analyzed_cells": len(available_slopes),
            "cells_by_trend": counts,
            "median_cell_sen_slope_per_year": (
                round(median(available_slopes), 10)
                if available_slopes
                else None
            ),
        },
        "geojson": {
            "type": "FeatureCollection",
            "features": features,
        },
        "limitations": [
            "Each cell is analyzed independently.",
            "No spatial autocorrelation correction is applied.",
            "No multiple-testing correction is applied across cells.",
            "The normal approximation is used for Mann-Kendall p-values.",
            "Input cells must represent comparable spatial sampling.",
            "The median of cell slopes is descriptive, not an "
            "area-weighted regional trend.",
            "Seasonality and temporal autocorrelation are not "
            "corrected by this endpoint.",
        ],
    }
