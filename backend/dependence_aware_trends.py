
from collections import defaultdict
from datetime import date
from math import erfc, isfinite, sqrt
import re
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator


router = APIRouter(
    prefix="/api/science/dependence-aware-trends",
    tags=["Dependence-Aware Trend Analysis"],
)


# =========================================================
# REQUEST MODELS
# =========================================================

class MonthlyObservation(BaseModel):
    date: str
    value: Optional[float] = None

    @field_validator("date")
    @classmethod
    def validate_date_format(cls, value: str) -> str:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError(
                "Date must use YYYY-MM-DD format."
            )

        try:
            date.fromisoformat(value)
        except ValueError:
            raise ValueError(
                f"Invalid calendar date: {value}."
            )

        return value

    @field_validator("value")
    @classmethod
    def validate_finite_value(
        cls,
        value: Optional[float],
    ) -> Optional[float]:

        if value is not None and not isfinite(value):
            raise ValueError(
                "Observation values must be finite numbers."
            )

        return value


class DependenceAwareRequest(BaseModel):
    observations: list[MonthlyObservation] = Field(
        ...,
        min_length=8,
        max_length=5000,
    )

    alpha: float = Field(
        default=0.05,
        gt=0,
        lt=0.5,
    )


# =========================================================
# DATE UTILITIES
# =========================================================

def month_index(date_string: str) -> int:
    try:
        parsed = date.fromisoformat(date_string)
    except ValueError:
        raise ValueError(
            f"Invalid ISO date: {date_string}. "
            "Expected YYYY-MM-DD."
        )

    return parsed.year * 12 + parsed.month - 1


def month_label(index: int) -> str:
    return (
        f"{index // 12:04d}-"
        f"{index % 12 + 1:02d}"
    )


# =========================================================
# NORMAL DISTRIBUTION
# =========================================================

def two_sided_p_value(z_score: float) -> float:
    if not isfinite(z_score):
        return 0.0

    return max(
        0.0,
        min(
            1.0,
            erfc(abs(z_score) / sqrt(2.0)),
        ),
    )


def normal_critical_value(alpha: float) -> float:
    """
    Numerically calculate a two-sided normal critical value.
    """

    if not 0 < alpha < 0.5:
        raise ValueError(
            "Alpha must be between 0 and 0.5."
        )

    target = 1.0 - alpha / 2.0

    low = 0.0
    high = 10.0

    for _ in range(80):
        middle = (low + high) / 2.0

        cdf = (
            0.5
            * erfc(-middle / sqrt(2.0))
        )

        if cdf < target:
            low = middle
        else:
            high = middle

    return (low + high) / 2.0


# =========================================================
# INPUT VALIDATION AND CALENDAR PREPARATION
# =========================================================

def prepare_observations(
    observations: list[MonthlyObservation],
) -> dict:

    if not observations:
        raise ValueError(
            "No observations were supplied."
        )

    records = {}
    duplicate_months = []

    for item in observations:
        month = month_index(item.date)

        if month in records:
            duplicate_months.append(
                month_label(month)
            )
            continue

        value = item.value

        if value is not None:
            value = float(value)

            if not isfinite(value):
                raise ValueError(
                    f"Non-finite value in {item.date}."
                )

        records[month] = {
            "date": item.date,
            "month": month,
            "value": value,
        }

    if duplicate_months:
        raise ValueError(
            "Duplicate monthly observations: "
            + ", ".join(sorted(set(duplicate_months)))
        )

    if not records:
        raise ValueError(
            "No valid monthly records were supplied."
        )

    first_month = min(records)
    last_month = max(records)

    calendar_span = last_month - first_month + 1

    # Prevent unexpectedly large calendar allocations.
    if calendar_span > 12000:
        raise ValueError(
            "The supplied date range exceeds the "
            "12,000-month processing limit."
        )

    calendar_series = []

    for month in range(
        first_month,
        last_month + 1,
    ):
        record = records.get(month)

        calendar_series.append({
            "month": month,
            "date": month_label(month),
            "value": (
                record["value"]
                if record is not None
                else None
            ),
        })

    valid = [
        item
        for item in calendar_series
        if item["value"] is not None
    ]

    if len(valid) < 8:
        raise ValueError(
            "At least eight valid monthly values "
            "are required."
        )

    missing_months = [
        item["date"]
        for item in calendar_series
        if item["value"] is None
    ]

    return {
        "valid_observations": valid,
        "calendar_series": calendar_series,
        "missing_months": missing_months,
        "first_month": first_month,
        "last_month": last_month,
        "calendar_span": calendar_span,
        "valid_count": len(valid),
    }


