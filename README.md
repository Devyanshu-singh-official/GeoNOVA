# GeoNOVA
### Scientific Intelligence & Environmental Research Platform

GeoNOVA is an AI-assisted environmental science and research platform designed to explore environmental datasets, analyze scientific observations, investigate trends, detect anomalies, and examine evidence from multiple scientific data sources.

It combines a Next.js frontend with a FastAPI backend and specialized scientific analysis modules.

> **Development status:** GeoNOVA is actively being developed. Feature implementation, frontend/backend integration, runtime testing, and scientific validation are tracked separately.

---

# 1. Core Capabilities

GeoNOVA is being developed with the following capabilities:

- Environmental data exploration and visualization.
- Multi-source scientific evidence retrieval.
- AI-assisted scientific investigation.
- Cross-source evidence comparison and discrepancy analysis.
- Confidence and agreement intelligence.
- Environmental anomaly detection.
- Historical and temporal trend analysis.
- Seasonal trend analysis.
- Temporal dependence and autocorrelation diagnostics.
- Scientific interpretation and evidence-grounded insights.
- Research report generation.
- Research reproducibility and data provenance.
- Scientific data validation.
- Scientific charts and data exports.

These capabilities support environmental research and analysis. Their outputs should not automatically be interpreted as verified scientific conclusions or operational disaster warnings.

---

# 2. Technology Stack

## Frontend

| Technology | Installed version |
|---|---|
| Next.js | 16.4.6 |
| React | 19.3.0 |
| React DOM | 19.3.0 |
| TypeScript | 5.x |
| Tailwind CSS | 4.3.3 |
| MapLibre GL | 6.18.0 |
| Recharts | 3.10.1 |
| Lucide React | 1.73.0 |
| ESLint | 9.x |

## Backend

| Technology | Installed version |
|---|---|
| Python | Local virtual environment |
| FastAPI | 0.162.7 |
| Uvicorn | 0.54.0 |
| Pydantic | 2.14.3 |
| NumPy | 2.5.4 |
| Pandas | 3.1.1 |
| SciPy | 1.18.1 |
| Xarray | 2026.9.0 |
| Requests | 2.34.2 |
| Python-dotenv | 1.2.4 |

Other installed packages include Starlette, PyYAML, python-dateutil, and networking dependencies.

Versions reflect the currently reported development environment, not necessarily a tested clean installation.

---

# 3. Project Architecture

```text
GeoNOVA/
│
├── backend/
│   ├── main.py
│   ├── ai_investigator.py
│   ├── confidence_intelligence.py
│   ├── dependence_aware_trends.py
│   ├── earth_domains.py
│   ├── environmental_anomalies.py
│   ├── evidence_analysis.py
│   ├── evidence_engine.py
│   ├── historical_trends.py
│   ├── isro_services.py
│   ├── llm_integration.py
│   ├── nasa_earthdata.py
│   ├── nasa_eonet.py
│   ├── research_orchestrator.py
│   ├── research_reports.py
│   ├── satellite_geospatial.py
│   ├── science_observations.py
│   ├── science_quality.py
│   ├── science_sources.py
│   ├── scientific_interpreter.py
│   ├── scientific_validation.py
│   ├── seasonal_mann_kendall.py
│   ├── serial_correlation.py
│   ├── smithsonian_volcanoes.py
│   ├── statistical_significance.py
│   ├── variable_registry.py
│   └── venv/
│
├── src/
│   ├── app/
│   ├── components/
│   └── lib/
│
├── public/
├── package.json
├── next.config.ts
├── tsconfig.json
└── README.md
```

This is a representative project structure. Additional files and components may exist.

## Architecture overview

```text
                  USER
                    |
                    v
             NEXT.JS FRONTEND
                    |
                    v
              FASTAPI BACKEND
                    |
          +---------+---------+
          |                   |
          v                   v
    DATA PROVIDERS       SCIENTIFIC
      AND APIs            ANALYSIS
          |                   |
          +---------+---------+
                    |
                    v
             EVIDENCE ENGINE
                    |
                    v
          AI AND RESEARCH PIPELINE
                    |
                    v
          REPORTS AND VISUALIZATION
```

