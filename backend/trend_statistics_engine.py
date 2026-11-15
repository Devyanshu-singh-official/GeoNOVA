
from collections import Counter
from datetime import date
from math import erfc, exp, floor, lgamma, log, sqrt
from statistics import median
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator

router = APIRouter()

ENGINE_VERSION = "1.0.0"
MAX_OBSERVATIONS = 2000
MIN_OBSERVATIONS = 8
DAYS_PER_YEAR = 365.2425


class Observation(BaseModel):
    date: date
    value: float | None


class TrendRequest(BaseModel):
    observations: list[Observation] = Field(
        ...,
        min_length=MIN_OBSERVATIONS,
        max_length=MAX_OBSERVATIONS,
    )
    parameter: str = "unknown"
    unit: str = ""
    confidence_level: float = Field(default=0.95, gt=0.80, lt=1.0)

    @model_validator(mode="after")
    def validate_dates(self):
        dates = [item.date for item in self.observations]

        if len(dates) != len(set(dates)):
            raise ValueError(
                "Duplicate dates are not allowed. Aggregate them first."
            )

        return self


def normal_two_sided_p(z: float) -> float:
    return min(1.0, erfc(abs(z) / sqrt(2.0)))


def normal_critical_value(confidence: float) -> float:
    # Accurate common critical values; interpolate otherwise.
    table = {
        0.90: 1.6448536269514722,
        0.95: 1.959963984540054,
        0.98: 2.3263478740408408,
        0.99: 2.5758293035489004,
    }

    nearest = min(table, key=lambda item: abs(item - confidence))

    if abs(nearest - confidence) < 1e-9:
        return table[nearest]

    # Inverse-normal approximation (Acklam).
    p = (1.0 + confidence) / 2.0
    a = [
        -3.969683028665376e1,
        2.209460984245205e2,
        -2.759285104469687e2,
        1.383577518672690e2,
        -3.066479806614716e1,
        2.506628277459239,
    ]
    b = [
        -5.447609879822406e1,
        1.615858368580409e2,
        -1.556989798598866e2,
        6.680131188771972e1,
        -1.328068155288572e1,
    ]
    c = [
        -7.784894002430293e-3,
        -3.223964580411365e-1,
        -2.400758277161838,
        -2.549732539343734,
        4.374664141464968,
        2.938163982698783,
    ]
    d = [
        7.784695709041462e-3,
        3.224671290700398e-1,
        2.445134137142996,
        3.754408661907416,
    ]

    low = 0.02425
    high = 1.0 - low

    if p < low:
        q = sqrt(-2.0 * log(p))
        return (
            (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5])
            / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0)
        )

    if p > high:
        q = sqrt(-2.0 * log(1.0 - p))
        return -(
            (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5])
            / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0)
        )

    q = p - 0.5
    r = q * q

    return (
        (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q
        / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0)
    )


def regularized_beta(x: float, a: float, b: float) -> float:
    """Regularized incomplete beta function using a continued fraction."""

    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0

    def beta_fraction(a_value, b_value, x_value):
        max_iterations = 300
        epsilon = 3e-14
        tiny = 1e-300

        qab = a_value + b_value
        qap = a_value + 1.0
        qam = a_value - 1.0

        c_value = 1.0
        d_value = 1.0 - qab * x_value / qap

        if abs(d_value) < tiny:
            d_value = tiny

        d_value = 1.0 / d_value
        h = d_value

        for m in range(1, max_iterations + 1):
            m2 = 2 * m

            aa = (
                m * (b_value - m) * x_value
                / ((qam + m2) * (a_value + m2))
            )

            d_value = 1.0 + aa * d_value
            if abs(d_value) < tiny:
                d_value = tiny

            c_value = 1.0 + aa / c_value
            if abs(c_value) < tiny:
                c_value = tiny

            d_value = 1.0 / d_value
            h *= d_value * c_value

            aa = (
                -(a_value + m) * (qab + m) * x_value
                / ((a_value + m2) * (qap + m2))
            )

            d_value = 1.0 + aa * d_value
            if abs(d_value) < tiny:
                d_value = tiny

            c_value = 1.0 + aa / c_value
            if abs(c_value) < tiny:
                c_value = tiny

            d_value = 1.0 / d_value
            delta = d_value * c_value
            h *= delta

            if abs(delta - 1.0) < epsilon:
                break

        return h

    log_beta = (
        lgamma(a + b)
        - lgamma(a)
        - lgamma(b)
        + a * log(x)
        + b * log(1.0 - x)
    )

    front = exp(log_beta)

    if x < (a + 1.0) / (a + b + 2.0):
        return front * beta_fraction(a, b, x) / a

    return 1.0 - (
        front * beta_fraction(b, a, 1.0 - x) / b
    )


