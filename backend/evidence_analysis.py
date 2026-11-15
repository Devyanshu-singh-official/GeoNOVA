
import math
from collections import defaultdict
from datetime import datetime, timezone
from statistics import median
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field


router = APIRouter()


# ---------------------------------------------------------
# UNIT NORMALIZATION
# ---------------------------------------------------------

UNIT_RULES = {
    "c": ("temperature", lambda x: x, "°C"),
    "°c": ("temperature", lambda x: x, "°C"),
    "celsius": ("temperature", lambda x: x, "°C"),
    "k": ("temperature", lambda x: x - 273.15, "°C"),
    "kelvin": ("temperature", lambda x: x - 273.15, "°C"),
    "f": ("temperature", lambda x: (x - 32) * 5 / 9, "°C"),
    "°f": ("temperature", lambda x: (x - 32) * 5 / 9, "°C"),
    "fahrenheit": ("temperature", lambda x: (x - 32) * 5 / 9, "°C"),

    "mm/day": ("precipitation", lambda x: x, "mm/day"),
    "mm/d": ("precipitation", lambda x: x, "mm/day"),
    "mm": ("precipitation", lambda x: x, "mm"),
    "mm/hr": ("precipitation_rate", lambda x: x, "mm/hr"),
    "mm/h": ("precipitation_rate", lambda x: x, "mm/hr"),

    "%": ("percentage", lambda x: x, "%"),
    "percent": ("percentage", lambda x: x, "%"),

    "m/s": ("wind_speed", lambda x: x, "m/s"),
    "km/h": ("wind_speed", lambda x: x / 3.6, "m/s"),
    "kph": ("wind_speed", lambda x: x / 3.6, "m/s"),

    "kpa": ("pressure", lambda x: x, "kPa"),
    "hpa": ("pressure", lambda x: x / 10, "kPa"),
    "pa": ("pressure", lambda x: x / 1000, "kPa"),

    "fraction": ("fraction", lambda x: x, "fraction"),
    "unitless": ("fraction", lambda x: x, "fraction"),
}


def normalize_unit(value: float, unit: str):
    if not isinstance(unit, str):
        return None

    key = unit.strip().lower()
    rule = UNIT_RULES.get(key)

    if rule is None:
        return None

    dimension, converter, canonical_unit = rule

    try:
        converted = float(converter(value))
    except (ValueError, TypeError, OverflowError):
        return None

    if not math.isfinite(converted):
        return None

    return {
        "dimension": dimension,
        "value": converted,
        "unit": canonical_unit,
    }


# ---------------------------------------------------------
# INPUT MODELS
# ---------------------------------------------------------

class EvidenceReading(BaseModel):
    source: str = Field(min_length=1, max_length=150)
    parameter: str = Field(min_length=1, max_length=100)
    value: float
    unit: str = Field(min_length=1, max_length=30)
    timestamp: str = Field(min_length=1, max_length=60)

    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)


class EvidenceAnalysisRequest(BaseModel):
    readings: list[EvidenceReading] = Field(min_length=1, max_length=200)

    time_tolerance_minutes: int = Field(
        default=60,
        ge=0,
        le=10080,
    )

    spatial_tolerance_km: float = Field(
        default=10,
        ge=0,
        le=1000,
    )

    agreement_threshold_percent: float = Field(
        default=10,
        gt=0,
        le=100,
    )


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def parse_timestamp(value: str):
    try:
        normalized = value.strip()

        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"

        parsed = datetime.fromisoformat(normalized)

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

        return parsed.astimezone(timezone.utc)

    except (ValueError, TypeError, OverflowError):
        return None


def haversine_km(lat1, lon1, lat2, lon2):
    earth_radius_km = 6371.0

    lat1, lon1, lat2, lon2 = map(
        math.radians,
        (lat1, lon1, lat2, lon2),
    )

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(dlon / 2) ** 2
    )

    # Protect against floating-point rounding outside [0, 1].
    a = min(1.0, max(0.0, a))

    return (
        2
        * earth_radius_km
        * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    )


def has_valid_location(reading):
    return (
        reading.latitude is not None
        and reading.longitude is not None
        and math.isfinite(reading.latitude)
        and math.isfinite(reading.longitude)
        and -90 <= reading.latitude <= 90
        and -180 <= reading.longitude <= 180
    )


def compatible_location(first, second, tolerance_km):
    first_has_location = has_valid_location(first)
    second_has_location = has_valid_location(second)

    # Do not compare a geolocated reading against an
    # observation without a complete location.
    if first_has_location != second_has_location:
        return False

    if not first_has_location:
        return True

    distance = haversine_km(
        first.latitude,
        first.longitude,
        second.latitude,
        second.longitude,
    )

    return distance <= tolerance_km


def compatible_time(first, second, tolerance_minutes):
    difference = abs((first - second).total_seconds())

    return difference <= tolerance_minutes * 60


def reading_duplicate_key(item):
    reading = item["reading"]

    return (
        reading.source.strip().casefold(),
        reading.parameter.strip().casefold(),
        item["normalized"]["value"],
        item["normalized"]["unit"],
        item["timestamp"],
        reading.latitude,
        reading.longitude,
    )


