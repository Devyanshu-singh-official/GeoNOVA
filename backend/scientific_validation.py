
from collections import Counter
from datetime import date, timedelta
from math import isfinite, sqrt
from statistics import median
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator


router = APIRouter(
    prefix="/api/science/validation",
    tags=["Scientific Data Validation"],
)


# =========================================================
# REQUEST MODELS
# =========================================================

class ValidationObservation(BaseModel):
    date: str
    value: Optional[float] = None


class ValidationRequest(BaseModel):
    observations: list[ValidationObservation] = Field(
        ...,
        min_length=1,
        max_length=100000,
    )

    parameter_key: str = Field(
        default="unknown",
        min_length=1,
        max_length=100,
    )

    unit: Optional[str] = None
    expected_unit: Optional[str] = None

    minimum_value: Optional[float] = None
    maximum_value: Optional[float] = None

    expected_frequency: str = "daily"

    outlier_threshold: float = Field(
        default=3.5,
        gt=0,
        le=10,
    )

    @model_validator(mode="after")
    def validate_limits(self):
        if (
            self.minimum_value is not None
            and self.maximum_value is not None
            and self.minimum_value > self.maximum_value
        ):
            raise ValueError(
                "minimum_value cannot exceed maximum_value."
            )

        if self.expected_frequency not in {
            "daily",
            "monthly",
            "none",
        }:
            raise ValueError(
                "expected_frequency must be daily, monthly, or none."
            )

        return self


class ReferenceValidationRequest(ValidationRequest):
    """
    Extends the original quality-validation request
    with a second dataset used as the reference series.
    """

    reference_observations: list[ValidationObservation] = Field(
        ...,
        min_length=1,
        max_length=100000,
    )

    reference_dataset_name: str = Field(
        default="Reference Dataset",
        min_length=1,
        max_length=200,
    )

    reference_source: Optional[str] = Field(
        default=None,
        max_length=500,
    )

    reference_version: Optional[str] = Field(
        default=None,
        max_length=100,
    )

    reference_unit: Optional[str] = Field(
        default=None,
        max_length=100,
    )

    reference_parameter_key: Optional[str] = Field(
        default=None,
        max_length=100,
    )

    @model_validator(mode="after")
    def validate_reference(self):
        if (
            self.reference_parameter_key
            and self.reference_parameter_key.casefold()
            != self.parameter_key.casefold()
        ):
            raise ValueError(
                "The reference parameter key must match "
                "the submitted parameter key."
            )

        return self


# =========================================================
# DATE UTILITIES
# =========================================================

def parse_observation_date(value: str) -> date:
    """
    Supports ISO dates and NASA POWER YYYYMMDD dates.
    """

    normalized = value.strip()

    if len(normalized) == 8 and normalized.isdigit():
        normalized = (
            f"{normalized[:4]}-"
            f"{normalized[4:6]}-"
            f"{normalized[6:8]}"
        )

    try:
        return date.fromisoformat(normalized)

    except ValueError:
        raise ValueError(
            f"Invalid observation date: {value}"
        )


def month_index(value: date) -> int:
    return value.year * 12 + value.month - 1


def expected_missing_dates(
    dates: list[date],
    frequency: str,
) -> list[str]:

    if len(dates) < 2 or frequency == "none":
        return []

    missing = []

    if frequency == "daily":
        existing = set(dates)

        current = min(dates)
        last = max(dates)

        while current <= last:
            if current not in existing:
                missing.append(current.isoformat())

            current += timedelta(days=1)

    elif frequency == "monthly":
        existing_months = {
            month_index(item)
            for item in dates
        }

        first = min(existing_months)
        last = max(existing_months)

        for index in range(first, last + 1):
            if index not in existing_months:
                year = index // 12
                month = index % 12 + 1

                missing.append(
                    f"{year:04d}-{month:02d}"
                )

    return missing


# =========================================================
# OUTLIER DETECTION
# =========================================================

def detect_mad_outliers(
    values: list[tuple[int, float]],
    threshold: float,
) -> list[dict]:

    if len(values) < 5:
        return []

    numeric_values = [
        value for _, value in values
    ]

    center = median(numeric_values)

    deviations = [
        abs(value - center)
        for value in numeric_values
    ]

    mad = median(deviations)

    if mad == 0:
        return []

    results = []

    for index, value in values:
        modified_z = (
            0.67448975 * (value - center) / mad
        )

        if abs(modified_z) > threshold:
            results.append({
                "observation_index": index,
                "value": value,
                "modified_z_score": round(
                    modified_z,
                    5,
                ),
                "reason": (
                    "Value is unusually distant from "
                    "the median under the MAD method."
                ),
            })

    return results


