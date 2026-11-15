
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field


router = APIRouter()


# ---------------------------------------------------------
# GEONOVA SCIENTIFIC INTERPRETATION ENGINE
# ---------------------------------------------------------

class InterpretationRequest(BaseModel):
    analysis: dict[str, Any]
    research_question: Optional[str] = Field(
        default=None,
        max_length=2000
    )


def make_finding_id(index: int) -> str:
    return f"GN-FINDING-{index:03d}"


def interpret_group(group: dict, index: int):
    parameter = group.get("parameter", "unknown")
    unit = group.get("normalized_unit", "unknown")

    median_value = group.get("median")
    minimum = group.get("minimum")
    maximum = group.get("maximum")

    source_count = group.get("independent_source_count", 0)
    agreement = group.get("agreement_percentage", 0)
    outlier_count = group.get("potential_outlier_count", 0)

    readings = group.get("readings", [])

    sources = sorted({
        reading.get("source", "Unknown source")
        for reading in readings
    })

    # -----------------------------------------------------
    # OBSERVATION
    # -----------------------------------------------------

    if median_value is None:
        observation = "No valid numerical comparison was available."
    else:
        observation = (
            f"The median of the submitted readings is "
            f"{median_value} {unit}. The reported range is "
            f"{minimum} to {maximum} {unit}."
        )

    # -----------------------------------------------------
    # COMPARISON
    # -----------------------------------------------------

    if source_count >= 3 and agreement >= 80:
        comparison = (
            "At least three distinct source labels contributed "
            "readings, and at least 80% of the submitted measurements "
            "were within the configured agreement threshold."
        )
        consistency = "higher_consistency"

    elif source_count >= 2 and agreement >= 60:
        comparison = (
            "At least two distinct source labels contributed readings. "
            "The measurements show moderate agreement under the "
            "configured comparison threshold."
        )
        consistency = "moderate_consistency"

    elif source_count >= 2:
        comparison = (
            "Multiple source labels contributed readings, but the "
            "measurements show limited agreement under the configured "
            "comparison threshold."
        )
        consistency = "low_consistency"

    else:
        comparison = (
            "The available evidence does not contain enough distinct "
            "source labels for a meaningful cross-source comparison."
        )
        consistency = "insufficient_comparison"

    # -----------------------------------------------------
    # INTERPRETATION
    # -----------------------------------------------------

    if outlier_count > 0:
        interpretation = (
            f"{outlier_count} reading(s) were flagged as potential "
            "statistical outliers. These readings should be checked "
            "against their original provider records, measurement "
            "methods, and timestamps before drawing conclusions."
        )
    elif source_count >= 2 and agreement >= 80:
        interpretation = (
            "The submitted sources show relatively strong numerical "
            "consistency for this parameter. This supports confidence "
            "in the agreement of the submitted readings, but does not "
            "establish their accuracy or representativeness."
        )
    elif source_count >= 2:
        interpretation = (
            "The submitted readings differ beyond the configured "
            "agreement threshold in some cases. Differences may arise "
            "from measurement methods, processing, timing, spatial "
            "sampling, or other factors that require investigation."
        )
    else:
        interpretation = (
            "The available evidence is insufficient for a cross-source "
            "scientific interpretation. Additional independent "
            "measurements would be useful."
        )

    # -----------------------------------------------------
    # EVIDENCE REFERENCES
    # -----------------------------------------------------

    evidence_references = []

    for reading_index, reading in enumerate(readings):
        evidence_references.append({
            "reference_id": f"GN-EVIDENCE-{index:03d}-{reading_index + 1:03d}",
            "source": reading.get("source"),
            "original_value": reading.get("original_value"),
            "original_unit": reading.get("original_unit"),
            "normalized_value": reading.get("normalized_value"),
            "normalized_unit": reading.get("normalized_unit"),
            "timestamp": reading.get("timestamp"),
        })

    # -----------------------------------------------------
    # LIMITATIONS
    # -----------------------------------------------------

    limitations = list(group.get("limitations", []))

    limitations.extend([
        "The interpretation is based only on the submitted analysis payload.",
        "Distinct source labels do not necessarily represent independent instruments or datasets.",
        "No causal relationship has been established.",
        "The comparison does not establish regional or global representativeness.",
        "Original provider records should be checked before consequential use."
    ])

    return {
        "finding_id": make_finding_id(index),
        "parameter": parameter,
        "unit": unit,
        "classification": "evidence_based_finding",
        "observed_facts": {
            "median": median_value,
            "minimum": minimum,
            "maximum": maximum,
            "measurement_count": group.get("measurement_count", 0),
            "source_count": source_count,
            "agreement_percentage": agreement,
            "potential_outlier_count": outlier_count,
        },
        "observation": observation,
        "source_comparison": comparison,
        "consistency_assessment": consistency,
        "scientific_interpretation": interpretation,
        "contributing_sources": sources,
        "evidence_references": evidence_references,
        "limitations": list(dict.fromkeys(limitations)),
    }


