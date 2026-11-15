
from datetime import datetime, timezone
from math import isfinite
from statistics import mean, median
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field, field_validator


router = APIRouter()


# =========================================================
# CONSTANTS
# =========================================================

ENGINE_NAME = "GeoNOVA Environmental Anomaly Engine"
ENGINE_VERSION = "1.1.0"

MIN_OBSERVATIONS = 5
MAX_OBSERVATIONS = 5000
MIN_BASELINE = 5


# =========================================================
# DATE AND NUMERICAL UTILITIES
# =========================================================

def parse_date(value: str):
    """
    Parse an ISO-8601 date or datetime.

    Timezone-aware datetimes are normalized to UTC before
    extracting their calendar date. Date-only inputs remain
    unchanged.
    """
    try:
        normalized = value.strip()

        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"

        parsed = datetime.fromisoformat(normalized)

        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc)

        return parsed.date()

    except (ValueError, TypeError, OverflowError):
        return None


def is_finite_number(value) -> bool:
    """
    Reject booleans, NaN and positive/negative infinity.
    """
    if isinstance(value, bool):
        return False

    try:
        return isfinite(float(value))
    except (TypeError, ValueError, OverflowError):
        return False


def safe_round(value: float, digits: int = 6):
    """
    Return a finite rounded number or None.
    """
    if not is_finite_number(value):
        return None

    return round(float(value), digits)


def robust_scale(values):
    """
    Robust standard-deviation estimate using MAD.

    Normal consistency factor:
        1.4826 * median absolute deviation
    """
    if len(values) < 3:
        return 0.0

    center = median(values)

    deviations = [
        abs(value - center)
        for value in values
    ]

    mad = median(deviations)

    return 1.4826 * mad


def normalized_source(source):
    if source is None:
        return None

    cleaned = str(source).strip()

    return cleaned or None


# =========================================================
# REQUEST MODELS
# =========================================================

class TimeSeriesPoint(BaseModel):
    date: str
    value: float
    source: Optional[str] = None

    @field_validator("date")
    @classmethod
    def validate_date(cls, value):
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Date must be a non-empty ISO-8601 string.")

        if parse_date(value) is None:
            raise ValueError("Date must be a valid ISO-8601 date or datetime.")

        return value.strip()

    @field_validator("value", mode="before")
    @classmethod
    def validate_value(cls, value):
        if not is_finite_number(value):
            raise ValueError("Observation value must be a finite number.")

        return float(value)

    @field_validator("source")
    @classmethod
    def validate_source(cls, value):
        if value is None:
            return None

        cleaned = value.strip()

        return cleaned or None


class AnomalyRequest(BaseModel):
    parameter: str = Field(min_length=1, max_length=100)
    unit: str = Field(min_length=1, max_length=40)

    observations: list[TimeSeriesPoint] = Field(
        min_length=MIN_OBSERVATIONS,
        max_length=MAX_OBSERVATIONS
    )

    baseline_window: int = Field(
        default=30,
        ge=MIN_BASELINE,
        le=365
    )

    anomaly_threshold: float = Field(
        default=3.5,
        ge=1,
        le=10
    )

    change_window: int = Field(
        default=7,
        ge=3,
        le=90
    )

    @field_validator("parameter", "unit")
    @classmethod
    def validate_nonempty_text(cls, value):
        cleaned = value.strip()

        if not cleaned:
            raise ValueError("This field cannot contain only whitespace.")

        return cleaned

    @field_validator("anomaly_threshold", mode="before")
    @classmethod
    def validate_threshold(cls, value):
        if not is_finite_number(value):
            raise ValueError("Anomaly threshold must be finite.")

        return float(value)


# =========================================================
# DATA PREPARATION
# =========================================================