# =========================================================
# QUALITY SCORING
# =========================================================

def calculate_quality_score(
    total: int,
    missing_values: int,
    invalid_dates: int,
    duplicate_dates: int,
    out_of_range: int,
    outliers: int,
    unit_mismatch: bool,
) -> dict:

    if total <= 0:
        return {
            "score": 0,
            "label": "unavailable",
            "method": "Rule-based quality score",
        }

    penalties = {
        "missing_values": min(
            35,
            35 * missing_values / total,
        ),
        "invalid_dates": min(
            30,
            30 * invalid_dates / total,
        ),
        "duplicate_dates": min(
            20,
            20 * duplicate_dates / total,
        ),
        "out_of_range": min(
            35,
            35 * out_of_range / total,
        ),
        "potential_outliers": min(
            10,
            10 * outliers / total,
        ),
        "unit_mismatch": 20 if unit_mismatch else 0,
    }

    score = max(
        0,
        round(100 - sum(penalties.values())),
    )

    if score >= 90:
        label = "high"
    elif score >= 70:
        label = "moderate"
    elif score >= 40:
        label = "low"
    else:
        label = "very_low"

    return {
        "score": score,
        "label": label,
        "penalties": {
            key: round(value, 3)
            for key, value in penalties.items()
        },
        "method": (
            "Rule-based heuristic; not a statistical "
            "probability or certification of accuracy."
        ),
    }


# =========================================================
# DATASET PREPARATION
# =========================================================

def prepare_dataset(
    observations: list[ValidationObservation],
) -> dict:

    valid_records = []
    invalid_dates = []
    missing_values = []
    non_finite_values = []

    date_counts = Counter()

    for index, observation in enumerate(observations):

        try:
            parsed_date = parse_observation_date(
                observation.date
            )

        except ValueError:
            invalid_dates.append({
                "observation_index": index,
                "date": observation.date,
                "reason": "Invalid or unsupported date.",
            })
            continue

        date_counts[parsed_date] += 1

        value = observation.value

        if value is None:
            missing_values.append({
                "observation_index": index,
                "date": parsed_date.isoformat(),
            })

            valid_records.append({
                "index": index,
                "date": parsed_date,
                "value": None,
            })

            continue

        if not isfinite(value):
            non_finite_values.append({
                "observation_index": index,
                "date": parsed_date.isoformat(),
                "value": str(value),
            })

            valid_records.append({
                "index": index,
                "date": parsed_date,
                "value": None,
            })

            continue

        valid_records.append({
            "index": index,
            "date": parsed_date,
            "value": float(value),
        })

    duplicate_dates = [
        {
            "date": timestamp.isoformat(),
            "count": count,
        }
        for timestamp, count in date_counts.items()
        if count > 1
    ]

    return {
        "records": valid_records,
        "date_counts": date_counts,
        "invalid_dates": invalid_dates,
        "missing_values": missing_values,
        "non_finite_values": non_finite_values,
        "duplicate_dates": duplicate_dates,
        "unique_dates": sorted(date_counts.keys()),
    }


# =========================================================
# ORIGINAL QUALITY VALIDATION ENGINE
# =========================================================

