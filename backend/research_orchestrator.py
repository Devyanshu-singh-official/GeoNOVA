
import math
from datetime import datetime, timezone
from typing import Any, Optional

import requests
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field


router = APIRouter()

CONNECT_TIMEOUT = 10
READ_TIMEOUT = 45
TIMEOUT = (CONNECT_TIMEOUT, READ_TIMEOUT)


# ---------------------------------------------------------
# REQUEST MODEL
# ---------------------------------------------------------

class ResearchRequest(BaseModel):
    question: str = Field(min_length=5, max_length=2000)

    domain_id: Optional[str] = None

    latitude: float = Field(default=26.8467, ge=-90, le=90)
    longitude: float = Field(default=80.9462, ge=-180, le=180)

    start_date: Optional[str] = None
    end_date: Optional[str] = None

    include_observations: bool = True
    include_datasets: bool = True


# ---------------------------------------------------------
# UTILITIES
# ---------------------------------------------------------

def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_http_session() -> requests.Session:
    session = requests.Session()

    session.headers.update({
        "User-Agent": "GeoNOVA-ResearchOrchestrator/1.1",
        "Accept": "application/json",
        "Content-Type": "application/json",
    })

    return session


# ---------------------------------------------------------
# INTERNAL API HELPER
# ---------------------------------------------------------

def call_local_api(
    session: requests.Session,
    base_url: str,
    endpoint: str,
    payload: dict,
) -> dict:
    url = f"{base_url.rstrip('/')}{endpoint}"

    try:
        response = session.post(
            url,
            json=payload,
            timeout=TIMEOUT,
        )

    except requests.Timeout:
        raise HTTPException(
            status_code=504,
            detail={
                "pipeline_stage": endpoint,
                "message": "Internal GeoNOVA service timed out.",
            },
        )

    except requests.RequestException:
        raise HTTPException(
            status_code=502,
            detail={
                "pipeline_stage": endpoint,
                "message": "Could not connect to the internal GeoNOVA service.",
            },
        )

    if not response.ok:
        raise HTTPException(
            status_code=response.status_code,
            detail={
                "pipeline_stage": endpoint,
                "message": "An internal GeoNOVA service returned an error.",
                "service_status_code": response.status_code,
                "service_response": response.text[:1000],
            },
        )

    try:
        data = response.json()
    except ValueError:
        raise HTTPException(
            status_code=502,
            detail={
                "pipeline_stage": endpoint,
                "message": "Internal service returned invalid JSON.",
            },
        )

    if not isinstance(data, dict):
        raise HTTPException(
            status_code=502,
            detail={
                "pipeline_stage": endpoint,
                "message": "Internal service returned an unexpected response structure.",
            },
        )

    return data


# ---------------------------------------------------------
# OBSERVATION EXTRACTION
# ---------------------------------------------------------

