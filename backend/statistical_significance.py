
from collections import Counter, defaultdict
from datetime import date
from math import erf, erfc, isfinite, sqrt, ceil, floor
from statistics import median
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field


router = APIRouter(
    prefix="/api/science/statistics",
    tags=["Statistical Significance"],
)


# =========================================================
# REQUEST MODELS
# =========================================================

class MonthlyObservation(BaseModel):
    date: str
    value: Optional[float] = None


class TrendAnalysisRequest(BaseModel):
    observations: list[MonthlyObservation] = Field(
        ...,
        min_length=3,
        max_length=5000,
    )

    domain_id: Optional[str] = None
    parameter_key: Optional[str] = None
    unit: Optional[str] = None

    seasonal_adjustment: bool = False

    alpha: Optional[float] = Field(
        default=None,
        gt=0,
        lt=0.5,
    )

    significance_level: float = Field(
        default=0.05,
        gt=0,
        lt=0.5,
    )

    confidence_level: float = Field(
        default=0.95,
        gt=0.5,
        lt=1,
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
    year = index // 12
    month = index % 12 + 1

    return f"{year:04d}-{month:02d}"


# =========================================================
# NORMAL DISTRIBUTION UTILITIES
# =========================================================

def normal_cdf(value: float) -> float:
    return 0.5 * erfc(-value / sqrt(2))


def normal_two_sided_p_value(z_score: float) -> float:
    return erfc(abs(z_score) / sqrt(2))


def normal_critical_value(confidence_level: float) -> float:
    """
    Numerically calculate the two-sided normal critical value.
    """

    target = (1.0 + confidence_level) / 2.0

    low = 0.0
    high = 10.0

    for _ in range(100):
        middle = (low + high) / 2.0

        if normal_cdf(middle) < target:
            low = middle
        else:
            high = middle

    return (low + high) / 2.0


# =========================================================
# REGULARIZED INCOMPLETE BETA FUNCTION
# =========================================================

def beta_continued_fraction(
    a: float,
    b: float,
    x: float,
) -> float:

    maximum_iterations = 200
    epsilon = 3.0e-14
    minimum_value = 1.0e-300

    qab = a + b
    qap = a + 1.0
    qam = a - 1.0

    c = 1.0
    d = 1.0 - qab * x / qap

    if abs(d) < minimum_value:
        d = minimum_value

    d = 1.0 / d
    result = d

    for iteration in range(1, maximum_iterations + 1):

        m2 = 2 * iteration

        aa = (
            iteration * (b - iteration) * x
            / ((qam + m2) * (a + m2))
        )

        d = 1.0 + aa * d

        if abs(d) < minimum_value:
            d = minimum_value

        c = 1.0 + aa / c

        if abs(c) < minimum_value:
            c = minimum_value

        d = 1.0 / d
        result *= d * c

        aa = (
            -(a + iteration)
            * (qab + iteration)
            * x
            / ((a + m2) * (qap + m2))
        )

        d = 1.0 + aa * d

        if abs(d) < minimum_value:
            d = minimum_value

        c = 1.0 + aa / c

        if abs(c) < minimum_value:
            c = minimum_value

        d = 1.0 / d

        delta = d * c
        result *= delta

        if abs(delta - 1.0) < epsilon:
            break

    return result


def regularized_incomplete_beta(
    a: float,
    b: float,
    x: float,
) -> float:

    if x <= 0:
        return 0.0

    if x >= 1:
        return 1.0

    from math import lgamma, log, exp

    log_beta_factor = (
        lgamma(a + b)
        - lgamma(a)
        - lgamma(b)
        + a * log(x)
        + b * log(1.0 - x)
    )

    beta_factor = exp(log_beta_factor)

    if x < (a + 1.0) / (a + b + 2.0):

        return (
            beta_factor
            * beta_continued_fraction(a, b, x)
            / a
        )

    return (
        1.0
        - beta_factor
        * beta_continued_fraction(b, a, 1.0 - x)
        / b
    )


# =========================================================
# STUDENT-T DISTRIBUTION
# =========================================================

def student_t_two_sided_p_value(
    statistic: float,
    degrees_of_freedom: int,
) -> float:

    if degrees_of_freedom <= 0:
        raise ValueError(
            "Degrees of freedom must be positive."
        )

    if statistic == 0:
        return 1.0

    x = (
        degrees_of_freedom
        / (
            degrees_of_freedom
            + statistic * statistic
        )
    )

    return regularized_incomplete_beta(
        degrees_of_freedom / 2.0,
        0.5,
        x,
    )


def student_t_critical_value(
    confidence_level: float,
    degrees_of_freedom: int,
) -> float:

    if degrees_of_freedom <= 0:
        raise ValueError(
            "Degrees of freedom must be positive."
        )

    target_p = 1.0 - confidence_level

    low = 0.0
    high = 1000.0

    for _ in range(120):

        middle = (low + high) / 2.0

        p_value = student_t_two_sided_p_value(
            middle,
            degrees_of_freedom,
        )

        if p_value > target_p:
            low = middle
        else:
            high = middle

    return (low + high) / 2.0


# =========================================================
# DATA VALIDATION ENGINE
# =========================================================

def validate_monthly_observations(
    observations: list[MonthlyObservation],
) -> dict:

    parsed_records = []
    invalid_dates = []
    duplicate_months = []
    missing_values = []
    non_finite_values = []

    month_counts = Counter()

    for item in observations:

        try:
            month = month_index(item.date)

        except ValueError:
            invalid_dates.append(item.date)
            continue

        month_counts[month] += 1

        if month_counts[month] > 1:
            duplicate_months.append(
                month_label(month)
            )

        if item.value is None:
            missing_values.append(item.date)
            continue

        if not isfinite(item.value):
            non_finite_values.append(item.date)
            continue

        parsed_records.append({
            "date": item.date,
            "month": month,
            "value": float(item.value),
        })

    if invalid_dates:
        raise ValueError(
            "Invalid observation dates: "
            + ", ".join(invalid_dates[:10])
        )

    if duplicate_months:
        raise ValueError(
            "Duplicate monthly observations: "
            + ", ".join(sorted(set(duplicate_months))[:10])
        )

    if non_finite_values:
        raise ValueError(
            "Non-finite values found in: "
            + ", ".join(non_finite_values[:10])
        )

    parsed_records.sort(
        key=lambda item: item["month"]
    )

    missing_calendar_months = []

    if parsed_records:

        first_month = parsed_records[0]["month"]
        last_month = parsed_records[-1]["month"]

        available_months = {
            item["month"]
            for item in parsed_records
        }

        missing_calendar_months = [
            month_label(month)
            for month in range(
                first_month,
                last_month + 1,
            )
            if month not in available_months
        ]

    values = [
        item["value"]
        for item in parsed_records
    ]

    outlier_records = []

    if len(values) >= 4:

        center = median(values)

        absolute_deviations = [
            abs(value - center)
            for value in values
        ]

        mad = median(absolute_deviations)

        if mad > 0:

            for item in parsed_records:

                modified_z = (
                    0.67448975
                    * (item["value"] - center)
                    / mad
                )

                if abs(modified_z) > 3.5:

                    outlier_records.append({
                        "date": item["date"],
                        "value": item["value"],
                        "modified_z_score": round(
                            modified_z,
                            4,
                        ),
                    })

        else:
            # When MAD is zero, use the IQR rule.
            sorted_values = sorted(values)

            def percentile(data, fraction):
                position = (
                    len(data) - 1
                ) * fraction

                lower = floor(position)
                upper = ceil(position)

                if lower == upper:
                    return data[lower]

                weight = position - lower

                return (
                    data[lower] * (1.0 - weight)
                    + data[upper] * weight
                )

            q1 = percentile(sorted_values, 0.25)
            q3 = percentile(sorted_values, 0.75)
            iqr = q3 - q1

            if iqr > 0:

                lower_bound = q1 - 1.5 * iqr
                upper_bound = q3 + 1.5 * iqr

                for item in parsed_records:

                    if (
                        item["value"] < lower_bound
                        or item["value"] > upper_bound
                    ):

                        outlier_records.append({
                            "date": item["date"],
                            "value": item["value"],
                            "method": "IQR",
                        })

    total_input = len(observations)
    valid_count = len(parsed_records)

    missing_month_count = len(
        missing_calendar_months
    )

    outlier_count = len(outlier_records)

    quality_score = 100.0

    if total_input:
        quality_score -= (
            len(missing_values)
            / total_input
        ) * 25.0

        quality_score -= (
            missing_month_count
            / max(total_input, 1)
        ) * 20.0

        quality_score -= (
            outlier_count
            / max(valid_count, 1)
        ) * 15.0

    quality_score = max(
        0.0,
        min(100.0, quality_score),
    )

    warnings = []

    if missing_values:
        warnings.append(
            f"{len(missing_values)} observations "
            "contain null values."
        )

    if missing_month_count:
        warnings.append(
            f"{missing_month_count} calendar months "
            "are missing from the observed time range."
        )

    if outlier_count:
        warnings.append(
            f"{outlier_count} potential outliers detected. "
            "They have not been removed."
        )

    if valid_count < 3:
        warnings.append(
            "Fewer than three valid observations remain."
        )

    if quality_score < 70:
        validation_status = "needs_review"
    elif warnings:
        validation_status = "warning"
    else:
        validation_status = "passed"

    return {
        "validation_status": validation_status,

        "quality": {
            "score": round(quality_score, 2),
            "classification": (
                "good"
                if quality_score >= 85
                else "moderate"
                if quality_score >= 70
                else "needs_review"
            ),
            "score_type": "Heuristic quality indicator",
            "not_a_probability": True,
        },

        "summary": {
            "input_observation_count": total_input,
            "valid_observation_count": valid_count,
            "null_value_count": len(missing_values),
            "invalid_date_count": len(invalid_dates),
            "duplicate_month_count": len(
                set(duplicate_months)
            ),
            "missing_calendar_month_count": (
                missing_month_count
            ),
            "potential_outlier_count": outlier_count,
        },

        "missing_values": missing_values,
        "missing_calendar_months": (
            missing_calendar_months
        ),

        "potential_outliers": outlier_records,

        "warnings": warnings,

        "data_modified": False,
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
        count * (count - 1) * (2 * count + 5)
        for count in tie_groups.values()
        if count > 1
    )

    return (
        n * (n - 1) * (2 * n + 5)
        - tie_correction
    ) / 18.0


# =========================================================
# SEASONAL ADJUSTMENT
# =========================================================

def remove_monthly_seasonality(
    observations: list[dict],
) -> tuple[list[dict], dict]:

    grouped = defaultdict(list)

    for item in observations:

        calendar_month = (
            item["month"] % 12 + 1
        )

        grouped[calendar_month].append(
            item["value"]
        )

    insufficient = [
        month
        for month in range(1, 13)
        if len(grouped[month]) < 2
    ]

    if insufficient:
        raise ValueError(
            "Seasonal adjustment requires at least "
            "two observations for every calendar month. "
            f"Insufficient months: {insufficient}"
        )

    monthly_means = {
        month: sum(values) / len(values)
        for month, values in grouped.items()
    }

    overall_mean = (
        sum(item["value"] for item in observations)
        / len(observations)
    )

    adjusted = []

    for item in observations:

        calendar_month = (
            item["month"] % 12 + 1
        )

        adjusted.append({
            **item,
            "original_value": item["value"],
            "value": (
                item["value"]
                - monthly_means[calendar_month]
                + overall_mean
            ),
        })

    return adjusted, {
        "method": "Calendar-month mean adjustment",

        "monthly_means": {
            f"{month:02d}": round(value, 6)
            for month, value in monthly_means.items()
        },

        "overall_mean": round(overall_mean, 6),
    }


# =========================================================
# MANN-KENDALL TREND TEST
# =========================================================

def mann_kendall_test(
    observations: list[dict],
) -> dict:

    values = [
        item["value"]
        for item in observations
    ]

    n = len(values)

    if n < 3:
        raise ValueError(
            "At least three valid observations "
            "are required."
        )

    score = 0

    for i in range(n - 1):

        for j in range(i + 1, n):

            difference = (
                values[j] - values[i]
            )

            if difference > 0:
                score += 1

            elif difference < 0:
                score -= 1

    variance = mann_kendall_variance(values)

    if variance <= 0:

        z_score = 0.0
        p_value = 1.0

    elif score > 0:

        z_score = (
            score - 1
        ) / sqrt(variance)

        p_value = normal_two_sided_p_value(
            z_score
        )

    elif score < 0:

        z_score = (
            score + 1
        ) / sqrt(variance)

        p_value = normal_two_sided_p_value(
            z_score
        )

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
        "test": "Mann-Kendall",
        "score": score,
        "variance": round(variance, 6),
        "z_score": round(z_score, 6),
        "p_value": round(p_value, 8),
        "direction": direction,
        "p_value_method": (
            "Two-sided normal approximation "
            "with continuity correction"
        ),
    }


