
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from time import perf_counter

import requests
from fastapi import APIRouter

router = APIRouter()

TIMEOUT_SECONDS = 8

SOURCES = [
    {
        "id": "nasa-cmr",
        "name": "NASA Earthdata CMR",
        "category": "Satellite data catalogue",
        "url": "https://cmr.earthdata.nasa.gov/search/collections.json",
        "params": {"page_size": 1},
    },
    {
        "id": "nasa-eonet",
        "name": "NASA EONET",
        "category": "Natural event intelligence",
        "url": "https://eonet.gsfc.nasa.gov/api/v3/events",
        "params": {"limit": 1},
    },
    {
        "id": "usgs-earthquakes",
        "name": "USGS Earthquake Catalog",
        "category": "Seismic activity",
        "url": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson",
        "params": {},
    },
    {
        "id": "smithsonian-gvp",
        "name": "Smithsonian Global Volcanism Program",
        "category": "Volcanic activity",
        "url": "https://webservices.volcano.si.edu/geoserver/GVP-VOTW/wfs",
        "params": {
            "service": "WFS",
            "version": "1.0.0",
            "request": "GetCapabilities",
        },
    },
    {
        "id": "nasa-power",
        "name": "NASA POWER",
        "category": "Environmental observations",
        "url": "https://power.larc.nasa.gov/api/temporal/daily/point",
        "params": {
            "parameters": "T2M",
            "community": "AG",
            "longitude": 78.96,
            "latitude": 22.59,
            "start": "20261101",
            "end": "20261102",
            "format": "JSON",
        },
    },
    {
        "id": "isro-bhuvan",
        "name": "ISRO Bhuvan WMS",
        "category": "Indian geospatial services",
        "url": "https://bhuvan-vec2.nrsc.gov.in/bhuvan/wms",
        "params": {
            "service": "WMS",
            "request": "GetCapabilities",
        },
    },
    {
        "id": "isro-mosdac",
        "name": "ISRO MOSDAC Portal",
        "category": "Indian meteorological satellite data",
        "url": "https://www.mosdac.gov.in/",
        "params": {},
    },
]


def check_source(source):
    started = perf_counter()

    try:
        response = requests.get(
            source["url"],
            params=source["params"],
            timeout=TIMEOUT_SECONDS,
            headers={
                "User-Agent": "GeoNOVA-Earth-Intelligence/2.2"
            },
        )

        elapsed = round((perf_counter() - started) * 1000)

        if response.status_code < 500:
            status = "online"
            message = "Provider responded to the connectivity check."
        else:
            status = "unavailable"
            message = f"Provider returned HTTP {response.status_code}."

        return {
            "id": source["id"],
            "name": source["name"],
            "category": source["category"],
            "status": status,
            "http_status": response.status_code,
            "response_time_ms": elapsed,
            "message": message,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    except requests.Timeout:
        return {
            "id": source["id"],
            "name": source["name"],
            "category": source["category"],
            "status": "unverified",
            "http_status": None,
            "response_time_ms": None,
            "message": "Request timed out; provider status could not be verified.",
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    except requests.RequestException as error:
        return {
            "id": source["id"],
            "name": source["name"],
            "category": source["category"],
            "status": "unavailable",
            "http_status": None,
            "response_time_ms": None,
            "message": f"Connection could not be established: {type(error).__name__}.",
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }


@router.get("/api/science/sources")
def get_source_observatory():
    results = []

    with ThreadPoolExecutor(max_workers=7) as executor:
        futures = {
            executor.submit(check_source, source): source
            for source in SOURCES
        }

        for future in as_completed(futures):
            results.append(future.result())

    # Keep the display order consistent with SOURCES.
    order = {source["id"]: index for index, source in enumerate(SOURCES)}
    results.sort(key=lambda item: order[item["id"]])

    counts = {
        "online": sum(r["status"] == "online" for r in results),
        "unavailable": sum(r["status"] == "unavailable" for r in results),
        "unverified": sum(r["status"] == "unverified" for r in results),
    }

    return {
        "platform": "GeoNOVA",
        "service": "Data Source Observatory",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "timeout_seconds": TIMEOUT_SECONDS,
        "summary": {
            "total": len(results),
            **counts,
        },
        "sources": results,
        "notice": (
            "Connectivity does not establish data completeness, "
            "scientific validity, licensing, or download availability."
        ),
    }
