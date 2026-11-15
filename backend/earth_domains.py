
from fastapi import APIRouter, HTTPException

router = APIRouter()


# ============================================================
# GEONOVA — EARTH SCIENCE DOMAIN REGISTRY
# ============================================================
#
# Ten reorganized scientific domains.
#
# Priority 1 = Core domains for initial implementation.
# Priority 2 = Extended scientific domains.
#
# Existing IDs are preserved wherever possible to maintain
# compatibility with existing frontend and backend services.
#
# observation_support indicates existing NASA POWER support.
# It does NOT mean every listed satellite dataset is integrated.
# ============================================================


DOMAINS = [
    {
        "id": "temperature",
        "name": "Climate & Temperature Intelligence",
        "description": (
            "Long-term climate patterns, air temperature, "
            "land surface temperature, thermal anomalies "
            "and climate variability."
        ),
        "icon": "thermometer",
        "priority": 1,
        "category": "Core Earth Systems",
        "search_terms": [
            "MODIS Land Surface Temperature",
            "ERA5 Temperature",
            "NASA POWER Temperature",
            "MERRA-2 Climate Reanalysis",
            "NOAA Climate Data",
            "Global Temperature Anomalies",
        ],
        "existing_variable_ids": [
            "land_surface_temperature",
        ],
        "observation_support": True,
    },
    {
        "id": "water",
        "name": "Hydrology & Water Intelligence",
        "description": (
            "Precipitation, rainfall, freshwater availability, "
            "groundwater, floods and terrestrial water storage."
        ),
        "icon": "droplets",
        "priority": 1,
        "category": "Core Earth Systems",
        "search_terms": [
            "GPM IMERG Precipitation",
            "GRACE GRACE-FO Terrestrial Water Storage",
            "Surface Water Ocean Topography SWOT",
            "NASA POWER Precipitation",
            "Global Flood Monitoring",
            "SMAP Soil Moisture",
        ],
        "existing_variable_ids": [
            "precipitation",
        ],
        "observation_support": True,
    },
    {
        "id": "vegetation",
        "name": "Vegetation, Agriculture & Forest Intelligence",
        "description": (
            "Vegetation health, agricultural productivity, "
            "forest cover, vegetation indices, land productivity "
            "and ecosystem greenness."
        ),
        "icon": "tree",
        "priority": 1,
        "category": "Core Earth Systems",
        "search_terms": [
            "MODIS Vegetation Indices NDVI",
            "Landsat Collection 2 Land Cover",
            "MODIS Leaf Area Index",
            "Sentinel-2 Vegetation Monitoring",
            "Global Forest Change",
            "MODIS Enhanced Vegetation Index EVI",
        ],
        "existing_variable_ids": [
            "ndvi",
        ],
        "observation_support": False,
    },
    {
        "id": "atmosphere",
        "name": "Atmospheric & Air Quality Intelligence",
        "description": (
            "Atmospheric composition, humidity, wind, pressure, "
            "ozone, aerosols, air quality and atmospheric chemistry."
        ),
        "icon": "cloud",
        "priority": 1,
        "category": "Core Earth Systems",
        "search_terms": [
            "MERRA-2 Atmospheric Reanalysis",
            "Aura OMI Ozone",
            "MODIS Atmosphere",
            "Sentinel-5P TROPOMI Air Quality",
            "NASA POWER Atmospheric Data",
            "Atmospheric Aerosol Optical Depth",
        ],
        "existing_variable_ids": [],
        "observation_support": True,
    },
    {
        "id": "ocean",
        "name": "Ocean & Marine Intelligence",
        "description": (
            "Sea surface temperature, ocean colour, ocean circulation, "
            "marine conditions, sea level and ocean ecosystem changes."
        ),
        "icon": "waves",
        "priority": 1,
        "category": "Core Earth Systems",
        "search_terms": [
            "MODIS Aqua Ocean Colour",
            "Sentinel-3 OLCI Ocean Colour",
            "SWOT Ocean Surface Water",
            "Sea Surface Temperature",
            "Ocean Chlorophyll Concentration",
            "Global Sea Level Observations",
        ],
        "existing_variable_ids": [],
        "observation_support": False,
    },
    {
        "id": "geophysical",
        "name": "Geophysical & Tectonic Intelligence",
        "description": (
            "Earthquakes, volcanoes, tectonic activity, "
            "ground deformation and other geophysical processes."
        ),
        "icon": "activity",
        "priority": 2,
        "category": "Extended Earth Systems",
        "search_terms": [
            "USGS Earthquake Catalog",
            "Smithsonian Global Volcanism Program",
            "NASA EONET Natural Events",
            "InSAR Ground Deformation",
            "NASA GRACE Geophysical Observations",
            "Global Tectonic Plate Boundaries",
        ],
        "existing_variable_ids": [],
        "observation_support": False,
    },
    {
        "id": "cryosphere",
        "name": "Cryosphere & Ice Intelligence",
        "description": (
            "Glaciers, snow cover, ice sheets, sea ice, "
            "permafrost and changes in frozen water systems."
        ),
        "icon": "snowflake",
        "priority": 2,
        "category": "Extended Earth Systems",
        "search_terms": [
            "MODIS Snow Cover",
            "ICESat-2 Ice Sheet",
            "NSIDC Sea Ice",
            "Landsat Glacier Monitoring",
            "Global Glacier Change",
            "Permafrost Observations",
        ],
        "existing_variable_ids": [],
        "observation_support": False,
    },
    {
        "id": "soil",
        "name": "Soil, Land & Surface Intelligence",
        "description": (
            "Soil moisture, land surface conditions, "
            "surface temperature, soil water availability "
            "and land degradation."
        ),
        "icon": "layers",
        "priority": 2,
        "category": "Extended Earth Systems",
        "search_terms": [
            "SMAP Soil Moisture",
            "MODIS Land Surface Products",
            "NASA POWER Soil Moisture",
            "SoilGrids Global Soil Data",
            "Land Degradation Monitoring",
            "Global Land Surface Conditions",
        ],
        "existing_variable_ids": [],
        "observation_support": True,
    },
    {
        "id": "ecosystem",
        "name": "Ecosystem & Biodiversity Intelligence",
        "description": (
            "Ecosystem distribution, habitat conditions, "
            "biodiversity indicators, ecological change "
            "and environmental stress."
        ),
        "icon": "leaf",
        "priority": 2,
        "category": "Extended Earth Systems",
        "search_terms": [
            "NASA MODIS Ecosystem Products",
            "Global Biodiversity Information Facility",
            "NASA Earth Observatory Ecosystems",
            "Global Habitat Change",
            "Protected Planet Areas",
            "Ecosystem Productivity",
        ],
        "existing_variable_ids": [],
        "observation_support": False,
    },
    {
        "id": "human-impact",
        "name": "Human Impact & Earth Systems Intelligence",
        "description": (
            "Urban expansion, nighttime lights, land-use change, "
            "human environmental pressure and interactions "
            "between human activity and Earth systems."
        ),
        "icon": "building",
        "priority": 2,
        "category": "Extended Earth Systems",
        "search_terms": [
            "VIIRS Nighttime Lights",
            "Landsat Land Cover Change",
            "Global Human Settlement Layer",
            "NASA Human Footprint",
            "Urban Expansion Monitoring",
            "Global Land Use Change",
        ],
        "existing_variable_ids": [],
        "observation_support": False,
    },
]


# Preserve compatibility with older domain references.
DOMAIN_ALIASES = {
    "climate-carbon": "temperature",
}


def find_domain(domain_id: str):
    canonical_id = DOMAIN_ALIASES.get(domain_id, domain_id)

    for domain in DOMAINS:
        if domain["id"] == canonical_id:
            return domain

    return None


@router.get("/api/science/domains")
def get_science_domains():
    return {
        "count": len(DOMAINS),
        "priority_1_count": sum(
            1 for domain in DOMAINS
            if domain["priority"] == 1
        ),
        "priority_2_count": sum(
            1 for domain in DOMAINS
            if domain["priority"] == 2
        ),
        "domains": DOMAINS,
    }


@router.get("/api/science/domains/{domain_id}")
def get_science_domain(domain_id: str):
    domain = find_domain(domain_id)

    if domain is not None:
        return domain

    raise HTTPException(
        status_code=404,
        detail=f"Scientific domain '{domain_id}' not found.",
    )
