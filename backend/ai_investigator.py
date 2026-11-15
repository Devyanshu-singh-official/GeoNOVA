
import re
from copy import deepcopy
from datetime import datetime, timezone
from functools import lru_cache
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field


router = APIRouter()


# ---------------------------------------------------------
# GEONOVA AI INVESTIGATOR
# Transparent, metadata-grounded research assistant
# ---------------------------------------------------------

DOMAIN_KNOWLEDGE = {
    "temperature": {
        "name": "Temperature Intelligence",
        "keywords": [
            "temperature", "heat", "hot", "cold", "warming",
            "land surface temperature", "heatwave"
        ],
        "datasets": [
            {
                "name": "MODIS Terra Land Surface Temperature",
                "product": "MOD11A2.061",
                "resolution": "1 km",
                "temporal_resolution": "8 days",
                "source": "NASA"
            },
            {
                "name": "NASA POWER Temperature",
                "product": "T2M, T2M_MAX, T2M_MIN",
                "resolution": "Gridded point estimates",
                "temporal_resolution": "Daily",
                "source": "NASA POWER"
            }
        ],
        "endpoint": "/api/science/observations/temperature"
    },

    "water": {
        "name": "Water Intelligence",
        "keywords": [
            "water", "rain", "rainfall", "precipitation",
            "flood", "flooding", "humidity", "river", "drought"
        ],
        "datasets": [
            {
                "name": "GPM IMERG",
                "product": "GPM_3IMERGM_07",
                "resolution": "Approximately 0.1 degrees",
                "temporal_resolution": "Monthly product",
                "source": "NASA"
            },
            {
                "name": "NASA POWER Precipitation",
                "product": "PRECTOTCORR",
                "resolution": "Gridded point estimates",
                "temporal_resolution": "Daily",
                "source": "NASA POWER"
            }
        ],
        "endpoint": "/api/science/observations/water"
    },

    "vegetation": {
        "name": "Vegetation & Forest Intelligence",
        "keywords": [
            "vegetation", "forest", "deforestation", "ndvi",
            "greenness", "plant", "crop", "canopy"
        ],
        "datasets": [
            {
                "name": "MODIS Terra Vegetation Indices",
                "product": "MOD13Q1.061",
                "resolution": "250 m",
                "temporal_resolution": "16 days",
                "source": "NASA"
            }
        ],
        "endpoint": "/api/science/variables"
    },

    "atmosphere": {
        "name": "Atmospheric Intelligence",
        "keywords": [
            "atmosphere", "wind", "pressure", "ozone",
            "air", "weather", "cloud", "storm", "cyclone"
        ],
        "datasets": [
            {
                "name": "NASA POWER Atmospheric Parameters",
                "product": "RH2M, WS10M, PS",
                "resolution": "Gridded point estimates",
                "temporal_resolution": "Daily",
                "source": "NASA POWER"
            }
        ],
        "endpoint": "/api/science/observations/atmosphere"
    },

    "ocean": {
        "name": "Ocean Intelligence",
        "keywords": [
            "ocean", "sea", "marine", "sea surface",
            "current", "wave", "coral", "salinity"
        ],
        "datasets": [
            {
                "name": "ISRO Ocean Surface Current",
                "product": "MOSDAC ocean-current product",
                "resolution": "Product-dependent",
                "temporal_resolution": "Product-dependent",
                "source": "ISRO MOSDAC"
            }
        ],
        "endpoint": "/api/isro/catalog"
    },

    "soil": {
        "name": "Soil & Land Intelligence",
        "keywords": [
            "soil", "moisture", "land", "ground",
            "surface", "erosion", "wetness"
        ],
        "datasets": [
            {
                "name": "NASA POWER Soil Wetness",
                "product": "GWETTOP, GWETROOT, GWETPROF",
                "resolution": "Gridded point estimates",
                "temporal_resolution": "Daily",
                "source": "NASA POWER"
            }
        ],
        "endpoint": "/api/science/observations/soil"
    },

    "cryosphere": {
        "name": "Cryosphere Intelligence",
        "keywords": [
            "cryosphere", "glacier", "ice", "snow",
            "ice sheet", "permafrost", "melt"
        ],
        "datasets": [],
        "endpoint": "/api/nasa/collections"
    },

    "human-impact": {
        "name": "Human Impact & Land Change",
        "keywords": [
            "human impact", "urban", "city growth",
            "land change", "land use", "land cover",
            "construction", "settlement"
        ],
        "datasets": [],
        "endpoint": "/api/nasa/collections"
    },

    "climate-carbon": {
        "name": "Climate & Carbon Intelligence",
        "keywords": [
            "climate", "carbon", "emission", "greenhouse",
            "global warming", "climate change", "co2"
        ],
        "datasets": [
            {
                "name": "NASA POWER Climate Parameters",
                "product": "T2M, PRECTOTCORR, RH2M",
                "resolution": "Gridded point estimates",
                "temporal_resolution": "Daily",
                "source": "NASA POWER"
            }
        ],
        "endpoint": "/api/science/observations/climate-carbon"
    },

    "geophysical": {
        "name": "Geophysical Intelligence",
        "keywords": [
            "earthquake", "volcano", "tectonic",
            "seismic", "fault", "eruption",
            "geophysical", "plate boundary"
        ],
        "datasets": [
            {
                "name": "Smithsonian Global Volcanism Program",
                "product": "Holocene Volcanoes",
                "resolution": "Geographic feature locations",
                "temporal_resolution": "Catalogue",
                "source": "Smithsonian Institution"
            },
            {
                "name": "USGS Earthquake Catalog",
                "product": "Earthquake GeoJSON feeds",
                "resolution": "Event locations",
                "temporal_resolution": "Event-based",
                "source": "USGS"
            }
        ],
        "endpoint": "/api/volcanoes"
    }
}


