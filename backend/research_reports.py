
import csv
import io
import json
import uuid

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter
from fastapi.responses import Response
from pydantic import BaseModel, Field


router = APIRouter()


# =========================================================
# REQUEST MODELS
# =========================================================

class ResearchReportRequest(BaseModel):
    title: str = Field(
        default="GeoNOVA Earth Intelligence Research Report",
        min_length=3,
        max_length=200
    )

    research_question: str = Field(
        min_length=5,
        max_length=3000
    )

    domains: list[str] = Field(
        default_factory=list,
        max_length=20
    )

    sources: list[dict[str, Any]] = Field(
        default_factory=list,
        max_length=100
    )

    observations: list[dict[str, Any]] = Field(
        default_factory=list,
        max_length=10000
    )

    findings: list[dict[str, Any]] = Field(
        default_factory=list,
        max_length=200
    )

    confidence_analysis: Optional[dict[str, Any]] = None

    anomaly_analysis: Optional[dict[str, Any]] = None

    trend_analysis: Optional[dict[str, Any]] = None

    methodology: list[str] = Field(
        default_factory=list,
        max_length=100
    )

    limitations: list[str] = Field(
        default_factory=list,
        max_length=100
    )

    # Structured reproducibility metadata.
    # Kept flexible so future manifest versions can add fields
    # without requiring an immediate backend schema migration.
    reproducibility_manifest: Optional[dict[str, Any]] = None


# =========================================================
# GENERAL UTILITIES
# =========================================================

def utc_timestamp():
    return datetime.now(timezone.utc).isoformat()


def safe_dict(value):
    return value if isinstance(value, dict) else {}


def safe_list(value):
    return value if isinstance(value, list) else []


def get_manifest(data):
    manifest = getattr(
        data,
        "reproducibility_manifest",
        None
    )

    if isinstance(manifest, dict) and manifest:
        return manifest

    return None


def get_manifest_dataset(manifest):
    if not isinstance(manifest, dict):
        return {}

    return safe_dict(manifest.get("dataset"))


def get_manifest_fingerprint(manifest):
    dataset = get_manifest_dataset(manifest)

    fingerprint = dataset.get("input_fingerprint")

    if fingerprint is None:
        return None

    return str(fingerprint)


def get_manifest_source_identifiers(manifest):
    dataset = get_manifest_dataset(manifest)

    identifiers = dataset.get("source_identifiers", [])

    if not isinstance(identifiers, list):
        return []

    return [
        str(item)
        for item in identifiers
        if item is not None
    ]


# =========================================================
# MANIFEST SUMMARY
# =========================================================

def build_manifest_summary(manifest):
    if not isinstance(manifest, dict):
        return {
            "available": False,
            "message": (
                "No structured reproducibility manifest "
                "was supplied."
            )
        }

    dataset = get_manifest_dataset(manifest)
    preprocessing = safe_dict(
        manifest.get("preprocessing")
    )
    statistical_configuration = safe_dict(
        manifest.get("statistical_configuration")
    )

    fingerprint = get_manifest_fingerprint(manifest)

    return {
        "available": True,

        "manifest_version": manifest.get(
            "manifest_version"
        ),

        "generated_at": manifest.get(
            "generated_at"
        ),

        "project": manifest.get(
            "project"
        ),

        "domain_id": manifest.get(
            "domain_id"
        ),

        "dataset": {
            "observation_count": dataset.get(
                "observation_count"
            ),

            "valid_date_count": dataset.get(
                "valid_date_count"
            ),

            "first_date": dataset.get(
                "first_date"
            ),

            "last_date": dataset.get(
                "last_date"
            ),

            "source_identifiers": get_manifest_source_identifiers(
                manifest
            ),

            "input_fingerprint": fingerprint,

            "algorithm": dataset.get(
                "algorithm"
            )
        },

        "preprocessing": preprocessing,

        "statistical_configuration": (
            statistical_configuration
        ),

        "reproducibility_notes": safe_list(
            manifest.get("reproducibility_notes")
        ),

        "fingerprint_notice": (
            "The supplied fingerprint is retained as "
            "report metadata. Its algorithm and security "
            "properties are not independently verified "
            "by the report service."
        )
    }


