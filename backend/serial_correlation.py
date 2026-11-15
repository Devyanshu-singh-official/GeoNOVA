
from datetime import date
from math import exp, isfinite, lgamma, log
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field


router = APIRouter(
    prefix="/api/science/temporal-dependence",
    tags=["Temporal Dependence"],
)


# =========================================================
# REQUEST MODELS
# =========================================================

class MonthlyValue(BaseModel):
    date: str
    value: Optional[float] = None


class DependenceRequest(BaseModel):
    observations: list[MonthlyValue] = Field(
        ...,
        min_length=8,
        max_length=5000,
    )

    max_lag: int = Field(
        default=12,
        ge=1,
        le=48,
    )

    significance_level: float = Field(
        default=0.05,
        gt=0,
        lt=0.5,
    )


# =========================================================
# DATE UTILITIES
# =========================================================

def get_month_index(date_string: str) -> int:
    try:
        parsed = date.fromisoformat(date_string)
    except ValueError:
        raise ValueError(
            f"Invalid ISO date: {date_string}"
        )

    return parsed.year * 12 + parsed.month - 1


def month_label(index: int) -> str:
    return (
        f"{index // 12:04d}-"
        f"{index % 12 + 1:02d}"
    )


# =========================================================
# GAMMA FUNCTION UTILITIES
# =========================================================

def regularized_gamma_q(
    a: float,
    x: float,
) -> float:
    """
    Upper regularized incomplete gamma function.

    Used to calculate the chi-square survival probability
    for the Ljung-Box statistic.
    """

    if a <= 0:
        raise ValueError(
            "Gamma shape parameter must be positive."
        )

    if x < 0:
        raise ValueError(
            "Gamma input cannot be negative."
        )

    if x == 0:
        return 1.0

    maximum_iterations = 300
    epsilon = 1e-14
    minimum_value = 1e-300

    log_factor = (
        -x
        + a * log(x)
        - lgamma(a)
    )

    if x < a + 1.0:
        # Calculate lower regularized gamma P
        term = 1.0 / a
        total = term
        current_a = a

        for _ in range(maximum_iterations):
            current_a += 1.0
            term *= x / current_a
            total += term

            if abs(term) < abs(total) * epsilon:
                break

        lower_p = total * exp(log_factor)

        return max(
            0.0,
            min(1.0, 1.0 - lower_p),
        )

    # Continued fraction for upper regularized gamma Q
    b = x + 1.0 - a
    c = 1.0 / minimum_value
    d = 1.0 / max(abs(b), minimum_value)

    if b < 0:
        d = -d

    h = d

    for iteration in range(1, maximum_iterations + 1):

        an = (
            -iteration
            * (iteration - a)
        )

        b += 2.0

        d = an * d + b

        if abs(d) < minimum_value:
            d = minimum_value

        c = b + an / c

        if abs(c) < minimum_value:
            c = minimum_value

        d = 1.0 / d

        delta = d * c
        h *= delta

        if abs(delta - 1.0) < epsilon:
            break

    result = exp(log_factor) * h

    return max(
        0.0,
        min(1.0, result),
    )


def chi_square_survival(
    statistic: float,
    degrees_of_freedom: int,
) -> float:

    if degrees_of_freedom <= 0:
        raise ValueError(
            "Degrees of freedom must be positive."
        )

    return regularized_gamma_q(
        degrees_of_freedom / 2.0,
        statistic / 2.0,
    )


# =========================================================
# VALIDATION AND CALENDAR GRID
# =========================================================

def prepare_monthly_series(
    observations: list[MonthlyValue],
) -> dict:

    records = {}
    duplicate_months = []

    for item in observations:

        month = get_month_index(item.date)

        if month in records:
            duplicate_months.append(
                month_label(month)
            )
            continue

        if item.value is not None:

            if not isfinite(item.value):
                raise ValueError(
                    f"Non-finite value in {item.date}."
                )

            value = float(item.value)

        else:
            value = None

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

    if len(records) < 8:
        raise ValueError(
            "At least eight distinct monthly records "
            "are required."
        )

    first_month = min(records)
    last_month = max(records)

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

    valid_values = [
        item["value"]
        for item in calendar_series
        if item["value"] is not None
    ]

    missing_months = [
        item["date"]
        for item in calendar_series
        if item["value"] is None
    ]

    if len(valid_values) < 8:
        raise ValueError(
            "At least eight non-null monthly values "
            "are required."
        )

    return {
        "calendar_series": calendar_series,
        "valid_values": valid_values,
        "missing_months": missing_months,
        "first_month": first_month,
        "last_month": last_month,
    }


# =========================================================
# AUTOCORRELATION FUNCTION
# =========================================================

