
import math
from collections import defaultdict
from datetime import datetime, timezone
from statistics import median
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field


router = APIRouter()


# ---------------------------------------------------------
# INPUT MODELS
# ---------------------------------------------------------

class SourceReading(BaseModel):
    source: str = Field(min_length=1, max_length=150)
    parameter: str = Field(min_length=1, max_length=100)
    value: float
    unit: str = Field(min_length=1, max_length=40)
    timestamp: str = Field(min_length=1, max_length=60)

    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    lon: Optional[float] = Field(default=None, ge=-180, le=180)


class ConfidenceRequest(BaseModel):
    readings: list[SourceReading] = Field(
        min_length=1,
        max_length=300,
    )

    time_tolerance_minutes: int = Field(
        default=60,
        ge=0,
        le=10080,
    )

    spatial_tolerance_km: float = Field(
        default=10,
        ge=0,
        le=20000,
    )


# ---------------------------------------------------------
# UNIT NORMALIZATION
# ---------------------------------------------------------

# Each unit family has its own canonical unit.
# Accumulated precipitation and precipitation rate
# intentionally remain separate dimensions.

UNIT_RULES = {
    "c": ("temperature", 1, 0),
    "°c": ("temperature", 1, 0),
    "celsius": ("temperature", 1, 0),
    "k": ("temperature", 1, -273.15),
    "kelvin": ("temperature", 1, -273.15),
    "f": ("temperature", 5 / 9, -32 * 5 / 9),
    "°f": ("temperature", 5 / 9, -32 * 5 / 9),
    "fahrenheit": ("temperature", 5 / 9, -32 * 5 / 9),

    "%": ("humidity", 1, 0),
    "percent": ("humidity", 1, 0),

    "m/s": ("speed", 1, 0),
    "km/h": ("speed", 1 / 3.6, 0),
    "kph": ("speed", 1 / 3.6, 0),

    "pa": ("pressure", 0.001, 0),
    "hpa": ("pressure", 0.1, 0),
    "kpa": ("pressure", 1, 0),

    "mm": ("precipitation_depth", 1, 0),
    "cm": ("precipitation_depth", 10, 0),
    "m": ("precipitation_depth", 1000, 0),

    "mm/day": ("precipitation_rate", 1, 0),
    "mm/d": ("precipitation_rate", 1, 0),
    "mm/hr": ("precipitation_rate", 24, 0),
    "mm/h": ("precipitation_rate", 24, 0),

    "fraction": ("fraction", 1, 0),
    "1": ("fraction", 1, 0),
}


CANONICAL_UNITS = {
    "temperature": "°C",
    "humidity": "%",
    "speed": "m/s",
    "pressure": "kPa",
    "precipitation_depth": "mm",
    "precipitation_rate": "mm/day",
    "fraction": "fraction",
}


# Used only as numerical comparison tolerances when MAD is zero.
# These are not claims about instrument accuracy.
NUMERICAL_FLOORS = {
    "temperature": 0.01,
    "humidity": 0.01,
    "speed": 0.001,
    "pressure": 0.001,
    "precipitation_depth": 0.001,
    "precipitation_rate": 0.001,
    "fraction": 0.000001,
}


def normalize_unit(unit: str):
    if not isinstance(unit, str):
        return None

    key = unit.strip().lower().replace(" ", "")

    return UNIT_RULES.get(key)


def convert_value(value: float, rule):
    dimension, multiplier, offset = rule

    converted = value * multiplier + offset

    if not math.isfinite(converted):
        return None

    return dimension, converted


# ---------------------------------------------------------
# TIMESTAMP AND GEOGRAPHIC HELPERS
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


def has_valid_coordinates(reading):
    lat = reading["lat"]
    lon = reading["lon"]

    return (
        lat is not None
        and lon is not None
        and math.isfinite(lat)
        and math.isfinite(lon)
        and -90 <= lat <= 90
        and -180 <= lon <= 180
    )


def haversine_km(lat1, lon1, lat2, lon2):
    earth_radius = 6371.0088

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

    # Guard against floating-point rounding.
    a = min(1.0, max(0.0, a))

    return (
        2
        * earth_radius
        * math.atan2(
            math.sqrt(a),
            math.sqrt(1.0 - a),
        )
    )


# ---------------------------------------------------------
# READING PREPARATION
# ---------------------------------------------------------