# =========================================================
# EXECUTIVE SUMMARY
# =========================================================

def make_executive_summary(data):
    findings = data.findings
    anomalies = data.anomaly_analysis or {}
    confidence = data.confidence_analysis or {}
    trend = data.trend_analysis or {}

    sections = []

    sections.append(
        f"This report addresses the research question: "
        f"{data.research_question}"
    )

    sections.append(
        f"The submitted evidence contains "
        f"{len(data.observations)} observation records and "
        f"{len(data.sources)} source records."
    )

    if findings:
        sections.append(
            f"The analysis package contains {len(findings)} "
            f"research finding(s)."
        )
    else:
        sections.append(
            "No research findings were supplied for this report."
        )

    anomaly_count = (
        anomalies.get("anomaly_analysis", {}).get("count")
        if isinstance(
            anomalies.get("anomaly_analysis"),
            dict
        )
        else anomalies.get("count")
    )

    if anomaly_count is not None:
        sections.append(
            f"The supplied anomaly analysis reports "
            f"{anomaly_count} detected anomalous observation(s)."
        )

    confidence_results = confidence.get(
        "results",
        []
    )

    if confidence_results:
        sections.append(
            f"The supplied confidence analysis contains "
            f"{len(confidence_results)} comparison group(s)."
        )

    if trend:
        direction = trend.get("direction")

        if direction:
            sections.append(
                f"The supplied trend analysis describes the "
                f"direction as {direction}."
            )

    manifest = get_manifest(data)

    if manifest:
        sections.append(
            "A structured reproducibility manifest was "
            "included with the report."
        )
    else:
        sections.append(
            "No structured reproducibility manifest was "
            "supplied with the report."
        )

    sections.append(
        "These statements summarize submitted analysis outputs. "
        "They do not independently validate the underlying "
        "measurements or establish physical causes."
    )

    return " ".join(sections)


# =========================================================
# REPORT GENERATION
# =========================================================

def build_report(data):
    report_id = f"GN-{uuid.uuid4().hex[:12].upper()}"
    generated_at = utc_timestamp()

    manifest = get_manifest(data)
    manifest_summary = build_manifest_summary(manifest)

    fingerprint = (
        get_manifest_fingerprint(manifest)
        if manifest
        else None
    )

    source_identifiers = (
        get_manifest_source_identifiers(manifest)
        if manifest
        else []
    )

    return {
        "report_id": report_id,

        "title": data.title,

        "generated_at": generated_at,

        "platform": "GeoNOVA Earth Intelligence",

        "report_version": "1.1",

        "research_question": data.research_question,

        "executive_summary": make_executive_summary(data),

        "research_scope": {
            "domains": data.domains,

            "observation_count": len(
                data.observations
            ),

            "source_record_count": len(
                data.sources
            ),

            "finding_count": len(
                data.findings
            )
        },

        # Original source records are preserved.
        "source_register": data.sources,

        # Original observation records are preserved.
        "observation_records": data.observations,

        "research_findings": data.findings,

        "analytical_results": {
            "confidence_analysis": data.confidence_analysis,

            "anomaly_analysis": data.anomaly_analysis,

            "trend_analysis": data.trend_analysis
        },

        "methodology": data.methodology,

        # Full structured manifest, not just a summary.
        "reproducibility_manifest": manifest,

        # Convenient report-level summary.
        "reproducibility_summary": manifest_summary,

        "limitations": data.limitations + [
            "This report is generated from evidence supplied to the report service.",
            "The report service does not independently verify source authenticity.",
            "Catalogue metadata must not be interpreted as downloaded observation data.",
            "Statistical agreement does not establish scientific accuracy.",
            "Interpretations should be reviewed before external or policy use.",
            "A reproducibility manifest records supplied analysis metadata but does not independently reproduce the analysis.",
            "Input fingerprints are retained as supplied metadata and are not independently verified by this service."
        ],

        # Audit and provenance information.
        "provenance": {
            "report_generator": "GeoNOVA Research Reports",

            "generated_at": generated_at,

            "evidence_supplied_by_request": True,

            "independent_source_validation_performed": False,

            "structured_manifest_available": (
                manifest is not None
            ),

            "input_fingerprint": fingerprint,

            "source_identifiers": source_identifiers,

            "audit_trail": {
                "report_id": report_id,

                "report_generated_at": generated_at,

                "observation_count": len(
                    data.observations
                ),

                "source_record_count": len(
                    data.sources
                ),

                "finding_count": len(
                    data.findings
                ),

                "manifest_attached": (
                    manifest is not None
                ),

                "manifest_generated_at": (
                    manifest.get("generated_at")
                    if manifest
                    else None
                ),

                "input_fingerprint": fingerprint,

                "fingerprint_verified": False,

                "source_authenticity_verified": False
            }
        }
    }