# =========================================================
# SEN'S SLOPE + CONFIDENCE INTERVAL
# =========================================================

def sens_slope(
    observations: list[dict],
    confidence_level: float = 0.95,
) -> dict:

    slopes = []

    for i in range(len(observations) - 1):

        for j in range(i + 1, len(observations)):

            month_difference = (
                observations[j]["month"]
                - observations[i]["month"]
            )

            if month_difference == 0:
                continue

            slope = (
                observations[j]["value"]
                - observations[i]["value"]
            ) / month_difference

            slopes.append(slope)

    if not slopes:
        raise ValueError(
            "Unable to calculate Sen's slope."
        )

    slopes.sort()

    count = len(slopes)

    median_slope = median(slopes)

    values = [
        item["value"]
        for item in observations
    ]

    variance = mann_kendall_variance(values)

    if variance <= 0:

        lower_slope = median_slope
        upper_slope = median_slope

    else:

        critical = normal_critical_value(
            confidence_level
        )

        confidence_radius = (
            critical * sqrt(variance)
        )

        lower_position = (
            count - confidence_radius
        ) / 2.0

        upper_position = (
            count + confidence_radius
        ) / 2.0

        lower_rank = max(
            0,
            min(
                count - 1,
                floor(lower_position),
            ),
        )

        upper_rank = max(
            0,
            min(
                count - 1,
                ceil(upper_position) - 1,
            ),
        )

        lower_slope = slopes[lower_rank]
        upper_slope = slopes[upper_rank]

    return {
        "method": "Sen's slope",

        "slope_per_month": round(
            median_slope,
            8,
        ),

        "slope_per_year": round(
            median_slope * 12,
            8,
        ),

        "pairwise_slopes_count": count,

        "confidence_interval": {
            "confidence_level": confidence_level,

            "lower_per_month": round(
                lower_slope,
                8,
            ),

            "upper_per_month": round(
                upper_slope,
                8,
            ),

            "lower_per_year": round(
                lower_slope * 12,
                8,
            ),

            "upper_per_year": round(
                upper_slope * 12,
                8,
            ),

            "method": (
                "Approximate distribution-free rank interval "
                "using tie-corrected Mann-Kendall variance"
            ),

            "includes_zero": (
                lower_slope <= 0 <= upper_slope
            ),
        },
    }


