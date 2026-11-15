"use client";

import { useEffect, useRef, useState } from "react";
import type { ElementType } from "react";

import {
  Map as MapLibreMap,
  NavigationControl,
  Popup,
  setWorkerUrl,
} from "maplibre-gl";

import {
  Globe2,
  LayoutDashboard,
  Earth,
  Activity,
  Sun,
  BrainCircuit,
  Database,
  FileText,
  Settings,
  Search,
  Bell,
  ChevronDown,
  ArrowUpRight,
  Layers,
  Maximize2,
  Satellite,
  Waves,
  Compass,
  ShieldCheck,
  RefreshCw,
  Mountain,
  CloudSun,
  TrendingUp,
  Droplets,
  Microscope,
} from "lucide-react";

import ScienceWorkspace from "@/components/ScienceWorkspace";
import MissionControl from "@/components/MissionControl";
import SourceIntegrityPanel from "@/components/SourceIntegrityPanel";
import AIResearchInterface from "@/components/AIResearchInterface";

import {
  SatelliteIntelligencePanel,
  ConfidenceIntelligencePanel,
  EnvironmentalAnomaliesPanel,
} from "@/components/AdvancedIntelligencePanels";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const MAP_STYLE =
  "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

const navigation = [
  { name: "Mission Control", icon: LayoutDashboard },
  { name: "Earth Trends", icon: Earth },
  { name: "Tectonic Intelligence", icon: Activity },
  { name: "Atmospheric Lab", icon: Sun },
  { name: "Science Workspace", icon: Microscope },
  { name: "AI Investigator", icon: BrainCircuit },
];

const researchNavigation = [
  { name: "Data Observatory", icon: Database },
  { name: "Source Integrity", icon: ShieldCheck },
  { name: "Satellite Intelligence", icon: Satellite },
  { name: "Confidence Intelligence", icon: ShieldCheck },
  { name: "Environmental Anomalies", icon: Activity },
  { name: "Research Reports", icon: FileText },
];

const descriptions: Record<string, string> = {
  "Mission Control": "A unified view of Earth's interconnected systems.",
  "Earth Trends": "Explore environmental observations and climate variables.",
  "Tectonic Intelligence":
    "Investigate earthquakes, volcanoes and tectonic structures.",
  "Atmospheric Lab":
    "Explore atmospheric aerosols, precipitation and satellite-derived atmospheric products.",
  "Science Workspace":
    "Explore scientific domains, variables and Earth observation data.",
  "AI Investigator":
    "Investigate scientific questions using evidence-grounded AI analysis.",
  "Data Observatory":
    "Explore official NASA and ISRO data resources.",
  "Source Integrity":
    "Inspect source availability, provenance and service status.",
  "Satellite Intelligence":
    "Discover satellite collections and geospatial metadata.",
  "Confidence Intelligence":
    "Evaluate evidence consistency, source agreement and uncertainty.",
  "Environmental Anomalies":
    "Investigate statistically unusual environmental observations.",
  "Research Reports":
    "Generate and export evidence-based scientific reports.",
};

type MapMode = "overview" | "trends" | "tectonic" | "atmospheric";

type MapLayer = "nasa" | "rainfall" | "vegetation" | "water" | "thermal" | "dark" | "aerosol";

type NasaCollection = {
  id?: string;
  title?: string;
  short_name?: string;
  version?: string;
  provider?: string;
  description?: string;
  granule_count?: string | number;
  has_granules?: boolean;
  browse_available?: boolean;
  source?: string;
  links?: Array<{ title?: string; href?: string }>;
};