---

# 4. Requirements

Install the following:

- Node.js with npm.
- Python compatible with the installed backend dependencies.
- Git (recommended).

The project currently uses a local Python virtual environment located at `backend/venv`.

---

# 5. Frontend Installation and Setup

Navigate to the project root:

```cmd
cd C:\Users\DELL\Documents\geonova
```

Install dependencies:

```cmd
npm install
```

Start the development server:

```cmd
npm run dev
```

Open the frontend:

http://localhost:3000

## Available frontend commands

| Command | Purpose |
|---|---|
| `npm run dev` | Start development server |
| `npm run build` | Create production build |
| `npm run start` | Start production server |
| `npm run lint` | Run ESLint |
| `npx tsc --noEmit` | Run TypeScript checks |

---

# 6. Backend Installation and Setup

Navigate to the backend directory:

```cmd
cd C:\Users\DELL\Documents\geonova\backend
```

Create a virtual environment if one does not already exist:

```cmd
python -m venv venv
```

Install the primary packages using the currently reported versions:

```cmd
venv\Scripts\python.exe -m pip install fastapi==0.162.7 uvicorn==0.54.0 pydantic==2.14.3 numpy==2.5.4 pandas==3.1.1 scipy==1.18.1 xarray==2026.9.0 requests==2.34.2 python-dotenv==1.2.4
```

Start the backend:

```cmd
venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Backend API documentation:

http://127.0.0.1:8000/docs

OpenAPI schema:

http://127.0.0.1:8000/openapi.json

**Dependency management:** The current development environment uses a local virtual environment. A committed dependency manifest or lockfile has not yet been established. The package list above documents the primary installed packages and is not a verified complete reproduction of the environment.

---

# 7. Backend Scientific Modules

| Module | Function |
|---|---|
| `ai_investigator.py` | Scientific domain identification |
| `confidence_intelligence.py` | Confidence and source agreement analysis |
| `dependence_aware_trends.py` | Dependence-aware trend analysis |
| `environmental_anomalies.py` | Environmental anomaly detection |
| `evidence_analysis.py` | Cross-source evidence analysis |
| `evidence_engine.py` | Multi-domain evidence retrieval |
| `historical_trends.py` | Historical trend analysis |
| `research_orchestrator.py` | Multi-stage AI research pipeline |
| `research_reports.py` | Research report generation and export |
| `scientific_interpreter.py` | Scientific interpretation |
| `scientific_validation.py` | Reference dataset validation |
| `seasonal_mann_kendall.py` | Seasonal Mann–Kendall analysis |
| `serial_correlation.py` | Temporal correlation diagnostics |
| `statistical_significance.py` | Statistical significance analysis |
| `science_observations.py` | Scientific observation services |
| `science_quality.py` | Data quality checks |
| `science_sources.py` | Scientific source management |
| `satellite_geospatial.py` | Satellite and geospatial services |
| `variable_registry.py` | Environmental variable definitions |

Additional integration modules include NASA Earthdata, NASA EONET, ISRO services, Earth domain information, and Smithsonian volcano data.

---

# 8. API Structure

The backend exposes API endpoints through FastAPI.

Important API groups include:

| API prefix | Purpose |
|---|---|
| `/api/ai/` | AI-assisted research and investigation |
| `/api/science/` | Scientific analysis and statistical methods |
| `/api/reports/` | Research reports and exports |

Consult the live OpenAPI documentation for the exact registered endpoints, request models, and response structures.

---

# 9. Scientific Analysis Methods

GeoNOVA includes or is being developed around methods such as:

- Median and median absolute deviation (MAD).
- Ordinary least-squares regression.
- Mann–Kendall trend analysis.
- Seasonal Mann–Kendall analysis.
- Temporal autocorrelation diagnostics.
- Dependence-aware trend estimation.
- Cross-source comparison.
- Statistical significance analysis.
- Reference dataset comparison.
- Scientific provenance and reproducibility metadata.

## Scientific limitations

- Correlation does not establish causation.
- Agreement between sources does not independently establish accuracy.
- An anomaly does not necessarily indicate an environmental emergency.
- Trend estimates do not automatically establish statistical significance.
- AI-generated interpretations depend on the quality and completeness of supporting evidence.
- External data providers may have different measurement methods, update schedules, and spatial coverage.
- Scientific conclusions require suitable reference datasets and independent validation.

---

# 10. External Data Sources

The backend contains integrations for configured scientific data providers, including:

- NASA Earthdata.
- NASA EONET.
- USGS.
- ISRO-related services.
- Smithsonian volcano data.
- Other configured environmental observation services.

Actual availability depends on provider access, API configuration, data coverage, and service status.

---

# 11. Environment Configuration and Security

Some integrations may require API credentials or provider-specific configuration.

Before deployment:

1. Inspect backend modules for required API keys.
2. Inspect frontend environment-variable references.
3. Configure credentials using environment variables.
4. Keep secrets outside source control.
5. Use production-specific configuration.
6. Restrict backend CORS origins to trusted frontend domains.
7. Use HTTPS for production communication.

Never commit passwords, access tokens, API keys, or private credentials.

The actual environment-variable names must be taken from the application code rather than assumed.

---

# 12. Testing and Quality Assurance

## Frontend TypeScript check

From the project root:

```cmd
npx tsc --noEmit
```

## Frontend production build

```cmd
npm run build
```

## Backend syntax check

From the backend directory:

```cmd
venv\Scripts\python.exe -m compileall .
```

## Backend runtime

```cmd
venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