def extract_readings(evidence: dict):
    """
    Extract structured scientific readings.

    A reading must contain:
    - An identifiable source
    - A parameter
    - A finite numeric value
    - A unit
    - A timestamp

    Duplicate readings are removed while preserving their
    original order.
    """

    readings = []
    seen = set()

    def add_reading(
        source,
        parameter,
        value,
        unit,
        timestamp,
        latitude=None,
        longitude=None,
    ):
        try:
            if value is None or isinstance(value, bool):
                return

            numeric_value = float(value)

            if not math.isfinite(numeric_value):
                return

            if not all([
                source,
                parameter,
                unit,
                timestamp,
            ]):
                return

            record = {
                "source": str(source),
                "parameter": str(parameter),
                "value": numeric_value,
                "unit": str(unit),
                "timestamp": str(timestamp),
            }

            if latitude is not None and longitude is not None:
                try:
                    lat = float(latitude)
                    lon = float(longitude)

                    if (
                        math.isfinite(lat)
                        and math.isfinite(lon)
                        and -90 <= lat <= 90
                        and -180 <= lon <= 180
                    ):
                        record["latitude"] = lat
                        record["longitude"] = lon

                except (TypeError, ValueError):
                    pass

            key = (
                record["source"],
                record["parameter"],
                record["value"],
                record["unit"],
                record["timestamp"],
                record.get("latitude"),
                record.get("longitude"),
            )

            if key not in seen:
                seen.add(key)
                readings.append(record)

        except (ValueError, TypeError, OverflowError):
            return

    def walk(node, inherited_source=None):
        if isinstance(node, list):
            for item in node:
                walk(item, inherited_source)
            return

        if not isinstance(node, dict):
            return

        source = (
            node.get("source")
            or node.get("source_name")
            or node.get("provider")
            or inherited_source
        )

        timestamp = (
            node.get("timestamp")
            or node.get("date")
            or node.get("time")
        )

        latitude = node.get("latitude", node.get("lat"))
        longitude = node.get("longitude", node.get("lon"))

        # Format A: already-normalized reading.
        if all(
            key in node
            for key in ("parameter", "value", "unit")
        ):
            add_reading(
                source,
                node.get("parameter"),
                node.get("value"),
                node.get("unit"),
                timestamp,
                latitude,
                longitude,
            )

        # Format B: observation with a parameters dictionary.
        parameters = node.get("parameters")

        if isinstance(parameters, dict):
            units = node.get("units", {})

            for parameter, value in parameters.items():
                unit = (
                    units.get(parameter)
                    if isinstance(units, dict)
                    else None
                )

                if isinstance(value, dict):
                    add_reading(
                        source,
                        parameter,
                        value.get("value"),
                        value.get("unit") or unit,
                        value.get("timestamp") or timestamp,
                        latitude,
                        longitude,
                    )

                elif unit is not None:
                    add_reading(
                        source,
                        parameter,
                        value,
                        unit,
                        timestamp,
                        latitude,
                        longitude,
                    )

        # Continue searching nested evidence structures.
        for key, value in node.items():
            if key != "parameters" and isinstance(value, (dict, list)):
                walk(value, source)

    walk(evidence)

    return readings


# ---------------------------------------------------------
# PIPELINE STAGE EXECUTION
# ---------------------------------------------------------

def execute_stage(
    session: requests.Session,
    base_url: str,
    endpoint: str,
    payload: dict,
):
    """
    Execute one pipeline stage.

    Returns:
        (response, None) on success
        (None, error_information) on failure
    """

    try:
        result = call_local_api(
            session,
            base_url,
            endpoint,
            payload,
        )

        return result, None

    except HTTPException as exc:
        detail = exc.detail

        if isinstance(detail, dict):
            message = detail.get("message", "Internal service failed.")
        else:
            message = str(detail)

        return None, {
            "endpoint": endpoint,
            "http_status": exc.status_code,
            "message": message,
        }

    except Exception:
        return None, {
            "endpoint": endpoint,
            "http_status": 500,
            "message": "Unexpected pipeline stage failure.",
        }


# ---------------------------------------------------------
# STATUS ENDPOINT
# ---------------------------------------------------------

@router.get("/api/ai/research/status")
def research_pipeline_status():
    return {
        "service": "GeoNOVA Unified Research Pipeline",
        "version": "1.1.0",
        "status": "operational",
        "stages": [
            "evidence_retrieval",
            "observation_extraction",
            "cross_source_analysis",
            "scientific_interpretation",
            "llm_grounded_answer",
        ],
        "performance": {
            "connection_reuse": True,
            "connect_timeout_seconds": CONNECT_TIMEOUT,
            "read_timeout_seconds": READ_TIMEOUT,
            "structured_partial_results": True,
            "automatic_stage_retries": False,
        },
        "timestamp": utc_timestamp(),
    }


# ---------------------------------------------------------
# UNIFIED RESEARCH PIPELINE
# ---------------------------------------------------------

