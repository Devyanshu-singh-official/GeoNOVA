
from fastapi import APIRouter, HTTPException

router = APIRouter()

VARIABLES = [
    {
        "id": "precipitation",
        "name": "Precipitation",
        "system": "Atmosphere and Water Cycle",
        "description": (
            "Satellite-derived precipitation estimates used to study "
            "rainfall variability, seasonal patterns and long-term changes."
        ),
        "nasa_mission": "Global Precipitation Measurement (GPM)",
        "instrument": "GPM constellation",
        "dataset": {
            "short_name": "GPM_3IMERGM_07",
            "product": "IMERG V07 Monthly Final Run",
            "doi": "10.5067/GPM/IMERG/3B-MONTH/07",
            "provider": "NASA GES DISC",
            "collection_type": "Monthly gridded satellite-gauge product"
        },
        "measurement": {
            "variable": "precipitation",
            "unit": "mm/hr",
            "description": "Merged satellite-gauge precipitation rate",
            "quality_variables": [
                "precipitationQualityIndex",
                "randomError",
                "gaugeRelativeWeighting"
            ]
        },
        "resolution": {
            "spatial": "0.1 degree (approximately 10 km)",
            "temporal": "Monthly"
        },
        "record": {
            "start": "1998-01",
            "end": "Present, subject to product processing and availability"
        },
        "recommended_analysis": [
            "Monthly precipitation climatology",
            "Annual and seasonal precipitation trends",
            "Rainfall anomalies",
            "Interannual variability"
        ],
        "processing": {
            "recommended_aggregation": "Monthly",
            "annual_method": "Calculate monthly precipitation accumulation before summing by year",
            "quality_control_required": True
        },
        "access": {
            "method": "NASA Earthdata / GES DISC",
            "url": "https://disc.gsfc.nasa.gov/",
            "visualization_url": "https://gpm.nasa.gov/data/imerg",
            "authentication": "NASA Earthdata account may be required for data access"
        },
        "documentation": "https://gpm.nasa.gov/data/directory"
    },
    {
        "id": "land_surface_temperature",
        "name": "Land Surface Temperature",
        "system": "Land and Climate",
        "description": (
            "Satellite-observed land surface temperature for investigating "
            "surface heating, cooling and regional thermal patterns."
        ),
        "nasa_mission": "Terra",
        "instrument": "MODIS",
        "dataset": {
            "short_name": "MOD11A2",
            "version": "061",
            "product": "MODIS/Terra Land Surface Temperature 8-Day L3 Global 1km",
            "doi": "10.5067/MODIS/MOD11A2.061",
            "provider": "NASA LP DAAC",
            "collection_type": "8-day Level-3 gridded product"
        },
        "measurement": {
            "variable": "LST_Day_1km",
            "unit": "Kelvin (scaled)",
            "display_unit": "degrees Celsius",
            "scale_factor": 0.02,
            "conversion": "(raw_value * 0.02) - 273.15",
            "quality_variables": [
                "QC_Day",
                "Clear_sky_days"
            ],
            "description": "Daytime land surface temperature"
        },
        "resolution": {
            "spatial": "1 km",
            "temporal": "8 days"
        },
        "record": {
            "start": "2000-02-18",
            "end": "Present, subject to product processing and availability"
        },
        "recommended_analysis": [
            "Annual mean daytime land surface temperature",
            "Seasonal temperature trends",
            "Temperature anomalies",
            "Spatial warming and cooling patterns"
        ],
        "processing": {
            "recommended_aggregation": "Monthly",
            "annual_method": "Calculate quality-screened monthly means",
            "quality_control_required": True
        },
        "access": {
            "method": "NASA LP DAAC / NASA Earthdata",
            "url": "https://lpdaac.usgs.gov/",
            "authentication": "NASA Earthdata account may be required for downloads"
        },
        "documentation": "https://ladsweb.modaps.eosdis.nasa.gov/missions-and-measurements/products/MOD11A2/"
    },
    {
        "id": "ndvi",
        "name": "Normalized Difference Vegetation Index",
        "system": "Biosphere and Land",
        "description": (
            "Satellite-derived vegetation index for examining vegetation "
            "greenness, seasonal changes and long-term vegetation patterns."
        ),
        "nasa_mission": "Terra",
        "instrument": "MODIS",
        "dataset": {
            "short_name": "MOD13Q1",
            "version": "061",
            "product": "MODIS/Terra Vegetation Indices 16-Day L3 Global 250m",
            "doi": "10.5067/MODIS/MOD13Q1.061",
            "provider": "NASA LP DAAC",
            "collection_type": "16-day Level-3 gridded product"
        },
        "measurement": {
            "variable": "250m 16 days NDVI",
            "unit": "Unitless",
            "scale_factor": 0.0001,
            "valid_range_raw": [-2000, 10000],
            "quality_variables": [
                "SummaryQA",
                "DetailedQA"
            ],
            "description": "Normalized Difference Vegetation Index"
        },
        "resolution": {
            "spatial": "250 m",
            "temporal": "16 days"
        },
        "record": {
            "start": "2000-02-18",
            "end": "Present, subject to product processing and availability"
        },
        "recommended_analysis": [
            "Annual vegetation-index averages",
            "Seasonal vegetation cycles",
            "Vegetation anomalies",
            "Regional greenness trends"
        ],
        "processing": {
            "recommended_aggregation": "Monthly",
            "annual_method": "Quality-screen 16-day observations before monthly aggregation",
            "quality_control_required": True
        },
        "access": {
            "method": "NASA LP DAAC / NASA Earthdata",
            "url": "https://lpdaac.usgs.gov/",
            "authentication": "NASA Earthdata account may be required for downloads"
        },
        "documentation": "https://ladsweb.modaps.eosdis.nasa.gov/missions-and-measurements/products/MOD13Q1/"
    }
]


@router.get("/api/science/variables")
def list_scientific_variables():
    return {
        "platform": "GeoNOVA",
        "module": "Scientific Variable Registry",
        "registry_version": "1.0",
        "total_variables": len(VARIABLES),
        "variables": VARIABLES,
        "notice": (
            "This endpoint describes supported scientific variables and "
            "their source products. It does not claim that historical "
            "observations have already been downloaded or analysed."
        )
    }


@router.get("/api/science/variables/{variable_id}")
def get_scientific_variable(variable_id: str):
    for variable in VARIABLES:
        if variable["id"] == variable_id:
            return variable

    raise HTTPException(
        status_code=404,
        detail=f"Scientific variable '{variable_id}' is not registered."
    )