function EarthMap({ mode, globe = false, compact = false, initialLayer }: { mode: MapMode; globe?: boolean; compact?: boolean; initialLayer?: MapLayer }) {
  const mapElement = useRef<HTMLDivElement>(null);
  const mapInstance = useRef<MapLibreMap | null>(null);

  const [mapLoaded, setMapLoaded] = useState(false);
  const [selectedLayer, setSelectedLayer] = useState<MapLayer>(
    initialLayer ?? (mode === "trends"
      ? "rainfall"
      : mode === "atmospheric"
      ? "aerosol"
      : mode === "tectonic"
      ? "dark"
      : "nasa")
  );

  const [nasaCount, setNasaCount] = useState(0);
  const [earthquakeCount, setEarthquakeCount] = useState(0);
  const [volcanoCount, setVolcanoCount] = useState(0);

  const [nasaStatus, setNasaStatus] = useState("Waiting for NASA...");
  const [earthquakeStatus, setEarthquakeStatus] =
    useState("Waiting for USGS...");
  const [volcanoStatus, setVolcanoStatus] =
    useState("Waiting for Smithsonian...");

  useEffect(() => {
    if (!mapElement.current || mapInstance.current) return;

    setWorkerUrl("/maplibre-gl-worker.mjs");

    const map = new MapLibreMap({
      container: mapElement.current,
      style: MAP_STYLE,
      center: [25, 18],
      zoom: mode === "overview" ? 1.15 : 1.35,
      minZoom: 1,
      maxZoom: 12,
      attributionControl: true,
    });

    mapInstance.current = map;
    let disposed = false;

    // Mission Control uses MapLibre's native 3D globe projection. The same
    // raster overlays and vector layers are reprojected onto the globe.
    let rotationTimer: ReturnType<typeof setInterval> | undefined;
    let resumeRotationTimer: ReturnType<typeof setTimeout> | undefined;
    let userInteracting = false;
    const pauseRotation = () => {
      userInteracting = true;
      if (resumeRotationTimer) clearTimeout(resumeRotationTimer);
      resumeRotationTimer = setTimeout(() => { userInteracting = false; }, 3500);
    };
    if (globe) {
      map.on("style.load", () => {
        map.setProjection({ type: "globe" });
      });
      map.on("dragstart", pauseRotation);
      map.on("zoomstart", pauseRotation);
      map.on("pitchstart", pauseRotation);
    }

    map.addControl(
      new NavigationControl({ visualizePitch: true }),
      "top-right"
    );

    map.on("error", (event) => {
      console.error("GEONOVA MAP ERROR:", event.error);
    });

    let refreshTimer: ReturnType<typeof setInterval> | undefined;

    // GIBS daily imagery can lag acquisition by a day or more. Use a
    // conservative recent UTC date for the time dimension in REST tile URLs.
    const gibsDate = new Date(Date.now() - 2 * 24 * 60 * 60 * 1000)
      .toISOString()
      .slice(0, 10);

    const addBlueMarble = () => {
      if (map.getSource("nasa-gibs-imagery")) return;

      map.addSource("nasa-gibs-imagery", {
        type: "raster",
        tiles: [
          "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/BlueMarble_NextGeneration/default/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpeg",
        ],
        tileSize: 256,
        attribution: "NASA Global Imagery Browse Services",
        minzoom: 0,
        maxzoom: 8,
      });

      map.addLayer({
        id: "nasa-satellite-layer",
        type: "raster",
        source: "nasa-gibs-imagery",
        paint: {
          "raster-opacity": 1,
          "raster-fade-duration": 0,
        },
      });
    };

    const addRainfallLayer = () => {
      if (map.getSource("nasa-imerg-rainfall")) return;

      map.addSource("nasa-imerg-rainfall", {
        type: "raster",
        tiles: [
          "https://gibs.earthdata.nasa.gov/wmts/epsg3857/nrt/IMERG_Precipitation_Rate_30min_v7_NRT/default/GoogleMapsCompatible_Level6/{z}/{y}/{x}.png",
        ],
        tileSize: 256,
        attribution: "NASA GPM IMERG · NASA GIBS",
        minzoom: 0,
        maxzoom: 6,
      });

      map.addLayer({
        id: "nasa-imerg-rainfall-layer",
        type: "raster",
        source: "nasa-imerg-rainfall",
        paint: {
          "raster-opacity": 0.75,
          "raster-fade-duration": 0,
        },
        layout: {
          visibility: "none",
        },
      });
    };

    const addVegetationLayer = () => {
      if (!map.getSource("nasa-modis-ndvi")) {
        map.addSource("nasa-modis-ndvi", {
          type: "raster",
          tiles: [
            "https://gibs.earthdata.nasa.gov/wms/epsg3857/best/wms.cgi?SERVICE=WMS&VERSION=1.1.1&REQUEST=GetMap&LAYERS=MODIS_Terra_NDVI_8Day&STYLES=&FORMAT=image%2Fpng&TRANSPARENT=TRUE&HEIGHT=256&WIDTH=256&SRS=EPSG%3A3857&BBOX={bbox-epsg-3857}",
          ],
          tileSize: 256,
          attribution: "NASA MODIS Terra NDVI 8-Day · NASA GIBS",
          minzoom: 0,
          maxzoom: 8,
        });
      }

      if (!map.getLayer("nasa-modis-ndvi-layer")) {
        map.addLayer({
          id: "nasa-modis-ndvi-layer",
          type: "raster",
          source: "nasa-modis-ndvi",
          layout: { visibility: "none" },
          paint: {
            "raster-opacity": 0.9,
            "raster-fade-duration": 0,
          },
        });
      }
    };

    const addWaterLayer = () => {
      if (!map.getSource("nasa-modis-water-mask")) {
        map.addSource("nasa-modis-water-mask", {
          type: "raster",
          tiles: [
            "https://gibs.earthdata.nasa.gov/wms/epsg3857/best/wms.cgi?SERVICE=WMS&VERSION=1.1.1&REQUEST=GetMap&LAYERS=MODIS_Water_Mask&STYLES=&FORMAT=image%2Fpng&TRANSPARENT=TRUE&HEIGHT=256&WIDTH=256&SRS=EPSG%3A3857&BBOX={bbox-epsg-3857}",
          ],
          tileSize: 256,
          attribution: "NASA MODIS Water Mask · NASA GIBS",
          minzoom: 0,
          maxzoom: 8,
        });
      }

      if (!map.getLayer("nasa-modis-water-mask-layer")) {
        map.addLayer({
          id: "nasa-modis-water-mask-layer",
          type: "raster",
          source: "nasa-modis-water-mask",
          layout: { visibility: "none" },
          paint: {
            "raster-opacity": 0.9,
            "raster-fade-duration": 0,
          },
        });
      }
    };

    const addThermalLayer = () => {
      // NASA GIBS WMTS: 1 km LST uses GoogleMapsCompatible_Level7.
      // WMTS avoids custom WMS BBOX requests that were producing tile seams.
      // This is satellite land-surface temperature, not a live ground thermometer.
      if (!map.getSource("nasa-modis-thermal")) {
        map.addSource("nasa-modis-thermal", {
          type: "raster",
          tiles: [
            `https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/MODIS_Terra_Land_Surface_Temp_Day/default/${gibsDate}/GoogleMapsCompatible_Level7/{z}/{y}/{x}.png`,
          ],
          tileSize: 256,
          attribution: "NASA MODIS Terra Land Surface Temperature · NASA GIBS",
          minzoom: 0,
          maxzoom: 7,
        });
      }

      if (!map.getLayer("nasa-modis-thermal-layer")) {
        map.addLayer({
          id: "nasa-modis-thermal-layer",
          type: "raster",
          source: "nasa-modis-thermal",
          layout: { visibility: "none" },
          paint: {
            "raster-opacity": 0.82,
            "raster-fade-duration": 0,
            "raster-resampling": "nearest",
          },
        });
      }
    };

    const addOmiAerosolLayer = () => {
      // Use NASA GIBS' current NRT v4 OMI aerosol-index visualization.
      // The older best/OMI_Aerosol_Index tiles were returning HTTP 500 for
      // valid XYZ requests. v4 NRT is the currently published near-real-time
      // layer. It measures UV-absorbing aerosol index, NOT surface PM2.5.
      if (!map.getSource("nasa-omi-aerosol")) {
        map.addSource("nasa-omi-aerosol", {
          type: "raster",
          scheme: "xyz",
          tiles: [
            `https://gibs.earthdata.nasa.gov/wmts/epsg3857/nrt/OMI_Aerosol_Index_v4_NRT/default/${gibsDate}/GoogleMapsCompatible_Level6/{z}/{y}/{x}.png`,
          ],
          tileSize: 256,
          attribution: "NASA Aura OMI Aerosol Index v4 NRT · NASA GIBS",
          minzoom: 0,
          maxzoom: 6,
        });
      }

      if (!map.getLayer("nasa-omi-aerosol-layer")) {
        map.addLayer({
          id: "nasa-omi-aerosol-layer",
          type: "raster",
          source: "nasa-omi-aerosol",
          layout: { visibility: "none" },
          paint: {
            // Keep the overlay legible without obscuring the satellite base.
            "raster-opacity": 0.58,
            "raster-fade-duration": 0,
            "raster-resampling": "linear",
          },
        });
      }
    };

    const addTectonicBoundaries = () => {
      if (map.getSource("tectonic-boundaries")) return;

      map.addSource("tectonic-boundaries", {
        type: "geojson",
        data: "/data/tectonic-boundaries.json",
      });

      map.addLayer({
        id: "tectonic-boundary-lines",
        type: "line",
        source: "tectonic-boundaries",
        paint: {
          "line-color": "#F59E0B",
          "line-width": [
            "interpolate",
            ["linear"],
            ["zoom"],
            1, 0.8,
            4, 1.5,
            7, 2.5,
          ],
          "line-opacity": 0.9,
        },
      });
    };

    const addEarthquakeLayer = () => {
      if (map.getSource("usgs-earthquakes")) return;

      map.addSource("usgs-earthquakes", {
        type: "geojson",
        data: {
          type: "FeatureCollection",
          features: [],
        },
      });

      map.addLayer({
        id: "usgs-earthquake-markers",
        type: "circle",
        source: "usgs-earthquakes",
        paint: {
          "circle-radius": [
            "interpolate",
            ["linear"],
            ["coalesce", ["get", "mag"], 0],
            0, 3,
            2, 4,
            4, 7,
            5, 10,
            7, 15,
          ],
          "circle-color": [
            "step",
            ["coalesce", ["get", "mag"], 0],
            "#38bdf8",
            2, "#22c55e",
            4, "#facc15",
            5, "#fb923c",
            6, "#ef4444",
          ],
          "circle-stroke-color": "#ffffff",
          "circle-stroke-width": 1,
          "circle-opacity": 0.9,
        },
      });

      map.on("mouseenter", "usgs-earthquake-markers", () => {
        map.getCanvas().style.cursor = "pointer";
      });

      map.on("mouseleave", "usgs-earthquake-markers", () => {
        map.getCanvas().style.cursor = "";
      });

      map.on("click", "usgs-earthquake-markers", (event) => {
        const feature = event.features?.[0];
        if (!feature) return;

        const properties = feature.properties ?? {};
        const geometry = feature.geometry as {
          type: string;
          coordinates?: number[];
        };

        const magnitude = Number(properties.mag);
        const depth =
          geometry.type === "Point" &&
          Array.isArray(geometry.coordinates)
            ? Number(geometry.coordinates[2])
            : NaN;

        const observed = Number(properties.time);

        const content = document.createElement("div");
        content.style.color = "#0f172a";
        content.style.minWidth = "210px";

        const heading = document.createElement("strong");
        heading.textContent = `Magnitude ${
          Number.isFinite(magnitude) ? magnitude.toFixed(1) : "Unknown"
        }`;

        const place = document.createElement("p");
        place.textContent = String(
          properties.place ?? "Location unavailable"
        );

        const details = document.createElement("p");
        details.textContent = `Depth: ${
          Number.isFinite(depth) ? `${depth} km` : "Unavailable"
        }`;

        const date = document.createElement("p");
        date.textContent = `Observed: ${
          Number.isFinite(observed)
            ? new Date(observed).toLocaleString()
            : "Unavailable"
        }`;

        const source = document.createElement("p");
        source.textContent = "Source: USGS ComCat";

        content.append(heading, place, details, date, source);

        const url = String(properties.url ?? "");
        if (url.startsWith("https://earthquake.usgs.gov/")) {
          const link = document.createElement("a");
          link.href = url;
          link.target = "_blank";
          link.rel = "noopener noreferrer";
          link.textContent = "Open USGS event record ↗";
          link.style.display = "block";
          link.style.marginTop = "8px";
          link.style.color = "#0369a1";
          content.append(link);
        }

        new Popup()
          .setLngLat(event.lngLat)
          .setDOMContent(content)
          .addTo(map);
      });
    };

    const addVolcanoLayer = () => {
      if (map.getSource("global-volcanoes")) return;

      map.addSource("global-volcanoes", {
        type: "geojson",
        data: {
          type: "FeatureCollection",
          features: [],
        },
      });

      map.addLayer({
        id: "global-volcano-markers",
        type: "circle",
        source: "global-volcanoes",
        minzoom: 0,
        maxzoom: 22,
        paint: {
          "circle-radius": [
            "interpolate",
            ["linear"],
            ["zoom"],
            0, 4.2,
            2, 5.5,
            5, 7,
            8, 9,
          ],
          "circle-color": "#fb536b",
          "circle-stroke-color": "#fff7ed",
          "circle-stroke-width": 1.35,
          "circle-opacity": 1,
          "circle-pitch-alignment": "map",
        },
      });

      map.on("mouseenter", "global-volcano-markers", () => {
        map.getCanvas().style.cursor = "pointer";
      });

      map.on("mouseleave", "global-volcano-markers", () => {
        map.getCanvas().style.cursor = "";
      });

      map.on("click", "global-volcano-markers", (event) => {
        const feature = event.features?.[0];
        if (!feature) return;

        const properties = feature.properties ?? {};

        const name =
          properties.Volcano_Name ??
          properties.NAME ??
          properties.name ??
          "Unnamed volcano";

        const region =
          properties.Country ??
          properties.COUNTRY ??
          properties.Region ??
          properties.region ??
          "Not specified";

        const elevation =
          properties.Elevation ??
          properties.ELEVATION ??
          properties.elevation ??
          "Not available";

        const content = document.createElement("div");
        content.style.color = "#0f172a";

        const heading = document.createElement("strong");
        heading.textContent = String(name);

        const country = document.createElement("p");
        country.textContent = `Region: ${String(region)}`;

        const height = document.createElement("p");
        height.textContent = `Elevation: ${String(elevation)}`;

        const source = document.createElement("p");
        source.textContent = "Smithsonian Global Volcanism Program";

        content.append(heading, country, height, source);

        new Popup()
          .setLngLat(event.lngLat)
          .setDOMContent(content)
          .addTo(map);
      });
    };

    const addNasaEvents = () => {
      if (map.getSource("nasa-events")) return;

      map.addSource("nasa-events", {
        type: "geojson",
        data: {
          type: "FeatureCollection",
          features: [],
        },
      });

      map.addLayer({
        id: "nasa-event-markers",
        type: "circle",
        source: "nasa-events",
        paint: {
          "circle-radius": [
            "interpolate",
            ["linear"],
            ["zoom"],
            1, 4,
            5, 7,
          ],
          "circle-color": [
            "match",
            ["downcase", ["get", "category"]],
            "wildfires", "#fb923c",
            "volcanoes", "#ef4444",
            "severe storms", "#a78bfa",
            "floods", "#38bdf8",
            "sea and lake ice", "#67e8f9",
            "dust and haze", "#facc15",
            "#34d399",
          ],
          "circle-stroke-color": "#ffffff",
          "circle-stroke-width": 1.2,
        },
      });

      map.on("click", "nasa-event-markers", (event) => {
        const feature = event.features?.[0];
        if (!feature) return;

        const properties = feature.properties ?? {};

        const content = document.createElement("div");
        content.style.color = "#0f172a";

        const heading = document.createElement("strong");
        heading.textContent = String(
          properties.title ?? "NASA natural event"
        );

        const category = document.createElement("p");
        category.textContent = `Category: ${String(
          properties.category ?? "Other"
        )}`;

        const date = document.createElement("p");
        date.textContent = `Observed: ${String(
          properties.date ?? "Unavailable"
        )}`;

        const source = document.createElement("p");
        source.textContent = "Source: NASA EONET";

        content.append(heading, category, date, source);

        new Popup()
          .setLngLat(event.lngLat)
          .setDOMContent(content)
          .addTo(map);
      });
    };

    const loadEarthquakes = async () => {
      try {
        setEarthquakeStatus("Loading USGS observations...");

        const response = await fetch(
          "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson"
        );

        if (!response.ok) {
          throw new Error(`USGS HTTP ${response.status}`);
        }

        const data = await response.json();
        const source = map.getSource("usgs-earthquakes");

        if (source && "setData" in source) {
          source.setData(data);
        }

        if (!disposed) {
          setEarthquakeCount(
            Array.isArray(data.features) ? data.features.length : 0
          );
          setEarthquakeStatus(
            `USGS · Updated ${new Date().toLocaleTimeString()}`
          );
        }
      } catch (error) {
        console.error("USGS ERROR:", error);
        if (!disposed) setEarthquakeStatus("USGS feed unavailable");
      }
    };

    const loadVolcanoes = async () => {
      try {
        setVolcanoStatus("Loading Smithsonian volcano catalogue...");

        const controller = new AbortController();
        const timeout = window.setTimeout(() => controller.abort(), 18000);
        let response: Response;
        try {
          response = await fetch(`${API_BASE_URL}/api/volcanoes`, {
            signal: controller.signal,
            cache: "no-store",
          });
        } finally {
          window.clearTimeout(timeout);
        }

        if (!response.ok) {
          // A provider-side 5xx should not break the map or flood the console.
          if (!disposed) {
            setVolcanoStatus(
              `Smithsonian catalogue unavailable (HTTP ${response.status}); other map layers remain active`
            );
          }
          return;
        }

        const data = await response.json();
        const rawFeatures = Array.isArray(data.features) ? data.features : [];
        const features = rawFeatures.filter((feature: any) => {
          const geometry = feature?.geometry;
          const coordinates = geometry?.coordinates;
          return (
            geometry?.type === "Point" &&
            Array.isArray(coordinates) &&
            coordinates.length >= 2 &&
            Number.isFinite(Number(coordinates[0])) &&
            Number.isFinite(Number(coordinates[1])) &&
            Math.abs(Number(coordinates[0])) <= 180 &&
            Math.abs(Number(coordinates[1])) <= 90
          );
        }).map((feature: any) => ({
          ...feature,
          geometry: {
            type: "Point",
            coordinates: [
              Number(feature.geometry.coordinates[0]),
              Number(feature.geometry.coordinates[1]),
            ],
          },
          properties: feature.properties ?? {},
        }));

        if (!features.length) {
          throw new Error(
            `API returned ${rawFeatures.length} records but no valid Point geometries`
          );
        }

        const source = map.getSource("global-volcanoes");
        if (source && "setData" in source) {
          source.setData({ type: "FeatureCollection", features });
        }

        if (!disposed) {
          setVolcanoCount(features.length);
          setVolcanoStatus(
            `Smithsonian GVP · ${features.length.toLocaleString()} volcanoes mapped · ${new Date().toLocaleTimeString()}`
          );
        }
      } catch (error) {
        const message =
          error instanceof Error && error.name === "AbortError"
            ? "request timed out"
            : "network/backend error";
        if (!disposed) {
          setVolcanoStatus(
            `Volcano catalogue unavailable (${message}); other map layers remain active`
          );
        }
      }
    };

    const loadNasaEvents = async () => {
      const normalizeEvents = (data: any): Array<Record<string, unknown>> => {
        // Backend adapter returns { events: [...] }; direct EONET v3 does too.
        return Array.isArray(data?.events) ? data.events : [];
      };

      const findPoint = (value: unknown): [number, number] | null => {
        if (!Array.isArray(value)) return null;
        if (
          value.length >= 2 &&
          typeof value[0] === "number" &&
          typeof value[1] === "number"
        ) {
          return [value[0], value[1]];
        }
        for (const item of value) {
          const result = findPoint(item);
          if (result) return result;
        }
        return null;
      };

      try {
        setNasaStatus("Connecting to NASA EONET...");

        let data: { events?: Array<Record<string, unknown>> } | null = null;
        let backendError = "";

        // Try GeoNOVA's normalized backend first.
        try {
          const controller = new AbortController();
          const timeout = window.setTimeout(() => controller.abort(), 12000);
          try {
            const response = await fetch(`${API_BASE_URL}/api/nasa/events`, {
              signal: controller.signal,
              cache: "no-store",
            });
            if (!response.ok) {
              backendError = `GeoNOVA backend HTTP ${response.status}`;
            } else {
              data = await response.json();
            }
          } finally {
            window.clearTimeout(timeout);
          }
        } catch (error) {
          backendError =
            error instanceof Error && error.name === "AbortError"
              ? "GeoNOVA backend timed out"
              : "GeoNOVA backend unreachable";
        }

        // If the backend's NASA upstream returns 502, try NASA's documented
        // public EONET v3 endpoint directly. No fabricated fallback data.
        let usedDirectNasa = false;
        if (!data) {
          setNasaStatus(`${backendError || "Backend unavailable"}; trying NASA EONET directly...`);
          const controller = new AbortController();
          const timeout = window.setTimeout(() => controller.abort(), 15000);
          try {
            const response = await fetch(
              "https://eonet.gsfc.nasa.gov/api/v3/events?status=open&limit=100",
              {
                signal: controller.signal,
                cache: "no-store",
                headers: { Accept: "application/json" },
              }
            );
            if (!response.ok) {
              throw new Error(`NASA EONET HTTP ${response.status}`);
            }
            data = await response.json();
            usedDirectNasa = true;
          } finally {
            window.clearTimeout(timeout);
          }
        }

        const events = normalizeEvents(data);
        const features = events.flatMap((event) => {
          // Backend adapter supplies `coordinates`; raw EONET supplies geometry[].
          const coordinates =
            findPoint(event.coordinates) ??
            findPoint(
              Array.isArray(event.geometry)
                ? event.geometry.map((item: any) => item?.coordinates)
                : null
            );
          if (!coordinates) return [];

          const rawCategories = Array.isArray(event.categories)
            ? event.categories
            : Array.isArray(event.category)
              ? event.category
              : [];
          const categories = rawCategories
            .map((item: any) =>
              typeof item === "string" ? item : item?.title
            )
            .filter((value: unknown): value is string => typeof value === "string");

          const latestGeometry = Array.isArray(event.geometry)
            ? [...event.geometry].sort((a: any, b: any) =>
                String(b?.date ?? "").localeCompare(String(a?.date ?? ""))
              )[0]
            : null;

          return [{
            type: "Feature" as const,
            geometry: {
              type: "Point" as const,
              coordinates,
            },
            properties: {
              title: String(event.title ?? "NASA natural event"),
              category: categories[0] ?? "Other",
              date: String(event.date ?? latestGeometry?.date ?? "Unavailable"),
              source: "NASA EONET",
            },
          }];
        });

        const source = map.getSource("nasa-events");
        if (source && "setData" in source) {
          source.setData({ type: "FeatureCollection", features });
        }

        if (!disposed) {
          setNasaCount(features.length);
          setNasaStatus(
            `${usedDirectNasa ? "NASA EONET direct" : "NASA EONET via GeoNOVA"} · ${features.length} mapped · ${new Date().toLocaleTimeString()}`
          );
        }
      } catch (error) {
        console.error("NASA EONET UNAVAILABLE:", error);
        if (!disposed) {
          const message = error instanceof Error ? error.message : "request failed";
          setNasaStatus(`NASA EONET unavailable (${message}); other map layers remain active`);
        }
      }
    };

    map.on("load", () => {
      if (globe && !rotationTimer) {
        rotationTimer = setInterval(() => {
          if (!userInteracting && !disposed) {
            map.rotateTo((map.getBearing() + 0.045) % 360, { duration: 90 });
          }
        }, 90);
      }

      if (mode === "overview" || mode === "trends") {
        addBlueMarble();
        addRainfallLayer();
        addVegetationLayer();
        addWaterLayer();
        addThermalLayer();
        addOmiAerosolLayer();
      }

      if (mode === "atmospheric") {
        addOmiAerosolLayer();
      }

      if (mode === "overview" || mode === "tectonic") {
        addTectonicBoundaries();
        addEarthquakeLayer();
        addVolcanoLayer();
      }

      if (mode === "overview") {
        addNasaEvents();
      }

      setMapLoaded(true);

      if (mode === "overview") {
        void loadNasaEvents();
      }

      if (mode === "overview" || mode === "tectonic") {
        void loadEarthquakes();
        void loadVolcanoes();
      }

      refreshTimer = setInterval(() => {
        if (mode === "overview") {
          void loadNasaEvents();
        }

        if (mode === "overview" || mode === "tectonic") {
          void loadEarthquakes();
          void loadVolcanoes();
        }
      }, 5 * 60 * 1000);
    });

    return () => {
      disposed = true;

      if (refreshTimer) clearInterval(refreshTimer);
      if (rotationTimer) clearInterval(rotationTimer);
      if (resumeRotationTimer) clearTimeout(resumeRotationTimer);

      map.remove();
      mapInstance.current = null;
    };
  }, [mode]);

  useEffect(() => {
    const map = mapInstance.current;
    if (!map || !mapLoaded) return;

    const setVisibility = (id: string, visible: boolean) => {
      if (map.getLayer(id)) {
        map.setLayoutProperty(
          id,
          "visibility",
          visible ? "visible" : "none"
        );
      }
    };

    setVisibility(
      "nasa-satellite-layer",
      mode !== "atmospheric" && selectedLayer === "nasa"
    );

    setVisibility(
      "nasa-imerg-rainfall-layer",
      selectedLayer === "rainfall"
    );

    setVisibility(
      "nasa-modis-ndvi-layer",
      selectedLayer === "vegetation"
    );

    setVisibility(
      "nasa-modis-water-mask-layer",
      selectedLayer === "water"
    );

    setVisibility(
      "nasa-modis-thermal-layer",
      selectedLayer === "thermal"
    );

    setVisibility(
      "nasa-omi-aerosol-layer",
      selectedLayer === "aerosol"
    );
  }, [selectedLayer, mapLoaded, mode]);

  const layerButton = (
    layer: MapLayer,
    label: string,
    Icon: ElementType
  ) => (
    <button
      key={layer}
      onClick={() => setSelectedLayer(layer)}
      aria-pressed={selectedLayer === layer}
      className={`flex w-full items-center gap-2 rounded-lg px-3 py-2 text-xs transition ${
        selectedLayer === layer
          ? "bg-sky-500/15 text-sky-300"
          : "text-slate-400 hover:bg-white/5"
      }`}
    >
      <Icon size={15} />
      {label}
    </button>
  );

  return (
    <div className="relative h-full w-full">
      <div ref={mapElement} className="map-container" />

      {mapLoaded && !compact && (
        <>
          {(mode === "overview" || mode === "tectonic") && (
            <div className="absolute bottom-3 left-3 z-10 rounded-lg border border-slate-700 bg-slate-950/95 px-3 py-2 shadow-xl">
              {mode === "overview" && (
                <>
                  <div className="text-[10px] font-semibold text-slate-200">
                    {nasaCount} NASA events mapped
                  </div>
                  <p className="mt-1 text-[9px] text-slate-400">
                    {nasaStatus}
                  </p>
                </>
              )}

              <div className="mt-2 border-t border-slate-800 pt-2">
                <div className="text-[10px] font-semibold text-slate-200">
                  {earthquakeCount} USGS earthquakes
                </div>
                <p className="mt-1 text-[9px] text-slate-400">
                  {earthquakeStatus}
                </p>
              </div>

              <div className="mt-2 border-t border-slate-800 pt-2">
                <div className="text-[10px] font-semibold text-slate-200">
                  {volcanoCount} volcano records
                </div>
                <p className="mt-1 text-[9px] text-slate-400">
                  {volcanoStatus}
                </p>
              </div>
            </div>
          )}

          <div className="absolute bottom-3 right-3 z-10 w-48 rounded-xl border border-slate-700 bg-slate-950/95 p-2 shadow-xl">
            <p className="px-2 py-1 text-[9px] font-bold tracking-widest text-slate-500">
              MAP LAYERS
            </p>

            {(mode === "overview" || mode === "trends") && (
              <>
                {layerButton("nasa", "NASA Blue Marble", Globe2)}
                {layerButton("rainfall", "GPM IMERG Rainfall", Waves)}
                {layerButton("vegetation", "MODIS Vegetation (NDVI)", Earth)}
                {layerButton("water", "MODIS Water Mask", Droplets)}
                {layerButton("thermal", "MODIS Land Surface Temp", Sun)}
                {layerButton("aerosol", "Aura OMI Aerosol Index", Sun)}
                {layerButton("dark", "Dark Reference", Layers)}
              </>
            )}

            {mode === "atmospheric" && (
              <>
                {layerButton("aerosol", "Aura OMI UV Aerosol Index", Sun)}
                {layerButton("dark", "Dark Reference", Layers)}
              </>
            )}

            {mode === "tectonic" && (
              <div className="px-2 py-2 text-[10px] text-slate-400">
                <div className="flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full bg-orange-400" />
                  Plate boundaries
                </div>
                <div className="mt-2 flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full bg-rose-400" />
                  Volcano records
                </div>
                <div className="mt-2 flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full bg-yellow-400" />
                  Earthquake observations
                </div>
              </div>
            )}

            {selectedLayer === "rainfall" && (
              <div className="mt-2 border-t border-slate-800 px-2 pt-3">
                <p className="text-[9px] font-bold tracking-widest text-slate-500">
                  PRECIPITATION RATE
                </p>
                <div className="mt-2 h-2 rounded-full bg-gradient-to-r from-blue-500 via-cyan-300 via-yellow-300 to-red-500" />
                <div className="mt-1 flex justify-between text-[8px] text-slate-500">
                  <span>Lower</span>
                  <span>Higher</span>
                </div>
                <p className="mt-2 text-[9px] text-slate-400">
                  NASA GPM IMERG · 30-minute visualization
                </p>
              </div>
            )}

            {selectedLayer === "vegetation" && (
              <p className="mt-2 border-t border-slate-800 px-2 pt-3 text-[9px] text-slate-400">
                NASA MODIS Terra · 8-day Normalized Difference Vegetation Index (NDVI)
              </p>
            )}

            {selectedLayer === "water" && (
              <p className="mt-2 border-t border-slate-800 px-2 pt-3 text-[9px] text-slate-400">
                NASA MODIS · Land/water classification mask
              </p>
            )}

            {selectedLayer === "thermal" && (
              <div className="mt-2 border-t border-slate-800 px-2 pt-3 text-[9px] text-slate-400">
                <p className="font-semibold text-amber-300">LAND SURFACE TEMPERATURE</p>
                <p className="mt-1">NASA Terra MODIS · daytime LST · daily visualization · native product units: Kelvin (K).</p>
                <p className="mt-1">Cloud-screened satellite retrieval; not air temperature. Coverage and latest date depend on product availability.</p>
              </div>
            )}

            {selectedLayer === "aerosol" && (
              <div className="mt-2 border-t border-slate-800 px-2 pt-3 text-[9px] text-slate-400">
                <p className="font-semibold text-violet-300">UV AEROSOL INDEX</p>
                <p className="mt-1">NASA Aura OMI v4 NRT · detects UV-absorbing aerosol signals such as smoke and dust. It is not ozone concentration or surface PM2.5.</p>
              </div>
            )}
          </div>
        </>
      )}

      {!mapLoaded && (
        <div className="absolute inset-0 z-10 flex items-center justify-center bg-slate-950/70 text-xs text-slate-400">
          Initializing {mode} map...
        </div>
      )}
    </div>
  );
}

