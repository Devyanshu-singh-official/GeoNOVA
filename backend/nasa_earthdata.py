from typing import Any

import requests
from fastapi import APIRouter, HTTPException, Query

from earth_domains import DOMAINS

router = APIRouter()

CMR_COLLECTIONS_URL = "https://cmr.earthdata.nasa.gov/search/collections.json"
CMR_GRANULES_URL = "https://cmr.earthdata.nasa.gov/search/granules.json"

DEFAULT_KEYWORD = "MODIS"
REQUEST_TIMEOUT = 25
USER_AGENT = "GeoNOVA-Earth-Intelligence/2.3"


def get_domain(domain_id: str):
    for domain in DOMAINS:
        if domain.get("id") == domain_id:
            return domain
    return None


def nasa_get_json(url: str, params: dict[str, Any]) -> dict[str, Any]:
    """Call NASA CMR and normalize transport/JSON errors for the API client."""
    try:
        response = requests.get(
            url,
            params=params,
            headers={
                "Accept": "application/json",
                "User-Agent": USER_AGENT,
            },
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
    except requests.Timeout as error:
        raise HTTPException(
            status_code=504,
            detail={
                "message": "NASA CMR request timed out.",
                "upstream": url,
                "reason": str(error),
            },
        ) from error
    except requests.RequestException as error:
        status_code = 502
        if getattr(error, "response", None) is not None:
            status_code = 502
        raise HTTPException(
            status_code=status_code,
            detail={
                "message": "NASA CMR could not be reached or returned an error.",
                "upstream": url,
                "reason": str(error),
            },
        ) from error

    try:
        data = response.json()
    except ValueError as error:
        raise HTTPException(
            status_code=502,
            detail={
                "message": "NASA CMR returned a response that was not valid JSON.",
                "upstream": url,
            },
        ) from error

    if not isinstance(data, dict):
        raise HTTPException(
            status_code=502,
            detail="NASA CMR returned an unexpected response format.",
        )
    return data


def search_cmr_collections(keyword: str, page_size: int) -> list[dict[str, Any]]:
    data = nasa_get_json(
        CMR_COLLECTIONS_URL,
        {
            "keyword": keyword,
            "page_size": page_size,
            "sort_key[]": "-score",
        },
    )

    entries = data.get("feed", {}).get("entry", [])
    collections = []

    for item in entries:
        links = [
            {
                "title": link.get("title"),
                "href": link.get("href"),
                "rel": link.get("rel"),
            }
            for link in item.get("links", [])
            if isinstance(link, dict) and link.get("href")
        ]

        collections.append(
            {
                "id": item.get("id"),
                "title": item.get("title"),
                "short_name": item.get("short_name"),
                "version": item.get("version_id"),
                "provider": item.get("provider_id"),
                "description": item.get("summary"),
                "granule_count": item.get("granule_count"),
                "has_granules": item.get("has_granules"),
                "browse_available": item.get("browse_flag"),
                "source": "NASA CMR",
                "links": links,
            }
        )

    return collections


@router.get("/api/nasa/collections")
def search_nasa_collections(
    keyword: str | None = Query(default=None, min_length=2, max_length=100),
    domain_id: str | None = Query(default=None, min_length=2, max_length=50),
    page_size: int = Query(default=10, ge=1, le=25),
):
    search_terms: list[str] = []

    if domain_id:
        domain = get_domain(domain_id)
        if not domain:
            raise HTTPException(
                status_code=404,
                detail=f"Scientific domain '{domain_id}' was not found.",
            )
        search_terms.extend(domain.get("search_terms", []))

    if keyword and keyword.strip():
        search_terms.insert(0, keyword.strip())

    if not search_terms:
        search_terms = [DEFAULT_KEYWORD]

    search_terms = list(dict.fromkeys(search_terms))
    all_collections: dict[str, dict[str, Any]] = {}
    search_errors: list[dict[str, str]] = []

    for term in search_terms:
        try:
            for collection in search_cmr_collections(term, page_size):
                collection_id = collection.get("id")
                if not collection_id:
                    continue

                if collection_id not in all_collections:
                    collection["matched_keywords"] = [term]
                    all_collections[collection_id] = collection
                elif term not in all_collections[collection_id]["matched_keywords"]:
                    all_collections[collection_id]["matched_keywords"].append(term)

        except HTTPException as error:
            detail = error.detail
            search_errors.append(
                {
                    "keyword": term,
                    "error": detail.get("message", str(detail))
                    if isinstance(detail, dict)
                    else str(detail),
                }
            )

    collections = list(all_collections.values())[:page_size]

    if not collections and search_errors:
        raise HTTPException(
            status_code=502,
            detail={
                "message": "NASA Earthdata collection search failed.",
                "errors": search_errors,
            },
        )

    return {
        "source": "NASA Common Metadata Repository",
        "domain_id": domain_id,
        "search_terms": search_terms,
        "total_returned": len(collections),
        "collections": collections,
        "partial_errors": search_errors,
        "notice": (
            "These are NASA collection metadata records. A listed collection "
            "does not guarantee public download access or real-time availability."
        ),
    }


@router.get("/api/nasa/granules")
def search_nasa_granules(
    keyword: str | None = Query(default=None, min_length=2, max_length=120),
    collection_concept_id: str | None = Query(default=None, min_length=3, max_length=80),
    page_size: int = Query(default=10, ge=1, le=100),
    page_num: int = Query(default=1, ge=1, le=10000),
    temporal: str | None = Query(default=None, max_length=100),
    bounding_box: str | None = Query(default=None, max_length=100),
):
    """
    Search NASA CMR granule metadata.
    Supports keyword search and narrowing to a selected collection concept ID.
    """
    if not keyword and not collection_concept_id:
        keyword = DEFAULT_KEYWORD

    params: dict[str, Any] = {
        "page_size": page_size,
        "page_num": page_num,
        "sort_key[]": "-start_date",
    }

    if keyword:
        params["keyword"] = keyword.strip()
    if collection_concept_id:
        params["collection_concept_id"] = collection_concept_id.strip()
    if temporal:
        params["temporal"] = temporal.strip()
    if bounding_box:
        params["bounding_box"] = bounding_box.strip()

    data = nasa_get_json(CMR_GRANULES_URL, params)
    entries = data.get("feed", {}).get("entry", [])
    granules = []

    for item in entries:
        links = [
            {
                "rel": link.get("rel"),
                "title": link.get("title"),
                "href": link.get("href"),
            }
            for link in item.get("links", [])
            if isinstance(link, dict) and link.get("href")
        ]

        granules.append(
            {
                "id": item.get("id"),
                "title": item.get("title"),
                "producer_granule_id": item.get("producer_granule_id"),
                "collection_concept_id": item.get("collection_concept_id"),
                "provider": item.get("provider_id"),
                "start_date": item.get("time_start"),
                "end_date": item.get("time_end"),
                "updated": item.get("updated"),
                "data_center": item.get(" data_center") or item.get("data_center"),
                "day_night_flag": item.get(" day_night_flag") or item.get("day_night_flag"),
                "orbit": item.get(" orbit") or item.get("orbit"),
                "browse_available": bool(item.get("links")),
                "source": "NASA CMR",
                "links": links,
            }
        )

    return {
        "source": "NASA Common Metadata Repository",
        "keyword": keyword,
        "collection_concept_id": collection_concept_id,
        "page": page_num,
        "page_size": page_size,
        "total_returned": len(granules),
        "granules": granules,
        "feed": {"entry": granules},
        "notice": (
            "Granule search returns metadata. Data access may require Earthdata "
            "Login and depends on the collection's access policy."
        ),
    }
