from typing import Any

import requests
from fastapi import APIRouter, HTTPException

router = APIRouter()

NASA_EONET_URL = "https://eonet.gsfc.nasa.gov/api/v3/events"
REQUEST_TIMEOUT = 20


def _latest_geometry(geometries: list[dict[str, Any]]) -> dict[str, Any] | None:
    valid = [
        geometry
        for geometry in geometries
        if isinstance(geometry, dict) and geometry.get("coordinates") is not None
    ]
    if not valid:
        return None
    return max(valid, key=lambda item: str(item.get("date") or ""))


@router.get("/api/nasa/events")
def get_nasa_events():
    try:
        response = requests.get(
            NASA_EONET_URL,
            params={"status": "open", "limit": 100},
            headers={"Accept": "application/json", "User-Agent": "GeoNOVA/2.3"},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
    except requests.Timeout as error:
        raise HTTPException(
            status_code=504,
            detail=f"NASA EONET request timed out: {error}",
        ) from error
    except requests.RequestException as error:
        raise HTTPException(
            status_code=502,
            detail=f"NASA EONET unavailable: {error}",
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=502,
            detail="NASA EONET returned invalid JSON.",
        ) from error

    if not isinstance(data, dict):
        raise HTTPException(
            status_code=502,
            detail="NASA EONET returned an unexpected response format.",
        )

    events = []
    for event in data.get("events", []):
        if not isinstance(event, dict):
            continue

        latest = _latest_geometry(event.get("geometry") or [])
        if not latest:
            continue

        categories = [
            category.get("title")
            for category in event.get("categories", [])
            if isinstance(category, dict) and category.get("title")
        ]

        sources = event.get("sources") or []
        source_url = None
        if sources and isinstance(sources[0], dict):
            source_url = sources[0].get("url")

        events.append(
            {
                "id": event.get("id"),
                "title": event.get("title"),
                "categories": categories,
                "date": latest.get("date"),
                "geometry_type": latest.get("type"),
                "coordinates": latest.get("coordinates"),
                "source": "NASA EONET",
                "source_url": source_url,
            }
        )

    return {
        "source": "NASA EONET",
        "total": len(events),
        "events": events,
    }