# =========================================================
# MANN-KENDALL VARIANCE
# =========================================================

def mann_kendall_variance(
    values: list[float],
) -> float:

    n = len(values)

    tie_groups = defaultdict(int)

    for value in values:
        tie_groups[value] += 1

    tie_correction = sum(
        count
        * (count - 1)
        * (2 * count + 5)
        for count in tie_groups.values()
        if count > 1
    )

    return (
        n * (n - 1) * (2 * n + 5)
        - tie_correction
    ) / 18.0


# =========================================================
# FENWICK TREE
# =========================================================

class FenwickTree:
    """
    Binary indexed tree for efficient prefix-frequency queries.

    Supports:
    - Point updates: O(log n)
    - Prefix sums: O(log n)
    """

    def __init__(self, size: int):
        self.size = size
        self.tree = [0] * (size + 1)

    def update(self, index: int, delta: int = 1):
        while index <= self.size:
            self.tree[index] += delta
            index += index & -index

    def query(self, index: int) -> int:
        result = 0

        while index > 0:
            result += self.tree[index]
            index -= index & -index

        return result


# =========================================================
# OPTIMIZED MANN-KENDALL SCORE
# =========================================================

def mann_kendall_score(
    values: list[float],
) -> int:
    """
    Calculate the exact Mann-Kendall S statistic.

    Uses coordinate compression and a Fenwick tree.

    Complexity:
        Original nested-loop implementation: O(n^2)
        Optimized implementation: O(n log n)

    Tied values contribute zero.
    """

    n = len(values)

    if n < 2:
        return 0

    unique_values = sorted(set(values))

    ranks = {
        value: index + 1
        for index, value in enumerate(unique_values)
    }

    tree = FenwickTree(len(unique_values))

    score = 0

    for index, value in enumerate(values):

        rank = ranks[value]

        # Number of previous values strictly smaller.
        smaller_count = tree.query(rank - 1)

        # Number of previous values less than or equal.
        less_or_equal_count = tree.query(rank)

        # Equal values do not contribute to S.
        equal_count = (
            less_or_equal_count - smaller_count
        )

        # Previous values strictly greater.
        greater_count = (
            index - less_or_equal_count
        )

        score += (
            smaller_count - greater_count
        )

        tree.update(rank)

    return score


# =========================================================
# MANN-KENDALL RESULT
# =========================================================

def calculate_mk_result(
    score: int,
    variance: float,
    alpha: float,
) -> dict:

    if variance <= 0:
        z_score = 0.0
        p_value = 1.0

    elif score > 0:
        z_score = (
            score - 1.0
        ) / sqrt(variance)

        p_value = two_sided_p_value(z_score)

    elif score < 0:
        z_score = (
            score + 1.0
        ) / sqrt(variance)

        p_value = two_sided_p_value(z_score)

    else:
        z_score = 0.0
        p_value = 1.0

    direction = (
        "increasing"
        if score > 0
        else "decreasing"
        if score < 0
        else "no_monotonic_trend"
    )

    return {
        "score": score,
        "variance": round(variance, 8),
        "z_score": round(z_score, 8),
        "p_value": round(p_value, 8),
        "direction": direction,
        "statistically_significant": (
            p_value < alpha
        ),
        "significance_level": alpha,
    }


# =========================================================
# LINEAR DETRENDING
# =========================================================

