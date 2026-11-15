
from collections import defaultdict
from datetime import date
from math import erfc, isfinite, sqrt
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field


router = APIRouter(
    prefix="/api/science/seasonal-trends",
    tags=["Seasonal Mann-Kendall"],
)


# =========================================================
# REQUEST MODELS
# =========================================================

class MonthlyObservation(BaseModel):
    date: str
    value: Optional[float] = None


class SeasonalTrendRequest(BaseModel):
    observations: list[MonthlyObservation] = Field(
        ...,
        min_length=12,
        max_length=5000,
    )
    alpha: float = Field(default=0.05, gt=0, lt=0.5)


# =========================================================
# DATE AND INPUT VALIDATION
# =========================================================

def parse_month(value: str) -> date:
    try:
        parsed = date.fromisoformat(value[:10])
        return date(parsed.year, parsed.month, 1)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=422,
            detail=f"Invalid observation date: {value}",
        )


def prepare_observations(observations):
    monthly = {}
    warnings = []

    for item in observations:
        parsed_date = parse_month(item.date)
        key = (parsed_date.year, parsed_date.month)

        if key in monthly:
            raise HTTPException(
                status_code=422,
                detail=f"Duplicate calendar month: {key[0]}-{key[1]:02d}",
            )

        value = item.value

        if value is not None:
            try:
                value = float(value)
            except (TypeError, ValueError):
                value = None

            if value is not None and not isfinite(value):
                value = None
                warnings.append(
                    f"Non-finite value treated as missing for "
                    f"{key[0]}-{key[1]:02d}."
                )

        monthly[key] = value

    valid = [
        (year, month, value)
        for (year, month), value in monthly.items()
        if value is not None
    ]

    if len(valid) < 12:
        raise HTTPException(
            status_code=422,
            detail="At least 12 valid monthly observations are required.",
        )

    years = sorted({year for year, _, _ in valid})

    if len(years) < 2:
        raise HTTPException(
            status_code=422,
            detail="At least two distinct years are required.",
        )

    if len(years) < 5:
        warnings.append(
            "Fewer than five years of data are available. "
            "Interpret the seasonal trend cautiously."
        )

    return monthly, valid, years, warnings


# =========================================================
# NORMAL DISTRIBUTION
# =========================================================

def normal_two_sided_p(z_score: float) -> float:
    return min(1.0, max(0.0, erfc(abs(z_score) / sqrt(2.0))))


def normal_cdf(z_score: float) -> float:
    return 0.5 * erfc(-z_score / sqrt(2.0))


# =========================================================
# SEASONAL MANN-KENDALL
# =========================================================

def calculate_seasonal_mk(valid):
    """
    Calculates a seasonal Mann-Kendall statistic.

    Each calendar month is treated as a separate season.
    Comparisons are made only between observations from
    the same calendar month in different years.
    """

    groups = defaultdict(list)

    for year, month, value in valid:
        groups[month].append((year, value))

    total_s = 0
    total_variance = 0.0
    season_details = []

    for month in range(1, 13):
        records = sorted(groups.get(month, []))
        values = [value for _, value in records]
        n = len(values)

        if n < 2:
            season_details.append({
                "month": month,
                "observations": n,
                "pairs": 0,
                "s_statistic": 0,
                "variance": 0.0,
                "status": "insufficient_data",
            })
            continue

        s_value = 0

        for i in range(n - 1):
            for j in range(i + 1, n):
                difference = values[j] - values[i]

                if difference > 0:
                    s_value += 1
                elif difference < 0:
                    s_value -= 1

        tie_counts = defaultdict(int)

        for value in values:
            tie_counts[value] += 1

        tie_term = sum(
            count * (count - 1) * (2 * count + 5)
            for count in tie_counts.values()
        )

        variance = (
            n * (n - 1) * (2 * n + 5) - tie_term
        ) / 18.0

        total_s += s_value
        total_variance += variance

        season_details.append({
            "month": month,
            "observations": n,
            "pairs": n * (n - 1) // 2,
            "s_statistic": s_value,
            "variance": round(variance, 8),
            "status": "analyzed",
        })

    if total_variance <= 0:
        z_score = 0.0
        p_value = 1.0
    else:
        if total_s > 0:
            z_score = (total_s - 1) / sqrt(total_variance)
        elif total_s < 0:
            z_score = (total_s + 1) / sqrt(total_variance)
        else:
            z_score = 0.0

        p_value = normal_two_sided_p(z_score)

    return {
        "s_statistic": total_s,
        "variance": total_variance,
        "z_score": z_score,
        "p_value": p_value,
        "seasons": season_details,
        "seasons_analyzed": sum(
            1 for item in season_details
            if item["status"] == "analyzed"
        ),
    }


# =========================================================
# SEASONAL SEN SLOPE
# =========================================================

