
from datetime import datetime
from typing import Optional

import requests
from fastapi import APIRouter, HTTPException, Query

router = APIRouter()

CMR_COLLECTIONS_URL = (
    "https://cmr.earthdata.nasa.gov/search/collections.json"
)
CMR_GRANULES_URL = (
    "https://cmr.earthdata.nasa.gov/search/granules.json"
)

HEADERS = {
    "User-Agent": "GeoNOVA-Earth-Intelligence/1.0"
}

TIMEOUT = 25


def validate_date(value: Optional[str], field_name: str):
    if value is None:
        return

    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} must use YYYY-MM-DD format."
        )


def build_temporal(start_date, end_date):
    validate_date(start_date, "start_date")
    validate_date(end_date, "end_date")

    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=400,
            detail="start_date cannot be after end_date."
        )

    if start_date or end_date:
        start = start_date or ""
        end = end_date or ""
        return f"{start}T00:00:00Z,{end}T23:59:59Z"

    return None


def validate_bbox(bbox: Optional[str]):
    if not bbox:
        return None

    try:
        values = [float(value.strip()) for value in bbox.split(",")]
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="bbox must contain four comma-separated numbers."
        )

    if len(values) != 4:
        raise HTTPException(
            status_code=400,
            detail="bbox format: west,south,east,north."
        )

    west, south, east, north = values

    if not (-180 <= west <= 180 and -180 <= east <= 180):
        raise HTTPException(
            status_code=400,
            detail="Longitude must be between -180 and 180."
        )

    if not (-90 <= south <= 90 and -90 <= north <= 90):
        raise HTTPException(
            status_code=400,
            detail="Latitude must be between -90 and 90."
        )

    if west >= east or south >= north:
        raise HTTPException(
            status_code=400,
            detail="Invalid bounding box. West must be less than east and south less than north."
        )

    return ",".join(str(value) for value in values)


def extract_links(links):
    results = []

    for link in links or []:
        if not isinstance(link, dict):
            continue

        href = link.get("href")

        if not href:
            continue

        results.append({
            "href": href,
            "rel": link.get("rel"),
            "title": link.get("title"),
            "type": link.get("type")
        })

    return results


def summarize_collection(item):
    return {
        "concept_id": item.get("id"),
        "title": item.get("title"),
        "short_name": item.get("short_name"),
        "version": item.get("version_id"),
        "provider": item.get("provider_id"),
        "archive_center": item.get("archive_center"),
        "description": item.get("summary"),
        "granule_count": item.get("granule_count"),
        "boxes": item.get("boxes", []),
        "polygons": item.get("polygons", []),
        "links": extract_links(item.get("links")),
        "metadata_source": "NASA Common Metadata Repository"
    }


def summarize_granule(item):
    return {
        "concept_id": item.get("id"),
        "title": item.get("title"),
        "collection_concept_id": item.get(
            "collection_concept_id"
        ),
        "producer_granule_id": item.get(
            "producer_granule_id"
        ),
        "time_start": item.get("time_start"),
        "time_end": item.get("time_end"),
        "updated": item.get("updated"),
        "boxes": item.get("boxes", []),
        "polygons": item.get("polygons", []),
        "links": extract_links(item.get("links")),
        "metadata_source": "NASA Common Metadata Repository"
    }


@router.get("/api/satellite/catalog")
def search_satellite_catalog(
    keyword: str = Query("MODIS", min_length=2, max_length=120),
    bbox: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    page_size: int = Query(15, ge=1, le=50)
):
    temporal = build_temporal(start_date, end_date)
    spatial = validate_bbox(bbox)

    params = {
        "keyword": keyword,
        "page_size": page_size
    }

    if temporal:
        params["temporal"] = temporal

    if spatial:
        params["bounding_box"] = spatial

    try:
        response = requests.get(
            CMR_COLLECTIONS_URL,
            params=params,
            headers=HEADERS,
            timeout=TIMEOUT
        )
        response.raise_for_status()
        payload = response.json()

    except requests.RequestException as exc:
        raise HTTPException(
            status_code=502,
            detail=f"NASA CMR collection search failed: {str(exc)}"
        )

    except ValueError:
        raise HTTPException(
            status_code=502,
            detail="NASA CMR returned invalid JSON."
        )

    entries = payload.get("feed", {}).get("entry", [])

    collections = [
        summarize_collection(item)
        for item in entries
    ]

    return {
        "status": "success",
        "query": {
            "keyword": keyword,
            "bounding_box": spatial,
            "start_date": start_date,
            "end_date": end_date,
            "page_size": page_size
        },
        "result_count": len(collections),
        "collections": collections,
        "metadata_only": True,
        "notice": (
            "These results describe NASA data collections and their "
            "catalogued spatial coverage. They do not confirm that "
            "individual imagery files have been downloaded."
        )
    }


@router.get("/api/satellite/granules")
def search_satellite_granules(
    collection_id: str = Query(..., min_length=5, max_length=100),
    bbox: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    page_size: int = Query(20, ge=1, le=100)
):
    temporal = build_temporal(start_date, end_date)
    spatial = validate_bbox(bbox)

    params = {
        "collection_concept_id": collection_id,
        "page_size": page_size
    }

    if temporal:
        params["temporal"] = temporal

    if spatial:
        params["bounding_box"] = spatial

    try:
        response = requests.get(
            CMR_GRANULES_URL,
            params=params,
            headers=HEADERS,
            timeout=TIMEOUT
        )
        response.raise_for_status()
        payload = response.json()

    except requests.RequestException as exc:
        raise HTTPException(
            status_code=502,
            detail=f"NASA CMR granule search failed: {str(exc)}"
        )

    except ValueError:
        raise HTTPException(
            status_code=502,
            detail="NASA CMR returned invalid granule JSON."
        )

    entries = payload.get("feed", {}).get("entry", [])

    granules = [
        summarize_granule(item)
        for item in entries
    ]

    return {
        "status": "success",
        "collection_concept_id": collection_id,
        "result_count": len(granules),
        "granules": granules,
        "metadata_only": True,
        "notice": (
            "Granule records provide observation metadata and available "
            "links. A listed link does not mean the data file has been "
            "downloaded or processed by GeoNOVA."
        )
    }


@router.get("/api/satellite/status")
def satellite_integration_status():
    return {
        "module": "GeoNOVA Satellite & Geospatial Intelligence",
        "version": "1.0.0",
        "provider": "NASA Common Metadata Repository",
        "collection_search": CMR_COLLECTIONS_URL,
        "granule_search": CMR_GRANULES_URL,
        "capabilities": [
            "Satellite collection discovery",
            "Geographic bounding-box filtering",
            "Date-range filtering",
            "Granule metadata discovery",
            "Spatial coverage metadata",
            "Source-link transparency"
        ],
        "imagery_download_enabled": False,
        "status": "configured"
    }