function IsroDataPanel() {
  type IsroProduct = {
    id: string;
    title: string;
    category: string;
    description: string;
    coverage: string;
    access: string;
    url: string;
    source: string;
  };

  type ServiceStatus = {
    status: string;
    message: string;
  };

  const [products, setProducts] = useState<IsroProduct[]>([]);
  const [services, setServices] =
    useState<Record<string, ServiceStatus> | null>(null);
  const [loading, setLoading] = useState(true);
  const [checking, setChecking] = useState(false);
  const [catalogError, setCatalogError] = useState("");
  const [statusError, setStatusError] = useState("");

  async function loadIsroDirectory() {
    setChecking(true);
    setCatalogError("");
    setStatusError("");

    const catalogTask = fetch(`${API_BASE_URL}/api/isro/catalog`)
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`Catalogue HTTP ${response.status}`);
        }

        const data = await response.json();
        setProducts(Array.isArray(data.products) ? data.products : []);
      })
      .catch((error) => {
        setCatalogError(
          error instanceof Error ? error.message : "Catalogue failed"
        );
      });

    const statusTask = fetch(`${API_BASE_URL}/api/isro/status`)
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`Status HTTP ${response.status}`);
        }

        const data = await response.json();

        if (!data.services) {
          throw new Error("Backend response does not contain services");
        }

        setServices(data.services);
      })
      .catch((error) => {
        setStatusError(
          error instanceof Error ? error.message : "Status failed"
        );
        setServices(null);
      });

    await Promise.all([catalogTask, statusTask]);

    setLoading(false);
    setChecking(false);
  }

  useEffect(() => {
    void loadIsroDirectory();
  }, []);

  const statusLabel = (status?: string) => {
    if (status === "reachable") return "Reachable";
    if (status === "unverified") return "Unverified";
    if (status === "unavailable") return "Unavailable";
    return "Unknown";
  };

  const statusClass = (status?: string) => {
    if (status === "reachable") return "text-emerald-300";
    if (status === "unavailable") return "text-rose-300";
    return "text-amber-300";
  };

  const ServiceCard = ({
    title,
    service,
  }: {
    title: string;
    service?: ServiceStatus;
  }) => (
    <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-4">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-semibold">{title}</span>
        <span className={`text-[10px] ${statusClass(service?.status)}`}>
          {checking && !service ? "Checking..." : statusLabel(service?.status)}
        </span>
      </div>
      <p className="mt-2 text-[10px] leading-relaxed text-slate-500">
        {service?.message ?? "Waiting for backend response."}
      </p>
    </div>
  );

  return (
    <section className="space-y-4">
      <div className="panel p-5">
        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div>
            <div className="eyebrow mb-2">
              INDIAN SPACE RESEARCH ORGANISATION
            </div>
            <h3 className="font-display text-xl font-semibold">
              ISRO data services
            </h3>
            <p className="mt-2 max-w-2xl text-xs leading-relaxed text-slate-500">
              Official Bhuvan geospatial services and MOSDAC meteorological,
              hydrological and oceanographic product records.
            </p>
          </div>

          <button
            onClick={() => void loadIsroDirectory()}
            disabled={checking}
            className="rounded-lg border border-slate-700 px-3 py-2 text-[10px] text-cyan-300 hover:bg-slate-800 disabled:opacity-50"
          >
            {checking ? "Checking..." : "Refresh ISRO status ↻"}
          </button>
        </div>

        <div className="mt-5 grid grid-cols-1 gap-3 md:grid-cols-2">
          <ServiceCard title="Bhuvan OGC WMS" service={services?.bhuvan_wms} />
          <ServiceCard title="MOSDAC public portal" service={services?.mosdac_portal} />
        </div>

        <div className="mt-4 flex flex-wrap gap-4">
          <a
            href="https://www.nrsc.gov.in/nrscnew/Services_Bhuvan_overview.php"
            target="_blank"
            rel="noreferrer"
            className="text-[10px] text-sky-300"
          >
            Bhuvan service information ↗
          </a>
          <a
            href="https://www.mosdac.gov.in/data-access-policy"
            target="_blank"
            rel="noreferrer"
            className="text-[10px] text-sky-300"
          >
            MOSDAC data-access policy ↗
          </a>
        </div>
      </div>

      {statusError && (
        <div className="panel p-3 text-xs text-rose-300">
          ISRO status error: {statusError}
        </div>
      )}

      {catalogError && (
        <div className="panel p-3 text-xs text-rose-300">
          ISRO catalogue error: {catalogError}
        </div>
      )}

      <div className="flex items-center justify-between">
        <div>
          <div className="panel-title">ISRO product directory</div>
          <p className="mt-1 text-[10px] text-slate-500">
            {loading ? "Loading..." : `${products.length} curated product records`}
          </p>
        </div>
        <span className="text-[9px] text-slate-500">MOSDAC RECORDS</span>
      </div>

      <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
        {products.map((product) => (
          <article key={product.id} className="panel p-4">
            <div className="mb-2 text-[9px] tracking-widest text-cyan-400">
              {product.category}
            </div>
            <h4 className="text-sm font-semibold">{product.title}</h4>
            <p className="mt-3 text-[10px] leading-relaxed text-slate-400">
              {product.description}
            </p>
            <div className="mt-3 rounded-md bg-slate-900/80 p-2">
              <div className="text-[9px] text-slate-500">COVERAGE</div>
              <div className="mt-1 text-[10px] text-slate-200">
                {product.coverage}
              </div>
            </div>
            <p className="mt-3 text-[9px] leading-relaxed text-amber-200/80">
              ACCESS · {product.access}
            </p>
            <div className="mt-3 flex items-center justify-between gap-2 border-t border-slate-800 pt-3">
              <span className="text-[9px] text-slate-600">{product.source}</span>
              <a
                href={product.url}
                target="_blank"
                rel="noreferrer"
                className="text-[10px] font-semibold text-cyan-300"
              >
                Open official record ↗
              </a>
            </div>
          </article>
        ))}
      </div>

      <div className="panel p-4">
        <div className="flex items-center gap-2 text-xs font-semibold">
          <ShieldCheck size={15} className="text-emerald-400" />
          Access and integration notes
        </div>
        <p className="mt-2 text-[10px] leading-relaxed text-slate-500">
          MOSDAC distinguishes anonymous, registered general and privileged
          users. Public metadata and some open-data products may be accessible
          without sign-in, while other downloads require additional access.
          This directory does not claim that product files are already
          downloaded or mapped.
        </p>
      </div>
    </section>
  );
}