def prepare_observations(observations):
    """
    Parse, validate, sort and deduplicate observations.

    Duplicate dates are not averaged because combining
    measurements from different sources could conceal
    conflicting environmental readings.

    The first valid observation for a date is retained.
    """
    valid_points = []
    rejected_points = []

    for index, point in enumerate(observations):
        parsed_date = parse_date(point.date)

        if parsed_date is None:
            rejected_points.append({
                "index": index,
                "date": point.date,
                "reason": "Invalid ISO date."
            })
            continue

        if not is_finite_number(point.value):
            rejected_points.append({
                "index": index,
                "date": point.date,
                "reason": "Observation value is not finite."
            })
            continue

        valid_points.append({
            "date": parsed_date,
            "value": float(point.value),
            "source": normalized_source(point.source),
            "original_index": index
        })

    # Python's sort is stable, so original input order is
    # retained when multiple readings have the same date.
    valid_points.sort(key=lambda item: item["date"])

    deduplicated = []
    seen_dates = set()

    for point in valid_points:
        date_key = point["date"].isoformat()

        if date_key in seen_dates:
            rejected_points.append({
                "index": point["original_index"],
                "date": date_key,
                "source": point["source"],
                "reason": (
                    "Duplicate date. Aggregate or compare "
                    "same-date source readings before this analysis."
                )
            })
            continue

        seen_dates.add(date_key)

        deduplicated.append({
            "date": point["date"],
            "value": point["value"],
            "source": point["source"]
        })

    return deduplicated, rejected_points


# =========================================================
# TREND ANALYSIS
# =========================================================

def linear_trend(points):
    """
    Ordinary least-squares regression using actual calendar days.

    The slope is expressed per day and annualized using
    365.2425 days per year.
    """
    if len(points) < 3:
        return {
            "available": False,
            "reason": (
                "At least three valid observations are required."
            )
        }

    first_date = points[0]["date"]

    x_values = [
        (item["date"] - first_date).days
        for item in points
    ]

    y_values = [
        item["value"]
        for item in points
    ]

    x_mean = mean(x_values)
    y_mean = mean(y_values)

    denominator = sum(
        (x - x_mean) ** 2
        for x in x_values
    )

    if denominator <= 0 or not isfinite(denominator):
        return {
            "available": False,
            "reason": (
                "Observation dates do not provide a usable time range."
            )
        }

    numerator = sum(
        (x - x_mean) * (y - y_mean)
        for x, y in zip(x_values, y_values)
    )

    slope = numerator / denominator

    if not isfinite(slope):
        return {
            "available": False,
            "reason": "The calculated trend is not finite."
        }

    return {
        "available": True,
        "slope_per_day": safe_round(slope, 8),
        "slope_per_year": safe_round(slope * 365.2425, 6),
        "direction": (
            "increasing" if slope > 0
            else "decreasing" if slope < 0
            else "stable"
        ),
        "method": "Ordinary least-squares linear regression"
    }


# =========================================================
# ANOMALY DETECTION
# =========================================================

def detect_anomalies(points, window, threshold):
    """
    Detect observations that differ substantially from
    their preceding historical baseline.

    Only previous observations are used for the baseline.
    The current observation is never included in its own
    baseline calculation.
    """
    results = []

    for index, current in enumerate(points):
        baseline_start = max(0, index - window)

        baseline = points[baseline_start:index]

        if len(baseline) < MIN_BASELINE:
            continue

        baseline_values = [
            item["value"]
            for item in baseline
        ]

        center = median(baseline_values)
        scale = robust_scale(baseline_values)

        difference = current["value"] - center

        if scale > 0:
            score = difference / scale
        elif difference == 0:
            score = 0.0
        else:
            # A non-zero difference against a zero-MAD
            # baseline is treated as an extreme deviation.
            score = None

        is_anomaly = (
            abs(score) >= threshold
            if score is not None
            else True
        )

        if not is_anomaly:
            continue

        results.append({
            "date": current["date"].isoformat(),
            "observed_value": current["value"],
            "baseline_median": safe_round(center),
            "difference_from_baseline": safe_round(difference),
            "robust_score": (
                safe_round(score, 4)
                if score is not None
                else None
            ),
            "direction": (
                "above_baseline" if difference > 0
                else "below_baseline"
            ),
            "source": current["source"],
            "method": "Historical rolling median and MAD"
        })

    return results


# =========================================================
# LEVEL-SHIFT DETECTION
# =========================================================