def prepare_readings(readings):
    valid = []
    rejected = []
    seen = set()
    duplicate_count = 0

    for index, reading in enumerate(readings):
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

        # Coordinates must be supplied as a complete pair.
        if (
            (reading.lat is None)
            != (reading.lon is None)
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
                "reason": "Invalid ISO-8601 timestamp.",
            })
            continue

        rule = normalize_unit(reading.unit)

        if rule is None:
            rejected.append({
                "index": index,
                "source": source,
                "reason": f"Unsupported unit: {reading.unit}",
            })
            continue

        converted = convert_value(reading.value, rule)

        if converted is None:
            rejected.append({
                "index": index,
                "source": source,
                "reason": "Unit conversion produced a non-finite value.",
            })
            continue

        dimension, normalized_value = converted

        item = {
            "source": source,
            "source_key": source.casefold(),
            "parameter": parameter.casefold(),
            "original_value": reading.value,
            "original_unit": reading.unit,
            "normalized_value": normalized_value,
            "dimension": dimension,
            "timestamp": timestamp,
            "lat": reading.lat,
            "lon": reading.lon,
        }

        duplicate_key = (
            item["source_key"],
            item["parameter"],
            item["dimension"],
            item["normalized_value"],
            item["timestamp"],
            item["lat"],
            item["lon"],
        )

        if duplicate_key in seen:
            duplicate_count += 1
            continue

        seen.add(duplicate_key)
        valid.append(item)

    return valid, rejected, duplicate_count


# ---------------------------------------------------------
# TEMPORAL AND SPATIAL COMPATIBILITY
# ---------------------------------------------------------

def compatible_with_cluster(
    reading,
    cluster,
    time_tolerance_minutes,
    spatial_tolerance_km,
):
    anchor = cluster[0]

    time_difference = abs(
        (
            reading["timestamp"]
            - anchor["timestamp"]
        ).total_seconds()
    ) / 60

    if time_difference > time_tolerance_minutes:
        return False

    reading_has_coordinates = has_valid_coordinates(reading)
    anchor_has_coordinates = has_valid_coordinates(anchor)

    # Never silently compare a geolocated reading with one
    # whose coordinates are missing.
    if reading_has_coordinates != anchor_has_coordinates:
        return False

    if reading_has_coordinates:
        distance = haversine_km(
            reading["lat"],
            reading["lon"],
            anchor["lat"],
            anchor["lon"],
        )

        if distance > spatial_tolerance_km:
            return False

    return True


# ---------------------------------------------------------
# CONFIDENCE AND OUTLIER ANALYSIS
# ---------------------------------------------------------

def calculate_outlier_threshold(dimension, mad):
    numerical_floor = NUMERICAL_FLOORS.get(
        dimension,
        0.000001,
    )

    if mad > 0:
        return max(
            3.5 * 1.4826 * mad,
            numerical_floor,
        )

    return numerical_floor


def analyze_cluster(parameter, dimension, cluster):
    values = [
        item["normalized_value"]
        for item in cluster
    ]

    center = median(values)

    deviations = [
        abs(value - center)
        for value in values
    ]

    mad = median(deviations)

    outlier_threshold = calculate_outlier_threshold(
        dimension,
        mad,
    )

    outlier_indices = [
        index
        for index, deviation in enumerate(deviations)
        if deviation > outlier_threshold
    ]

    outlier_set = set(outlier_indices)

    # Aggregate readings within each source before calculating
    # agreement. This prevents a source with many readings from
    # automatically dominating the agreement score.
    source_readings = defaultdict(list)

    for item in cluster:
        source_readings[item["source_key"]].append(
            item["normalized_value"]
        )

    source_medians = {
        source: median(source_values)
        for source, source_values in source_readings.items()
    }

    source_labels = {}

    for item in cluster:
        source_labels.setdefault(
            item["source_key"],
            item["source"],
        )

    source_count = len(source_medians)

    agreeing_sources = sum(
        1
        for source_value in source_medians.values()
        if abs(source_value - center) <= outlier_threshold
    )

    agreement_ratio = (
        agreeing_sources / source_count
        if source_count
        else 0.0
    )

    if source_count >= 3 and agreement_ratio >= 0.8:
        confidence = "high"
    elif source_count >= 2 and agreement_ratio >= 0.6:
        confidence = "moderate"
    else:
        confidence = "limited"

    source_results = []

    for index, item in enumerate(cluster):
        source_results.append({
            "source": item["source"],
            "original_value": item["original_value"],
            "original_unit": item["original_unit"],
            "normalized_value": round(
                item["normalized_value"],
                6,
            ),
            "timestamp": item["timestamp"].isoformat(),
            "is_outlier": index in outlier_set,
        })

    unique_source_labels = sorted(
        source_labels.values(),
        key=str.casefold,
    )

    canonical_unit = CANONICAL_UNITS.get(
        dimension,
        dimension,
    )

    if confidence == "high":
        interpretation = (
            "Strong agreement among submitted source labels. "
            "This does not establish scientific accuracy."
        )
    elif confidence == "moderate":
        interpretation = (
            "Partial agreement; additional independent evidence may help."
        )
    else:
        interpretation = (
            "Insufficient agreement or source diversity "
            "for a strong conclusion."
        )

    return {
        "parameter": parameter,
        "unit_dimension": dimension,
        "canonical_unit": canonical_unit,
        "reading_count": len(cluster),
        "independent_source_labels": source_count,
        "sources": unique_source_labels,
        "median_value": round(center, 6),
        "minimum_value": round(min(values), 6),
        "maximum_value": round(max(values), 6),
        "median_absolute_deviation": round(mad, 6),
        "agreement_ratio": round(agreement_ratio, 4),
        "agreement_percentage": round(
            agreement_ratio * 100,
            2,
        ),
        "confidence": confidence,
        "outlier_count": len(outlier_indices),
        "source_comparisons": source_results,
        "source_level_agreement": {
            "sources_evaluated": source_count,
            "sources_within_threshold": agreeing_sources,
            "source_medians": {
                source_labels[source]: round(value, 6)
                for source, value in source_medians.items()
            },
            "comparison_threshold": round(
                outlier_threshold,
                6,
            ),
            "method": "Source median compared against pooled median.",
        },
        "interpretation": interpretation,
    }