def calculate_acf(
    series: list[Optional[float]],
    max_lag: int,
) -> list[dict]:

    valid_values = [
        value
        for value in series
        if value is not None
    ]

    if len(valid_values) < 3:
        raise ValueError(
            "Insufficient values for autocorrelation."
        )

    mean_value = (
        sum(valid_values)
        / len(valid_values)
    )

    denominator = sum(
        (value - mean_value) ** 2
        for value in valid_values
    )

    if denominator <= 0:
        return [
            {
                "lag": lag,
                "autocorrelation": None,
                "pair_count": 0,
            }
            for lag in range(1, max_lag + 1)
        ]

    results = []

    for lag in range(1, max_lag + 1):

        numerator = 0.0
        pair_count = 0

        for index in range(
            lag,
            len(series),
        ):

            previous = series[index - lag]
            current = series[index]

            if previous is None or current is None:
                continue

            numerator += (
                (previous - mean_value)
                * (current - mean_value)
            )

            pair_count += 1

        if pair_count == 0:
            autocorrelation = None
        else:
            autocorrelation = (
                numerator / denominator
            )

        results.append({
            "lag": lag,

            "autocorrelation": (
                round(autocorrelation, 8)
                if autocorrelation is not None
                else None
            ),

            "pair_count": pair_count,
        })

    return results


# =========================================================
# PARTIAL AUTOCORRELATION
# DURBIN-LEVINSON RECURSION
# =========================================================

def calculate_pacf(
    acf_values: list[float],
) -> list[dict]:

    if not acf_values:
        return []

    coefficients = []
    previous_phi = []

    for order in range(1, len(acf_values) + 1):

        current_acf = acf_values[order - 1]

        if order == 1:

            reflection = current_acf
            current_phi = [reflection]

        else:

            numerator = (
                current_acf
                - sum(
                    previous_phi[index]
                    * acf_values[order - index - 2]
                    for index in range(order - 1)
                )
            )

            denominator = (
                1.0
                - sum(
                    previous_phi[index]
                    * acf_values[index]
                    for index in range(order - 1)
                )
            )

            if abs(denominator) < 1e-12:
                reflection = None
                current_phi = []
            else:

                reflection = (
                    numerator / denominator
                )

                current_phi = [
                    previous_phi[index]
                    - reflection
                    * previous_phi[
                        order - index - 2
                    ]
                    for index in range(order - 1)
                ]

                current_phi.append(reflection)

        coefficients.append({
            "lag": order,
            "partial_autocorrelation": (
                round(reflection, 8)
                if reflection is not None
                else None
            ),
        })

        if reflection is None:
            break

        previous_phi = current_phi

    return coefficients


# =========================================================
# LJUNG-BOX TEST
# =========================================================

def ljung_box_test(
    acf_values: list[dict],
    sample_size: int,
    significance_level: float,
) -> dict:

    usable = [
        item
        for item in acf_values
        if item["autocorrelation"] is not None
    ]

    if not usable:

        return {
            "test": "Ljung-Box",
            "statistic": None,
            "degrees_of_freedom": 0,
            "p_value": None,
            "significant_dependence": None,
            "status": "insufficient_data",
        }

    statistic = 0.0

    for item in usable:

        lag = item["lag"]
        rho = item["autocorrelation"]

        if sample_size - lag <= 0:
            continue

        statistic += (
            rho * rho
            / (sample_size - lag)
        )

    statistic *= (
        sample_size
        * (sample_size + 2)
    )

    degrees_of_freedom = len(usable)

    p_value = chi_square_survival(
        statistic,
        degrees_of_freedom,
    )

    return {
        "test": "Ljung-Box",

        "statistic": round(
            statistic,
            8,
        ),

        "degrees_of_freedom": (
            degrees_of_freedom
        ),

        "p_value": round(
            p_value,
            8,
        ),

        "significance_level": (
            significance_level
        ),

        "significant_dependence": (
            p_value < significance_level
        ),

        "interpretation": (
            "Evidence of temporal autocorrelation "
            "at one or more tested lags."
            if p_value < significance_level
            else
            "Insufficient evidence of temporal "
            "autocorrelation at the tested lags."
        ),

        "status": "calculated",
    }


# =========================================================
# EFFECTIVE SAMPLE SIZE
# =========================================================

def estimate_effective_sample_size(
    sample_size: int,
    lag_one_autocorrelation: Optional[float],
) -> dict:

    if lag_one_autocorrelation is None:

        return {
            "estimate": None,
            "method": "AR(1) approximation",
            "interpretation": (
                "Could not estimate because lag-one "
                "autocorrelation was unavailable."
            ),
        }

    rho = lag_one_autocorrelation

    denominator = 1.0 + rho

    if abs(denominator) < 1e-12:

        effective_size = 1.0

    else:

        effective_size = (
            sample_size
            * (1.0 - rho)
            / denominator
        )

    effective_size = max(
        1.0,
        min(
            float(sample_size),
            effective_size,
        ),
    )

    return {
        "estimate": round(
            effective_size,
            3,
        ),

        "original_sample_size": sample_size,

        "method": (
            "Approximate AR(1) effective sample size"
        ),

        "lag_one_autocorrelation": round(
            rho,
            8,
        ),

        "interpretation": (
            "This is an approximate diagnostic, "
            "not a replacement for a dependence-adjusted "
            "trend significance test."
        ),
    }