def build_summary(findings: list[dict]):
    if not findings:
        return {
            "status": "insufficient_evidence",
            "text": "No valid findings were available for interpretation."
        }

    higher = sum(
        finding["consistency_assessment"] == "higher_consistency"
        for finding in findings
    )

    moderate = sum(
        finding["consistency_assessment"] == "moderate_consistency"
        for finding in findings
    )

    low = sum(
        finding["consistency_assessment"] == "low_consistency"
        for finding in findings
    )

    insufficient = sum(
        finding["consistency_assessment"] == "insufficient_comparison"
        for finding in findings
    )

    return {
        "status": "interpretation_completed",
        "finding_count": len(findings),
        "higher_consistency_findings": higher,
        "moderate_consistency_findings": moderate,
        "low_consistency_findings": low,
        "insufficient_comparison_findings": insufficient,
        "text": (
            f"GeoNOVA generated {len(findings)} structured findings. "
            f"{higher} show higher numerical consistency, "
            f"{moderate} show moderate consistency, "
            f"{low} show low consistency, and "
            f"{insufficient} lack sufficient independent source labels."
        )
    }


# ---------------------------------------------------------
# API ENDPOINTS
# ---------------------------------------------------------

@router.get("/api/ai/interpreter/status")
def interpreter_status():
    return {
        "service": "GeoNOVA Scientific Interpretation Engine",
        "version": "0.1.0",
        "status": "operational",
        "mode": "deterministic evidence interpretation",
        "language_model_connected": False,
        "capabilities": [
            "structured_scientific_findings",
            "observation_and_interpretation_separation",
            "source_attribution",
            "evidence_references",
            "uncertainty_and_limitation_reporting",
        ],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/api/ai/interpret")
def interpret_evidence(request: InterpretationRequest):
    analysis = request.analysis

    if analysis.get("status") != "analysis_completed":
        return {
            "status": "analysis_not_completed",
            "message": (
                "The supplied payload does not contain a completed "
                "GeoNOVA evidence analysis."
            ),
            "findings": [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    results = analysis.get("results")

    if not isinstance(results, list):
        return {
            "status": "invalid_analysis_payload",
            "message": "The analysis results field must be a list.",
            "findings": [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    findings = []

    for index, group in enumerate(results, start=1):
        if not isinstance(group, dict):
            continue

        if not isinstance(group.get("readings"), list):
            continue

        findings.append(
            interpret_group(group, index)
        )

    return {
        "status": "interpretation_completed",
        "research_question": request.research_question,
        "interpretation_timestamp": datetime.now(timezone.utc).isoformat(),
        "input_analysis_timestamp": analysis.get("analysis_timestamp"),
        "summary": build_summary(findings),
        "findings": findings,
        "overall_conclusion": (
            "The findings describe consistency and variation within "
            "the submitted evidence. They should not be interpreted "
            "as proof of causation, verified ground truth, or a "
            "forecast of future environmental conditions."
        ),
        "methodology": {
            "interpretation_type": "rule-based",
            "uses_external_llm": False,
            "uses_new_observations": False,
            "uses_supplied_analysis_only": True,
        },
    }