def student_t_two_sided_p(t_value: float, degrees_freedom: int) -> float:
    if degrees_freedom <= 0:
        return 1.0

    x = degrees_freedom / (
        degrees_freedom + t_value * t_value
    )

    return max(
        0.0,
        min(
            1.0,
            regularized_beta(
                x,
                degrees_freedom / 2.0,
                0.5,
            ),
        ),
    )


def date_to_decimal_year(day: date) -> float:
    start = date(day.year, 1, 1)
    end = date(day.year + 1, 1, 1)

    fraction = (day - start).days / (end - start).days
    return day.year + fraction


def mann_kendall(values: list[float]) -> dict[str, Any]:
    n = len(values)

    score = 0
    for i in range(n - 1):
        for j in range(i + 1, n):
            difference = values[j] - values[i]

            if difference > 0:
                score += 1
            elif difference < 0:
                score -= 1

    ties = Counter(values)

    tie_correction = sum(
        count * (count - 1) * (2 * count + 5)
        for count in ties.values()
        if count > 1
    )

    variance = (
        n * (n - 1) * (2 * n + 5) - tie_correction
    ) / 18.0

    if variance <= 0:
        z_score = 0.0
        p_value = 1.0
    elif score > 0:
        z_score = (score - 1.0) / sqrt(variance)
        p_value = normal_two_sided_p(z_score)
    elif score < 0:
        z_score = (score + 1.0) / sqrt(variance)
        p_value = normal_two_sided_p(z_score)
    else:
        z_score = 0.0
        p_value = 1.0

    if p_value < 0.05:
        direction = (
            "increasing" if score > 0 else "decreasing"
        )
    else:
        direction = "no statistically significant monotonic trend"

    return {
        "test": "Mann-Kendall",
        "score_S": score,
        "variance_S": variance,
        "z_score": z_score,
        "p_value": p_value,
        "direction": direction,
        "significant_at_0_05": p_value < 0.05,
        "method": "Tie-corrected normal approximation with continuity correction",
    }


def sen_slope(
    x_values: list[float],
    y_values: list[float],
    confidence: float,
) -> dict[str, Any]:
    slopes = []

    n = len(y_values)

    for i in range(n - 1):
        for j in range(i + 1, n):
            delta_x = x_values[j] - x_values[i]

            if delta_x > 0:
                slopes.append(
                    (y_values[j] - y_values[i]) / delta_x
                )

    if not slopes:
        return {
            "slope_per_year": None,
            "confidence_interval": None,
        }

    slopes.sort()
    estimate = median(slopes)

    # Mann-Kendall variance-based confidence interval for Sen's slope.
    ties = Counter(y_values)
    tie_correction = sum(
        count * (count - 1) * (2 * count + 5)
        for count in ties.values()
        if count > 1
    )

    variance = (
        n * (n - 1) * (2 * n + 5) - tie_correction
    ) / 18.0

    z_critical = normal_critical_value(confidence)
    confidence_width = z_critical * sqrt(max(variance, 0.0))

    total_slopes = len(slopes)

    lower_index = max(
        0,
        min(
            total_slopes - 1,
            floor((total_slopes - confidence_width) / 2.0),
        ),
    )

    upper_index = max(
        0,
        min(
            total_slopes - 1,
            floor((total_slopes + confidence_width) / 2.0),
        ),
    )

    return {
        "slope_per_year": estimate,
        "confidence_interval": {
            "level": confidence,
            "lower": slopes[lower_index],
            "upper": slopes[upper_index],
            "method": "Mann-Kendall variance-based Sen slope interval",
        },
        "pairwise_slopes_calculated": total_slopes,
    }