def validate_observations(
    request: ValidationRequest,
) -> dict:

    prepared = prepare_dataset(
        request.observations
    )

    total = len(request.observations)

    valid_dates = prepared["unique_dates"]
    invalid_dates = prepared["invalid_dates"]
    missing_values = prepared["missing_values"]
    non_finite_values = prepared["non_finite_values"]
    duplicate_dates = prepared["duplicate_dates"]

    numeric_values = []

    out_of_range = []

    for record in prepared["records"]:
        value = record["value"]

        if value is None:
            continue

        numeric_values.append((
            record["index"],
            value,
        ))

        if (
            request.minimum_value is not None
            and value < request.minimum_value
        ):
            out_of_range.append({
                "observation_index": record["index"],
                "date": record["date"].isoformat(),
                "value": value,
                "reason": "Below configured minimum.",
                "minimum": request.minimum_value,
            })

        elif (
            request.maximum_value is not None
            and value > request.maximum_value
        ):
            out_of_range.append({
                "observation_index": record["index"],
                "date": record["date"].isoformat(),
                "value": value,
                "reason": "Above configured maximum.",
                "maximum": request.maximum_value,
            })

    missing_intervals = expected_missing_dates(
        valid_dates,
        request.expected_frequency,
    )

    outliers = detect_mad_outliers(
        numeric_values,
        request.outlier_threshold,
    )

    actual_unit = (
        request.unit.strip()
        if request.unit
        else None
    )

    expected_unit = (
        request.expected_unit.strip()
        if request.expected_unit
        else None
    )

    unit_mismatch = (
        actual_unit is not None
        and expected_unit is not None
        and actual_unit.casefold()
        != expected_unit.casefold()
    )

    values = [
        value for _, value in numeric_values
    ]

    descriptive = None

    if values:
        descriptive = {
            "valid_value_count": len(values),
            "minimum": min(values),
            "maximum": max(values),
            "mean": round(
                sum(values) / len(values),
                8,
            ),
            "median": round(
                median(values),
                8,
            ),
        }

    quality = calculate_quality_score(
        total=total,
        missing_values=len(missing_values),
        invalid_dates=len(invalid_dates),
        duplicate_dates=sum(
            item["count"] - 1
            for item in duplicate_dates
        ),
        out_of_range=len(out_of_range),
        outliers=len(outliers),
        unit_mismatch=unit_mismatch,
    )

    warnings = []

    if missing_values:
        warnings.append(
            "Some observations have missing values."
        )

    if invalid_dates:
        warnings.append(
            "Some observations contain invalid dates."
        )

    if duplicate_dates:
        warnings.append(
            "Duplicate dates were detected. Resolve duplicates "
            "before interpreting time-series results."
        )

    if missing_intervals:
        warnings.append(
            "Calendar gaps were detected in the expected "
            "observation frequency."
        )

    if out_of_range:
        warnings.append(
            "Some values exceed configured scientific limits."
        )

    if outliers:
        warnings.append(
            "Potential MAD outliers require review."
        )

    if non_finite_values:
        warnings.append(
            "Non-finite numeric values were detected."
        )

    if unit_mismatch:
        warnings.append(
            "The supplied unit does not match the expected unit."
        )

    if (
        request.minimum_value is None
        and request.maximum_value is None
    ):
        warnings.append(
            "No physical value limits were supplied."
        )

    if request.expected_frequency == "none":
        warnings.append(
            "Missing calendar intervals were not evaluated."
        )

    blocking_issues = (
        bool(invalid_dates)
        or bool(duplicate_dates)
        or bool(non_finite_values)
        or bool(out_of_range)
        or unit_mismatch
    )

    if blocking_issues:
        status = "review_required"
    elif warnings:
        status = "passed_with_warnings"
    else:
        status = "passed"

    return {
        "status": "success",
        "validation_status": status,
        "parameter_key": request.parameter_key,

        "units": {
            "provided": actual_unit,
            "expected": expected_unit,
            "match": (
                not unit_mismatch
                if actual_unit and expected_unit
                else None
            ),
        },

        "summary": {
            "total_observations": total,
            "valid_dates": len(valid_dates),
            "valid_numeric_values": len(values),
            "missing_values": len(missing_values),
            "invalid_dates": len(invalid_dates),
            "duplicate_dates": len(duplicate_dates),
            "missing_intervals": len(missing_intervals),
            "non_finite_values": len(non_finite_values),
            "out_of_range_values": len(out_of_range),
            "potential_outliers": len(outliers),
        },

        "quality": quality,

        "descriptive_statistics": descriptive,

        "checks": {
            "missing_values": missing_values,
            "invalid_dates": invalid_dates,
            "duplicate_dates": duplicate_dates,
            "missing_intervals": missing_intervals,
            "non_finite_values": non_finite_values,
            "out_of_range_values": out_of_range,
            "potential_outliers": outliers,
        },

        "warnings": warnings,

        "data_modified": False,

        "scientific_note": (
            "This engine flags potential data-quality issues. "
            "It does not modify source observations. Outlier "
            "flags are not proof of measurement errors. "
            "Configured limits must be scientifically "
            "appropriate for the selected variable and unit."
        ),
    }


# =========================================================
# STATISTICAL COMPARISON UTILITIES
# =========================================================

