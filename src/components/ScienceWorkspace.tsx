
"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import type { ElementType } from "react";

import {
  Activity,
  ArrowDownToLine,
  CheckCircle2,
  Cloud,
  Database,
  Droplets,
  Globe2,
  Layers3,
  Leaf,
  Mountain,
  RefreshCw,
  Satellite,
  Search,
  Thermometer,
  TreePine,
  Waves,
  AlertCircle,
  ChartNoAxesCombined,
  Clock3,
  FileJson,
} from "lucide-react";

import ScientificChartEngine from "./ScientificChartEngine";
import TrendIntelligenceWorkspace from "./TrendIntelligenceWorkspace";
import ResearchReportPanel from "./ResearchReportPanel";

import {
  exportScientificCSV,
  exportScientificJSON,
} from "@/lib/scientificExports";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

type Domain = {
  id: string;
  name: string;
  description: string;
  icon: string;
  priority: number;
  category: string;
  search_terms: string[];
  existing_variable_ids: string[];
  observation_support: boolean;
};

type Dataset = {
  id?: string;
  title?: string;
  short_name?: string;
  version?: string;
  provider?: string;
  description?: string;
  granule_count?: number | null;
  has_granules?: boolean;
  links?: { href?: string }[];
};

type Observation = {
  date: string;
  [key: string]: string | number | null;
};

type ObservationResponse = {
  observations: Observation[];
  count: number;
  source: {
    name: string;
    url: string;
    type: string;
  };
  metadata: {
    parameters: Record<string, { label: string; unit: string }>;
    temporal_resolution: string;
    spatial_interpretation: string;
    quality_notice: string;
  };
  coordinates: {
    latitude: number;
    longitude: number;
  };
};

type ChartType = "line" | "area" | "bar" | "histogram";

const DOMAIN_ICONS: Record<string, ElementType> = {
  temperature: Thermometer,
  water: Droplets,
  vegetation: TreePine,
  atmosphere: Cloud,
  ocean: Waves,
  geophysical: Activity,
  cryosphere: Mountain,
  soil: Layers3,
  ecosystem: Leaf,
  "human-impact": Globe2,
};

const CHART_OPTIONS: { id: ChartType; label: string }[] = [
  { id: "line", label: "Line" },
  { id: "area", label: "Area" },
  { id: "bar", label: "Bar" },
  { id: "histogram", label: "Distribution" },
];

