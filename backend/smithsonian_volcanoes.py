"""Smithsonian Global Volcanism Program volcano catalogue endpoint.

Returns a validated GeoJSON FeatureCollection in EPSG:4326 for MapLibre.
"""

from __future__ import annotations

from typing import Any

import requests
from fastapi import APIRouter, HTTPException

router = APIRouter()

GVP_WFS_URLS = (
    "https://webservices.volcano.si.edu/geoserver/GVP-VOTW/ows",
    "https://webservices.volcano.si.edu/geoserver/GVP-VOTW/wfs",
)
LAYER_NAME = "GVP-VOTW:Smithsonian_VOTW_Holocene_Volcanoes"


def _valid_point_feature(feature: Any) -> bool:
    if not isinstance(feature, dict):
        return False
    geometry = feature.get("geometry")
    if not isinstance(geometry, dict) or geometry.get("type") != "Point":
        return False
    coordinates = geometry.get("coordinates")
    if not isinstance(coordinates, (list, tuple)) or len(coordinates) < 2:
        return False
    try:
        lon, lat = float(coordinates[0]), float(coordinates[1])
    except (TypeError, ValueError):
        return False
    return -180 <= lon <= 180 and -90 <= lat <= 90


def _request_gvp(url: str, version: str) -> dict[str, Any]:
    params: dict[str, Any] = {
        "service": "WFS",
        "version": version,
        "request": "GetFeature",
        "outputFormat": "application/json",
        "srsName": "EPSG:4326",
    }
    if version == "2.0.0":
        params.update({"typeNames": LAYER_NAME, "count": 2000})
    else:
        params.update({"typeName": LAYER_NAME, "maxFeatures": 2000})

    response = requests.get(
        url,
        params=params,
        headers={
            "Accept": "application/geo+json, application/json",
            "User-Agent": "GeoNOVA/2.4 (educational geospatial research)",
        },
        timeout=(8, 45),
    )
    response.raise_for_status()

    try:
        payload = response.json()
    except ValueError as exc:
        excerpt = response.text[:300].replace("\n", " ")
        raise ValueError(f"GVP returned non-JSON content: {excerpt}") from exc

    if not isinstance(payload, dict):
        raise ValueError("GVP response was not a GeoJSON object")

    features = payload.get("features")
    if not isinstance(features, list):
        raise ValueError("GVP response did not contain a features array")

    valid_features = [feature for feature in features if _valid_point_feature(feature)]
    if not valid_features:
        raise ValueError("GVP response contained no valid point features")

    return {
        "type": "FeatureCollection",
        "source": "Smithsonian Global Volcanism Program",
        "dataset": "Holocene Volcanoes",
        "coordinate_reference_system": "EPSG:4326",
        "total": len(valid_features),
        "features": valid_features,
    }


@router.get("/api/volcanoes")
def get_volcanoes():
    errors: list[str] = []

    # Try WFS 2.0.0 first, then the broadly supported WFS 1.1.0 and 1.0.0
    # variants. The Smithsonian documents this layer as a public WFS service.
    attempts = (
        (GVP_WFS_URLS[0], "2.0.0"),
        (GVP_WFS_URLS[0], "1.1.0"),
        (GVP_WFS_URLS[1], "1.0.0"),
    )

    for url, version in attempts:
        try:
            return _request_gvp(url, version)
        except (requests.RequestException, ValueError) as exc:
            errors.append(f"WFS {version}: {str(exc)[:220]}")

    raise HTTPException(
        status_code=503,
        detail="Smithsonian Global Volcanism Program is temporarily unavailable. "
        + " | ".join(errors),
    )