def calculate_pearson_correlation(
    x_values: list[float],
    y_values: list[float],
) -> Optional[float]:

    count = len(x_values)

    if count < 2:
        return None

    mean_x = sum(x_values) / count
    mean_y = sum(y_values) / count

    numerator = sum(
        (x - mean_x) * (y - mean_y)
        for x, y in zip(x_values, y_values)
    )

    denominator_x = sum(
        (x - mean_x) ** 2
        for x in x_values
    )

    denominator_y = sum(
        (y - mean_y) ** 2
        for y in y_values
    )

    denominator = sqrt(
        denominator_x * denominator_y
    )

    if denominator == 0:
        return None

    return round(
        numerator / denominator,
        8,
    )


def calculate_comparison_metrics(
    observed: list[float],
    reference: list[float],
) -> dict:

    if len(observed) != len(reference):
        raise ValueError(
            "Comparison series must have equal lengths."
        )

    count = len(observed)

    if count == 0:
        return {
            "sample_count": 0,
            "bias": None,
            "mean_absolute_error": None,
            "root_mean_square_error": None,
            "correlation": None,
            "mean_absolute_percentage_error": None,
            "normalized_rmse_percent": None,
        }

    errors = [
        observed_value - reference_value
        for observed_value, reference_value
        in zip(observed, reference)
    ]

    absolute_errors = [
        abs(error)
        for error in errors
    ]

    squared_errors = [
        error ** 2
        for error in errors
    ]

    bias = sum(errors) / count

    mae = sum(absolute_errors) / count

    rmse = sqrt(
        sum(squared_errors) / count
    )

    correlation = calculate_pearson_correlation(
        observed,
        reference,
    )

    percentage_errors = [
        abs(observed_value - reference_value)
        / abs(reference_value)
        * 100
        for observed_value, reference_value
        in zip(observed, reference)
        if reference_value != 0
    ]

    mape = (
        sum(percentage_errors) / len(percentage_errors)
        if percentage_errors
        else None
    )

    reference_range = (
        max(reference) - min(reference)
    )

    normalized_rmse = (
        rmse / reference_range * 100
        if reference_range > 0
        else None
    )

    return {
        "sample_count": count,

        "bias": round(bias, 8),

        "mean_absolute_error": round(
            mae,
            8,
        ),

        "root_mean_square_error": round(
            rmse,
            8,
        ),

        "correlation": correlation,

        "mean_absolute_percentage_error": (
            round(mape, 8)
            if mape is not None
            else None
        ),

        "mape_sample_count": len(
            percentage_errors
        ),

        "normalized_rmse_percent": (
            round(normalized_rmse, 8)
            if normalized_rmse is not None
            else None
        ),

        "reference_range": round(
            reference_range,
            8,
        ),

        "error_direction": (
            "positive_bias"
            if bias > 0
            else "negative_bias"
            if bias < 0
            else "zero_bias"
        ),
    }


# =========================================================
# REFERENCE DATASET COMPARISON
# =========================================================

