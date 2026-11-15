
from collections import defaultdict
from datetime import datetime, timezone
from statistics import median
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field, model_validator

router = APIRouter()


class Reading(BaseModel):
    source: str = Field(min_length=1, max_length=120)
    parameter: str = Field(min_length=1, max_length=100)
    value: Optional[float] = None
    unit: str = Field(min_length=1, max_length=40)
    timestamp: str
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def validate_coordinates(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError(
                "Latitude and longitude must either both be provided or both be omitted."
            )
        return self


class QualityRequest(BaseModel):
    readings: list[Reading] = Field(min_length=1, max_length=100)


def parse_timestamp(value: str):
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

        return parsed
    except ValueError:
        return None


def calculate_mad(values):
    center = median(values)
    deviations = [abs(value - center) for value in values]
    return median(deviations)


def classify_confidence(source_count, agreement_ratio):
    if source_count >= 3 and agreement_ratio >= 0.8:
        return "high"

    if source_count >= 2 and agreement_ratio >= 0.6:
        return "moderate"

    return "limited"


@router.post("/api/science/quality-check")
def check_scientific_quality(request: QualityRequest):
    groups = defaultdict(list)
    rejected = []

    for reading in request.readings:
        parsed_time = parse_timestamp(reading.timestamp)

        if parsed_time is None:
            rejected.append({
                "source": reading.source,
                "reason": "Invalid timestamp.",
            })
            continue

        if reading.value is None:
            rejected.append({
                "source": reading.source,
                "reason": "Missing observation value.",
            })
            continue

        if reading.unit.strip() == "":
            rejected.append({
                "source": reading.source,
                "reason": "Missing unit.",
            })
            continue

        # Group only observations with matching parameter,
        # unit and exact timestamp.
        key = (
            reading.parameter.strip().lower(),
            reading.unit.strip().lower(),
            parsed_time.isoformat(),
        )

        groups[key].append({
            "source": reading.source,
            "parameter": reading.parameter,
            "value": reading.value,
            "unit": reading.unit,
            "timestamp": parsed_time.isoformat(),
            "latitude": reading.latitude,
            "longitude": reading.longitude,
        })

    comparisons = []

    for key, items in groups.items():
        values = [item["value"] for item in items]
        center = median(values)
        mad = calculate_mad(values)

        # A robust outlier threshold.
        # If MAD is zero, do not automatically label
        # different values as outliers.
        threshold = 3.5 * 1.4826 * mad if mad > 0 else None

        source_results = []
        agreeing = 0

        for item in items:
            deviation = abs(item["value"] - center)

            is_outlier = (
                threshold is not None and deviation > threshold
            )

            if not is_outlier:
                agreeing += 1

            source_results.append({
                **item,
                "deviation_from_median": round(deviation, 6),
                "possible_outlier": is_outlier,
            })

        agreement_ratio = agreeing / len(items)

        spread = max(values) - min(values) if len(values) > 1 else 0

        comparisons.append({
            "parameter": items[0]["parameter"],
            "unit": items[0]["unit"],
            "timestamp": items[0]["timestamp"],
            "source_count": len(items),
            "median": center,
            "minimum": min(values),
            "maximum": max(values),
            "spread": spread,
            "median_absolute_deviation": mad,
            "agreement_ratio": round(agreement_ratio, 3),
            "confidence": classify_confidence(
                len(items),
                agreement_ratio,
            ),
            "sources": source_results,
            "interpretation": (
                "Values are broadly consistent."
                if agreement_ratio >= 0.8
                else "Some disagreement exists between sources."
                if agreement_ratio >= 0.5
                else "Substantial disagreement exists between sources."
            ),
        })

    return {
        "engine": "GeoNOVA Scientific Quality Engine",
        "version": "1.0",
        "comparison_count": len(comparisons),
        "input_count": len(request.readings),
        "rejected_count": len(rejected),
        "comparisons": comparisons,
        "rejected_readings": rejected,
        "limitations": [
            "Only readings with matching parameter, unit and timestamp are compared.",
            "Spatial proximity is not checked by this endpoint.",
            "Different datasets may have different resolutions and measurement methods.",
            "Confidence describes agreement among submitted readings, not scientific truth.",
            "Possible outliers require investigation and are not automatically invalid.",
        ],
    }