export default function ScienceWorkspace() {
  const [domains, setDomains] = useState<Domain[]>([]);
  const [selectedDomain, setSelectedDomain] = useState("temperature");

  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [observations, setObservations] = useState<Observation[]>([]);

  const [metadata, setMetadata] =
    useState<ObservationResponse["metadata"] | null>(null);

  const [source, setSource] =
    useState<ObservationResponse["source"] | null>(null);

  // Editable example coordinates, not detected user location.
  const [latitude, setLatitude] = useState("26.8467");
  const [longitude, setLongitude] = useState("80.9462");

  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  const [selectedParameter, setSelectedParameter] = useState("");
  const [chartType, setChartType] = useState<ChartType>("line");

  const [loadingDomains, setLoadingDomains] = useState(true);
  const [loadingDatasets, setLoadingDatasets] = useState(false);
  const [loadingObservations, setLoadingObservations] = useState(false);

  const [error, setError] = useState("");
  const [exportMessage, setExportMessage] = useState("");

  const [activeView, setActiveView] = useState<
    "observations" | "datasets"
  >("observations");

  const selectedDomainInfo = domains.find(
    (domain) => domain.id === selectedDomain
  );

  const supportsObservations =
    selectedDomainInfo?.observation_support ?? false;

  const sortedDomains = useMemo(
    () =>
      [...domains].sort(
        (a, b) =>
          a.priority - b.priority ||
          a.name.localeCompare(b.name)
      ),
    [domains]
  );

  const parameters = metadata?.parameters || {};

  // ---------------------------------------------------------
  // LOAD SCIENTIFIC DOMAINS
  // ---------------------------------------------------------

  const loadDomains = useCallback(async () => {
    setLoadingDomains(true);

    try {
      const response = await fetch(
        `${API_BASE}/api/science/domains`
      );

      if (!response.ok) {
        throw new Error(
          `Domain API returned HTTP ${response.status}`
        );
      }

      const data = await response.json();
      const receivedDomains: Domain[] = data.domains || [];

      setDomains(receivedDomains);

      if (
        receivedDomains.length > 0 &&
        !receivedDomains.some(
          (domain) => domain.id === selectedDomain
        )
      ) {
        setSelectedDomain(receivedDomains[0].id);
      }
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to load domains."
      );
    } finally {
      setLoadingDomains(false);
    }
  }, [selectedDomain]);

  // ---------------------------------------------------------
  // NASA EARTHDATA COLLECTION DISCOVERY
  // ---------------------------------------------------------

  const loadDatasets = useCallback(async () => {
    setLoadingDatasets(true);

    try {
      const response = await fetch(
        `${API_BASE}/api/nasa/collections?domain_id=${encodeURIComponent(
          selectedDomain
        )}&page_size=15`
      );

      if (!response.ok) {
        throw new Error(
          `NASA catalogue returned HTTP ${response.status}`
        );
      }

      const data = await response.json();
      setDatasets(data.collections || []);
    } catch (err) {
      setDatasets([]);

      setError(
        err instanceof Error
          ? err.message
          : "Unable to load datasets."
      );
    } finally {
      setLoadingDatasets(false);
    }
  }, [selectedDomain]);

  // ---------------------------------------------------------
  // FETCH NASA POWER OBSERVATIONS
  // ---------------------------------------------------------

  const loadObservations = useCallback(async () => {
    if (!supportsObservations) return;

    const lat = Number(latitude);
    const lon = Number(longitude);

    if (
      !Number.isFinite(lat) ||
      !Number.isFinite(lon) ||
      lat < -90 ||
      lat > 90 ||
      lon < -180 ||
      lon > 180
    ) {
      setError(
        "Enter valid coordinates. Latitude must be between -90 and 90, and longitude between -180 and 180."
      );
      return;
    }

    if (startDate && endDate && startDate > endDate) {
      setError("Start date cannot be later than end date.");
      return;
    }

    setLoadingObservations(true);
    setError("");
    setExportMessage("");

    try {
      const params = new URLSearchParams({
        latitude: String(lat),
        longitude: String(lon),
      });

      if (startDate) {
        params.set("start_date", startDate.replaceAll("-", ""));
      }

      if (endDate) {
        params.set("end_date", endDate.replaceAll("-", ""));
      }

      const response = await fetch(
        `${API_BASE}/api/science/observations/${selectedDomain}?${params}`
      );

      if (!response.ok) {
        const body = await response.json().catch(() => ({}));

        throw new Error(
          body.detail ||
            `Observation API returned HTTP ${response.status}`
        );
      }

      const data: ObservationResponse = await response.json();

      setObservations(data.observations || []);
      setMetadata(data.metadata);
      setSource(data.source);

      const firstParameter = Object.keys(
        data.metadata?.parameters || {}
      )[0];

      setSelectedParameter(firstParameter || "");
      setChartType("line");
    } catch (err) {
      setObservations([]);
      setMetadata(null);
      setSource(null);
      setSelectedParameter("");

      setError(
        err instanceof Error
          ? err.message
          : "Unable to load observations."
      );
    } finally {
      setLoadingObservations(false);
    }
  }, [
    supportsObservations,
    latitude,
    longitude,
    startDate,
    endDate,
    selectedDomain,
  ]);

  // ---------------------------------------------------------
  // INITIAL LOADING
  // ---------------------------------------------------------

  useEffect(() => {
    loadDomains();
  }, [loadDomains]);

  useEffect(() => {
    if (domains.length > 0) {
      loadDatasets();
    }
  }, [domains.length, loadDatasets]);

  // ---------------------------------------------------------
  // RESET DATA WHEN DOMAIN CHANGES
  // ---------------------------------------------------------

  useEffect(() => {
    setObservations([]);
    setMetadata(null);
    setSource(null);
    setSelectedParameter("");
    setDatasets([]);
    setError("");
    setExportMessage("");
  }, [selectedDomain]);

  // ---------------------------------------------------------
  // CHART DATA
  // ---------------------------------------------------------

  const chartData = useMemo(
    () =>
      observations.map((item) => ({
        date: item.date,
        value:
          typeof item[selectedParameter] === "number"
            ? (item[selectedParameter] as number)
            : null,
      })),
    [observations, selectedParameter]
  );

  const validValues = useMemo(
    () =>
      chartData
        .map((item) => item.value)
        .filter((value): value is number => value !== null),
    [chartData]
  );

  // ---------------------------------------------------------
  // DESCRIPTIVE STATISTICS
  // ---------------------------------------------------------

  const statistics = useMemo(() => {
    if (validValues.length === 0) return null;

    const sorted = [...validValues].sort((a, b) => a - b);
    const middle = Math.floor(sorted.length / 2);

    const median =
      sorted.length % 2 === 0
        ? (sorted[middle - 1] + sorted[middle]) / 2
        : sorted[middle];

    return {
      average:
        validValues.reduce((sum, value) => sum + value, 0) /
        validValues.length,
      minimum: Math.min(...validValues),
      maximum: Math.max(...validValues),
      median,
      count: validValues.length,
    };
  }, [validValues]);

  // ---------------------------------------------------------
  // EXPORT METADATA
  // ---------------------------------------------------------

  const getExportMetadata = useCallback(() => {
    return {
      title: `${selectedDomainInfo?.name || selectedDomain} observations`,
      domain: selectedDomain,
      domain_name: selectedDomainInfo?.name || selectedDomain,
      parameter: selectedParameter,
      parameter_label:
        parameters[selectedParameter]?.label || selectedParameter,
      unit: parameters[selectedParameter]?.unit || "",
      source: source?.name || "Unavailable",
      source_url: source?.url || "",
      source_type: source?.type || "",
      generatedAt: new Date().toISOString(),
      methodology:
        "Descriptive statistics are calculated from the returned observation values. Missing parameter values are excluded from numerical summaries.",
      temporal_resolution:
        metadata?.temporal_resolution || "Unavailable",
      spatial_interpretation:
        metadata?.spatial_interpretation || "Unavailable",
      quality_notice:
        metadata?.quality_notice || "Unavailable",
      coordinates: {
        latitude: Number(latitude),
        longitude: Number(longitude),
      },
      requested_date_range: {
        start_date: startDate || null,
        end_date: endDate || null,
      },
      chart_type: chartType,
      observation_count: observations.length,
      valid_observation_count: statistics?.count || 0,
    };
  }, [
    selectedDomainInfo,
    selectedDomain,
    selectedParameter,
    parameters,
    source,
    metadata,
    latitude,
    longitude,
    startDate,
    endDate,
    chartType,
    observations.length,
    statistics,
  ]);

  // ---------------------------------------------------------
  // EXPORT OBSERVATIONS AS CSV
  // ---------------------------------------------------------

  function exportCSV() {
    if (observations.length === 0) return;

    try {
      setExportMessage("");
      setError("");

      const exportMetadata = getExportMetadata();

      exportScientificCSV(
        observations,
        exportMetadata,
        `geonova-${selectedDomain}-observations.csv`
      );

      setExportMessage(
        "Observation CSV export requested successfully."
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? `CSV export failed: ${err.message}`
          : "CSV export failed."
      );
    }
  }

  // ---------------------------------------------------------
  // EXPORT OBSERVATIONS AND STATISTICS AS JSON
  // ---------------------------------------------------------

  function exportJSON() {
    if (observations.length === 0) return;

    try {
      setExportMessage("");
      setError("");

      const exportPayload = {
        project: "GeoNOVA",
        export_type: "scientific_observation_dataset",

        metadata: getExportMetadata(),

        descriptive_statistics: statistics
          ? {
              average: statistics.average,
              minimum: statistics.minimum,
              maximum: statistics.maximum,
              median: statistics.median,
              valid_observation_count: statistics.count,
              total_record_count: observations.length,
            }
          : null,

        parameter_information: {
          selected_parameter: selectedParameter,
          label:
            parameters[selectedParameter]?.label ||
            selectedParameter,
          unit: parameters[selectedParameter]?.unit || "",
          available_parameters: parameters,
        },

        observation_source: source,

        scientific_metadata: metadata,

        observations,
      };

      exportScientificJSON(
        exportPayload,
        {
          ...getExportMetadata(),
          description:
            "GeoNOVA scientific observation export containing original observations, descriptive statistics, source provenance, and acquisition metadata.",
        },
        `geonova-${selectedDomain}-research-data.json`
      );

      setExportMessage(
        "Scientific JSON export requested successfully."
      );
    } catch (err) {
      setError(
        err instanceof Error
          ? `JSON export failed: ${err.message}`
          : "JSON export failed."
      );
    }
  }

  // ---------------------------------------------------------
  // NUMBER FORMATTING
  // ---------------------------------------------------------

  function formatNumber(value: number | null | undefined) {
    if (value === null || value === undefined) return "—";
    return value.toFixed(2);
  }

  // ---------------------------------------------------------
  // RENDER
  // ---------------------------------------------------------

  return (
    <div className="space-y-6">
      {/* HEADER */}

      <div className="panel p-5">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="eyebrow">EARTH SCIENCE DIVISION</div>

            <h2 className="font-display text-2xl font-semibold mt-1">
              Scientific Workspace
            </h2>

            <p className="muted text-sm mt-1">
              Explore environmental observations and scientific datasets
              across ten Earth intelligence domains.
            </p>
          </div>

          <div className="flex items-center gap-2 text-xs text-emerald-400">
            <span className="status-dot" />
            Domain registry connected
          </div>
        </div>
      </div>

      {/* ERRORS */}

      {error && (
        <div className="panel p-4 border border-red-500/30 flex gap-3">
          <AlertCircle
            className="text-red-400 shrink-0"
            size={19}
          />

          <div className="text-sm text-red-300">{error}</div>

          <button
            onClick={() => setError("")}
            className="ml-auto text-xs text-slate-400 hover:text-white"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* EXPORT FEEDBACK */}

      {exportMessage && (
        <div className="panel p-3 border border-emerald-500/30 flex items-center gap-2">
          <CheckCircle2
            size={17}
            className="text-emerald-400 shrink-0"
          />

          <p className="text-xs text-emerald-300">
            {exportMessage}
          </p>

          <button
            onClick={() => setExportMessage("")}
            className="ml-auto text-xs text-slate-400 hover:text-white"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* DOMAIN SELECTOR */}

      <div>
        <div className="flex flex-wrap justify-between items-center mb-3 gap-2">
          <div>
            <h3 className="font-display font-semibold">
              Earth Intelligence Domains
            </h3>

            <p className="muted text-xs mt-1">
              Ten scientific domains organized by implementation priority.
            </p>
          </div>

          <span className="muted text-xs">
            {domains.length} / 10 domains
          </span>
        </div>

        {loadingDomains ? (
          <div className="panel p-8 text-center muted">
            Loading scientific domains...
          </div>
        ) : (
          <div className="space-y-5">
            {[1, 2].map((priority) => {
              const priorityDomains = sortedDomains.filter(
                (domain) => domain.priority === priority
              );

              if (priorityDomains.length === 0) return null;

              return (
                <div key={priority}>
                  <div className="flex items-center gap-2 mb-3">
                    <span
                      className={`text-[10px] font-bold tracking-wider rounded-full px-2.5 py-1 ${
                        priority === 1
                          ? "bg-cyan-400/15 text-cyan-300"
                          : "bg-slate-700/70 text-slate-300"
                      }`}
                    >
                      PRIORITY {priority}
                    </span>

                    <span className="muted text-xs">
                      {priority === 1
                        ? "Core Earth Systems"
                        : "Extended Earth Systems"}
                    </span>

                    <span className="muted text-xs ml-auto">
                      {priorityDomains.length} domains
                    </span>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
                    {priorityDomains.map((domain) => {
                      const Icon =
                        DOMAIN_ICONS[domain.id] || Satellite;

                      const active = selectedDomain === domain.id;

                      return (
                        <button
                          key={domain.id}
                          onClick={() => setSelectedDomain(domain.id)}
                          className={`panel p-4 text-left transition-all ${
                            active
                              ? "border-cyan-400/50 bg-cyan-400/5"
                              : "hover:border-slate-500/50"
                          }`}
                        >
                          <div className="flex justify-between gap-3">
                            <div className="flex gap-3 min-w-0">
                              <div className="rounded-xl bg-cyan-400/10 p-2 h-fit">
                                <Icon
                                  size={19}
                                  className="text-cyan-300"
                                />
                              </div>

                              <div className="min-w-0">
                                <div className="text-sm font-semibold leading-snug">
                                  {domain.name}
                                </div>

                                <div className="muted text-xs mt-1 leading-relaxed">
                                  {domain.description}
                                </div>
                              </div>
                            </div>

                            {active && (
                              <CheckCircle2
                                size={17}
                                className="text-cyan-300 shrink-0"
                              />
                            )}
                          </div>

                          <div className="mt-3 flex gap-2 flex-wrap">
                            <span className="text-[10px] rounded-full bg-slate-700/60 px-2 py-1">
                              Dataset discovery
                            </span>

                            {domain.observation_support ? (
                              <span className="text-[10px] rounded-full bg-emerald-500/10 text-emerald-300 px-2 py-1">
                                Observations supported
                              </span>
                            ) : (
                              <span className="text-[10px] rounded-full bg-amber-500/10 text-amber-300 px-2 py-1">
                                Dataset discovery only
                              </span>
                            )}
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* SELECTED DOMAIN WORKSPACE */}

      <div className="panel p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="eyebrow">SELECTED DOMAIN</div>

            <h3 className="font-display text-xl font-semibold mt-1">
              {selectedDomainInfo?.name || selectedDomain}
            </h3>

            <p className="muted text-xs mt-1">
              {selectedDomainInfo?.description}
            </p>
          </div>

          <div className="flex gap-2">
            <button
              onClick={() => setActiveView("observations")}
              className={`rounded-lg px-3 py-2 text-xs ${
                activeView === "observations"
                  ? "bg-cyan-400/15 text-cyan-300"
                  : "bg-slate-800 text-slate-300"
              }`}
            >
              Observations
            </button>

            <button
              onClick={() => setActiveView("datasets")}
              className={`rounded-lg px-3 py-2 text-xs ${
                activeView === "datasets"
                  ? "bg-cyan-400/15 text-cyan-300"
                  : "bg-slate-800 text-slate-300"
              }`}
            >
              NASA Datasets
            </button>
          </div>
        </div>

        {/* OBSERVATIONS */}

        {activeView === "observations" && (
          <div className="mt-5 space-y-5">
            {supportsObservations ? (
              <>
                {/* LOCATION AND DATE FILTERS */}

                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                  <label className="text-xs muted">
                    Latitude
                    <input
                      type="number"
                      min="-90"
                      max="90"
                      step="any"
                      value={latitude}
                      onChange={(event) =>
                        setLatitude(event.target.value)
                      }
                      className="mt-2 w-full rounded-lg bg-slate-900 border border-slate-700 p-2 text-sm text-white"
                    />
                  </label>

                  <label className="text-xs muted">
                    Longitude
                    <input
                      type="number"
                      min="-180"
                      max="180"
                      step="any"
                      value={longitude}
                      onChange={(event) =>
                        setLongitude(event.target.value)
                      }
                      className="mt-2 w-full rounded-lg bg-slate-900 border border-slate-700 p-2 text-sm text-white"
                    />
                  </label>

                  <label className="text-xs muted">
                    Start date
                    <input
                      type="date"
                      value={startDate}
                      onChange={(event) =>
                        setStartDate(event.target.value)
                      }
                      className="mt-2 w-full rounded-lg bg-slate-900 border border-slate-700 p-2 text-sm text-white"
                    />
                  </label>

                  <label className="text-xs muted">
                    End date
                    <input
                      type="date"
                      value={endDate}
                      onChange={(event) =>
                        setEndDate(event.target.value)
                      }
                      className="mt-2 w-full rounded-lg bg-slate-900 border border-slate-700 p-2 text-sm text-white"
                    />
                  </label>
                </div>

                {/* OBSERVATION ACTIONS */}

                <div className="flex flex-wrap gap-2">
                  <button
                    onClick={loadObservations}
                    disabled={loadingObservations}
                    className="rounded-lg bg-cyan-400 text-slate-950 px-4 py-2 text-sm font-semibold flex items-center gap-2 disabled:opacity-50"
                  >
                    <RefreshCw
                      size={15}
                      className={
                        loadingObservations ? "animate-spin" : ""
                      }
                    />

                    {loadingObservations
                      ? "Fetching observations..."
                      : "Load observations"}
                  </button>

                  {observations.length > 0 && (
                    <>
                      <button
                        onClick={exportCSV}
                        className="rounded-lg bg-slate-800 px-4 py-2 text-sm flex items-center gap-2 hover:bg-slate-700"
                      >
                        <ArrowDownToLine size={15} />
                        Export CSV
                      </button>

                      <button
                        onClick={exportJSON}
                        className="rounded-lg bg-slate-800 px-4 py-2 text-sm flex items-center gap-2 hover:bg-slate-700"
                      >
                        <FileJson size={15} />
                        Export Research JSON
                      </button>
                    </>
                  )}
                </div>

                {/* PARAMETER SELECTOR */}

                {metadata && (
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(parameters).map(
                      ([code, details]) => (
                        <button
                          key={code}
                          onClick={() => setSelectedParameter(code)}
                          className={`rounded-lg px-3 py-2 text-xs ${
                            selectedParameter === code
                              ? "bg-cyan-400/15 text-cyan-300 border border-cyan-400/30"
                              : "bg-slate-800 text-slate-300"
                          }`}
                        >
                          {details.label}
                        </button>
                      )
                    )}
                  </div>
                )}

                {/* OBSERVATION RESULTS */}

                {loadingObservations ? (
                  <div className="text-center py-12 muted text-sm">
                    <RefreshCw
                      size={22}
                      className="animate-spin mx-auto mb-3"
                    />
                    Retrieving NASA POWER observations...
                  </div>
                ) : observations.length > 0 ? (
                  <>
                    {/* SUMMARY STATISTICS */}

                    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                      {[
                        ["Average", statistics?.average],
                        ["Minimum", statistics?.minimum],
                        ["Maximum", statistics?.maximum],
                        ["Median", statistics?.median],
                      ].map(([label, value]) => (
                        <div
                          key={String(label)}
                          className="data-card p-3"
                        >
                          <div className="muted text-xs">
                            {label}
                          </div>

                          <div className="font-display text-xl font-semibold mt-2">
                            {formatNumber(value as number | undefined)}
                          </div>

                          <div className="muted text-[10px]">
                            {parameters[selectedParameter]?.unit}
                          </div>
                        </div>
                      ))}
                    </div>

                    {/* SCIENTIFIC VISUALIZATION */}

                    <div className="panel p-4 space-y-4">
                      <div className="flex flex-wrap justify-between items-center gap-3">
                        <div>
                          <div className="flex items-center gap-2">
                            <ChartNoAxesCombined
                              size={18}
                              className="text-cyan-300"
                            />

                            <h4 className="font-semibold text-sm">
                              Scientific Visualization
                            </h4>
                          </div>

                          <p className="muted text-xs mt-1">
                            {parameters[selectedParameter]?.label}
                            {parameters[selectedParameter]?.unit
                              ? ` · ${parameters[selectedParameter].unit}`
                              : ""}
                          </p>
                        </div>

                        <div className="flex flex-wrap gap-1.5">
                          {CHART_OPTIONS.map((option) => (
                            <button
                              key={option.id}
                              onClick={() => setChartType(option.id)}
                              className={`rounded-lg px-3 py-2 text-xs transition-colors ${
                                chartType === option.id
                                  ? "bg-cyan-400/15 text-cyan-300 border border-cyan-400/30"
                                  : "bg-slate-800 text-slate-300 hover:bg-slate-700"
                              }`}
                            >
                              {option.label}
                            </button>
                          ))}
                        </div>
                      </div>

                      <ScientificChartEngine
                        title={
                          chartType === "histogram"
                            ? "Observation Value Distribution"
                            : "Observation Time Series"
                        }
                        subtitle={
                          chartType === "histogram"
                            ? "Frequency distribution of available observations"
                            : "Values across the selected observation period"
                        }
                        chartType={chartType}
                        data={chartData}
                        xKey="date"
                        yKey="value"
                        height={320}
                        unit={parameters[selectedParameter]?.unit || ""}
                        emptyMessage="No valid values are available for this parameter."
                        showLegend={false}
                        showGrid={true}
                        showTooltip={true}
                      />

                      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-800 pt-3">
                        <div className="flex items-center gap-2 text-xs muted">
                          <Activity
                            size={14}
                            className="text-cyan-300"
                          />
                          {statistics?.count ?? 0} valid observations
                        </div>

                        <div className="text-xs muted">
                          {observations.length} records received
                        </div>
                      </div>
                    </div>

                    {/* OBSERVATION COVERAGE */}

                    <div className="panel p-4">
                      <div className="flex items-center gap-2 text-sm font-semibold mb-3">
                        <Clock3
                          size={16}
                          className="text-cyan-300"
                        />
                        Observation coverage
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                        <div>
                          <div className="muted text-xs">
                            First returned date
                          </div>

                          <div className="text-sm mt-1">
                            {observations[0]?.date || "—"}
                          </div>
                        </div>

                        <div>
                          <div className="muted text-xs">
                            Last returned date
                          </div>

                          <div className="text-sm mt-1">
                            {observations[observations.length - 1]?.date ||
                              "—"}
                          </div>
                        </div>

                        <div>
                          <div className="muted text-xs">
                            Missing parameter values
                          </div>

                          <div className="text-sm mt-1">
                            {observations.length -
                              (statistics?.count || 0)}
                          </div>
                        </div>
                      </div>

                      <p className="muted text-[10px] mt-3">
                        Coverage describes the records returned by the source.
                        It does not independently establish measurement quality
                        or statistical significance.
                      </p>
                    </div>

                    {/* PROVENANCE */}

                    <div className="panel p-4 space-y-2">
                      <div className="flex items-center gap-2 text-sm font-semibold">
                        <Database
                          size={16}
                          className="text-cyan-300"
                        />
                        Observation provenance
                      </div>

                      <p className="text-xs muted">
                        Source: {source?.name || "Unavailable"}
                      </p>

                      <p className="text-xs muted">
                        Resolution:{" "}
                        {metadata?.temporal_resolution || "Unavailable"}
                      </p>

                      <p className="text-xs muted">
                        Spatial interpretation:{" "}
                        {metadata?.spatial_interpretation || "Unavailable"}
                      </p>

                      <p className="text-xs muted">
                        Quality: {metadata?.quality_notice || "Unavailable"}
                      </p>

                      {source?.url && (
                        <a
                          href={source.url}
                          target="_blank"
                          rel="noreferrer"
                          className="text-xs text-cyan-300 underline"
                        >
                          Open source documentation
                        </a>
                      )}
                    </div>

                    {/* UNIFIED TREND INTELLIGENCE WORKSPACE */}

                    <TrendIntelligenceWorkspace
                      domainId={selectedDomain}
                      observations={observations}
                      parameterKey={selectedParameter}
                      parameterLabel={
                        parameters[selectedParameter]?.label ||
                        selectedParameter
                      }
                      unit={parameters[selectedParameter]?.unit || ""}
                    />

                    {/* REPRODUCIBLE SCIENTIFIC RESEARCH REPORT */}

                    <ResearchReportPanel
                      domainId={selectedDomain}
                      observations={observations}
                      parameterKey={selectedParameter}
                      parameterLabel={
                        parameters[selectedParameter]?.label ||
                        selectedParameter
                      }
                      unit={parameters[selectedParameter]?.unit || ""}
                    />
                  </>
                ) : (
                  <div className="panel p-8 text-center">
                    <Satellite
                      size={28}
                      className="mx-auto text-cyan-300 mb-3"
                    />

                    <p className="text-sm font-semibold">
                      No observations loaded
                    </p>

                    <p className="muted text-xs mt-2">
                      Choose coordinates and a date range, then load observations.
                    </p>

                    <p className="muted text-[10px] mt-2">
                      Coordinates initially show an editable example point in
                      Lucknow, India.
                    </p>
                  </div>
                )}
              </>
            ) : (
              <div className="panel p-8 text-center">
                <Database
                  size={30}
                  className="mx-auto text-cyan-300 mb-3"
                />

                <h4 className="font-semibold">
                  Dataset discovery available
                </h4>

                <p className="muted text-sm mt-2 max-w-xl mx-auto">
                  This domain currently has catalogue discovery configured.
                  Direct observation acquisition and time-series processing
                  have not yet been connected for this domain.
                </p>

                <button
                  onClick={() => setActiveView("datasets")}
                  className="mt-4 rounded-lg bg-cyan-400 text-slate-950 px-4 py-2 text-sm font-semibold"
                >
                  Explore NASA datasets
                </button>
              </div>
            )}
          </div>
        )}

        {/* NASA DATASETS */}

        {activeView === "datasets" && (
          <div className="mt-5">
            <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
              <div className="flex items-center gap-2 text-sm muted">
                <Search size={16} />
                NASA Earthdata collection discovery
              </div>

              <button
                onClick={loadDatasets}
                disabled={loadingDatasets}
                className="rounded-lg bg-slate-800 px-3 py-2 text-xs flex items-center gap-2"
              >
                <RefreshCw
                  size={14}
                  className={
                    loadingDatasets ? "animate-spin" : ""
                  }
                />
                Refresh catalogue
              </button>
            </div>

            {loadingDatasets ? (
              <div className="text-center py-10 muted text-sm">
                Searching NASA Earthdata...
              </div>
            ) : datasets.length > 0 ? (
              <div className="space-y-3">
                {datasets.map((dataset, index) => {
                  const resourceUrl = dataset.links?.find(
                    (link) => link.href?.startsWith("http")
                  )?.href;

                  return (
                    <div
                      key={dataset.id || index}
                      className="panel p-4"
                    >
                      <div className="flex flex-wrap justify-between gap-3">
                        <div className="min-w-0 flex-1">
                          <h4 className="text-sm font-semibold">
                            {dataset.title || "Untitled collection"}
                          </h4>

                          <div className="muted text-xs mt-2">
                            {dataset.short_name || "No short name"}
                            {dataset.version
                              ? ` · Version ${dataset.version}`
                              : ""}
                            {dataset.provider
                              ? ` · ${dataset.provider}`
                              : ""}
                          </div>

                          {dataset.description && (
                            <p className="muted text-xs mt-3 leading-relaxed">
                              {dataset.description.slice(0, 350)}
                              {dataset.description.length > 350
                                ? "..."
                                : ""}
                            </p>
                          )}
                        </div>

                        <div className="text-right text-xs muted">
                          {dataset.granule_count != null && (
                            <div>
                              {Number(
                                dataset.granule_count
                              ).toLocaleString()}{" "}
                              granules
                            </div>
                          )}

                          {dataset.has_granules && (
                            <div className="text-emerald-300 mt-1">
                              Granules reported
                            </div>
                          )}
                        </div>
                      </div>

                      {resourceUrl && (
                        <a
                          href={resourceUrl}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-block mt-3 text-xs text-cyan-300 underline"
                        >
                          Open collection resource
                        </a>
                      )}
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="panel p-8 text-center muted text-sm">
                No matching collections were returned.
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