def compare_with_reference(
    request: ReferenceValidationRequest,
) -> dict:

    primary = prepare_dataset(
        request.observations
    )

    reference = prepare_dataset(
        request.reference_observations
    )

    primary_unit = (
        request.unit.strip()
        if request.unit
        else None
    )

    reference_unit = (
        request.reference_unit.strip()
        if request.reference_unit
        else None
    )

    if primary_unit and reference_unit:
        units_match = (
            primary_unit.casefold()
            == reference_unit.casefold()
        )
    else:
        units_match = None

    primary_parameter = request.parameter_key

    reference_parameter = (
        request.reference_parameter_key
        or request.parameter_key
    )

    parameter_match = (
        primary_parameter.casefold()
        == reference_parameter.casefold()
    )

    # A unit mismatch prevents numerical comparison.
    # We do not attempt implicit unit conversion.
    if units_match is False:
        return {
            "status": "success",
            "validation_status": "comparison_blocked",

            "comparison": {
                "performed": False,
                "reason": (
                    "Primary and reference units do not match. "
                    "Convert both datasets to a common unit "
                    "before comparison."
                ),
            },

            "dataset_metadata": {
                "primary": {
                    "parameter_key": primary_parameter,
                    "unit": primary_unit,
                    "observation_count": len(
                        request.observations
                    ),
                },

                "reference": {
                    "name": request.reference_dataset_name,
                    "source": request.reference_source,
                    "version": request.reference_version,
                    "parameter_key": reference_parameter,
                    "unit": reference_unit,
                    "observation_count": len(
                        request.reference_observations
                    ),
                },
            },

            "scientific_note": (
                "No numerical comparison was performed because "
                "the units differ. No automatic conversion "
                "or assumption of equivalence was made."
            ),
        }

    primary_counts = primary["date_counts"]
    reference_counts = reference["date_counts"]

    primary_records = primary["records"]
    reference_records = reference["records"]

    # Only dates with exactly one record in each dataset
    # are eligible for direct comparison.
    primary_by_date = {
        record["date"]: record
        for record in primary_records
        if (
            record["value"] is not None
            and primary_counts[record["date"]] == 1
        )
    }

    reference_by_date = {
        record["date"]: record
        for record in reference_records
        if (
            record["value"] is not None
            and reference_counts[record["date"]] == 1
        )
    }

    primary_unique_dates = set(primary_counts.keys())
    reference_unique_dates = set(reference_counts.keys())

    common_dates = sorted(
        primary_unique_dates & reference_unique_dates
    )

    duplicate_common_dates = [
        item.isoformat()
        for item in common_dates
        if (
            primary_counts[item] > 1
            or reference_counts[item] > 1
        )
    ]

    paired_dates = sorted(
        set(primary_by_date.keys())
        & set(reference_by_date.keys())
    )

    primary_values = [
        primary_by_date[item]["value"]
        for item in paired_dates
    ]

    reference_values = [
        reference_by_date[item]["value"]
        for item in paired_dates
    ]

    metrics = calculate_comparison_metrics(
        primary_values,
        reference_values,
    )

    unmatched_primary = sorted(
        primary_unique_dates - reference_unique_dates
    )

    unmatched_reference = sorted(
        reference_unique_dates - primary_unique_dates
    )

    primary_valid_unique = sum(
        1
        for item in primary_unique_dates
        if (
            primary_counts[item] == 1
            and item in primary_by_date
        )
    )

    reference_valid_unique = sum(
        1
        for item in reference_unique_dates
        if (
            reference_counts[item] == 1
            and item in reference_by_date
        )
    )

    primary_coverage = (
        len(paired_dates) / primary_valid_unique * 100
        if primary_valid_unique
        else 0
    )

    reference_coverage = (
        len(paired_dates) / reference_valid_unique * 100
        if reference_valid_unique
        else 0
    )

    warnings = []

    if not primary_unit or not reference_unit:
        warnings.append(
            "One or both dataset units are unspecified. "
            "Unit equivalence could not be independently confirmed."
        )

    if duplicate_common_dates:
        warnings.append(
            "Dates with duplicate records in either dataset "
            "were excluded from paired comparison."
        )

    if unmatched_primary:
        warnings.append(
            "Some primary dataset dates have no matching "
            "reference date."
        )

    if unmatched_reference:
        warnings.append(
            "Some reference dataset dates have no matching "
            "primary date."
        )

    if len(paired_dates) < 2:
        warnings.append(
            "Fewer than two paired observations are available. "
            "Correlation cannot be meaningfully estimated."
        )

    if len(paired_dates) == 0:
        warnings.append(
            "No eligible date-matched observations were found."
        )

    if metrics["correlation"] is None and len(paired_dates) >= 2:
        warnings.append(
            "Correlation is undefined because at least one "
            "comparison series has zero variance."
        )

    if metrics["normalized_rmse_percent"] is None:
        warnings.append(
            "Normalized RMSE is unavailable because the "
            "reference dataset has zero range or no paired values."
        )

    if metrics["mean_absolute_percentage_error"] is None:
        warnings.append(
            "MAPE is unavailable because all paired reference "
            "values are zero or no pairs were available."
        )

    comparison_status = (
        "insufficient_data"
        if len(paired_dates) == 0
        else "completed_with_warnings"
        if warnings
        else "completed"
    )

    return {
        "status": "success",

        "validation_status": comparison_status,

        "comparison": {
            "performed": True,

            "method": (
                "Exact calendar-date matching; duplicate dates "
                "are excluded rather than averaged."
            ),

            "matching_rule": "Exact date equality",

            "parameter_match": parameter_match,

            "unit_match": units_match,

            "paired_observation_count": len(
                paired_dates
            ),

            "metrics": metrics,

            "date_range": {
                "first_paired_date": (
                    paired_dates[0].isoformat()
                    if paired_dates
                    else None
                ),

                "last_paired_date": (
                    paired_dates[-1].isoformat()
                    if paired_dates
                    else None
                ),
            },

            "coverage": {
                "primary_dataset_percent": round(
                    primary_coverage,
                    3,
                ),

                "reference_dataset_percent": round(
                    reference_coverage,
                    3,
                ),

                "primary_valid_unique_dates": (
                    primary_valid_unique
                ),

                "reference_valid_unique_dates": (
                    reference_valid_unique
                ),
            },
        },

        "dataset_metadata": {
            "primary": {
                "parameter_key": primary_parameter,
                "unit": primary_unit,
                "observation_count": len(
                    request.observations
                ),
                "valid_unique_dates": (
                    primary_valid_unique
                ),
            },

            "reference": {
                "name": request.reference_dataset_name,
                "source": request.reference_source,
                "version": request.reference_version,
                "parameter_key": reference_parameter,
                "unit": reference_unit,
                "observation_count": len(
                    request.reference_observations
                ),
                "valid_unique_dates": (
                    reference_valid_unique
                ),
            },
        },

        "date_alignment": {
            "common_unique_dates": len(common_dates),

            "paired_dates": len(paired_dates),

            "unmatched_primary_dates": len(
                unmatched_primary
            ),

            "unmatched_reference_dates": len(
                unmatched_reference
            ),

            "duplicate_common_dates_excluded": len(
                duplicate_common_dates
            ),

            "unmatched_primary_date_samples": [
                item.isoformat()
                for item in unmatched_primary[:500]
            ],

            "unmatched_reference_date_samples": [
                item.isoformat()
                for item in unmatched_reference[:500]
            ],

            "duplicate_common_date_samples": (
                duplicate_common_dates[:500]
            ),

            "sample_limit": 500,
        },

        "warnings": warnings,

        "scientific_interpretation": {
            "bias": (
                "Mean difference between primary and reference "
                "values. Positive values indicate the primary "
                "series is higher on average."
            ),

            "mean_absolute_error": (
                "Average absolute difference between paired values."
            ),

            "root_mean_square_error": (
                "Square root of the average squared difference. "
                "Larger errors receive greater weight."
            ),

            "correlation": (
                "Measures linear association, not numerical "
                "agreement or causal relationship."
            ),

            "mean_absolute_percentage_error": (
                "Percentage error calculated only where "
                "reference values are non-zero."
            ),

            "normalized_rmse_percent": (
                "RMSE divided by the range of the paired "
                "reference values, expressed as a percentage."
            ),
        },

        "scientific_limitations": [
            "Reference data are treated as a comparison baseline, not automatically as ground truth.",
            "Exact-date matching does not account for temporal offsets or different aggregation periods.",
            "No automatic unit conversion is performed.",
            "No spatial matching or geographic representativeness assessment is performed.",
            "Correlation does not establish agreement.",
            "Comparison metrics do not independently establish which dataset is scientifically correct.",
            "No statistical significance test or uncertainty propagation is performed.",
            "The reference source and version are supplied metadata and are not independently authenticated."
        ],

        "data_modified": False,
    }