# ---------------------------------------------------------
# REQUEST MODEL
# ---------------------------------------------------------

class InvestigationRequest(BaseModel):
    question: str = Field(
        min_length=3,
        max_length=2000,
    )

    domain_id: Optional[str] = Field(
        default=None,
        max_length=100,
    )


# ---------------------------------------------------------
# TEXT NORMALIZATION
# ---------------------------------------------------------

def normalize_question(question: str) -> str:
    """
    Normalize user input for predictable keyword matching.

    Preserves letters and numbers while converting punctuation
    and repeated whitespace into word separators.
    """

    normalized = question.casefold().strip()

    normalized = re.sub(
        r"[^\w]+",
        " ",
        normalized,
        flags=re.UNICODE,
    )

    return re.sub(r"\s+", " ", normalized).strip()


# ---------------------------------------------------------
# KEYWORD MATCHING
# ---------------------------------------------------------

@lru_cache(maxsize=512)
def compile_keyword_pattern(keyword: str):
    """
    Compile a cached word-boundary-aware keyword expression.

    Multi-word phrases allow flexible whitespace between words.
    """

    normalized = normalize_question(keyword)

    if not normalized:
        return None

    escaped_words = [
        re.escape(word)
        for word in normalized.split()
    ]

    phrase = r"\s+".join(escaped_words)

    return re.compile(
        rf"(?<!\w){phrase}(?!\w)",
        flags=re.UNICODE,
    )


def match_keywords(normalized_question: str, keywords: list[str]):
    matches = []

    for keyword in keywords:
        pattern = compile_keyword_pattern(keyword)

        if pattern is None:
            continue

        if pattern.search(normalized_question):
            matches.append(keyword)

    return matches


# ---------------------------------------------------------
# DOMAIN IDENTIFICATION
# ---------------------------------------------------------

def identify_domains(question: str):
    """
    Identify all configured domains relevant to a question.

    Matching uses complete words and phrases rather than
    arbitrary substring matches.
    """

    normalized_question = normalize_question(question)

    if not normalized_question:
        return []

    matches = []

    for domain_id, domain in DOMAIN_KNOWLEDGE.items():
        matched_keywords = match_keywords(
            normalized_question,
            domain["keywords"],
        )

        if not matched_keywords:
            continue

        matches.append({
            "domain_id": domain_id,
            "name": domain["name"],
            "matched_keywords": matched_keywords,
            "datasets": deepcopy(domain["datasets"]),
            "endpoint": domain["endpoint"],
        })

    # Most specific keyword matches appear first.
    matches.sort(
        key=lambda item: (
            -sum(
                len(keyword.split())
                for keyword in item["matched_keywords"]
            ),
            -len(item["matched_keywords"]),
            item["domain_id"],
        )
    )

    return matches


# ---------------------------------------------------------
# DOMAIN SELECTION
# ---------------------------------------------------------

def get_selected_domain(requested_domain: Optional[str]):
    if requested_domain is None:
        return None

    domain_id = requested_domain.strip().casefold()

    if not domain_id:
        return None

    return DOMAIN_KNOWLEDGE.get(domain_id)


def build_domain_match(domain_id: str, selected: dict):
    return {
        "domain_id": domain_id,
        "name": selected["name"],
        "matched_keywords": list(selected["keywords"]),
        "datasets": deepcopy(selected["datasets"]),
        "endpoint": selected["endpoint"],
    }