def calculate_detrended_residuals(
    observations: list[dict],
) -> dict:

    n = len(observations)

    if n < 3:
        raise ValueError(
            "At least three observations are required "
            "for residual autocorrelation analysis."
        )

    x_values = [
        item["month"]
        for item in observations
    ]

    y_values = [
        item["value"]
        for item in observations
    ]

    mean_x = sum(x_values) / n
    mean_y = sum(y_values) / n

    centered_x = [
        x - mean_x
        for x in x_values
    ]

    centered_y = [
        y - mean_y
        for y in y_values
    ]

    ss_xx = sum(
        value * value
        for value in centered_x
    )

    if ss_xx <= 0 or not isfinite(ss_xx):
        raise ValueError(
            "Insufficient time variation for detrending."
        )

    ss_xy = sum(
        x * y
        for x, y in zip(
            centered_x,
            centered_y,
        )
    )

    slope = ss_xy / ss_xx

    intercept = mean_y - slope * mean_x

    if not isfinite(slope) or not isfinite(intercept):
        raise ValueError(
            "Numerical instability occurred during detrending."
        )

    residuals = {}

    for item in observations:

        fitted = (
            mean_y
            + slope * (
                item["month"] - mean_x
            )
        )

        residual = item["value"] - fitted

        if not isfinite(residual):
            raise ValueError(
                "Non-finite residual encountered during detrending."
            )

        residuals[item["month"]] = residual

    return {
        "residuals": residuals,
        "linear_slope_per_month": slope,
        "linear_intercept": intercept,
    }


# =========================================================
# LAG-ONE RESIDUAL AUTOCORRELATION
# =========================================================

def calculate_lag_one_autocorrelation(
    residuals: dict[int, float],
) -> dict:

    if len(residuals) < 3:
        return {
            "value": None,
            "adjacent_pair_count": 0,
        }

    months = sorted(residuals)

    mean_residual = (
        sum(residuals.values())
        / len(residuals)
    )

    centered = {
        month: residuals[month] - mean_residual
        for month in months
    }

    denominator = sum(
        value * value
        for value in centered.values()
    )

    if denominator <= 0 or not isfinite(denominator):
        return {
            "value": None,
            "adjacent_pair_count": 0,
        }

    numerator = 0.0
    pair_count = 0

    for month in months:

        previous_month = month - 1

        if previous_month not in centered:
            continue

        numerator += (
            centered[month]
            * centered[previous_month]
        )

        pair_count += 1

    if pair_count < 3:
        return {
            "value": None,
            "adjacent_pair_count": pair_count,
        }

    rho = numerator / denominator

    if not isfinite(rho):
        return {
            "value": None,
            "adjacent_pair_count": pair_count,
        }

    # Numerical protection for the AR(1) approximation.
    rho = max(
        -0.999,
        min(0.999, rho),
    )

    return {
        "value": rho,
        "adjacent_pair_count": pair_count,
    }


# =========================================================
# AR(1) EFFECTIVE SAMPLE SIZE
# =========================================================

def calculate_effective_sample_size(
    sample_size: int,
    rho: Optional[float],
) -> dict:

    if sample_size < 1:
        raise ValueError(
            "Sample size must be positive."
        )

    if rho is None:
        return {
            "estimate": None,
            "reduction": None,
            "original_sample_size": sample_size,
            "method": "AR(1) approximation",
        }

    denominator = 1.0 + rho

    if abs(denominator) < 1e-12:
        effective_n = 1.0

    else:
        effective_n = (
            sample_size
            * (1.0 - rho)
            / denominator
        )

    # Negative autocorrelation can mathematically imply
    # an effective sample size greater than n. This
    # implementation conservatively caps it at n.
    effective_n = max(
        1.0,
        min(
            float(sample_size),
            effective_n,
        ),
    )

    return {
        "estimate": round(effective_n, 4),
        "original_sample_size": sample_size,
        "reduction": round(
            sample_size - effective_n,
            4,
        ),
        "method": (
            "Approximate AR(1) effective sample size"
        ),
        "assumption": (
            "Stationary first-order autoregressive "
            "dependence approximation"
        ),
    }