def detect_level_shift(points, window):
    """
    Compare the latest two adjacent windows.

    This is a descriptive shift detector, not a formal
    hypothesis test or a causal attribution method.
    """
    if len(points) < window * 2:
        return {
            "detected": False,
            "reason": (
                f"At least {window * 2} observations are needed "
                "for two complete comparison windows."
            )
        }

    previous = points[-(window * 2):-window]
    recent = points[-window:]

    previous_values = [
        item["value"]
        for item in previous
    ]

    recent_values = [
        item["value"]
        for item in recent
    ]

    previous_mean = mean(previous_values)
    recent_mean = mean(recent_values)

    combined = previous_values + recent_values

    scale = robust_scale(combined)

    difference = recent_mean - previous_mean

    if scale > 0:
        shift_score = abs(difference) / scale
    elif difference == 0:
        shift_score = 0.0
    else:
        shift_score = None

    detected = (
        shift_score >= 2.0
        if shift_score is not None
        else difference != 0
    )

    return {
        "detected": detected,
        "previous_window_mean": safe_round(previous_mean),
        "recent_window_mean": safe_round(recent_mean),
        "difference": safe_round(difference),
        "robust_shift_score": (
            safe_round(shift_score, 4)
            if shift_score is not None
            else None
        ),
        "direction": (
            "upward" if difference > 0
            else "downward" if difference < 0
            else "unchanged"
        ),
        "window_size": window,
        "method": "Adjacent-window mean comparison"
    }


# =========================================================
# API STATUS
# =========================================================

@router.get("/api/science/anomalies/status")
def anomaly_engine_status():
    return {
        "module": ENGINE_NAME,
        "version": ENGINE_VERSION,
        "status": "configured",
        "capabilities": [
            "Rolling historical baseline",
            "Robust anomaly scoring",
            "Environmental level-shift detection",
            "Linear trend estimation",
            "Finite-value and date validation",
            "Duplicate-date reporting",
            "Evidence and method reporting"
        ],
        "performance": {
            "maximum_observations": MAX_OBSERVATIONS,
            "maximum_baseline_window": 365,
            "anomaly_method": "Rolling median and MAD",
            "trend_complexity": "O(n)"
        },
        "important_limitation": (
            "Detected anomalies and shifts are statistical signals, "
            "not proof of a physical cause or a disaster prediction."
        )
    }


# =========================================================
# MAIN ANALYSIS ENDPOINT
# =========================================================

@router.post("/api/science/anomalies/analyze")
def analyze_environmental_series(request: AnomalyRequest):
    points, rejected_points = prepare_observations(
        request.observations
    )

    if len(points) < MIN_OBSERVATIONS:
        return {
            "status": "insufficient_data",
            "parameter": request.parameter,
            "unit": request.unit,
            "valid_count": len(points),
            "rejected_count": len(rejected_points),
            "rejected_observations": rejected_points,
            "message": (
                "At least five unique valid dates are required."
            )
        }

    anomalies = detect_anomalies(
        points,
        request.baseline_window,
        request.anomaly_threshold
    )

    shift = detect_level_shift(
        points,
        request.change_window
    )

    trend = linear_trend(points)

    values = [
        item["value"]
        for item in points
    ]

    return {
        "status": "completed",
        "engine": ENGINE_NAME,
        "parameter": request.parameter,
        "unit": request.unit,

        "observation_count": len(points),
        "rejected_count": len(rejected_points),

        "time_range": {
            "start": points[0]["date"].isoformat(),
            "end": points[-1]["date"].isoformat()
        },

        "summary": {
            "minimum": min(values),
            "maximum": max(values),
            "mean": safe_round(mean(values)),
            "median": safe_round(median(values))
        },

        "anomaly_analysis": {
            "count": len(anomalies),
            "threshold": request.anomaly_threshold,
            "baseline_window": request.baseline_window,
            "events": anomalies
        },

        "change_detection": shift,

        "trend_analysis": trend,

        "rejected_observations": rejected_points,

        "methodology": {
            "anomaly_method": "Rolling median and MAD",
            "change_method": "Adjacent-window comparison",
            "trend_method": "Ordinary least-squares regression",
            "missing_dates": (
                "Missing dates are not interpolated. "
                "The trend uses actual calendar-day differences."
            ),
            "duplicate_dates": (
                "The first valid observation for each calendar date "
                "is retained. Subsequent same-date observations are "
                "reported as rejected."
            ),
            "numerical_validation": (
                "Non-finite observation values are rejected."
            )
        },

        "limitations": [
            "Anomaly detection requires sufficient historical baseline data.",
            "A statistical anomaly does not establish its physical cause.",
            "Level shifts can be influenced by seasonality and sampling changes.",
            "Linear trends do not establish statistical significance.",
            "The input series should represent a consistent location, "
            "parameter, unit and measurement method.",
            "Duplicate dates are not automatically averaged.",
            "The level-shift detector is descriptive and is not a formal "
            "statistical significance test.",
            "This engine does not predict earthquakes, disasters or future events."
        ]
    }
