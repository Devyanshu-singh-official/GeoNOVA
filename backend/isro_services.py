
from fastapi import APIRouter
import requests
import xml.etree.ElementTree as ET

router = APIRouter()

BUHVAN_WMS_URL = "https://bhuvan-vec2.nrsc.gov.in/bhuvan/wms"
MOSDAC_URL = "https://www.mosdac.gov.in/data-access-policy"


@router.get("/api/isro/status")
def get_isro_status():
    services = {}

    # Check Bhuvan WMS
    try:
        response = requests.get(
            BUHVAN_WMS_URL,
            params={
                "service": "WMS",
                "request": "GetCapabilities"
            },
            timeout=40
        )
        response.raise_for_status()
        ET.fromstring(response.content)

        services["bhuvan_wms"] = {
            "status": "reachable",
            "message": "Bhuvan WMS capabilities endpoint responded."
        }

    except requests.exceptions.Timeout as error:
        services["bhuvan_wms"] = {
            "status": "unverified",
            "message": f"Bhuvan WMS timed out. The service may still be operational: {error}"
        }

    except requests.RequestException as error:
        services["bhuvan_wms"] = {
            "status": "unavailable",
            "message": f"Bhuvan WMS request failed: {error}"
        }

    except ET.ParseError as error:
        services["bhuvan_wms"] = {
            "status": "unverified",
            "message": f"Bhuvan responded, but its XML capabilities could not be parsed: {error}"
        }

    # Check MOSDAC public portal independently
    try:
        response = requests.get(
            MOSDAC_URL,
            timeout=15
        )
        response.raise_for_status()

        services["mosdac_portal"] = {
            "status": "reachable",
            "message": "MOSDAC public data-access policy page responded. This does not verify authenticated downloads."
        }

    except requests.RequestException as error:
        services["mosdac_portal"] = {
            "status": "unavailable",
            "message": str(error)
        }

    return {
        "source": "ISRO",
        "services": services
    }


@router.get("/api/isro/catalog")
def get_isro_catalog():
    products = [
        {
            "id": "gsmap-isro-rain",
            "title": "GSMaP ISRO Rain",
            "category": "Precipitation",
            "description": "Satellite-derived global precipitation estimates at approximately 0.1-degree resolution with hourly products.",
            "coverage": "Global",
            "access": "MOSDAC portal; product-specific access conditions apply",
            "url": "https://www.mosdac.gov.in/",
            "source": "ISRO MOSDAC"
        },
        {
            "id": "inland-water-height",
            "title": "Inland Water Height",
            "category": "Hydrology",
            "description": "Water-level observations for selected inland water bodies and river locations.",
            "coverage": "Selected Indian river basins",
            "access": "MOSDAC portal; product-specific access conditions apply",
            "url": "https://www.mosdac.gov.in/",
            "source": "ISRO MOSDAC"
        },
        {
            "id": "river-discharge",
            "title": "River Discharge",
            "category": "Hydrology",
            "description": "Historical river-discharge product records for selected river basins.",
            "coverage": "Selected Indian river basins",
            "access": "MOSDAC portal; product-specific access conditions apply",
            "url": "https://www.mosdac.gov.in/",
            "source": "ISRO MOSDAC"
        },
        {
            "id": "soil-moisture",
            "title": "Soil Moisture",
            "category": "Land Surface",
            "description": "Satellite-derived soil moisture and soil wetness information.",
            "coverage": "Product-dependent",
            "access": "MOSDAC portal; product-specific access conditions apply",
            "url": "https://www.mosdac.gov.in/",
            "source": "ISRO MOSDAC"
        },
        {
            "id": "global-ocean-current",
            "title": "Global Ocean Surface Current",
            "category": "Oceanography",
            "description": "Ocean surface current information for oceanographic analysis.",
            "coverage": "Global",
            "access": "MOSDAC portal; product-specific access conditions apply",
            "url": "https://www.mosdac.gov.in/",
            "source": "ISRO MOSDAC"
        }
    ]

    return {
        "source": "ISRO MOSDAC",
        "catalogue_type": "Curated directory of official product records",
        "total": len(products),
        "products": products,
        "notice": "This is a product directory, not a live MOSDAC catalogue API. Availability and download permissions must be checked on MOSDAC."
    }
