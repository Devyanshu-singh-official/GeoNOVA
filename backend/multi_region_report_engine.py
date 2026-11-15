
from datetime import date
from math import erf, isfinite, sqrt
from statistics import median
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(
    prefix="/api/science/reports",
    tags=["Multi-Region Scientific Reports"],
)

MAX_REGIONS = 30
MAX_OBSERVATIONS = 2000
MIN_OBSERVATIONS = 8


class Observation(BaseModel):
    date: date
    value: Optional[float] = None


class RegionInput(BaseModel):
    region_id: str = Field(min_length=1, max_length=100)
    region_name: str = Field(min_length=1, max_length=150)
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    source_name: str = Field(min_length=1, max_length=150)
    dataset_id: str = Field(min_length=1, max_length=150)
    source_url: Optional[str] = Field(default=None, max_length=500)
    spatial_description: str = Field(
        default="Not provided",
        max_length=300,
    )
    observations: list[Observation] = Field(min_length=1)


class InvestigationRequest(BaseModel):
    investigation_title: str = Field(
        min_length=3,
        max_length=200,
    )
    variable: str = Field(min_length=1, max_length=100)
    unit: str = Field(min_length=1, max_length=50)
    significance_level: float = Field(
        default=0.05,
        gt=0,
        lt=1,
    )
    regions: list[RegionInput] = Field(
        min_length=2,
        max_length=MAX_REGIONS,
    )


def normal_cdf(z: float) -> float:
    return 0.5 * (1 + erf(z / sqrt(2)))


def two_sided_p(z: float) -> float:
    return max(
        0.0,
        min(1.0, 2 * (1 - normal_cdf(abs(z)))),
    )


def decimal_year(d: date) -> float:
    start = date(d.year, 1, 1)
    end = date(d.year + 1, 1, 1)

    return d.year + (d - start).days / (end - start).days


def analyze_region(
    region: RegionInput,
    significance_level: float,
) -> dict:
    if len(region.observations) > MAX_OBSERVATIONS:
        raise HTTPException(
            status_code=413,
            detail=(
                f"{region.region_name} exceeds "
                f"{MAX_OBSERVATIONS} observations."
            ),
        )

    ordered = sorted(
        region.observations,
        key=lambda item: item.date,
    )

    seen_dates = set()
    dates = []
    values = []

    for observation in ordered:
        if observation.date in seen_dates:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Duplicate date in {region.region_name}: "
                    f"{observation.date}"
                ),
            )

        seen_dates.add(observation.date)

        if observation.value is None:
            continue

        value = float(observation.value)

        if not isfinite(value):
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Non-finite value in {region.region_name}."
                ),
            )

        dates.append(observation.date)
        values.append(value)

    valid_count = len(values)
    missing_count = len(ordered) - valid_count

    result = {
        "region_id": region.region_id,
        "region_name": region.region_name,
        "latitude": region.latitude,
        "longitude": region.longitude,
        "source_name": region.source_name,
        "dataset_id": region.dataset_id,
        "source_url": region.source_url,
        "spatial_description": region.spatial_description,
        "input_observations": len(ordered),
        "valid_observations": valid_count,
        "missing_observations": missing_count,
    }

    if valid_count < MIN_OBSERVATIONS:
        return {
            **result,
            "available": False,
            "trend": "insufficient_data",
            "reason": (
                f"At least {MIN_OBSERVATIONS} valid observations "
                "are required."
            ),
            "sen_slope_per_year": None,
            "p_value": None,
            "significant": None,
        }

    n = valid_count
    score = 0
    slopes = []

    years = [decimal_year(d) for d in dates]

    for i in range(n):
        for j in range(i + 1, n):
            difference = values[j] - values[i]

            if difference > 0:
                score += 1
            elif difference < 0:
                score -= 1

            elapsed = years[j] - years[i]

            if elapsed > 0:
                slopes.append(
                    (values[j] - values[i]) / elapsed
                )

    variance = n * (n - 1) * (2 * n + 5) / 18.0

    tie_counts = {}

    for value in values:
        tie_counts[value] = tie_counts.get(value, 0) + 1

    for count in tie_counts.values():
        if count > 1:
            variance -= (
                count * (count - 1) * (2 * count + 5) / 18.0
            )

    if variance <= 0 or score == 0:
        z = 0.0
    elif score > 0:
        z = (score - 1) / sqrt(variance)
    else:
        z = (score + 1) / sqrt(variance)

    p_value = two_sided_p(z)
    slope = median(slopes) if slopes else None
    significant = p_value < significance_level

    if significant and score > 0:
        trend = "significant_increase"
    elif significant and score < 0:
        trend = "significant_decrease"
    elif slope is not None and slope > 0:
        trend = "non_significant_increase"
    elif slope is not None and slope < 0:
        trend = "non_significant_decrease"
    else:
        trend = "no_detected_trend"

    return {
        **result,
        "available": True,
        "trend": trend,
        "mann_kendall_s": score,
        "mann_kendall_z": round(z, 6),
        "p_value": round(p_value, 8),
        "significant": significant,
        "significance_level": significance_level,
        "sen_slope_per_year": (
            round(slope, 10) if slope is not None else None
        ),
        "first_observation": dates[0].isoformat(),
        "last_observation": dates[-1].isoformat(),
    }