def linear_regression(
    x_values: list[float],
    y_values: list[float],
    confidence: float,
) -> dict[str, Any]:
    n = len(x_values)

    mean_x = sum(x_values) / n
    mean_y = sum(y_values) / n

    sxx = sum((x - mean_x) ** 2 for x in x_values)
    syy = sum((y - mean_y) ** 2 for y in y_values)
    sxy = sum(
        (x_values[i] - mean_x) * (y_values[i] - mean_y)
        for i in range(n)
    )

    if sxx <= 0:
        raise HTTPException(
            status_code=422,
            detail="Regression requires distinct observation dates.",
        )

    slope = sxy / sxx
    intercept = mean_y - slope * mean_x

    predicted = [
        intercept + slope * x
        for x in x_values
    ]

    residuals = [
        y_values[i] - predicted[i]
        for i in range(n)
    ]

    residual_sum_squares = sum(
        residual ** 2 for residual in residuals
    )

    r_squared = (
        1.0 - residual_sum_squares / syy
        if syy > 0
        else 1.0
    )

    degrees_freedom = n - 2

    if degrees_freedom > 0:
        residual_variance = (
            residual_sum_squares / degrees_freedom
        )

        standard_error = sqrt(
            max(0.0, residual_variance / sxx)
        )

        if standard_error > 0:
            t_statistic = slope / standard_error
            p_value = student_t_two_sided_p(
                t_statistic,
                degrees_freedom,
            )
        else:
            t_statistic = 0.0 if slope == 0 else float("inf")
            p_value = 1.0 if slope == 0 else 0.0

        z_critical = normal_critical_value(confidence)

        confidence_interval = {
            "level": confidence,
            "lower": slope - z_critical * standard_error,
            "upper": slope + z_critical * standard_error,
            "method": "Normal approximation",
        }
    else:
        standard_error = None
        t_statistic = None
        p_value = None
        confidence_interval = None

    return {
        "slope_per_year": slope,
        "intercept": intercept,
        "r_squared": r_squared,
        "standard_error": standard_error,
        "t_statistic": t_statistic,
        "degrees_of_freedom": degrees_freedom,
        "p_value": p_value,
        "confidence_interval": confidence_interval,
        "significant_at_0_05": (
            p_value < 0.05 if p_value is not None else None
        ),
    }


@router.post("/api/science/trends/analyze")
def analyze_trend(request: TrendRequest):
    valid = [
        item
        for item in request.observations
        if item.value is not None
    ]

    valid.sort(key=lambda item: item.date)

    if len(valid) < MIN_OBSERVATIONS:
        raise HTTPException(
            status_code=422,
            detail=(
                f"At least {MIN_OBSERVATIONS} valid non-missing "
                "observations are required."
            ),
        )

    values = [float(item.value) for item in valid]

    if any(not value == value for value in values):
        raise HTTPException(
            status_code=422,
            detail="NaN observations are not allowed.",
        )

    x_values = [
        date_to_decimal_year(item.date)
        for item in valid
    ]

    mk = mann_kendall(values)

    sen = sen_slope(
        x_values,
        values,
        request.confidence_level,
    )

    regression = linear_regression(
        x_values,
        values,
        request.confidence_level,
    )

    missing_count = (
        len(request.observations) - len(valid)
    )

    trend_direction = (
        "increasing"
        if sen["slope_per_year"] > 0
        else "decreasing"
        if sen["slope_per_year"] < 0
        else "flat"
    )

    return {
        "project": "GeoNOVA",
        "engine": "Statistical Trend Detection Engine",
        "version": ENGINE_VERSION,
        "parameter": request.parameter,
        "unit": request.unit,
        "period": {
            "start": valid[0].date.isoformat(),
            "end": valid[-1].date.isoformat(),
            "span_years": x_values[-1] - x_values[0],
        },
        "data_quality": {
            "input_observations": len(request.observations),
            "valid_observations": len(valid),
            "missing_observations": missing_count,
            "missing_values_excluded": True,
        },
        "trend": {
            "direction_from_sen_slope": trend_direction,
            "sen_slope": sen,
            "mann_kendall": mk,
            "linear_regression": regression,
        },
        "interpretation": {
            "monotonic_trend_detected": mk["p_value"] < 0.05,
            "regression_trend_detected": (
                regression["p_value"] < 0.05
                if regression["p_value"] is not None
                else None
            ),
            "significance_threshold": 0.05,
            "caution": (
                "Statistical significance does not establish causation. "
                "Serial autocorrelation and seasonality have not been "
                "adjusted in this endpoint. Use GeoNOVA's dependence-aware "
                "and seasonal trend modules before making final climate "
                "trend claims."
            ),
        },
        "methodology": {
            "mann_kendall": (
                "Tie-corrected Mann-Kendall test using a normal "
                "approximation and continuity correction."
            ),
            "sen_slope": (
                "Median of all pairwise slopes using actual elapsed "
                "time expressed in decimal years."
            ),
            "linear_regression": (
                "Ordinary least squares with Student-t significance "
                "test and a normal-approximation slope interval."
            ),
            "missing_data": (
                "Null observations are excluded. No interpolation "
                "or synthetic values are generated."
            ),
        },
    }