# =========================================================
# DEPENDENCE-ADJUSTED VARIANCE
# =========================================================

def adjust_mann_kendall_variance(
    original_variance: float,
    sample_size: int,
    effective_sample_size: Optional[float],
) -> dict:

    if effective_sample_size is None:
        return {
            "adjusted_variance": original_variance,
            "adjustment_factor": 1.0,
            "adjustment_applied": False,
            "reason": (
                "Lag-one autocorrelation could not be "
                "estimated reliably."
            ),
        }

    if effective_sample_size <= 0:
        raise ValueError(
            "Effective sample size must be positive."
        )

    factor = (
        sample_size / effective_sample_size
    )

    adjusted_variance = (
        original_variance * factor
    )

    if not isfinite(adjusted_variance):
        raise ValueError(
            "Dependence-adjusted variance is not finite."
        )

    return {
        "adjusted_variance": adjusted_variance,
        "adjustment_factor": round(factor, 8),
        "adjustment_applied": (
            abs(factor - 1.0) > 1e-10
        ),
        "method": (
            "AR(1) effective-sample-size variance scaling"
        ),
    }


# =========================================================
# STATUS
# =========================================================

@router.get("/status")
def dependence_aware_status():

    return {
        "service": (
            "GeoNOVA Dependence-Aware Trend Engine"
        ),
        "version": "1.1.0",
        "status": "online",
        "methods": [
            "Mann-Kendall trend test",
            "Tie-corrected Mann-Kendall variance",
            "Fenwick-tree optimized Mann-Kendall score",
            "Linear detrending",
            "Lag-one residual autocorrelation",
            "AR(1) effective sample size",
            "Effective-sample-size variance adjustment",
        ],
        "performance": {
            "mann_kendall_score_complexity": "O(n log n)",
            "variance_complexity": "O(n)",
            "maximum_input_observations": 5000,
            "maximum_calendar_span_months": 12000,
        },
        "limitations": [
            "The dependence correction is an AR(1) approximation.",
            "It is not a full Hamed-Rao or Yue-Wang implementation.",
            "Lag-one autocorrelation can be unstable in short records.",
            "Missing calendar months reduce usable adjacent pairs.",
            "Seasonal dependence is not separately modeled.",
            "Multiple testing is not corrected.",
            "The adjusted p-value remains approximate.",
        ],
    }


# =========================================================
# MAIN ANALYSIS
# =========================================================