# =========================================================
# STATUS
# =========================================================

@router.get("/status")
def temporal_dependence_status():

    return {
        "service": (
            "GeoNOVA Temporal Dependence Engine"
        ),

        "status": "online",

        "methods": [
            "Autocorrelation Function",
            "Partial Autocorrelation Function",
            "Ljung-Box Test",
            "Effective Sample Size Approximation",
        ],

        "calendar_gap_handling": (
            "Missing calendar months are preserved "
            "as missing values; they are not compressed."
        ),

        "limitations": [
            "This module diagnoses dependence; it does not "
            "correct trend-test p-values.",
            "Effective sample size uses an approximate AR(1) model.",
            "PACF is available only for complete monthly series.",
            "Ljung-Box results depend on the selected maximum lag.",
            "Seasonality may contribute to measured autocorrelation.",
        ],
    }


# =========================================================
# MAIN ANALYSIS
# =========================================================

@router.post("/analyze")
def analyze_temporal_dependence(
    request: DependenceRequest,
):

    try:

        prepared = prepare_monthly_series(
            request.observations
        )

        calendar_series = prepared[
            "calendar_series"
        ]

        valid_values = prepared[
            "valid_values"
        ]

        sample_size = len(valid_values)

        calendar_length = len(calendar_series)

        effective_max_lag = min(
            request.max_lag,
            calendar_length - 1,
            max(1, sample_size // 3),
        )

        if effective_max_lag < 1:
            raise ValueError(
                "Insufficient time span for lag analysis."
            )

        series = [
            item["value"]
            for item in calendar_series
        ]

        # -------------------------------------------------
        # ACF
        # -------------------------------------------------

        acf_results = calculate_acf(
            series,
            effective_max_lag,
        )

        # -------------------------------------------------
        # PACF
        # -------------------------------------------------

        has_missing = any(
            value is None
            for value in series
        )

        if has_missing:

            pacf_results = []

            pacf_status = (
                "unavailable_due_to_missing_months"
            )

        else:

            complete_acf = [
                item["autocorrelation"]
                for item in acf_results
            ]

            if any(
                value is None
                for value in complete_acf
            ):

                pacf_results = []

                pacf_status = (
                    "unavailable_due_to_constant_series"
                )

            else:

                pacf_results = calculate_pacf(
                    complete_acf
                )

                pacf_status = "calculated"

        # -------------------------------------------------
        # LJUNG-BOX
        # -------------------------------------------------

        ljung_box = ljung_box_test(
            acf_results,
            sample_size,
            request.significance_level,
        )

        # -------------------------------------------------
        # EFFECTIVE SAMPLE SIZE
        # -------------------------------------------------

        lag_one = (
            acf_results[0]["autocorrelation"]
            if acf_results
            else None
        )

        effective_sample = (
            estimate_effective_sample_size(
                sample_size,
                lag_one,
            )
        )

        # -------------------------------------------------
        # WARNINGS
        # -------------------------------------------------

        warnings = []

        if prepared["missing_months"]:

            warnings.append(
                "Missing calendar months were preserved. "
                "Lag estimates may be less stable."
            )

        if (
            ljung_box["significant_dependence"]
            is True
        ):

            warnings.append(
                "The Ljung-Box test detected temporal "
                "dependence. Conventional independent-error "
                "trend inference may be unreliable."
            )

        if pacf_status != "calculated":

            warnings.append(
                "PACF was not calculated because the "
                "monthly series contains missing values "
                "or insufficient variation."
            )

        if effective_sample["estimate"] is not None:

            if (
                effective_sample["estimate"]
                < sample_size * 0.75
            ):

                warnings.append(
                    "The approximate effective sample size "
                    "is substantially smaller than the "
                    "number of valid observations."
                )

        return {
            "status": "success",

            "analysis": {
                "observation_count": sample_size,

                "calendar_month_count": (
                    calendar_length
                ),

                "missing_month_count": len(
                    prepared["missing_months"]
                ),

                "first_month": month_label(
                    prepared["first_month"]
                ),

                "last_month": month_label(
                    prepared["last_month"]
                ),

                "maximum_lag": effective_max_lag,

                "significance_level": (
                    request.significance_level
                ),
            },

            "autocorrelation": {
                "acf": acf_results,

                "pacf": {
                    "status": pacf_status,
                    "values": pacf_results,
                },
            },

            "dependence_test": ljung_box,

            "effective_sample_size": (
                effective_sample
            ),

            "interpretation": {
                "temporal_dependence_detected": (
                    ljung_box[
                        "significant_dependence"
                    ]
                ),

                "trend_inference_warning": (
                    ljung_box[
                        "significant_dependence"
                    ] is True
                ),

                "warnings": warnings,

                "important_limitation": (
                    "This analysis diagnoses temporal dependence. "
                    "It does not adjust Mann-Kendall or OLS "
                    "p-values. Use an appropriate dependence-aware "
                    "method before making scientific claims."
                ),
            },
        }

    except ValueError as exc:

        raise HTTPException(
            status_code=422,
            detail=str(exc),
        )
