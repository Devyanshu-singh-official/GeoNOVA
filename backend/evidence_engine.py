
import re
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Optional

import requests
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ai_investigator import DOMAIN_KNOWLEDGE, identify_domains


router = APIRouter()

OBSERVATION_DOMAINS = {
    "temperature",
    "water",
    "soil",
    "atmosphere",
    "climate-carbon",
}

REQUEST_TIMEOUT = 25
MAX_DOMAINS = 5
MAX_WORKERS = 10

# NASA catalogue metadata changes less frequently than live observations.
CATALOGUE_CACHE_TTL = 300
CATALOGUE_CACHE_MAX_ENTRIES = 128

_catalogue_cache: OrderedDict = OrderedDict()
_catalogue_cache_lock = Lock()


class EvidenceRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    domain_id: Optional[str] = None

    latitude: float = Field(default=26.8467, ge=-90, le=90)
    longitude: float = Field(default=80.9462, ge=-180, le=180)

    start_date: Optional[str] = None
    end_date: Optional[str] = None

    include_observations: bool = True
    include_datasets: bool = True


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_date(value: Optional[str], field_name: str):
    if value is None:
        return

    if not re.fullmatch(r"\d{8}", value):
        raise HTTPException(
            status_code=422,
            detail=f"{field_name} must use YYYYMMDD format.",
        )

    try:
        datetime.strptime(value, "%Y%m%d")
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"{field_name} is not a valid calendar date.",
        )


def get_domains(
    question: str,
    requested_domain: Optional[str],
):
    if requested_domain:
        if requested_domain not in DOMAIN_KNOWLEDGE:
            raise HTTPException(
                status_code=404,
                detail=f"Unknown GeoNOVA domain: {requested_domain}",
            )

        return [requested_domain]

    matches = identify_domains(question)

    return list(
        dict.fromkeys(
            match["domain_id"]
            for match in matches
            if match.get("domain_id") in DOMAIN_KNOWLEDGE
        )
    )[:MAX_DOMAINS]


def fetch_json(url: str, params: dict):
    try:
        response = requests.get(
            url,
            params=params,
            timeout=REQUEST_TIMEOUT,
            headers={
                "User-Agent": "GeoNOVA-EvidenceEngine/1.1",
                "Accept": "application/json",
            },
        )

        response.raise_for_status()

        try:
            return response.json(), None
        except ValueError:
            return None, "Provider returned an invalid JSON response."

    except requests.Timeout:
        return None, "Provider request timed out."

    except requests.RequestException as exc:
        return None, f"Provider request failed: {str(exc)[:250]}"

    except Exception:
        return None, "Unexpected error during provider retrieval."


def retrieve_observations(
    base_url: str,
    domain_id: str,
    payload: EvidenceRequest,
):
    endpoint = (
        f"{base_url}/api/science/observations/{domain_id}"
    )

    params = {
        "lat": payload.latitude,
        "lon": payload.longitude,
    }

    if payload.start_date:
        params["start_date"] = payload.start_date

    if payload.end_date:
        params["end_date"] = payload.end_date

    data, error = fetch_json(endpoint, params)

    if error:
        return {
            "domain_id": domain_id,
            "status": "retrieval_failed",
            "endpoint": endpoint,
            "error": error,
            "observations": [],
            "observation_count": 0,
        }

    if not isinstance(data, dict):
        return {
            "domain_id": domain_id,
            "status": "invalid_response",
            "endpoint": endpoint,
            "observations": [],
            "observation_count": 0,
            "error": (
                "Observation endpoint returned an unexpected structure."
            ),
        }

    observations = data.get("observations", [])

    if not isinstance(observations, list):
        return {
            "domain_id": domain_id,
            "status": "invalid_response",
            "endpoint": endpoint,
            "observations": [],
            "observation_count": 0,
            "error": "Observation records were not returned as a list.",
        }

    return {
        "domain_id": domain_id,
        "status": "retrieved" if observations else "no_observations",
        "endpoint": endpoint,
        "source": data.get("source"),
        "coordinates": data.get("coordinates"),
        "time_range": data.get("time_range"),
        "units": data.get("units"),
        "metadata": data.get("metadata"),
        "quality_notice": data.get("quality_notice"),
        "observations": observations,
        "observation_count": len(observations),
    }


