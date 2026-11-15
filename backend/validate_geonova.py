
import argparse
import json
import sys
from datetime import date
from pathlib import Path

import requests


def observations(start_year=2015, count=10, start_value=20.0, step=0.5):
    return [
        {
            "date": f"{start_year + i}-01-01",
            "value": round(start_value + i * step, 4),
        }
        for i in range(count)
    ]


def build_seasonal_observations():
    result = []

    # Synthetic monthly observations for six years.
    for year in range(2018, 2024):
        result.append({
            "date": f"{year}-01-15",
            "value": 10 + (year - 2018) * 0.5,
        })
        result.append({
            "date": f"{year}-02-15",
            "value": 20 + (year - 2018) * 0.2,
        })

    return result


def build_spatial_payload():
    return {
        "variable": "surface_temperature",
        "unit": "degrees_C",
        "significance_level": 0.05,
        "cells": [
            {
                "cell_id": "TEST_NORTH",
                "latitude": 28.6,
                "longitude": 77.2,
                "observations": observations(
                    2015, 10, 20.0, 0.5
                ),
            },
            {
                "cell_id": "TEST_SOUTH",
                "latitude": 13.1,
                "longitude": 80.2,
                "observations": observations(
                    2015, 10, 25.0, 0.0
                ),
            },
        ],
    }


def build_report_payload():
    return {
        "investigation_title": "GeoNOVA Final Validation",
        "variable": "surface_temperature",
        "unit": "degrees_C",
        "significance_level": 0.05,
        "regions": [
            {
                "region_id": "north_test",
                "region_name": "Northern Test Region",
                "latitude": 28.6,
                "longitude": 77.2,
                "source_name": "Synthetic Validation Data",
                "dataset_id": "GEONOVA-TEST-001",
                "source_url": None,
                "spatial_description": "Synthetic test location",
                "observations": observations(
                    2015, 10, 20.0, 0.5
                ),
            },
            {
                "region_id": "south_test",
                "region_name": "Southern Test Region",
                "latitude": 13.1,
                "longitude": 80.2,
                "source_name": "Synthetic Validation Data",
                "dataset_id": "GEONOVA-TEST-001",
                "source_url": None,
                "spatial_description": "Synthetic test location",
                "observations": observations(
                    2015, 10, 25.0, 0.0
                ),
            },
        ],
    }


