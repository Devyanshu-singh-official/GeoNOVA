
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from smithsonian_volcanoes import router as volcanoes_router
from nasa_eonet import router as nasa_eonet_router
from nasa_earthdata import router as nasa_earthdata_router
from nasa_power import router as nasa_power_router
from isro_services import router as isro_services_router
from variable_registry import router as variable_registry_router
from time_series_engine import router as time_series_engine_router
from earth_domains import router as earth_domains_router
from science_observations import router as science_observations_router
from science_quality import router as science_quality_router
from science_sources import router as science_sources_router
from ai_investigator import router as ai_investigator_router
from evidence_engine import router as evidence_engine_router
from evidence_analysis import router as evidence_analysis_router
from scientific_interpreter import router as scientific_interpreter_router
from llm_integration import router as llm_integration_router
from research_orchestrator import router as research_orchestrator_router
from historical_trends import router as historical_trends_router
from satellite_geospatial import router as satellite_geospatial_router
from confidence_intelligence import router as confidence_intelligence_router
from environmental_anomalies import router as environmental_anomalies_router
from research_reports import router as research_reports_router
from statistical_significance import router as statistical_significance_router
from serial_correlation import router as serial_correlation_router
from scientific_validation import router as scientific_validation_router
from dependence_aware_trends import router as dependence_aware_trends_router
from seasonal_mann_kendall import router as seasonal_mann_kendall_router
from trend_statistics_engine import router as trend_statistics_engine_router
from seasonality_dependence_engine import (
    router as seasonality_dependence_router,
)
from spatial_trend_engine import router as spatial_trend_engine_router
from multi_region_report_engine import (
    router as multi_region_report_router,
)



app = FastAPI(
    title="GeoNOVA Earth Intelligence API",
    description=(
        "Earth observation, environmental monitoring, historical climate "
        "data retrieval, scientific discovery and cross-source intelligence."
    ),
    version="2.4.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Core data providers
app.include_router(volcanoes_router)
app.include_router(nasa_eonet_router)
app.include_router(nasa_earthdata_router)
app.include_router(nasa_power_router)
app.include_router(isro_services_router)
app.include_router(variable_registry_router)

# AI and scientific intelligence
app.include_router(ai_investigator_router)
app.include_router(earth_domains_router)
app.include_router(science_observations_router)
app.include_router(science_quality_router)
app.include_router(science_sources_router)
app.include_router(evidence_engine_router)
app.include_router(evidence_analysis_router)
app.include_router(scientific_interpreter_router)
app.include_router(llm_integration_router)
app.include_router(research_orchestrator_router)
app.include_router(historical_trends_router)
app.include_router(satellite_geospatial_router)
app.include_router(confidence_intelligence_router)
app.include_router(environmental_anomalies_router)
app.include_router(research_reports_router)
app.include_router(statistical_significance_router)
app.include_router(scientific_validation_router)
app.include_router(serial_correlation_router)
app.include_router(dependence_aware_trends_router)
app.include_router(seasonal_mann_kendall_router)
app.include_router(time_series_engine_router)
app.include_router(trend_statistics_engine_router)
app.include_router(seasonality_dependence_router)
app.include_router(spatial_trend_engine_router)
app.include_router(multi_region_report_router)




@app.get("/")
def root():
    return {
        "name": "GeoNOVA Earth Intelligence API",
        "version": app.version,
        "status": "online",
        "documentation": "/docs",
    }


@app.get("/api/health")
def health():
    return {
        "status": "online",
        "platform": "GeoNOVA",
        "version": app.version,
        "modules": {
            "volcanoes": True,
            "nasa_eonet": True,
            "nasa_earthdata_collections": True,
            "nasa_earthdata_granules": True,
            "nasa_power_historical_data": True,
            "isro_services": True,
            "variable_registry": True,
            "scientific_domains": True,
            "science_observations": True,
            "science_quality": True,
            "science_sources": True,
            "ai_investigator": True,
            "research_reports": True,
        },
    }