# =========================================================
# API: STATUS
# =========================================================

@router.get("/status")
def validation_status():
    return {
        "service": "GeoNOVA Scientific Data Validation",

        "status": "online",

        "version": "2.0.0",

        "checks": [
            "Date validation",
            "Duplicate timestamp detection",
            "Missing value detection",
            "Missing interval detection",
            "Non-finite value detection",
            "Configurable scientific value limits",
            "MAD outlier screening",
            "Unit consistency",
            "Descriptive statistics",
            "Rule-based quality scoring",
            "Reference dataset comparison",
            "Exact-date alignment",
            "Bias calculation",
            "Mean absolute error",
            "Root mean square error",
            "Pearson correlation",
            "Comparison coverage",
            "Unmatched date reporting",
        ],

        "endpoints": {
            "status": "/api/science/validation/status",
            "quality_check": "/api/science/validation/check",
            "reference_comparison": "/api/science/validation/compare",
        },

        "automatic_data_modification": False,

        "automatic_unit_conversion": False,

        "independent_reference_authentication": False,
    }


# =========================================================
# API: ORIGINAL QUALITY CHECK
# =========================================================

@router.post("/check")
def run_validation(
    request: ValidationRequest,
):
    try:
        return validate_observations(request)

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Validation engine error: {str(exc)}",
        )


# =========================================================
# API: REFERENCE DATASET COMPARISON
# =========================================================

@router.post("/compare")
def run_reference_comparison(
    request: ReferenceValidationRequest,
):
    try:
        return compare_with_reference(request)

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Reference comparison error: "
                f"{str(exc)}"
            ),
        )