def make_findings(results: list[dict]) -> list[str]:
    findings = []

    available = [
        result for result in results
        if result["available"]
    ]

    unavailable = [
        result for result in results
        if not result["available"]
    ]

    findings.append(
        f"{len(available)} of {len(results)} regions "
        "had sufficient observations for analysis."
    )

    for result in available:
        slope = result["sen_slope_per_year"]
        p_value = result["p_value"]

        findings.append(
            f"{result['region_name']}: {result['trend']}; "
            f"Sen's slope = {slope} per year; "
            f"p = {p_value}; "
            f"valid observations = {result['valid_observations']}."
        )

    for result in unavailable:
        findings.append(
            f"{result['region_name']}: analysis unavailable — "
            f"{result['reason']}"
        )

    significant = [
        result for result in available
        if result["significant"]
    ]

    if significant:
        findings.append(
            f"{len(significant)} analyzed regions showed a "
            "statistically significant trend at the selected "
            "significance level."
        )
    else:
        findings.append(
            "No analyzed region showed a statistically significant "
            "trend at the selected significance level."
        )

    return findings


def build_markdown(
    request: InvestigationRequest,
    results: list[dict],
    findings: list[str],
    warnings: list[str],
) -> str:
    lines = [
        f"# {request.investigation_title}",
        "",
        "## Investigation details",
        "",
        f"- Variable: {request.variable}",
        f"- Unit: {request.unit}",
        f"- Regions submitted: {len(results)}",
        f"- Significance threshold: {request.significance_level}",
        "- Statistical methods: Mann–Kendall test and Sen's slope",
        "",
        "## Regional results",
        "",
        "| Region | Trend | Sen's slope/year | p-value | Valid observations |",
        "|---|---|---:|---:|---:|",
    ]

    for result in results:
        slope = result.get("sen_slope_per_year")
        p_value = result.get("p_value")

        lines.append(
            f"| {result['region_name']} "
            f"| {result['trend']} "
            f"| {slope if slope is not None else 'N/A'} "
            f"| {p_value if p_value is not None else 'N/A'} "
            f"| {result['valid_observations']} |"
        )

    lines.extend([
        "",
        "## Evidence-based findings",
        "",
    ])

    for finding in findings:
        lines.append(f"- {finding}")

    lines.extend([
        "",
        "## Data provenance",
        "",
    ])

    for result in results:
        lines.extend([
            f"### {result['region_name']}",
            f"- Source: {result['source_name']}",
            f"- Dataset: {result['dataset_id']}",
            f"- Source URL: {result['source_url'] or 'Not supplied'}",
            f"- Spatial description: {result['spatial_description']}",
            f"- Observation period: "
            f"{result.get('first_observation', 'Unavailable')} to "
            f"{result.get('last_observation', 'Unavailable')}",
            "",
        ])

    lines.extend([
        "## Methodology",
        "",
        "Each region was analyzed independently using the "
        "Mann–Kendall trend test and Sen's median pairwise slope.",
        "",
        "The significance threshold is applied to the "
        "two-sided Mann–Kendall p-value. A statistically "
        "significant result indicates evidence of a monotonic "
        "trend in the supplied observations; it does not establish "
        "causation.",
        "",
        "## Limitations and warnings",
        "",
    ])

    for warning in warnings:
        lines.append(f"- {warning}")

    lines.extend([
        "",
        "## Reproducibility",
        "",
        "This report uses the exact observations and metadata "
        "submitted to the API. Preserve the input dataset and "
        "request parameters to reproduce the analysis.",
        "",
    ])

    return "\n".join(lines)


@router.post("/multi-region")
def generate_multi_region_report(request: InvestigationRequest):
    region_ids = [region.region_id for region in request.regions]

    if len(region_ids) != len(set(region_ids)):
        raise HTTPException(
            status_code=422,
            detail="Each region_id must be unique.",
        )

    results = [
        analyze_region(region, request.significance_level)
        for region in request.regions
    ]

    findings = make_findings(results)
    warnings = []

    if len({
        result["source_name"] for result in results
    }) > 1:
        warnings.append(
            "Regions use different named data sources. "
            "Check calibration, processing, and measurement "
            "definitions before interpreting differences."
        )

    if len({
        result["dataset_id"] for result in results
    }) > 1:
        warnings.append(
            "Regions use different dataset identifiers. "
            "Dataset comparability has not been independently verified."
        )

    periods = {
        (
            result.get("first_observation"),
            result.get("last_observation"),
        )
        for result in results
        if result["available"]
    }

    if len(periods) > 1:
        warnings.append(
            "Analyzed regions do not all share the same observation "
            "period. Direct slope comparisons may be affected."
        )

    if any(
        result["missing_observations"] > 0
        for result in results
    ):
        warnings.append(
            "One or more regions contain missing observations. "
            "Missing values were excluded, not interpolated."
        )

    warnings.extend([
        "Temporal autocorrelation and seasonality are not corrected "
        "by this endpoint.",
        "No multiple-testing correction is applied across regions.",
        "Spatial autocorrelation is not modeled.",
        "Regional slopes are not area-weighted.",
        "The supplied source metadata is reported as provided and "
        "has not been independently authenticated.",
    ])

    markdown_report = build_markdown(
        request,
        results,
        findings,
        warnings,
    )

    return {
        "status": "success",
        "investigation_title": request.investigation_title,
        "variable": request.variable,
        "unit": request.unit,
        "method": "Mann-Kendall and Sen's slope",
        "regional_results": results,
        "findings": findings,
        "warnings": warnings,
        "markdown_report": markdown_report,
    }