# =========================================================
# CSV UTILITIES
# =========================================================

def csv_safe_value(value):
    if isinstance(value, (dict, list)):
        return json.dumps(
            value,
            ensure_ascii=False
        )

    if value is None:
        return ""

    return str(value)


def observations_to_csv(observations):
    output = io.StringIO()

    if not observations:
        writer = csv.writer(output)

        writer.writerow(["message"])

        writer.writerow([
            "No observation records were supplied."
        ])

        return output.getvalue()

    columns = []

    for observation in observations:
        for key in observation.keys():
            if key not in columns:
                columns.append(key)

    writer = csv.DictWriter(
        output,
        fieldnames=columns,
        extrasaction="ignore"
    )

    writer.writeheader()

    for observation in observations:
        writer.writerow({
            key: csv_safe_value(
                observation.get(key)
            )
            for key in columns
        })

    return output.getvalue()


# =========================================================
# API: SERVICE STATUS
# =========================================================

@router.get("/api/reports/status")
def report_service_status():
    return {
        "module": "GeoNOVA Research Reports",

        "version": "1.1.0",

        "status": "configured",

        "capabilities": [
            "Structured research report generation",
            "Executive summary generation",
            "Source register",
            "Observation record inclusion",
            "Confidence and anomaly result inclusion",
            "Methodology and limitation documentation",
            "Structured reproducibility manifest",
            "Input fingerprint metadata retention",
            "Source identifier recording",
            "Research parameter documentation",
            "Report provenance and audit trail",
            "JSON report export",
            "CSV observation export"
        ],

        "formats": [
            "JSON",
            "CSV"
        ],

        "pdf_export": False,

        "reproducibility": {
            "structured_manifest": True,

            "input_fingerprint_recording": True,

            "source_identifier_recording": True,

            "analysis_configuration_recording": True,

            "independent_fingerprint_verification": False,

            "independent_source_validation": False,

            "automatic_analysis_reexecution": False
        },

        "notice": (
            "Reports organize submitted evidence and analysis. "
            "They do not independently validate scientific claims "
            "or automatically reproduce submitted analyses."
        )
    }


# =========================================================
# API: GENERATE REPORT
# =========================================================

@router.post("/api/reports/generate")
def generate_research_report(
    request: ResearchReportRequest
):
    report = build_report(request)

    return {
        "status": "success",

        "report": report
    }


# =========================================================
# API: EXPORT JSON
# =========================================================

@router.post("/api/reports/export/json")
def export_report_json(
    request: ResearchReportRequest
):
    report = build_report(request)

    content = json.dumps(
        report,
        ensure_ascii=False,
        indent=2
    )

    filename = (
        f"{report['report_id']}.json"
    )

    return Response(
        content=content,

        media_type="application/json",

        headers={
            "Content-Disposition": (
                f'attachment; filename="{filename}"'
            )
        }
    )


# =========================================================
# API: EXPORT CSV
# =========================================================

@router.post("/api/reports/export/csv")
def export_observations_csv(
    request: ResearchReportRequest
):
    content = observations_to_csv(
        request.observations
    )

    filename = (
        f"geonova_observations_"
        f"{uuid.uuid4().hex[:8]}.csv"
    )

    return Response(
        content=content,

        media_type="text/csv; charset=utf-8",

        headers={
            "Content-Disposition": (
                f'attachment; filename="{filename}"'
            )
        }
    )