@router.post("/api/ai/research")
def run_research_pipeline(
    payload: ResearchRequest,
    request: Request,
):
    base_url = str(request.base_url).rstrip("/")

    result = {
        "status": "research_started",
        "research_question": payload.question,
        "generated_at": utc_timestamp(),
        "evidence": None,
        "reading_count": 0,
        "analysis": None,
        "interpretation": None,
        "answer": None,
        "pipeline_notes": [],
        "stage_errors": [],
    }

    # Reuse one HTTP session for the complete pipeline.
    with create_http_session() as session:

        # -------------------------------------------------
        # STAGE 1: EVIDENCE RETRIEVAL
        # -------------------------------------------------

        # Important: EvidenceRequest expects latitude and
        # longitude, not lat and lon.
        evidence_payload = {
            "question": payload.question,
            "domain_id": payload.domain_id,
            "latitude": payload.latitude,
            "longitude": payload.longitude,
            "start_date": payload.start_date,
            "end_date": payload.end_date,
            "include_observations": payload.include_observations,
            "include_datasets": payload.include_datasets,
        }

        evidence, error = execute_stage(
            session,
            base_url,
            "/api/ai/evidence",
            evidence_payload,
        )

        if error:
            raise HTTPException(
                status_code=error["http_status"],
                detail={
                    "pipeline_stage": error["endpoint"],
                    "message": error["message"],
                },
            )

        result["evidence"] = evidence
        result["status"] = "evidence_retrieved"

        # -------------------------------------------------
        # STAGE 2: OBSERVATION EXTRACTION
        # -------------------------------------------------

        readings = extract_readings(evidence)

        result["reading_count"] = len(readings)

        if not readings:
            result["pipeline_notes"].append(
                "Evidence was retrieved, but no observations could "
                "be converted into comparable scientific readings. "
                "Analysis and AI interpretation were not run."
            )

            result["status"] = "evidence_only"

            return result

        # -------------------------------------------------
        # STAGE 3: CROSS-SOURCE ANALYSIS
        # -------------------------------------------------

        analysis, error = execute_stage(
            session,
            base_url,
            "/api/ai/analyze-evidence",
            {
                "readings": readings,
            },
        )

        if error:
            result["status"] = "analysis_incomplete"
            result["stage_errors"].append(error)

            result["pipeline_notes"].append(
                "Evidence retrieval and observation extraction "
                "completed, but cross-source analysis failed."
            )

            return result

        result["analysis"] = analysis

        if analysis.get("status") != "analysis_completed":
            result["status"] = "analysis_incomplete"

            result["pipeline_notes"].append(
                "The analysis service did not report a completed analysis."
            )

            return result

        # -------------------------------------------------
        # STAGE 4: SCIENTIFIC INTERPRETATION
        # -------------------------------------------------

        interpretation, error = execute_stage(
            session,
            base_url,
            "/api/ai/interpret",
            {
                "research_question": payload.question,
                "analysis": analysis,
            },
        )

        if error:
            result["status"] = "interpretation_incomplete"
            result["stage_errors"].append(error)

            result["pipeline_notes"].append(
                "Cross-source analysis completed, but scientific "
                "interpretation could not be completed."
            )

            return result

        result["interpretation"] = interpretation

        if interpretation.get("status") != "interpretation_completed":
            result["status"] = "interpretation_incomplete"

            result["pipeline_notes"].append(
                "The interpretation service did not report completion."
            )

            return result

        # -------------------------------------------------
        # STAGE 5: GROUNDED LLM ANSWER
        # -------------------------------------------------

        answer, error = execute_stage(
            session,
            base_url,
            "/api/ai/grounded-answer",
            {
                "research_question": payload.question,
                "interpretation": interpretation,
                "evidence_package": evidence,
            },
        )

        if error:
            result["status"] = "answer_incomplete"
            result["stage_errors"].append(error)

            result["pipeline_notes"].append(
                "Evidence retrieval, analysis and scientific "
                "interpretation completed, but grounded answer "
                "generation failed."
            )

            return result

        result["answer"] = answer
        result["status"] = "research_completed"

        result["pipeline_notes"].append(
            "The answer was generated from the supplied evidence "
            "and interpretation. Scientific correctness still requires "
            "independent validation."
        )

    return result