def get_cached_catalogue(key: tuple):
    now = time.monotonic()

    with _catalogue_cache_lock:
        cached = _catalogue_cache.get(key)

        if cached is None:
            return None

        expires_at, value = cached

        if now >= expires_at:
            del _catalogue_cache[key]
            return None

        _catalogue_cache.move_to_end(key)
        return deepcopy(value)


def set_cached_catalogue(key: tuple, value: dict):
    expires_at = time.monotonic() + CATALOGUE_CACHE_TTL

    with _catalogue_cache_lock:
        _catalogue_cache[key] = (
            expires_at,
            deepcopy(value),
        )

        _catalogue_cache.move_to_end(key)

        while len(_catalogue_cache) > CATALOGUE_CACHE_MAX_ENTRIES:
            _catalogue_cache.popitem(last=False)


def retrieve_datasets(
    base_url: str,
    domain_id: str,
):
    endpoint = f"{base_url}/api/nasa/collections"

    cache_key = (base_url, domain_id)

    cached = get_cached_catalogue(cache_key)

    if cached is not None:
        cached["cache"] = {
            "status": "hit",
            "ttl_seconds": CATALOGUE_CACHE_TTL,
        }
        return cached

    data, error = fetch_json(
        endpoint,
        {
            "domain_id": domain_id,
            "page_size": 10,
        },
    )

    if error:
        return {
            "domain_id": domain_id,
            "status": "retrieval_failed",
            "endpoint": endpoint,
            "error": error,
            "collections": [],
            "collection_count": 0,
            "cache": {"status": "miss"},
        }

    if not isinstance(data, dict):
        return {
            "domain_id": domain_id,
            "status": "invalid_response",
            "endpoint": endpoint,
            "collections": [],
            "collection_count": 0,
            "error": (
                "NASA catalogue returned an unexpected structure."
            ),
            "cache": {"status": "miss"},
        }

    collections = data.get("collections", [])

    if not isinstance(collections, list):
        return {
            "domain_id": domain_id,
            "status": "invalid_response",
            "endpoint": endpoint,
            "collections": [],
            "collection_count": 0,
            "error": "NASA collections were not returned as a list.",
            "cache": {"status": "miss"},
        }

    result = {
        "domain_id": domain_id,
        "status": "retrieved" if collections else "no_collections",
        "endpoint": endpoint,
        "collections": collections,
        "collection_count": len(collections),
        "partial_errors": (
            data.get("partial_errors", [])
            if isinstance(data.get("partial_errors", []), list)
            else []
        ),
        "notice": (
            "NASA CMR results are catalogue metadata. "
            "They do not mean observation files were downloaded."
        ),
        "cache": {"status": "miss"},
    }

    set_cached_catalogue(cache_key, result)

    return result


def retrieve_domain_evidence(
    base_url: str,
    domain_id: str,
    domain: dict,
    payload: EvidenceRequest,
):
    item = {
        "domain_id": domain_id,
        "domain_name": domain["name"],
        "observation_evidence": None,
        "dataset_catalogue": None,
    }

    if payload.include_observations:
        if domain_id in OBSERVATION_DOMAINS:
            item["observation_evidence"] = retrieve_observations(
                base_url,
                domain_id,
                payload,
            )
        else:
            item["observation_evidence"] = {
                "status": "not_configured",
                "observations": [],
                "observation_count": 0,
                "notice": (
                    "This domain does not yet have a configured "
                    "observation retrieval endpoint."
                ),
            }

    if payload.include_datasets:
        item["dataset_catalogue"] = retrieve_datasets(
            base_url,
            domain_id,
        )

    return item


def failed_domain_evidence(
    domain_id: str,
    domain: dict,
    error: str,
    payload: EvidenceRequest,
):
    item = {
        "domain_id": domain_id,
        "domain_name": domain["name"],
        "observation_evidence": None,
        "dataset_catalogue": None,
        "retrieval_error": error,
    }

    if payload.include_observations:
        item["observation_evidence"] = {
            "status": "retrieval_failed",
            "observations": [],
            "observation_count": 0,
            "error": error,
        }

    if payload.include_datasets:
        item["dataset_catalogue"] = {
            "status": "retrieval_failed",
            "collections": [],
            "collection_count": 0,
            "error": error,
        }

    return item