## Recommended validation stages

1. Python syntax and import checks.
2. Backend startup and router registration.
3. Individual API endpoint tests.
4. Frontend TypeScript checks.
5. Frontend production build.
6. Frontend/backend integration tests.
7. Scientific reference-dataset validation.
8. Production deployment and smoke tests.

A successful syntax check or build does not prove scientific correctness.

---

# 13. Deployment Preparation

GeoNOVA can be prepared for deployment using separate frontend and backend hosting environments.

## Frontend

The Next.js frontend can be deployed to a compatible hosting provider such as Vercel.

Production build:

```cmd
npm run build
```

Production start:

```cmd
npm run start
```

## Backend

The FastAPI backend requires a Python-compatible hosting environment.

Production deployment should account for:

- Production API base URL.
- Secure environment variables.
- HTTPS.
- CORS restrictions.
- API timeouts.
- Logging and monitoring.
- External provider credentials.
- Resource and request limits.

The frontend and backend must be configured to communicate through their production URLs.

**Deployment status:** Production deployment should only be marked complete after hosting, configuration, and runtime verification have succeeded.

---

# 14. Development Roadmap

GeoNOVA follows a fixed 55-task development milestone.

The roadmap covers:

- Scientific data integration.
- Evidence retrieval and cross-validation.
- Statistical and temporal analysis.
- AI-assisted scientific research.
- Research reports and reproducibility.
- Scientific exports.
- Performance optimization.
- API reliability.
- Frontend/backend integration.
- Testing, validation, and deployment preparation.

Implementation, integration testing, and scientific validation are tracked separately.

---

# 15. Development Guidelines

When extending GeoNOVA:

1. Preserve existing API compatibility unless a change is intentional.
2. Validate incoming scientific observations.
3. Handle missing and non-finite values.
4. Document statistical assumptions.
5. Report uncertainty and limitations.
6. Preserve source information and provenance.
7. Test affected endpoints and frontend components.
8. Avoid presenting unvalidated outputs as established scientific facts.

---

# 16. Project Vision

GeoNOVA aims to become a unified scientific intelligence environment where environmental observations, verified data sources, statistical methods, and AI-assisted research work together.

Its long-term objective is to make environmental research more transparent, reproducible, evidence-based, and accessible.

**GeoNOVA — Connecting Environmental Data with Scientific Intelligence.**

---

# 17. License

The project's license has not yet been specified.

Add the chosen open-source or proprietary license before public distribution. Until then, do not assume that the source code is available for unrestricted reuse.