# ---------------------------------------------------------
# READING PREPARATION AND GROUPING
# ---------------------------------------------------------

def get_reading_groups(request: EvidenceAnalysisRequest):
    prepared = []
    rejected = []
    seen = set()
    duplicate_count = 0

    for index, reading in enumerate(request.readings):
        source = reading.source.strip()
        parameter = reading.parameter.strip()

        if not source or not parameter:
            rejected.append({
                "index": index,
                "source": reading.source,
                "reason": "Source and parameter must not be empty.",
            })
            continue

        if not math.isfinite(reading.value):
            rejected.append({
                "index": index,
                "source": source,
                "reason": "Measurement value must be finite.",
            })
            continue

        # A partial coordinate is not sufficient for spatial matching.
        if (
            (reading.latitude is None)
            != (reading.longitude is None)
        ):
            rejected.append({
                "index": index,
                "source": source,
                "reason": "Latitude and longitude must be supplied together.",
            })
            continue

        timestamp = parse_timestamp(reading.timestamp)

        if timestamp is None:
            rejected.append({
                "index": index,
                "source": source,
                "reason": "Invalid ISO 8601 timestamp or date.",
            })
            continue

        normalized = normalize_unit(
            reading.value,
            reading.unit,
        )

        if normalized is None:
            rejected.append({
                "index": index,
                "source": source,
                "reason": f"Unsupported or invalid unit: {reading.unit}",
            })
            continue

        item = {
            "index": index,
            "reading": reading,
            "timestamp": timestamp,
            "normalized": normalized,
        }

        duplicate_key = reading_duplicate_key(item)

        if duplicate_key in seen:
            duplicate_count += 1
            continue

        seen.add(duplicate_key)

        prepared.append(item)

    # Group by normalized parameter and physical dimension.
    by_parameter = defaultdict(list)

    for item in prepared:
        key = (
            item["reading"].parameter.strip().casefold(),
            item["normalized"]["dimension"],
        )

        by_parameter[key].append(item)

    groups = []

    for (parameter, dimension), items in by_parameter.items():
        items.sort(
            key=lambda item: (
                item["timestamp"],
                item["index"],
            )
        )

        clusters = []

        # Only clusters whose anchor remains within the temporal
        # window need to be considered.
        active_clusters = []
        tolerance_seconds = (
            request.time_tolerance_minutes * 60
        )

        for item in items:
            current_time = item["timestamp"]

            active_clusters = [
                cluster
                for cluster in active_clusters
                if (
                    current_time - cluster[0]["timestamp"]
                ).total_seconds() <= tolerance_seconds
            ]

            placed = False

            for cluster in active_clusters:
                anchor = cluster[0]

                if compatible_location(
                    anchor["reading"],
                    item["reading"],
                    request.spatial_tolerance_km,
                ):
                    cluster.append(item)
                    placed = True
                    break

            if not placed:
                new_cluster = [item]
                clusters.append(new_cluster)
                active_clusters.append(new_cluster)

        for cluster in clusters:
            groups.append({
                "parameter": parameter,
                "dimension": dimension,
                "unit": cluster[0]["normalized"]["unit"],
                "items": cluster,
            })

    return groups, rejected, duplicate_count


# ---------------------------------------------------------
# ANALYSIS
# ---------------------------------------------------------

def comparison_floor_for_dimension(dimension):
    return {
        "temperature": 1.0,
        "precipitation": 0.1,
        "precipitation_rate": 0.1,
        "percentage": 1.0,
        "wind_speed": 0.1,
        "pressure": 0.1,
        "fraction": 0.01,
    }.get(dimension, 0.001)