class GeoNOVAValidator:
    def __init__(self, base_url, timeout=45):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.results = []
        self.openapi = None

    def record(self, name, passed, detail):
        result = {
            "test": name,
            "status": "PASS" if passed else "FAIL",
            "detail": str(detail)[:1000],
        }

        self.results.append(result)

        symbol = "PASS" if passed else "FAIL"
        print(f"[{symbol}] {name}: {detail}")

    def get(self, path):
        return self.session.get(
            self.base_url + path,
            timeout=self.timeout,
        )

    def post(self, path, payload):
        return self.session.post(
            self.base_url + path,
            json=payload,
            timeout=self.timeout,
        )

    def check_health(self):
        try:
            response = self.get("/api/health")

            self.record(
                "Backend health",
                response.ok,
                f"HTTP {response.status_code}",
            )

            return response.ok

        except requests.RequestException as exc:
            self.record("Backend health", False, exc)
            return False

    def load_openapi(self):
        try:
            response = self.get("/openapi.json")
            response.raise_for_status()

            self.openapi = response.json()
            paths = self.openapi.get("paths", {})

            self.record(
                "OpenAPI documentation",
                bool(paths),
                f"{len(paths)} documented API paths",
            )

            return True

        except Exception as exc:
            self.record("OpenAPI documentation", False, exc)
            return False

    def check_route(self, path, name):
        exists = (
            self.openapi is not None
            and path in self.openapi.get("paths", {})
        )

        self.record(
            name,
            exists,
            f"{path} {'registered' if exists else 'not found'}",
        )

        return exists

    def check_historical_routes(self):
        routes = [
            (
                "/api/nasa/power/daily",
                "NASA POWER historical data route",
            ),
            (
                "/api/nasa/power/timeseries",
                "Historical time-series route",
            ),
            (
                "/api/science/trends/analyze",
                "Statistical trend route",
            ),
            (
                "/api/science/seasonality/analyze",
                "Seasonality and dependence route",
            ),
            (
                "/api/science/spatial-trends/analyze",
                "Spatial trend route",
            ),
            (
                "/api/science/reports/multi-region",
                "Multi-region report route",
            ),
        ]

        for path, name in routes:
            self.check_route(path, name)

    def test_statistical_trends(self):
        path = "/api/science/trends/analyze"

        payload = {
            "observations": observations(
                2015, 10, 20.0, 0.5
            )
        }

        try:
            response = self.post(path, payload)

            if not response.ok:
                self.record(
                    "Statistical trend analysis",
                    False,
                    f"HTTP {response.status_code}: {response.text}",
                )
                return

            data = response.json()

            has_result = isinstance(data, dict) and bool(data)

            self.record(
                "Statistical trend analysis",
                has_result,
                "Synthetic observations accepted; response returned.",
            )

        except Exception as exc:
            self.record("Statistical trend analysis", False, exc)

    def test_seasonality(self):
        path = "/api/science/seasonality/analyze"

        payload = {
            "autocorrelation_correction": True,
            "observations": build_seasonal_observations(),
        }

        try:
            response = self.post(path, payload)

            if not response.ok:
                self.record(
                    "Seasonality and dependence",
                    False,
                    f"HTTP {response.status_code}: {response.text}",
                )
                return

            data = response.json()

            valid = (
                data.get("status") == "success"
                and "monthly_results" in data
                and "autocorrelation_summary" in data
            )

            self.record(
                "Seasonality and dependence",
                valid,
                "Monthly analysis and autocorrelation summary returned.",
            )

        except Exception as exc:
            self.record("Seasonality and dependence", False, exc)

    def test_spatial_trends(self):
        path = "/api/science/spatial-trends/analyze"

        try:
            response = self.post(
                path,
                build_spatial_payload(),
            )

            if not response.ok:
                self.record(
                    "Spatial trend analysis",
                    False,
                    f"HTTP {response.status_code}: {response.text}",
                )
                return

            data = response.json()
            geojson = data.get("geojson", {})
            features = geojson.get("features", [])

            valid = (
                data.get("status") == "success"
                and geojson.get("type") == "FeatureCollection"
                and len(features) == 2
                and all(
                    feature.get("geometry", {}).get("type") == "Point"
                    for feature in features
                )
            )

            self.record(
                "Spatial trend analysis",
                valid,
                f"GeoJSON FeatureCollection returned with {len(features)} features.",
            )

        except Exception as exc:
            self.record("Spatial trend analysis", False, exc)

    def test_multi_region_report(self):
        path = "/api/science/reports/multi-region"

        try:
            response = self.post(
                path,
                build_report_payload(),
            )

            if not response.ok:
                self.record(
                    "Multi-region scientific report",
                    False,
                    f"HTTP {response.status_code}: {response.text}",
                )
                return

            data = response.json()
            report = data.get("markdown_report", "")

            valid = (
                data.get("status") == "success"
                and len(data.get("regional_results", [])) == 2
                and len(data.get("findings", [])) > 0
                and "# GeoNOVA Final Validation" in report
            )

            self.record(
                "Multi-region scientific report",
                valid,
                f"Report returned ({len(report)} characters).",
            )

        except Exception as exc:
            self.record(
                "Multi-region scientific report",
                False,
                exc,
            )

    def run(self):
        print("\n========================================")
        print("        GEONOVA VALIDATION SUITE")
        print("========================================")
        print(f"Backend: {self.base_url}\n")

        if not self.check_health():
            print("\nBackend is unavailable. Start FastAPI and retry.")
            return self.save_report()

        if not self.load_openapi():
            print("\nCannot inspect API routes. Check FastAPI startup.")
            return self.save_report()

        self.check_historical_routes()

        # Run the synthetic analysis tests.
        self.test_statistical_trends()
        self.test_seasonality()
        self.test_spatial_trends()
        self.test_multi_region_report()

        return self.save_report()

    def save_report(self):
        passed = sum(
            item["status"] == "PASS"
            for item in self.results
        )

        failed = len(self.results) - passed

        report = {
            "project": "GeoNOVA",
            "validation_type": "Backend integration checks",
            "backend_url": self.base_url,
            "date_utc": date.today().isoformat(),
            "summary": {
                "total_checks": len(self.results),
                "passed": passed,
                "failed": failed,
                "all_passed": failed == 0 and passed > 0,
            },
            "results": self.results,
            "scientific_validation_status": (
                "NOT_ESTABLISHED_BY_THIS_SCRIPT"
            ),
            "notes": [
                "Synthetic observations are used for statistical tests.",
                "NASA endpoint registration does not prove live data retrieval.",
                "Frontend rendering is not tested by this script.",
                "Scientific methods require independent validation.",
            ],
        }

        output = Path(__file__).resolve().parent / "geonova_validation_report.json"

        output.write_text(
            json.dumps(report, indent=2),
            encoding="utf-8",
        )

        print("\n========================================")
        print(f"PASSED: {passed}")
        print(f"FAILED: {failed}")
        print(f"REPORT: {output}")
        print("========================================\n")

        return failed == 0 and passed > 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="GeoNOVA backend validation suite"
    )

    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=45,
    )

    args = parser.parse_args()

    validator = GeoNOVAValidator(
        args.base_url,
        args.timeout,
    )

    success = validator.run()
    sys.exit(0 if success else 1)