# =========================================================
# ORDINARY LEAST SQUARES + STUDENT-T INFERENCE
# =========================================================

def linear_regression(
    observations: list[dict],
    confidence_level: float = 0.95,
) -> dict:

    n = len(observations)

    if n < 3:
        raise ValueError(
            "At least three observations are required."
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

    ss_xx = sum(
        (x - mean_x) ** 2
        for x in x_values
    )

    ss_yy = sum(
        (y - mean_y) ** 2
        for y in y_values
    )

    ss_xy = sum(
        (x - mean_x) * (y - mean_y)
        for x, y in zip(x_values, y_values)
    )

    if ss_xx == 0:
        raise ValueError(
            "Time values must contain more than one month."
        )

    slope = ss_xy / ss_xx

    intercept = (
        mean_y - slope * mean_x
    )

    residuals = [
        y - (intercept + slope * x)
        for x, y in zip(x_values, y_values)
    ]

    residual_sum_squares = sum(
        residual ** 2
        for residual in residuals
    )

    r_squared = (
        1.0 - residual_sum_squares / ss_yy
        if ss_yy > 0
        else 0.0
    )

    r_squared = max(
        0.0,
        min(1.0, r_squared),
    )

    degrees_of_freedom = n - 2

    residual_variance = (
        residual_sum_squares
        / degrees_of_freedom
    )

    standard_error = sqrt(
        max(0.0, residual_variance / ss_xx)
    )

    if standard_error > 0:

        test_statistic = (
            slope / standard_error
        )

        p_value = student_t_two_sided_p_value(
            test_statistic,
            degrees_of_freedom,
        )

        critical = student_t_critical_value(
            confidence_level,
            degrees_of_freedom,
        )

        lower_slope = (
            slope - critical * standard_error
        )

        upper_slope = (
            slope + critical * standard_error
        )

    elif slope == 0:

        test_statistic = 0.0
        p_value = 1.0

        lower_slope = 0.0
        upper_slope = 0.0

    else:

        # A perfect non-zero linear fit has zero residual
        # variance. Do not manufacture a finite uncertainty
        # interval or a conventional inferential p-value.

        test_statistic = None
        p_value = None

        lower_slope = None
        upper_slope = None

    confidence_interval = {
        "confidence_level": confidence_level,

        "lower_per_month": (
            round(lower_slope, 8)
            if lower_slope is not None
            else None
        ),

        "upper_per_month": (
            round(upper_slope, 8)
            if upper_slope is not None
            else None
        ),

        "lower_per_year": (
            round(lower_slope * 12, 8)
            if lower_slope is not None
            else None
        ),

        "upper_per_year": (
            round(upper_slope * 12, 8)
            if upper_slope is not None
            else None
        ),

        "method": (
            "Two-sided Student-t interval using OLS "
            "residual standard error and n-2 degrees "
            "of freedom"
        ),

        "includes_zero": (
            lower_slope <= 0 <= upper_slope
            if lower_slope is not None
            else None
        ),
    }

    return {
        "method": "Ordinary Least Squares",

        "slope_per_month": round(
            slope,
            8,
        ),

        "slope_per_year": round(
            slope * 12,
            8,
        ),

        "intercept": round(
            intercept,
            8,
        ),

        "r_squared": round(
            r_squared,
            6,
        ),

        "standard_error": round(
            standard_error,
            8,
        ),

        "degrees_of_freedom": degrees_of_freedom,

        "test_statistic": (
            round(test_statistic, 6)
            if test_statistic is not None
            else None
        ),

        "p_value": (
            round(p_value, 8)
            if p_value is not None
            else None
        ),

        "p_value_method": (
            "Two-sided Student-t distribution"
        ),

        "confidence_interval": confidence_interval,
    }


# =========================================================
# STATUS
# =========================================================

@router.get("/status")
def statistical_engine_status():

    return {
        "service": "GeoNOVA Statistical Trend Engine",
        "status": "online",

        "methods": [
            "Ordinary Least Squares",
            "Mann-Kendall",
            "Sen's slope",
        ],

        "validation": {
            "enabled": True,
            "date_validation": True,
            "duplicate_month_detection": True,
            "missing_value_detection": True,
            "missing_month_detection": True,
            "non_finite_value_detection": True,
            "robust_outlier_screening": True,
            "automatic_outlier_removal": False,
            "quality_score": "Heuristic",
        },

        "seasonal_adjustment": True,

        "confidence_intervals": True,

        "confidence_interval_level_default": 0.95,

        "confidence_interval_methods": [
            "Sen's slope approximate distribution-free rank interval",
            "OLS Student-t interval",
        ],

        "p_value_methods": [
            "Mann-Kendall normal approximation",
            "OLS Student-t distribution",
        ],

        "limitations": [
            "Serial correlation is not corrected.",
            "Multiple testing is not corrected.",
            "Mann-Kendall p-values use a normal approximation.",
            "Sen's slope confidence intervals are approximate.",
            "The validation quality score is heuristic.",
            "Outlier detection does not establish data errors.",
            "OLS inference assumes its model conditions are appropriate.",
        ],
    }


# =========================================================
# MAIN ANALYSIS
# =========================================================

@router.post("/trend")
def analyze_trend(
    request: TrendAnalysisRequest,
):

    try:

        # -------------------------------------------------
        # SIGNIFICANCE CONFIGURATION
        # -------------------------------------------------

        selected_alpha = (
            request.alpha
            if request.alpha is not None
            else request.significance_level
        )

        # -------------------------------------------------
        # DATA VALIDATION
        # -------------------------------------------------

        validation_report = (
            validate_monthly_observations(
                request.observations
            )
        )

        observations = []

        for item in request.observations:

            month = month_index(item.date)

            if item.value is None:
                continue

            if not isfinite(item.value):
                raise ValueError(
                    f"Non-finite value in {item.date}."
                )

            observations.append({
                "date": item.date,
                "month": month,
                "value": float(item.value),
            })

        observations.sort(
            key=lambda item: item["month"]
        )

        if len(observations) < 3:
            raise ValueError(
                "At least three valid monthly values "
                "are required for trend analysis."
            )

        # -------------------------------------------------
        # MISSING CALENDAR MONTHS
        # -------------------------------------------------

        first_month = observations[0]["month"]
        last_month = observations[-1]["month"]

        observed_months = {
            item["month"]
            for item in observations
        }

        missing_months = [
            month_label(month)
            for month in range(
                first_month,
                last_month + 1,
            )
            if month not in observed_months
        ]

        # -------------------------------------------------
        # SEASONAL ADJUSTMENT
        # -------------------------------------------------

        analysis_observations = observations
        seasonal_metadata = None

        if request.seasonal_adjustment:

            if len(observations) < 24:
                raise ValueError(
                    "Seasonal adjustment requires at least "
                    "24 valid monthly observations."
                )

            (
                analysis_observations,
                seasonal_metadata,
            ) = remove_monthly_seasonality(
                observations
            )

        # -------------------------------------------------
        # STATISTICAL ANALYSIS
        # -------------------------------------------------

        mk_result = mann_kendall_test(
            analysis_observations
        )

        sen_result = sens_slope(
            analysis_observations,
            request.confidence_level,
        )

        ols_result = linear_regression(
            analysis_observations,
            request.confidence_level,
        )

        significant = (
            mk_result["p_value"] < selected_alpha
        )

        # -------------------------------------------------
        # INTERPRETATION
        # -------------------------------------------------

        if significant:

            decision = (
                "Evidence of a monotonic trend "
                "at the selected significance level."
            )

        else:

            decision = (
                "Insufficient evidence of a monotonic "
                "trend at the selected significance level."
            )

        # -------------------------------------------------
        # RESPONSE
        # -------------------------------------------------

        return {
            "status": "success",

            "metadata": {
                "domain_id": request.domain_id,
                "parameter_key": request.parameter_key,
                "unit": request.unit,
            },

            "data_validation": validation_report,

            "analysis": {
                "observation_count": len(observations),

                "analysis_count": len(
                    analysis_observations
                ),

                "first_month": month_label(
                    first_month
                ),

                "last_month": month_label(
                    last_month
                ),

                "missing_month_count": len(
                    missing_months
                ),

                "missing_months": missing_months,

                "seasonal_adjustment": (
                    request.seasonal_adjustment
                ),

                "significance_level": selected_alpha,

                "confidence_level": (
                    request.confidence_level
                ),
            },

            "seasonality": seasonal_metadata,

            "results": {
                "mann_kendall": mk_result,
                "sens_slope": sen_result,
                "ordinary_least_squares": ols_result,
            },

            "interpretation": {
                "direction": mk_result["direction"],

                "statistically_significant": significant,

                "decision": decision,

                "basis": "Mann-Kendall test",

                "confidence_interval_interpretation": {
                    "sens_slope_includes_zero": (
                        sen_result["confidence_interval"][
                            "includes_zero"
                        ]
                    ),

                    "ols_slope_includes_zero": (
                        ols_result["confidence_interval"][
                            "includes_zero"
                        ]
                    ),
                },

                "caution": (
                    "Mann-Kendall p-values use a normal "
                    "approximation. OLS inference uses a "
                    "Student-t distribution but depends on "
                    "regression assumptions. Serial correlation "
                    "and multiple testing are not corrected. "
                    "The Sen's slope interval is approximate. "
                    "Outlier flags are screening indicators, "
                    "not proof of erroneous measurements. "
                    "These results require scientific review "
                    "before being treated as definitive."
                ),
            },
        }

    except ValueError as exc:

        raise HTTPException(
            status_code=422,
            detail=str(exc),
        )