@router.post("/analyze")
def analyze_dependence_aware_trend(
    request: DependenceAwareRequest,
):

    try:
        prepared = prepare_observations(
            request.observations
        )

        observations = prepared[
            "valid_observations"
        ]

        values = [
            item["value"]
            for item in observations
        ]

        sample_size = len(values)

        # -------------------------------------------------
        # ORDINARY MANN-KENDALL
        # -------------------------------------------------

        score = mann_kendall_score(values)

        original_variance = mann_kendall_variance(
            values
        )

        ordinary_result = calculate_mk_result(
            score,
            original_variance,
            request.alpha,
        )

        # -------------------------------------------------
        # LINEAR DETRENDING
        # -------------------------------------------------

        detrending = calculate_detrended_residuals(
            observations
        )

        residuals = detrending["residuals"]

        # -------------------------------------------------
        # LAG-ONE AUTOCORRELATION
        # -------------------------------------------------

        autocorrelation = (
            calculate_lag_one_autocorrelation(
                residuals
            )
        )

        rho = autocorrelation["value"]

        # -------------------------------------------------
        # EFFECTIVE SAMPLE SIZE
        # -------------------------------------------------

        effective_sample = (
            calculate_effective_sample_size(
                sample_size,
                rho,
            )
        )

        effective_n = effective_sample["estimate"]

        # -------------------------------------------------
        # ADJUSTED VARIANCE
        # -------------------------------------------------

        adjustment = (
            adjust_mann_kendall_variance(
                original_variance,
                sample_size,
                effective_n,
            )
        )

        adjusted_variance = adjustment[
            "adjusted_variance"
        ]

        adjusted_result = calculate_mk_result(
            score,
            adjusted_variance,
            request.alpha,
        )

        # -------------------------------------------------
        # COMPARISON
        # -------------------------------------------------

        ordinary_significant = (
            ordinary_result[
                "statistically_significant"
            ]
        )

        adjusted_significant = (
            adjusted_result[
                "statistically_significant"
            ]
        )

        conclusion_changed = (
            ordinary_significant
            != adjusted_significant
        )

        warnings = []

        if rho is None:
            warnings.append(
                "Lag-one residual autocorrelation could not "
                "be estimated reliably. The adjusted result "
                "uses the original variance."
            )

        elif rho > 0.2:
            warnings.append(
                "Positive residual autocorrelation was detected. "
                "The ordinary independent-observation trend "
                "test may overstate statistical evidence."
            )

        elif rho < -0.2:
            warnings.append(
                "Negative residual autocorrelation was detected. "
                "The AR(1) approximation is sensitive to the "
                "estimated dependence structure."
            )

        if prepared["missing_months"]:
            warnings.append(
                "Missing months were preserved rather than "
                "compressed. Only adjacent calendar months "
                "were used to estimate lag-one dependence."
            )

        if conclusion_changed:
            warnings.append(
                "The statistical significance conclusion "
                "changed after the approximate dependence "
                "adjustment."
            )

        warnings.append(
            "The adjusted result is an exploratory AR(1) "
            "approximation, not a validated substitute for "
            "established modified Mann-Kendall procedures."
        )

        return {
            "status": "success",

            "analysis": {
                "observation_count": sample_size,

                "first_month": month_label(
                    prepared["first_month"]
                ),

                "last_month": month_label(
                    prepared["last_month"]
                ),

                "missing_month_count": len(
                    prepared["missing_months"]
                ),

                "missing_months": (
                    prepared["missing_months"]
                ),

                "significance_level": request.alpha,
            },

            "temporal_dependence": {
                "lag": 1,

                "residual_autocorrelation": (
                    round(rho, 8)
                    if rho is not None
                    else None
                ),

                "adjacent_pair_count": (
                    autocorrelation[
                        "adjacent_pair_count"
                    ]
                ),

                "detrending_method": (
                    "Ordinary least-squares linear detrending"
                ),

                "effective_sample_size": effective_sample,
            },

            "ordinary_mann_kendall": ordinary_result,

            "dependence_adjusted_mann_kendall": {
                **adjusted_result,
                "variance_adjustment": adjustment,
            },

            "comparison": {
                "ordinary_significant": (
                    ordinary_significant
                ),

                "adjusted_significant": (
                    adjusted_significant
                ),

                "conclusion_changed": (
                    conclusion_changed
                ),

                "interpretation": (
                    "The approximate dependence adjustment "
                    "changes the significance conclusion."
                    if conclusion_changed
                    else
                    "The approximate dependence adjustment "
                    "does not change the significance conclusion."
                ),
            },

            "diagnostics": {
                "linear_detrending_slope_per_month": round(
                    detrending[
                        "linear_slope_per_month"
                    ],
                    8,
                ),

                "ordinary_variance": round(
                    original_variance,
                    8,
                ),

                "adjusted_variance": round(
                    adjusted_variance,
                    8,
                ),
            },

            "warnings": warnings,

            "scientific_limitations": [
                "The adjusted variance uses an AR(1) effective-sample-size approximation.",
                "This is not a full Hamed-Rao or Yue-Wang modified Mann-Kendall test.",
                "The correction assumes a simplified stationary dependence structure.",
                "The residual autocorrelation estimate may be unstable for short records.",
                "Seasonal autocorrelation is not separately corrected.",
                "Neither result corrects for multiple hypothesis testing.",
            ],
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        )