function DatasetExplorer() {
  const [keyword, setKeyword] = useState("MODIS");
  const [collections, setCollections] = useState<NasaCollection[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [error, setError] = useState("");

  async function searchCollections(searchTerm = keyword) {
    const term = searchTerm.trim();

    if (term.length < 2) {
      setError("Enter at least 2 characters.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/nasa/collections?keyword=${encodeURIComponent(term)}&page_size=15`
      );

      if (!response.ok) {
        throw new Error(`NASA dataset search HTTP ${response.status}`);
      }

      const data = await response.json();
      setCollections(data.collections ?? []);
      setSearched(true);
    } catch (err) {
      setError(
        err instanceof Error
          ? `${err.message}. Check the FastAPI backend.`
          : "Could not reach NASA CMR."
      );
      setCollections([]);
      setSearched(true);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void searchCollections("MODIS");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const quickSearches = ["MODIS", "VIIRS", "GPM", "MERRA-2", "GRACE"];

  return (
    <section className="space-y-5">
      <div className="panel p-5">
        <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-end">
          <div>
            <div className="eyebrow mb-2">NASA / COMMON METADATA REPOSITORY</div>
            <h3 className="font-display text-xl font-semibold">
              Dataset discovery
            </h3>
            <p className="mt-2 max-w-2xl text-xs leading-relaxed text-slate-500">
              Search NASA Earth science collections by mission, instrument or
              research variable. Access conditions depend on each dataset.
            </p>
          </div>
          <div className="rounded-lg border border-slate-700 px-3 py-2 text-[10px] text-slate-500">
            SOURCE · NASA CMR
          </div>
        </div>

        <form
          className="mt-5 flex flex-col gap-2 sm:flex-row"
          onSubmit={(event) => {
            event.preventDefault();
            void searchCollections();
          }}
        >
          <input
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
            placeholder="Search MODIS, VIIRS, precipitation, ozone..."
            className="min-w-0 flex-1 rounded-lg border border-slate-700 bg-slate-950/70 px-4 py-3 text-sm text-slate-100 outline-none focus:border-sky-500"
          />
          <button
            type="submit"
            disabled={loading}
            className="rounded-lg bg-sky-500 px-5 py-3 text-sm font-semibold text-slate-950 hover:bg-sky-400 disabled:opacity-50"
          >
            {loading ? "Searching..." : "Search datasets"}
          </button>
        </form>

        <div className="mt-3 flex flex-wrap gap-2">
          <span className="py-1 text-[10px] text-slate-500">QUICK SEARCH</span>
          {quickSearches.map((term) => (
            <button
              key={term}
              onClick={() => {
                setKeyword(term);
                void searchCollections(term);
              }}
              className="rounded-full border border-slate-700 px-3 py-1 text-[10px] text-slate-400 hover:border-sky-500 hover:text-sky-300"
            >
              {term}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-rose-500/30 bg-rose-500/5 p-4 text-xs text-rose-300">
          {error}
        </div>
      )}

      <div className="flex items-center justify-between">
        <div>
          <div className="panel-title">Catalogue results</div>
          <p className="mt-1 text-[10px] text-slate-500">
            {searched
              ? `${collections.length} collections returned for "${keyword}"`
              : "Run a search to discover NASA collections."}
          </p>
        </div>

        {searched && (
          <button
            onClick={() => void searchCollections()}
            className="flex items-center gap-2 text-[10px] text-sky-300"
          >
            <RefreshCw size={13} /> Refresh
          </button>
        )}
      </div>

      {loading && (
        <div className="panel p-8 text-center text-xs text-slate-400">
          Querying NASA Common Metadata Repository...
        </div>
      )}

      {!loading && searched && collections.length === 0 && !error && (
        <div className="panel p-8 text-center text-xs text-slate-400">
          No collections returned. Try a broader keyword.
        </div>
      )}

      {!loading && collections.length > 0 && (
        <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
          {collections.map((item, index) => {
            const metadataLink =
              item.links?.find((link) =>
                link.href?.includes("earthdata.nasa.gov")
              ) ?? item.links?.[0];

            return (
              <article
                key={item.id ?? `${item.short_name}-${index}`}
                className="panel p-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="mb-2 text-[9px] tracking-widest text-sky-400">
                      {item.short_name || "NASA COLLECTION"}
                    </div>
                    <h4 className="text-sm font-semibold leading-snug">
                      {item.title || "Untitled NASA collection"}
                    </h4>
                  </div>
                  <Database size={17} className="shrink-0 text-slate-500" />
                </div>

                <p className="mt-3 line-clamp-4 text-[10px] leading-relaxed text-slate-400">
                  {item.description || "No collection summary provided."}
                </p>

                <div className="mt-4 grid grid-cols-2 gap-2">
                  {[
                    ["PROVIDER", item.provider || "NASA CMR"],
                    ["VERSION", item.version || "Not specified"],
                    ["GRANULES", item.granule_count ?? "Not listed"],
                    [
                      "BROWSE DATA",
                      item.browse_available ? "Available" : "Not indicated",
                    ],
                  ].map(([label, value]) => (
                    <div key={label} className="rounded-md bg-slate-900/80 p-2">
                      <div className="text-[9px] text-slate-500">{label}</div>
                      <div className="mt-1 text-[10px] text-slate-200">
                        {value}
                      </div>
                    </div>
                  ))}
                </div>

                <div className="mt-4 flex items-center justify-between gap-3 border-t border-slate-800 pt-3">
                  <span className="text-[9px] text-slate-600">
                    NASA CMR catalogue record
                  </span>
                  {metadataLink?.href ? (
                    <a
                      href={metadataLink.href}
                      target="_blank"
                      rel="noreferrer"
                      className="text-[10px] font-semibold text-sky-300"
                    >
                      Open dataset record ↗
                    </a>
                  ) : (
                    <span className="text-[10px] text-slate-600">
                      No external link
                    </span>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      )}

      <IsroDataPanel />

      <div className="panel p-4">
        <div className="flex items-center gap-2 text-xs font-semibold">
          <ShieldCheck size={15} className="text-emerald-400" />
          Data interpretation note
        </div>
        <p className="mt-2 text-[10px] leading-relaxed text-slate-500">
          A collection listing confirms that metadata exists in NASA CMR. It
          does not automatically confirm that data are open, downloadable or
          suitable for every analysis.
        </p>
      </div>
    </section>
  );
}

function EarthTrendsPanel() {
  return (
    <div className="space-y-4">
      <section className="panel p-4">
        <div className="flex flex-col justify-between gap-3 md:flex-row md:items-center">
          <div>
            <div className="eyebrow mb-2">EARTH SYSTEM OBSERVATIONS</div>
            <h3 className="font-display text-lg font-semibold">
              Environmental observation map
            </h3>
            <p className="mt-1 text-[10px] text-slate-500">
              Explore NASA imagery, rainfall, vegetation and land/water patterns.
            </p>
          </div>
          <span className="rounded-lg border border-slate-700 px-3 py-2 text-[9px] text-cyan-300">
            NASA GIBS / MODIS / GPM
          </span>
        </div>
      </section>

      <section className="panel overflow-hidden p-3">
        <div className="mb-2 flex items-center justify-between px-2 py-2">
          <div>
            <div className="panel-title">Global Earth trends map</div>
            <p className="mt-1 text-[10px] text-slate-500">
              Original full-size flat satellite map with selectable environmental layers.
            </p>
          </div>
          <Satellite size={17} className="text-sky-400" />
        </div>
        <div className="relative h-[440px] md:h-[560px]">
          <EarthMap mode="trends" />
        </div>
      </section>

      <section className="panel p-4">
        <div className="mb-3 flex items-center justify-between gap-3">
          <div>
            <div className="eyebrow mb-1">FACTOR EXPLORER</div>
            <h3 className="panel-title">Climate factor globes</h3>
            <p className="mt-1 text-[10px] text-slate-500">Each rotating mini-globe displays its own environmental layer. The full-size flat map above remains available.</p>
          </div>
          <Globe2 size={19} className="text-cyan-300" />
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {[
            { layer: "thermal" as MapLayer, title: "Thermal", detail: "MODIS land-surface temperature", source: "NASA Terra MODIS", color: "text-amber-300" },
            { layer: "rainfall" as MapLayer, title: "Precipitation", detail: "GPM IMERG precipitation rate", source: "NASA GPM", color: "text-cyan-300" },
            { layer: "vegetation" as MapLayer, title: "Vegetation", detail: "NDVI vegetation index", source: "NASA MODIS", color: "text-emerald-300" },
            { layer: "water" as MapLayer, title: "Water", detail: "Land / water classification", source: "NASA MODIS", color: "text-sky-300" },
            { layer: "aerosol" as MapLayer, title: "Aerosol", detail: "UV-absorbing aerosol index", source: "NASA Aura OMI", color: "text-violet-300" },
          ].map((factor) => (
            <article key={factor.layer} className="overflow-hidden rounded-xl border border-slate-800 bg-slate-950/70 p-3">
              <div className="mb-2 flex items-start justify-between gap-2">
                <div>
                  <h4 className={`text-xs font-semibold ${factor.color}`}>{factor.title}</h4>
                  <p className="mt-1 text-[9px] text-slate-400">{factor.detail}</p>
                </div>
                <span className="text-[8px] text-slate-600">ROTATING GLOBE</span>
              </div>
              <div className="relative h-[180px] overflow-hidden rounded-lg border border-slate-800 bg-black">
                <EarthMap mode="trends" globe compact initialLayer={factor.layer} />
              </div>
              <p className="mt-2 text-[9px] text-slate-500">Source: {factor.source}</p>
            </article>
          ))}
        </div>
      </section>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <article className="panel p-4">
          <Droplets size={20} className="text-cyan-400" />
          <h4 className="mt-3 text-sm font-semibold">Precipitation</h4>
          <p className="mt-2 text-[10px] leading-relaxed text-slate-500">
            NASA GPM IMERG provides precipitation-rate visualizations at
            approximately 30-minute intervals.
          </p>
          <div className="mt-3 text-[9px] text-cyan-300">
            SOURCE · NASA GPM
          </div>
        </article>

        <article className="panel p-4">
          <Earth size={20} className="text-emerald-400" />
          <h4 className="mt-3 text-sm font-semibold">Land and surface</h4>
          <p className="mt-2 text-[10px] leading-relaxed text-slate-500">
            The map provides MODIS Terra 8-day NDVI vegetation patterns and a
            MODIS land/water mask for distinguishing mapped water areas.
          </p>
          <div className="mt-3 text-[9px] text-emerald-300">
            SOURCE · NASA MODIS / GIBS
          </div>
        </article>

        <article className="panel p-4">
          <TrendingUp size={20} className="text-violet-400" />
          <h4 className="mt-3 text-sm font-semibold">Long-term analysis</h4>
          <p className="mt-2 text-[10px] leading-relaxed text-slate-500">
            Historical trend analysis will use time-series datasets such as
            MERRA-2 and other validated Earth science collections.
          </p>
          <div className="mt-3 text-[9px] text-violet-300">
            NEXT · HISTORICAL TIME SERIES
          </div>
        </article>
      </div>

      <section className="panel p-4">
        <div className="flex items-center gap-2 text-xs font-semibold">
          <Microscope size={16} className="text-sky-400" />
          Research interpretation
        </div>
        <p className="mt-2 text-[10px] leading-relaxed text-slate-500">
          The rainfall layer is a satellite-derived observation visualization,
          not a rainfall forecast. A single map snapshot does not establish a
          long-term climate trend. Historical comparisons require consistent
          datasets, time ranges and statistical analysis.
        </p>
      </section>
    </div>
  );
}

function TectonicPanel() {
  return (
    <div className="space-y-4">
      <section className="panel p-4">
        <div className="eyebrow mb-2">GEOPHYSICAL OBSERVATIONS</div>
        <h3 className="font-display text-lg font-semibold">
          Global tectonic activity
        </h3>
        <p className="mt-1 text-[10px] leading-relaxed text-slate-500">
          Explore earthquake observations, volcano locations and mapped
          tectonic plate boundaries.
        </p>
      </section>

      <section className="panel overflow-hidden p-3">
        <div className="mb-2 flex items-center justify-between px-2 py-2">
          <div>
            <div className="panel-title">Tectonic intelligence map</div>
            <p className="mt-1 text-[10px] text-slate-500">
              Click earthquake and volcano markers for details.
            </p>
          </div>
          <Mountain size={18} className="text-orange-400" />
        </div>
        <div className="relative h-[460px] md:h-[580px]">
          <EarthMap mode="tectonic" />
        </div>
      </section>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <article className="panel p-4">
          <Activity size={19} className="text-orange-400" />
          <h4 className="mt-3 text-sm font-semibold">Seismic observations</h4>
          <p className="mt-2 text-[10px] leading-relaxed text-slate-500">
            USGS earthquake feed containing recent event locations, magnitude,
            depth and event details.
          </p>
          <div className="mt-3 text-[9px] text-orange-300">
            SOURCE · USGS COMCAT
          </div>
        </article>

        <article className="panel p-4">
          <Mountain size={19} className="text-rose-400" />
          <h4 className="mt-3 text-sm font-semibold">Volcano database</h4>
          <p className="mt-2 text-[10px] leading-relaxed text-slate-500">
            Volcano location and geological records from the Smithsonian
            Global Volcanism Program.
          </p>
          <div className="mt-3 text-[9px] text-rose-300">
            SOURCE · SMITHSONIAN GVP
          </div>
        </article>

        <article className="panel p-4">
          <Layers size={19} className="text-amber-400" />
          <h4 className="mt-3 text-sm font-semibold">Plate boundaries</h4>
          <p className="mt-2 text-[10px] leading-relaxed text-slate-500">
            Geographic boundary dataset displayed as a separate tectonic
            reference layer.
          </p>
          <div className="mt-3 text-[9px] text-amber-300">
            SOURCE · LOCAL GEOJSON
          </div>
        </article>
      </div>

      <section className="panel p-4">
        <div className="flex items-center gap-2 text-xs font-semibold">
          <ShieldCheck size={16} className="text-emerald-400" />
          Scientific limitation
        </div>
        <p className="mt-2 text-[10px] leading-relaxed text-slate-500">
          Earthquakes and volcanic activity are observations, not predictions.
          The map does not forecast earthquakes or identify a guaranteed future
          eruption location.
        </p>
      </section>
    </div>
  );
}

function AtmosphericPanel() {
  return (
    <div className="space-y-4">
      <section className="panel p-4">
        <div className="eyebrow mb-2">ATMOSPHERIC OBSERVATIONS</div>
        <h3 className="font-display text-lg font-semibold">
          Atmospheric research workspace
        </h3>
        <p className="mt-1 text-[10px] leading-relaxed text-slate-500">
          Explore satellite-derived atmospheric composition and aerosol
          observations.
        </p>
      </section>

      <section className="panel overflow-hidden p-3">
        <div className="mb-2 flex items-center justify-between px-2 py-2">
          <div>
            <div className="panel-title">Atmospheric observation map</div>
            <p className="mt-1 text-[10px] text-slate-500">
              NASA Aura OMI aerosol index visualization.
            </p>
          </div>
          <CloudSun size={18} className="text-amber-300" />
        </div>
        <div className="relative h-[460px] md:h-[580px]">
          <EarthMap mode="atmospheric" />
        </div>
      </section>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <article className="panel p-4">
          <Sun size={20} className="text-amber-300" />
          <h4 className="mt-3 text-sm font-semibold">Aerosol observations</h4>
          <p className="mt-2 text-[10px] leading-relaxed text-slate-500">
            NASA Aura OMI Aerosol Index v4 NRT visualization for tracking absorbing
            aerosol signals. This is not a total-column ozone product.
          </p>
          <div className="mt-3 text-[9px] text-amber-300">
            SOURCE · NASA AURA OMI
          </div>
        </article>

        <article className="panel p-4">
          <Waves size={20} className="text-cyan-400" />
          <h4 className="mt-3 text-sm font-semibold">Water cycle</h4>
          <p className="mt-2 text-[10px] leading-relaxed text-slate-500">
            GPM precipitation observations can help investigate global and
            regional water-cycle patterns.
          </p>
          <div className="mt-3 text-[9px] text-cyan-300">
            SOURCE · NASA GPM
          </div>
        </article>

        <article className="panel p-4">
          <Database size={20} className="text-violet-400" />
          <h4 className="mt-3 text-sm font-semibold">Atmospheric datasets</h4>
          <p className="mt-2 text-[10px] leading-relaxed text-slate-500">
            MERRA-2 and other NASA Earthdata collections can support further
            atmospheric research.
          </p>
          <div className="mt-3 text-[9px] text-violet-300">
            SOURCE · NASA EARTHDATA
          </div>
        </article>
      </div>

      <section className="panel p-4">
        <div className="flex items-center gap-2 text-xs font-semibold">
          <ShieldCheck size={16} className="text-emerald-400" />
          Data interpretation
        </div>
        <p className="mt-2 text-[10px] leading-relaxed text-slate-500">
          The displayed Aura OMI layer is an aerosol-index product, not an
          ozone measurement. Aerosol index is a satellite-derived indicator
          and should not be interpreted as ground-level air quality.
        </p>
      </section>
    </div>
  );
}

function AIInvestigatorPanel() {
  return (
    <section className="space-y-4">
      <div className="panel p-5">
        <div className="eyebrow mb-2">SCIENTIFIC RESEARCH ASSISTANT</div>
        <h3 className="font-display text-xl font-semibold">
          AI Earth Investigator
        </h3>
        <p className="mt-2 max-w-2xl text-xs leading-relaxed text-slate-500">
          Investigate Earth science questions using traceable observations,
          datasets and scientific references.
        </p>
      </div>

      <AIResearchInterface />
    </section>
  );
}

export default function Home() {
  const [activePage, setActivePage] = useState("Mission Control");
  const [backendStatus, setBackendStatus] = useState("checking");
  const [nasaCatalogueStatus, setNasaCatalogueStatus] =
    useState("checking");
  const [lastChecked, setLastChecked] = useState("");

  async function checkBackend() {
    setBackendStatus("checking");
    setNasaCatalogueStatus("checking");

    try {
      const response = await fetch(`${API_BASE_URL}/api/health`);

      if (!response.ok) {
        throw new Error("Backend unavailable");
      }

      const data = await response.json();
      setBackendStatus(
        data.status === "online" || data.status === "healthy"
          ? "online"
          : "offline"
      );
    } catch {
      setBackendStatus("offline");
      setNasaCatalogueStatus("offline");
      setLastChecked(new Date().toLocaleTimeString());
      return;
    }

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/nasa/collections?keyword=MODIS&page_size=1`
      );

      if (!response.ok) {
        throw new Error("NASA CMR unavailable");
      }

      const data = await response.json();

      setNasaCatalogueStatus(
        Array.isArray(data.collections) ? "connected" : "unavailable"
      );
    } catch {
      setNasaCatalogueStatus("unavailable");
    }

    setLastChecked(new Date().toLocaleTimeString());
  }

  useEffect(() => {
    void checkBackend();
  }, []);

  const navButton = (item: {
    name: string;
    icon: ElementType;
  }) => {
    const Icon = item.icon;

    return (
      <button
        key={item.name}
        onClick={() => setActivePage(item.name)}
        className={`nav-item ${activePage === item.name ? "active" : ""}`}
      >
        <Icon size={17} strokeWidth={1.8} />
        <span>{item.name}</span>
      </button>
    );
  };

  return (
    <main className="dashboard">
      <aside className="sidebar">
        <div className="flex items-center gap-3 px-2">
          <div className="brand-mark">
            <Globe2 size={23} />
          </div>
          <div>
            <h1 className="font-display text-xl font-bold tracking-tight">
              Geo<span className="text-sky-400">NOVA</span>
            </h1>
            <p className="text-[9px] tracking-[2px] text-slate-500">
              EARTH INTELLIGENCE
            </p>
          </div>
        </div>

        <div className="section-label">PLATFORM</div>
        <nav className="sidebar-navigation space-y-1">
          {navigation.map(navButton)}
        </nav>

        <div className="section-label">RESEARCH INTELLIGENCE</div>
        <nav className="space-y-1">
          {researchNavigation.map(navButton)}
        </nav>

        <div className="mt-auto sidebar-footer">
          <div className="panel mt-8 p-3">
            <div className="mb-2 flex items-center gap-2">
              <ShieldCheck size={15} className="text-emerald-400" />
              <span className="text-xs font-semibold">
                Research integrity
              </span>
            </div>
            <p className="text-[10px] leading-relaxed text-slate-500">
              Scientific observations, derived analyses and AI explanations
              are identified separately.
            </p>
          </div>

          <button className="nav-item mt-4">
            <Settings size={17} />
            <span>Settings</span>
          </button>

          <div className="mt-5 px-3 text-[10px] text-slate-600">
            GEONOVA PREVIEW · VERSION 2.0
          </div>
        </div>
      </aside>

      <section className="main-content">
        <header className="mb-9 flex items-center justify-between gap-4">
          <div>
            <div className="eyebrow mb-2">
              EARTH SCIENCE / MISSION CENTER
            </div>
            <h2 className="font-display text-2xl font-semibold md:text-3xl">
              {activePage}
            </h2>
            <p className="mt-1 text-sm text-slate-500">
              {descriptions[activePage] ??
                "Explore GeoNOVA's integrated Earth intelligence systems."}
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button className="hidden items-center gap-2 rounded-lg border border-slate-700/60 px-3 py-2 text-xs text-slate-400 sm:flex">
              <Search size={14} />
              Search
            </button>
            <button className="rounded-lg border border-slate-700/60 p-2.5 text-slate-400 hover:text-white">
              <Bell size={17} />
            </button>
            <div className="hidden items-center gap-2 border-l border-slate-700/60 pl-3 sm:flex">
              <div className="flex h-8 w-8 items-center justify-center rounded-full border border-sky-700/50 bg-sky-900/70 text-xs text-sky-200">
                GN
              </div>
              <ChevronDown size={14} className="text-slate-500" />
            </div>
          </div>
        </header>

        {activePage === "Mission Control" ? (
          <MissionControl
            mapContent={
              <div className="grid h-full grid-cols-1 gap-3 lg:grid-cols-2">
                <section className="min-w-0 overflow-hidden rounded-xl border border-slate-800 bg-slate-950/70 p-2">
                  <div className="mb-2 flex items-center justify-between px-1">
                    <div>
                      <div className="text-xs font-semibold text-slate-100">Satellite map</div>
                      <p className="text-[9px] text-slate-500">Original flat map · pan, zoom and switch layers</p>
                    </div>
                    <Satellite size={15} className="text-cyan-300" />
                  </div>
                  <div className="relative h-[330px] lg:h-[450px] overflow-hidden rounded-lg">
                    <EarthMap mode="trends" />
                  </div>
                </section>
                <section className="min-w-0 overflow-hidden rounded-xl border border-cyan-500/20 bg-slate-950/70 p-2">
                  <div className="mb-2 flex items-center justify-between px-1">
                    <div>
                      <div className="text-xs font-semibold text-slate-100">3D rotating Earth</div>
                      <p className="text-[9px] text-slate-500">Same satellite layers · interactive globe</p>
                    </div>
                    <Globe2 size={15} className="text-cyan-300" />
                  </div>
                  <div className="relative h-[330px] lg:h-[450px] overflow-hidden rounded-lg">
                    <EarthMap mode="trends" globe />
                  </div>
                </section>
              </div>
            }
          />
        ) : activePage === "Data Observatory" ? (
          <DatasetExplorer />
        ) : activePage === "Earth Trends" ? (
          <EarthTrendsPanel />
        ) : activePage === "Tectonic Intelligence" ? (
          <TectonicPanel />
        ) : activePage === "Atmospheric Lab" ? (
          <AtmosphericPanel />
        ) : activePage === "Science Workspace" ? (
          <ScienceWorkspace />
        ) : activePage === "Source Integrity" ? (
          <SourceIntegrityPanel />
        ) : activePage === "Satellite Intelligence" ? (
          <SatelliteIntelligencePanel />
        ) : activePage === "Confidence Intelligence" ? (
          <ConfidenceIntelligencePanel />
        ) : activePage === "Environmental Anomalies" ? (
          <EnvironmentalAnomaliesPanel />
        ) : activePage === "AI Investigator" ? (
          <AIInvestigatorPanel />
        ) : activePage === "Research Reports" ? (
          <div className="space-y-4">
            <section className="panel p-5">
              <div className="eyebrow mb-2">
                REPRODUCIBLE SCIENTIFIC REPORTING
              </div>

              <h3 className="font-display text-xl font-semibold">
                Research report workspace
              </h3>

              <p className="mt-2 max-w-2xl text-xs leading-relaxed text-slate-400">
                Load scientific observations, select a parameter and generate
                a reproducible report with statistical analysis, provenance
                information and exportable results.
              </p>
            </section>

            <ScienceWorkspace />
          </div>
        ) : (
          <>
            <div className="mb-5 grid grid-cols-1 gap-3 sm:grid-cols-3">
              <div className="panel p-4">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-400">Data providers</span>
                  <Satellite size={17} className="text-sky-400" />
                </div>
                <div className="mt-3 font-display text-2xl font-semibold">
                  02
                </div>
                <p className="mt-1 text-[10px] text-slate-500">
                  NASA and ISRO selected
                </p>
              </div>

              <div className="panel p-4">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-400">
                    Research domains
                  </span>
                  <Compass size={17} className="text-cyan-400" />
                </div>
                <div className="mt-3 font-display text-2xl font-semibold">
                  10
                </div>
                <p className="mt-1 text-[10px] text-slate-500">
                  Integrated Earth science domains
                </p>
              </div>

              <div className="panel p-4">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-400">
                    Backend connection
                  </span>
                  <Activity size={17} className="text-emerald-400" />
                </div>
                <div className="mt-3 flex items-center gap-2">
                  <span
                    className={`status-dot ${
                      backendStatus === "online" ? "" : "offline"
                    }`}
                  />
                  <span className="font-display text-xl font-semibold capitalize">
                    {backendStatus === "checking"
                      ? "Checking"
                      : backendStatus}
                  </span>
                </div>
                <p className="mt-1 text-[10px] text-slate-500">
                  {lastChecked
                    ? `Last checked ${lastChecked}`
                    : "Connecting to FastAPI"}
                </p>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-4 xl:grid-cols-[2fr_0.85fr]">
              <section className="panel p-3">
                <div className="mb-2 flex items-center justify-between px-2 py-2">
                  <div>
                    <div className="panel-title">
                      Global observation map
                    </div>
                    <p className="mt-1 text-[10px] text-slate-500">
                      Global view of NASA events, earthquakes and volcanoes
                    </p>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      className="rounded-lg bg-slate-800/80 p-2 text-slate-400"
                      title="Refresh backend"
                      onClick={() => void checkBackend()}
                    >
                      <RefreshCw size={15} />
                    </button>
                    <button
                      className="rounded-lg bg-slate-800/80 p-2 text-slate-400"
                      title="Open Earth Trends"
                      onClick={() => setActivePage("Earth Trends")}
                    >
                      <Maximize2 size={15} />
                    </button>
                  </div>
                </div>

                <div className="relative h-[460px] md:h-[560px]">
                  <EarthMap mode="overview" />

                  <div className="pointer-events-none absolute left-3 top-3 rounded-lg border border-slate-700/60 bg-slate-950/85 px-3 py-2">
                    <div className="flex items-center gap-2 text-[10px] text-slate-300">
                      <Globe2 size={13} className="text-sky-400" />
                      GLOBAL VIEW
                    </div>
                    <p className="mt-1 text-[9px] text-slate-500">
                      Multi-source observation map
                    </p>
                  </div>
                </div>
              </section>

              <div className="space-y-4">
                <section className="panel p-4">
                  <div className="mb-4 flex items-center justify-between">
                    <div className="panel-title">Research divisions</div>
                    <ArrowUpRight size={15} className="text-slate-500" />
                  </div>

                  {[
                    {
                      icon: Earth,
                      title: "Earth systems",
                      subtitle: "Climate · Hydrology · Land",
                      color: "text-sky-400",
                      target: "Earth Trends",
                    },
                    {
                      icon: Activity,
                      title: "Tectonic intelligence",
                      subtitle: "Seismicity · Volcanoes",
                      color: "text-orange-400",
                      target: "Tectonic Intelligence",
                    },
                    {
                      icon: Sun,
                      title: "Atmospheric science",
                      subtitle: "UV · Ozone · Atmosphere",
                      color: "text-amber-300",
                      target: "Atmospheric Lab",
                    },
                    {
                      icon: Microscope,
                      title: "Science workspace",
                      subtitle: "Observations · Domains",
                      color: "text-cyan-400",
                      target: "Science Workspace",
                    },
                    {
                      icon: BrainCircuit,
                      title: "AI investigator",
                      subtitle: "Evidence-based discovery",
                      color: "text-violet-400",
                      target: "AI Investigator",
                    },
                  ].map((item) => {
                    const Icon = item.icon;

                    return (
                      <button
                        key={item.title}
                        onClick={() => setActivePage(item.target)}
                        className="flex w-full items-center gap-3 rounded-lg p-3 text-left transition-colors hover:bg-white/[0.035]"
                      >
                        <div className={`rounded-lg bg-slate-800/80 p-2 ${item.color}`}>
                          <Icon size={17} />
                        </div>
                        <div className="flex-1">
                          <div className="text-xs font-semibold">
                            {item.title}
                          </div>
                          <div className="mt-1 text-[10px] text-slate-500">
                            {item.subtitle}
                          </div>
                        </div>
                        <ArrowUpRight size={13} className="text-slate-600" />
                      </button>
                    );
                  })}
                </section>

                <section className="panel p-4">
                  <div className="mb-3 flex items-center justify-between">
                    <div className="panel-title">Data observatory</div>
                    <Database size={16} className="text-sky-400" />
                  </div>

                  <div className="data-card mb-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold">
                        NASA Earthdata
                      </span>
                      <span
                        className={`text-[9px] ${
                          nasaCatalogueStatus === "connected"
                            ? "text-emerald-300"
                            : nasaCatalogueStatus === "checking"
                            ? "text-amber-300"
                            : "text-rose-300"
                        }`}
                      >
                        {nasaCatalogueStatus === "connected"
                          ? "Catalogue connected"
                          : nasaCatalogueStatus === "checking"
                          ? "Checking..."
                          : "Unavailable"}
                      </span>
                    </div>
                    <p className="mt-1 text-[10px] text-slate-500">
                      Dataset discovery and Earth science services
                    </p>
                  </div>

                  <div className="data-card">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold">
                        ISRO data services
                      </span>
                      <span className="text-[9px] text-emerald-300">
                        Directory integrated
                      </span>
                    </div>
                    <p className="mt-1 text-[10px] text-slate-500">
                      Bhuvan · MOSDAC · Product directory
                    </p>
                  </div>

                  <button
                    onClick={() => setActivePage("Data Observatory")}
                    className="mt-3 text-[10px] font-semibold text-sky-300"
                  >
                    Explore data sources ↗
                  </button>
                </section>
              </div>
            </div>

            <section className="panel mt-4 p-5">
              <div className="mb-4 flex items-center justify-between">
                <div>
                  <div className="panel-title">Scientific workspace</div>
                  <p className="mt-1 text-[10px] text-slate-500">
                    Choose a research division to begin an investigation.
                  </p>
                </div>
                <Waves size={18} className="text-cyan-400" />
              </div>

              <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                {[
                  {
                    step: "01 / DISCOVER",
                    title: "Choose a variable",
                    text: "Find relevant NASA and ISRO datasets and observations.",
                    target: "Science Workspace",
                  },
                  {
                    step: "02 / INVESTIGATE",
                    title: "Analyse Earth changes",
                    text: "Examine regional patterns, time series and statistics.",
                    target: "Confidence Intelligence",
                  },
                  {
                    step: "03 / UNDERSTAND",
                    title: "Generate evidence",
                    text: "Create transparent research summaries with sources.",
                    target: "Research Reports",
                  },
                ].map((item) => (
                  <button
                    key={item.step}
                    onClick={() => setActivePage(item.target)}
                    className="data-card text-left transition hover:border-sky-500/40"
                  >
                    <div className="eyebrow mb-2">{item.step}</div>
                    <div className="text-sm font-semibold">{item.title}</div>
                    <p className="mt-2 text-[10px] leading-relaxed text-slate-500">
                      {item.text}
                    </p>
                  </button>
                ))}
              </div>
            </section>

            <footer className="mt-6 flex flex-col justify-between gap-2 text-[10px] text-slate-600 sm:flex-row">
              <span>GEONOVA · EARTH INTELLIGENCE PLATFORM</span>
              <span>Scientific data integrations are under development</span>
            </footer>
          </>
        )}
      </section>
    </main>
  );
}