@router.get("/api/ai/evidence/status")
def evidence_engine_status():
    with _catalogue_cache_lock:
        cache_entries = len(_catalogue_cache)

    return {
        "service": "GeoNOVA Evidence Retrieval Engine",
        "version": "1.1.0",
        "status": "operational",
        "observation_domains": sorted(OBSERVATION_DOMAINS),
        "dataset_catalogue": "NASA CMR",
        "observation_retrieval": "Existing GeoNOVA observation API",
        "automatic_satellite_file_download": False,
        "performance": {
            "parallel_retrieval": True,
            "maximum_domains": MAX_DOMAINS,
            "maximum_workers": MAX_WORKERS,
            "provider_timeout_seconds": REQUEST_TIMEOUT,
            "catalogue_cache_ttl_seconds": CATALOGUE_CACHE_TTL,
            "catalogue_cache_entries": cache_entries,
            "observation_cache_enabled": False,
        },
        "timestamp": utc_timestamp(),
    }


@router.post("/api/ai/evidence")
def retrieve_evidence(
    payload: EvidenceRequest,
    request: Request,
):
    validate_date(payload.start_date, "start_date")
    validate_date(payload.end_date, "end_date")

    if payload.start_date and payload.end_date:
        if payload.start_date > payload.end_date:
            raise HTTPException(
                status_code=422,
                detail="start_date must not be later than end_date.",
            )

    domain_ids = get_domains(
        payload.question,
        payload.domain_id,
    )

    if not domain_ids:
        return {
            "status": "no_domain_match",
            "question": payload.question,
            "evidence": [],
            "notice": (
                "No scientific domain could be identified. "
                "Specify a domain or use clearer scientific terms."
            ),
            "timestamp": utc_timestamp(),
        }

    base_url = str(request.base_url).rstrip("/")

    evidence_by_domain = {}

    worker_count = min(MAX_WORKERS, len(domain_ids))

    # Each domain is retrieved independently. A failure in one domain
    # does not prevent other domains from completing.
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {
            executor.submit(
                retrieve_domain_evidence,
                base_url,
                domain_id,
                DOMAIN_KNOWLEDGE[domain_id],
                payload,
            ): domain_id
            for domain_id in domain_ids
        }

        for future in as_completed(futures):
            domain_id = futures[future]
            domain = DOMAIN_KNOWLEDGE[domain_id]

            try:
                evidence_by_domain[domain_id] = future.result()
            except Exception as exc:
                evidence_by_domain[domain_id] = failed_domain_evidence(
                    domain_id,
                    domain,
                    f"Domain retrieval failed: {str(exc)[:200]}",
                    payload,
                )

    # Restore the original domain matching order.
    evidence = [
        evidence_by_domain[domain_id]
        for domain_id in domain_ids
    ]

    retrieved_observation_count = sum(
        item["observation_evidence"].get("observation_count", 0)
        for item in evidence
        if isinstance(item.get("observation_evidence"), dict)
    )

    retrieved_collection_count = sum(
        item["dataset_catalogue"].get("collection_count", 0)
        for item in evidence
        if isinstance(item.get("dataset_catalogue"), dict)
    )

    failed_domain_count = sum(
        1
        for item in evidence
        if item.get("retrieval_error")
        or any(
            isinstance(item.get(key), dict)
            and item[key].get("status") in {
                "retrieval_failed",
                "invalid_response",
            }
            for key in (
                "observation_evidence",
                "dataset_catalogue",
            )
        )
    )

    return {
        "status": (
            "evidence_retrieval_completed"
            if failed_domain_count == 0
            else "evidence_retrieval_partial"
        ),
        "question": payload.question,
        "location": {
            "latitude": payload.latitude,
            "longitude": payload.longitude,
        },
        "requested_period": {
            "start_date": payload.start_date,
            "end_date": payload.end_date,
        },
        "summary": {
            "domains_examined": len(evidence),
            "observation_records_retrieved": (
                retrieved_observation_count
            ),
            "catalogue_collections_retrieved": (
                retrieved_collection_count
            ),
            "domains_with_retrieval_errors": failed_domain_count,
        },
        "evidence": evidence,
        "interpretation_status": "not_performed",
        "notice": (
            "Retrieved observations and catalogue metadata are kept "
            "separate. Catalogue records are not observation measurements. "
            "No AI scientific interpretation has been performed. "
            "Catalogue metadata may be cached briefly; live observations "
            "are retrieved without this cache."
        ),
        "timestamp": utc_timestamp(),
    }