# ---------------------------------------------------------
# CLUSTERING
# ---------------------------------------------------------

def make_clusters(
    readings,
    time_tolerance_minutes,
    spatial_tolerance_km,
):
    grouped = defaultdict(list)

    for reading in readings:
        key = (
            reading["parameter"],
            reading["dimension"],
        )

        grouped[key].append(reading)

    output = []

    tolerance_seconds = time_tolerance_minutes * 60

    for (parameter, dimension), records in grouped.items():
        records.sort(
            key=lambda item: item["timestamp"]
        )

        clusters = []
        active_clusters = []

        for reading in records:
            current_time = reading["timestamp"]

            # Because records are sorted, clusters outside the
            # temporal window can be removed from active matching.
            active_clusters = [
                cluster
                for cluster in active_clusters
                if (
                    current_time - cluster[0]["timestamp"]
                ).total_seconds() <= tolerance_seconds
            ]

            matching_cluster = None

            for cluster in active_clusters:
                if compatible_with_cluster(
                    reading,
                    cluster,
                    time_tolerance_minutes,
                    spatial_tolerance_km,
                ):
                    matching_cluster = cluster
                    break

            if matching_cluster is None:
                new_cluster = [reading]
                clusters.append(new_cluster)
                active_clusters.append(new_cluster)
            else:
                matching_cluster.append(reading)

        for cluster in clusters:
            output.append(
                analyze_cluster(
                    parameter,
                    dimension,
                    cluster,
                )
            )

    return output


# ---------------------------------------------------------
# API STATUS
# ---------------------------------------------------------

@router.get("/api/science/confidence/status")
def confidence_status():
    return {
        "module": "GeoNOVA Confidence Intelligence",
        "version": "1.1.0",
        "status": "configured",
        "capabilities": [
            "Unit compatibility checks",
            "Temperature and pressure normalization",
            "Time-window comparison",
            "Geographic proximity checks",
            "Duplicate reading detection",
            "Median and MAD disagreement analysis",
            "Source-level agreement assessment",
            "Confidence classification",
            "Missing-coordinate handling",
        ],
        "important_limitation": (
            "Confidence measures agreement among submitted readings. "
            "It does not establish source accuracy or scientific truth."
        ),
    }


# ---------------------------------------------------------
# API ANALYSIS
# ---------------------------------------------------------

@router.post("/api/science/confidence/analyze")
def analyze_confidence(request: ConfidenceRequest):
    valid, rejected, duplicate_count = prepare_readings(
        request.readings
    )

    clusters = make_clusters(
        valid,
        request.time_tolerance_minutes,
        request.spatial_tolerance_km,
    )

    return {
        "status": "completed",
        "engine": "GeoNOVA Confidence Intelligence",
        "input_count": len(request.readings),
        "valid_count": len(valid),
        "rejected_count": len(rejected),
        "duplicate_readings_removed": duplicate_count,
        "comparison_cluster_count": len(clusters),
        "results": clusters,
        "rejected_readings": rejected,
        "methodology": {
            "central_measure": "Median",
            "outlier_method": "Median Absolute Deviation",
            "agreement_method": "Source-level median comparison",
            "time_tolerance_minutes": request.time_tolerance_minutes,
            "spatial_tolerance_km": request.spatial_tolerance_km,
            "unit_normalization": True,
            "duplicate_detection": True,
        },
        "limitations": [
            "Different physical parameters are not compared.",
            "Accumulated precipitation and precipitation rates are kept separate.",
            "Readings with incomplete coordinates are rejected.",
            "Readings with missing coordinates are not spatially compared against geolocated readings.",
            "Source labels are not proof of independent instruments or organizations.",
            "Multiple readings from one source are aggregated before agreement scoring.",
            "Confidence describes agreement, not measurement accuracy.",
            "No source reliability weights are assumed.",
            "The outlier threshold is a statistical comparison threshold, not an instrument uncertainty estimate.",
        ],
    }
