
from datetime import date
from math import erf, sqrt
from statistics import median
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(
    prefix="/api/science/seasonality",
    tags=["Seasonality and Dependence"],
)

MAX_OBSERVATIONS = 2000
MIN_SEASON_OBSERVATIONS = 4


class Observation(BaseModel):
    date: date
    value: Optional[float] = None


class SeasonalTrendRequest(BaseModel):
    observations: list[Observation] = Field(min_length=8)
    autocorrelation_correction: bool = True


def normal_cdf(z: float) -> float:
    return 0.5 * (1.0 + erf(z / sqrt(2.0)))


def two_sided_p_value(z: float) -> float:
    return max(0.0, min(1.0, 2.0 * (1.0 - normal_cdf(abs(z)))))


def decimal_year(d: date) -> float:
    start = date(d.year, 1, 1)
    end = date(d.year + 1, 1, 1)
    return d.year + (d - start).days / (end - start).days


def sen_slope(points: list[tuple[float, float]]) -> Optional[float]:
    slopes = []

    for i in range(len(points)):
        x1, y1 = points[i]

        for j in range(i + 1, len(points)):
            x2, y2 = points[j]

            if x2 != x1:
                slopes.append((y2 - y1) / (x2 - x1))

    return median(slopes) if slopes else None


def mk_variance(values: list[float]) -> float:
    n = len(values)

    if n < 2:
        return 0.0

    variance = n * (n - 1) * (2 * n + 5) / 18.0

    counts = {}

    for value in values:
        counts[value] = counts.get(value, 0) + 1

    for count in counts.values():
        if count > 1:
            variance -= (
                count * (count - 1) * (2 * count + 5) / 18.0
            )

    return max(0.0, variance)


def mk_score(values: list[float]) -> int:
    score = 0

    for i in range(len(values)):
        for j in range(i + 1, len(values)):
            difference = values[j] - values[i]

            if difference > 0:
                score += 1
            elif difference < 0:
                score -= 1

    return score


def mk_test(values: list[float]) -> dict:
    n = len(values)

    if n < MIN_SEASON_OBSERVATIONS:
        return {
            "available": False,
            "reason": "Insufficient observations for this season.",
            "n": n,
        }

    score = mk_score(values)
    variance = mk_variance(values)

    if variance <= 0:
        z = 0.0
        p = 1.0
    elif score > 0:
        z = (score - 1) / sqrt(variance)
        p = two_sided_p_value(z)
    elif score < 0:
        z = (score + 1) / sqrt(variance)
        p = two_sided_p_value(z)
    else:
        z = 0.0
        p = 1.0

    if p < 0.05:
        direction = "increasing" if score > 0 else "decreasing"
        significance = "statistically_significant"
    else:
        direction = "no_detected_direction"
        significance = "not_statistically_significant"

    return {
        "available": True,
        "n": n,
        "s": score,
        "variance": round(variance, 6),
        "z": round(z, 6),
        "p_value": round(p, 8),
        "direction": direction,
        "significance": significance,
    }


def lag1_autocorrelation(values: list[float]) -> Optional[float]:
    if len(values) < 4:
        return None

    mean_value = sum(values) / len(values)
    centered = [value - mean_value for value in values]

    denominator = sum(value * value for value in centered)

    if denominator == 0:
        return 0.0

    numerator = sum(
        centered[i] * centered[i - 1]
        for i in range(1, len(centered))
    )

    return max(-1.0, min(1.0, numerator / denominator))


def prepare_season(points: list[tuple[int, float]]) -> dict:
    points = sorted(points)

    years = [year for year, _ in points]
    values = [value for _, value in points]

    slope = sen_slope(
        [(float(year), value) for year, value in points]
    )

    if slope is None:
        return {
            "points": points,
            "slope": None,
            "autocorrelation": None,
            "correction_applied": False,
            "correction_reason": "Unable to estimate seasonal slope.",
        }

    intercept = median(
        [
            value - slope * year
            for year, value in points
        ]
    )

    residuals = [
        value - (intercept + slope * year)
        for year, value in points
    ]

    autocorrelation = lag1_autocorrelation(residuals)

    consecutive = all(
        years[i] == years[i - 1] + 1
        for i in range(1, len(years))
    )

    correction_applied = False
    correction_reason = "Autocorrelation correction not requested."

    adjusted_points = points

    if len(points) < 5:
        correction_reason = (
            "At least five observations are required for TFPW."
        )
    elif not consecutive:
        correction_reason = (
            "Missing years detected; TFPW was not applied."
        )
    elif autocorrelation is None:
        correction_reason = (
            "Insufficient residual data for autocorrelation analysis."
        )
    else:
        # Trend-free pre-whitening:
        # remove estimated trend, pre-whiten residuals,
        # then restore the estimated trend.
        adjusted_values = [values[0]]

        for i in range(1, len(values)):
            whitened_residual = (
                residuals[i] - autocorrelation * residuals[i - 1]
            )

            restored_value = (
                intercept
                + slope * years[i]
                + whitened_residual
            )

            adjusted_values.append(restored_value)

        adjusted_points = list(zip(years, adjusted_values))
        correction_applied = True
        correction_reason = (
            "Trend-free pre-whitening applied to a continuous "
            "annual seasonal series."
        )

    return {
        "points": adjusted_points,
        "original_points": points,
        "slope": slope,
        "autocorrelation": autocorrelation,
        "correction_applied": correction_applied,
        "correction_reason": correction_reason,
    }