# ---------------------------------------------------------
# RESPONSE HELPERS
# ---------------------------------------------------------

def insufficient_context_response(reason: str):
    return {
        "status": "insufficient_domain_context",
        "answer": (
            "I could not confidently identify a scientific domain "
            "from this question. Try mentioning a topic such as "
            "temperature, rainfall, vegetation, ocean conditions, "
            "soil moisture, climate, earthquakes or volcanoes."
        ),
        "identified_domains": [],
        "recommended_datasets": [],
        "recommended_endpoints": [],
        "confidence": {
            "level": "limited",
            "reason": reason,
        },
    }


def build_recommendations(matches):
    recommended_datasets = []
    recommended_endpoints = []

    for match in matches:
        for dataset in match["datasets"]:
            recommended_datasets.append({
                **deepcopy(dataset),
                "domain": match["name"],
            })

        endpoint_record = {
            "domain": match["name"],
            "endpoint": match["endpoint"],
        }

        if endpoint_record not in recommended_endpoints:
            recommended_endpoints.append(endpoint_record)

    return recommended_datasets, recommended_endpoints


# ---------------------------------------------------------
# INVESTIGATION ENGINE
# ---------------------------------------------------------

def build_investigation(
    question: str,
    requested_domain: Optional[str],
):
    if not isinstance(question, str) or not question.strip():
        return insufficient_context_response(
            "The investigation question is empty."
        )

    matches = identify_domains(question)

    if requested_domain:
        domain_id = requested_domain.strip().casefold()

        selected = DOMAIN_KNOWLEDGE.get(domain_id)

        if selected is None:
            return insufficient_context_response(
                f"The requested domain '{domain_id}' is not registered."
            )

        matches = [
            build_domain_match(domain_id, selected)
        ]

    if not matches:
        return insufficient_context_response(
            "No matching domain keywords were identified."
        )

    recommended_datasets, recommended_endpoints = (
        build_recommendations(matches)
    )

    domain_names = ", ".join(
        match["name"]
        for match in matches
    )

    if recommended_datasets:
        dataset_names = ", ".join(
            dataset["name"]
            for dataset in recommended_datasets
        )

        answer = (
            f"This question is most closely related to {domain_names}. "
            f"Relevant registered datasets include: {dataset_names}. "
            "These are dataset recommendations based on GeoNOVA's "
            "configured metadata. No new observation has been retrieved "
            "or analysed by this investigation."
        )
    else:
        answer = (
            f"This question is related to {domain_names}. "
            "GeoNOVA has identified a relevant domain, but its current "
            "investigator catalogue does not yet contain a configured "
            "observation dataset for this topic."
        )

    return {
        "status": "metadata_analysis_complete",
        "answer": answer,
        "identified_domains": [
            {
                "domain_id": match["domain_id"],
                "name": match["name"],
                "matched_keywords": match["matched_keywords"],
            }
            for match in matches
        ],
        "recommended_datasets": recommended_datasets,
        "recommended_endpoints": recommended_endpoints,
        "confidence": {
            "level": "metadata_match",
            "reason": (
                "Domain identification is based on normalized "
                "word-boundary keyword matching. This is not a "
                "measurement-confidence score or scientific validation."
            ),
        },
    }


# ---------------------------------------------------------
# STATUS ENDPOINT
# ---------------------------------------------------------

@router.get("/api/ai/status")
def investigator_status():
    return {
        "service": "GeoNOVA AI Investigator",
        "version": "1.0.0",
        "status": "operational",
        "mode": "metadata-grounded rule-based analysis",
        "language_model_connected": False,
        "observation_analysis_enabled": False,
        "registered_domains": len(DOMAIN_KNOWLEDGE),
        "matching_method": "normalized_word_boundary_keyword_matching",
        "keyword_pattern_cache": {
            "maximum_entries": 512,
            "current_entries": compile_keyword_pattern.cache_info().currsize,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "notice": (
            "The current version identifies scientific domains and "
            "recommends registered datasets. It does not generate "
            "LLM responses or independently analyse observations."
        ),
    }


# ---------------------------------------------------------
# INVESTIGATION ENDPOINT
# ---------------------------------------------------------

@router.post("/api/ai/investigate")
def investigate(request: InvestigationRequest):
    result = build_investigation(
        request.question,
        request.domain_id,
    )

    result["question"] = request.question
    result["timestamp"] = datetime.now(timezone.utc).isoformat()

    return result