def calculate_seasonal_sen_slope(valid):
    """
    Calculates pairwise slopes within each calendar month.

    Slope units are the observation unit per year.
    """

    groups = defaultdict(list)

    for year, month, value in valid:
        groups[month].append((year, value))

    slopes = []

    for month, records in groups.items():
        records = sorted(records)

        for i in range(len(records) - 1):
            year_i, value_i = records[i]

            for j in range(i + 1, len(records)):
                year_j, value_j = records[j]

                year_difference = year_j - year_i

                if year_difference <= 0:
                    continue

                slopes.append(
                    (value_j - value_i) / year_difference
                )

    if not slopes:
        return None, 0

    slopes.sort()
    count = len(slopes)
    middle = count // 2

    if count % 2:
        median_slope = slopes[middle]
    else:
        median_slope = (
            slopes[middle - 1] + slopes[middle]
        ) / 2.0

    return median_slope, count


# =========================================================
# SEASONAL COVERAGE
# =========================================================

def calculate_coverage(monthly, years):
    total_expected = len(years) * 12
    total_valid = sum(
        1 for value in monthly.values()
        if value is not None
    )

    month_coverage = []

    for month in range(1, 13):
        valid_count = sum(
            1
            for year in years
            if monthly.get((year, month)) is not None
        )

        month_coverage.append({
            "month": month,
            "valid_years": valid_count,
            "expected_years": len(years),
            "coverage_percent": round(
                100 * valid_count / len(years), 2
            ),
        })

    return {
        "valid_observations": total_valid,
        "expected_observations": total_expected,
        "overall_coverage_percent": round(
            100 * total_valid / total_expected, 2
        ),
        "by_calendar_month": month_coverage,
    }


# =========================================================
# STATUS
# =========================================================

@router.get("/status")
def seasonal_trend_status():
    return {
        "module": "Seasonal Mann-Kendall Trend Analysis",
        "status": "online",
        "method": "Seasonal Mann-Kendall",
        "slope_method": "Seasonal Sen slope",
        "supported_frequency": "monthly",
        "season_definition": "calendar month",
        "limitations": [
            "Uses a normal approximation for the p-value.",
            "Does not correct for serial correlation.",
            "Does not calculate a seasonal Sen slope confidence interval.",
            "Does not automatically remove or model long-term seasonality.",
            "Requires sufficient observations within calendar-month groups.",
            "Does not correct for multiple hypothesis testing.",
        ],
    }


# =========================================================
# MAIN ANALYSIS
# =========================================================

@router.post("/analyze")
def analyze_seasonal_trend(request: SeasonalTrendRequest):
    monthly, valid, years, warnings = prepare_observations(
        request.observations
    )

    mk = calculate_seasonal_mk(valid)

    slope, slope_pair_count = calculate_seasonal_sen_slope(
        valid
    )

    coverage = calculate_coverage(monthly, years)

    significant = mk["p_value"] < request.alpha

    if significant and mk["s_statistic"] > 0:
        direction = "increasing"
    elif significant and mk["s_statistic"] < 0:
        direction = "decreasing"
    elif mk["s_statistic"] > 0:
        direction = "positive_but_not_significant"
    elif mk["s_statistic"] < 0:
        direction = "negative_but_not_significant"
    else:
        direction = "no_detectable_monotonic_direction"

    if mk["seasons_analyzed"] < 6:
        warnings.append(
            "Fewer than six calendar-month groups contain enough "
            "observations for within-season comparisons."
        )

    if coverage["overall_coverage_percent"] < 80:
        warnings.append(
            "Overall monthly coverage is below 80%. "
            "Missing observations may affect interpretation."
        )

    if slope is None:
        warnings.append(
            "A seasonal Sen slope could not be calculated."
        )

    return {
        "metadata": {
            "method": "Seasonal Mann-Kendall",
            "slope_method": "Seasonal Sen slope",
            "alpha": request.alpha,
            "confidence_level": round(
                (1 - request.alpha) * 100, 2
            ),
            "years_covered": {
                "first": years[0],
                "last": years[-1],
                "count": len(years),
            },
            "valid_observations": len(valid),
            "calendar_month_groups": 12,
        },
        "results": {
            "seasonal_mann_kendall": {
                "s_statistic": mk["s_statistic"],
                "variance": round(mk["variance"], 8),
                "z_score": round(mk["z_score"], 6),
                "p_value": round(mk["p_value"], 8),
                "significance_level": request.alpha,
                "is_significant": significant,
                "direction": direction,
            },
            "seasonal_sen_slope": {
                "slope_per_year": (
                    round(slope, 8)
                    if slope is not None
                    else None
                ),
                "unit": "input unit per year",
                "pairwise_slopes_used": slope_pair_count,
            },
        },
        "coverage": coverage,
        "calendar_month_diagnostics": mk["seasons"],
        "warnings": warnings,
        "limitations": [
            "The p-value uses a normal approximation.",
            "Serial correlation is not corrected by this endpoint.",
            "The seasonal Sen slope is a point estimate without a confidence interval.",
            "The test does not establish causation.",
            "A statistically significant result does not establish practical importance.",
            "Results should be checked against data quality and temporal-dependence diagnostics.",
        ],
        "data_modified": False,
    }