@router.post("/analyze")
def analyze_seasonality(request: SeasonalTrendRequest):
    if len(request.observations) > MAX_OBSERVATIONS:
        raise HTTPException(
            status_code=413,
            detail=f"Maximum {MAX_OBSERVATIONS} observations allowed.",
        )

    observations = sorted(
        request.observations,
        key=lambda item: item.date,
    )

    seen_dates = set()
    monthly_groups = {month: [] for month in range(1, 13)}
    excluded = 0

    for observation in observations:
        if observation.date in seen_dates:
            raise HTTPException(
                status_code=422,
                detail=f"Duplicate date: {observation.date}",
            )

        seen_dates.add(observation.date)

        value = observation.value

        if value is None:
            excluded += 1
            continue

        if not isinstance(value, (int, float)):
            raise HTTPException(
                status_code=422,
                detail="Observation values must be numeric or null.",
            )

        if not (-1e100 < value < 1e100):
            raise HTTPException(
                status_code=422,
                detail="Observation values must be finite.",
            )

        monthly_groups[observation.date.month].append(
            (observation.date.year, float(value))
        )

    monthly_results = {}
    combined_score = 0
    combined_variance = 0.0
    combined_slopes = []
    correction_results = []

    for month in range(1, 13):
        original_points = monthly_groups[month]

        if len(original_points) < MIN_SEASON_OBSERVATIONS:
            monthly_results[str(month)] = {
                "available": False,
                "observations": len(original_points),
                "reason": "Insufficient observations for this month.",
            }
            continue

        prepared = prepare_season(original_points)

        analysis_points = prepared["points"]

        if request.autocorrelation_correction:
            values = [value for _, value in analysis_points]
        else:
            values = [value for _, value in original_points]

        result = mk_test(values)

        original_slope = sen_slope(
            [(float(year), value) for year, value in original_points]
        )

        result["month"] = month
        result["seasonal_sen_slope_per_year"] = (
            round(original_slope, 8)
            if original_slope is not None
            else None
        )

        result["lag1_autocorrelation"] = (
            round(prepared["autocorrelation"], 6)
            if prepared["autocorrelation"] is not None
            else None
        )

        result["tfpw_applied"] = (
            prepared["correction_applied"]
            if request.autocorrelation_correction
            else False
        )

        result["dependence_note"] = (
            prepared["correction_reason"]
            if request.autocorrelation_correction
            else "Autocorrelation correction disabled."
        )

        monthly_results[str(month)] = result

        if result.get("available"):
            combined_score += result["s"]
            combined_variance += result["variance"]

        if original_slope is not None:
            combined_slopes.append(original_slope)

        correction_results.append(prepared["correction_applied"])

    if combined_variance > 0:
        if combined_score > 0:
            combined_z = (
                combined_score - 1
            ) / sqrt(combined_variance)
        elif combined_score < 0:
            combined_z = (
                combined_score + 1
            ) / sqrt(combined_variance)
        else:
            combined_z = 0.0

        combined_p = two_sided_p_value(combined_z)
    else:
        combined_z = 0.0
        combined_p = 1.0

    if combined_p < 0.05:
        combined_direction = (
            "increasing" if combined_score > 0 else "decreasing"
        )
        combined_significance = "statistically_significant"
    else:
        combined_direction = "no_detected_direction"
        combined_significance = "not_statistically_significant"

    return {
        "status": "success",
        "method": "Seasonal Mann-Kendall",
        "dependence_method": (
            "Trend-free pre-whitening"
            if request.autocorrelation_correction
            else "Diagnostic only"
        ),
        "overall": {
            "seasonal_mk_score": combined_score,
            "z": round(combined_z, 6),
            "p_value": round(combined_p, 8),
            "direction": combined_direction,
            "significance": combined_significance,
            "median_seasonal_sen_slope_per_year": (
                round(median(combined_slopes), 8)
                if combined_slopes
                else None
            ),
        },
        "monthly_results": monthly_results,
        "data_quality": {
            "input_observations": len(observations),
            "valid_observations": len(observations) - excluded,
            "excluded_missing_values": excluded,
            "months_with_sufficient_data": sum(
                1
                for result in monthly_results.values()
                if result.get("available")
            ),
        },
        "autocorrelation_summary": {
            "correction_requested": request.autocorrelation_correction,
            "months_corrected": sum(correction_results),
            "months_not_corrected": (
                len(correction_results) - sum(correction_results)
            ),
        },
        "limitations": [
            "TFPW is applied only to continuous annual observations "
            "within a calendar month.",
            "Missing years prevent TFPW for that seasonal group.",
            "The combined seasonal test uses the sum of monthly "
            "Mann-Kendall scores and variances.",
            "This implementation does not yet perform a block "
            "bootstrap or correct for multiple testing across months.",
            "Statistical significance does not establish causation.",
        ],
    }