def analyse_group(
    group,
    agreement_threshold_percent,
):
    items = group["items"]

    values = [
        item["normalized"]["value"]
        for item in items
    ]

    center = median(values)

    absolute_deviations = [
        abs(value - center)
        for value in values
    ]

    mad = median(absolute_deviations)

    comparison_floor = comparison_floor_for_dimension(
        group["dimension"]
    )

    comparison_scale = max(
        abs(center),
        comparison_floor,
    )

    threshold = max(
        comparison_scale * agreement_threshold_percent / 100,
        comparison_floor,
    )

    # First aggregate readings within each source. This prevents
    # one provider with many measurements from dominating the
    # source-level agreement calculation.
    source_values = defaultdict(list)

    for item in items:
        source_key = item["reading"].source.strip().casefold()

        source_values[source_key].append(
            item["normalized"]["value"]
        )

    source_medians = {
        source: median(source_readings)
        for source, source_readings in source_values.items()
    }

    source_count = len(source_medians)

    agreeing_sources = sum(
        1
        for source_value in source_medians.values()
        if abs(source_value - center) <= threshold
    )

    agreement_ratio = (
        agreeing_sources / source_count
        if source_count
        else 0.0
    )

    outlier_results = []

    for item in items:
        value = item["normalized"]["value"]
        deviation = abs(value - center)

        potential_outlier = (
            len(values) >= 3
            and mad > 0
            and deviation > 3.5 * 1.4826 * mad
        )

        outlier_results.append({
            "source": item["reading"].source,
            "original_value": item["reading"].value,
            "original_unit": item["reading"].unit,
            "normalized_value": round(value, 6),
            "normalized_unit": group["unit"],
            "deviation_from_median": round(deviation, 6),
            "potential_outlier": potential_outlier,
            "timestamp": item["reading"].timestamp,
        })

    if source_count >= 3 and agreement_ratio >= 0.8:
        confidence = "higher_consistency"
    elif source_count >= 2 and agreement_ratio >= 0.6:
        confidence = "moderate_consistency"
    else:
        confidence = "limited_evidence"

    locations_available = all(
        has_valid_location(item["reading"])
        for item in items
    )

    unique_timestamps = sorted({
        item["timestamp"].isoformat()
        for item in items
    })

    return {
        "parameter": group["parameter"],
        "dimension": group["dimension"],
        "normalized_unit": group["unit"],
        "measurement_count": len(items),
        "independent_source_count": source_count,
        "median": round(center, 6),
        "minimum": round(min(values), 6),
        "maximum": round(max(values), 6),
        "range": round(max(values) - min(values), 6),
        "median_absolute_deviation": round(mad, 6),
        "agreement_threshold": round(threshold, 6),
        "agreement_ratio": round(agreement_ratio, 4),
        "agreement_percentage": round(
            agreement_ratio * 100,
            2,
        ),
        "consistency_assessment": confidence,
        "source_level_agreement": {
            "sources_evaluated": source_count,
            "sources_within_threshold": agreeing_sources,
            "source_medians": {
                source: round(value, 6)
                for source, value in source_medians.items()
            },
            "method": "Median of each source's readings compared with the pooled median.",
        },
        "spatial_comparison": (
            "coordinates_checked"
            if locations_available
            else "coordinates_not_available"
        ),
        "timestamps": unique_timestamps,
        "readings": outlier_results,
        "potential_outlier_count": sum(
            1
            for item in outlier_results
            if item["potential_outlier"]
        ),
        "limitations": [
            "Sources may share upstream datasets and may not be independent.",
            "Source-level agreement does not establish measurement accuracy.",
            "Different instruments and processing methods can introduce bias.",
            "The median is a comparison reference, not verified ground truth.",
            "A potential outlier requires independent investigation.",
            "The consistency assessment is descriptive, not a calibrated probability.",
        ],
    }


# ---------------------------------------------------------
# API
# ---------------------------------------------------------

@router.get("/api/ai/analysis/status")
def analysis_status():
    return {
        "service": "GeoNOVA Evidence Analysis Engine",
        "version": "1.1.0",
        "status": "operational",
        "capabilities": [
            "unit_normalization",
            "temporal_compatibility",
            "spatial_compatibility",
            "cross_source_comparison",
            "source_level_agreement",
            "duplicate_reading_detection",
            "median_and_mad_analysis",
            "potential_outlier_detection",
        ],
        "limits": {
            "maximum_readings_per_request": 200,
            "automatic_unit_guessing": False,
            "source_independence_verification": False,
            "ground_truth_verification": False,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/api/ai/analyze-evidence")
def analyze_evidence(request: EvidenceAnalysisRequest):
    groups, rejected, duplicate_count = get_reading_groups(
        request
    )

    results = [
        analyse_group(
            group,
            request.agreement_threshold_percent,
        )
        for group in groups
    ]

    comparable_groups = [
        result
        for result in results
        if result["independent_source_count"] >= 2
    ]

    return {
        "status": "analysis_completed",
        "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
        "input_summary": {
            "submitted_readings": len(request.readings),
            "analysed_groups": len(results),
            "comparable_groups": len(comparable_groups),
            "rejected_readings": len(rejected),
            "duplicate_readings_removed": duplicate_count,
            "usable_readings": sum(
                result["measurement_count"]
                for result in results
            ),
        },
        "comparison_settings": {
            "time_tolerance_minutes": request.time_tolerance_minutes,
            "spatial_tolerance_km": request.spatial_tolerance_km,
            "agreement_threshold_percent": (
                request.agreement_threshold_percent
            ),
            "agreement_calculation": "source_level",
        },
        "results": results,
        "rejected_readings": rejected,
        "overall_assessment": (
            "Cross-source consistency analysis completed. "
            "Agreement is calculated at source level to reduce "
            "the influence of providers contributing multiple readings. "
            "Results describe agreement among submitted observations, "
            "not verified scientific accuracy."
        ),
        "notices": [
            "Only readings with compatible parameters and dimensions are compared.",
            "Readings are clustered using temporal and spatial compatibility.",
            "Unknown units are excluded rather than guessed.",
            "Exact duplicate readings from the same source are removed.",
            "Source-level agreement reduces measurement-count imbalance but does not prove source independence.",
            "Sources are not guaranteed to be statistically independent.",
            "This endpoint does not predict earthquakes, weather, or disasters.",
        ],
    }
