
"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Satellite,
  ShieldCheck,
  Activity,
  FileText,
  RefreshCw,
  AlertTriangle,
  Download,
  Database,
  Loader2,
} from "lucide-react";

const API =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

type JsonData = Record<string, unknown>;

function pretty(value: unknown) {
  return JSON.stringify(value, null, 2);
}

function errorMessage(value: unknown, fallback: string) {
  if (typeof value === "string" && value.trim()) return value;
  if (value && typeof value === "object") {
    return JSON.stringify(value, null, 2);
  }
  return fallback;
}

async function readJsonResponse(response: Response): Promise<any> {
  const body = await response.text();

  try {
    return body ? JSON.parse(body) : {};
  } catch {
    throw new Error(
      body.trim() ||
        `The backend returned HTTP ${response.status} ${response.statusText}.`
    );
  }
}

function DataPanel({
  title,
  description,
  endpoint,
}: {
  title: string;
  description: string;
  endpoint: string;
}) {
  const [data, setData] = useState<JsonData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const response = await fetch(`${API}${endpoint}`, {
        cache: "no-store",
      });

      const result = await readJsonResponse(response);

      if (!response.ok) {
        throw new Error(
          errorMessage(
            result.detail,
            `HTTP ${response.status} ${response.statusText}`
          )
        );
      }

      setData(result);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Request failed"
      );
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [endpoint]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <section className="panel p-5 space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-display text-lg font-semibold">{title}</h3>
          <p className="mt-1 text-xs text-slate-500">{description}</p>
        </div>

        <button
          onClick={() => void load()}
          disabled={loading}
          className="rounded-lg border border-slate-700 p-2 text-slate-400 hover:text-white disabled:opacity-50"
          title="Refresh"
        >
          <RefreshCw size={15} />
        </button>
      </div>

      {loading && (
        <div className="flex items-center gap-2 py-6 text-xs text-slate-400">
          <Loader2 size={15} className="animate-spin" />
          Loading backend response...
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-rose-500/30 bg-rose-500/5 p-3 text-xs text-rose-300">
          <AlertTriangle size={14} className="mr-2 inline" />
          {error}
        </div>
      )}

      {data && (
        <pre className="max-h-[520px] overflow-auto rounded-lg border border-slate-800 bg-slate-950/80 p-4 text-[10px] leading-relaxed text-slate-300">
          {pretty(data)}
        </pre>
      )}
    </section>
  );
}

function AnalysisPanel({
  title,
  description,
  endpoint,
  fields,
}: {
  title: string;
  description: string;
  endpoint: string;
  fields: Array<{
    name: string;
    label: string;
    initial: string;
    type?: string;
  }>;
}) {
  const [values, setValues] = useState<Record<string, string>>(
    Object.fromEntries(fields.map((field) => [field.name, field.initial]))
  );
  const [result, setResult] = useState<JsonData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function analyse() {
    setLoading(true);
    setError("");
    setResult(null);

    const payload: Record<string, unknown> = {};

    for (const field of fields) {
      const value = values[field.name];

      if (field.type === "number") {
        const numberValue = Number(value);
        if (!Number.isFinite(numberValue)) {
          setError(`Invalid number for ${field.label}`);
          setLoading(false);
          return;
        }
        payload[field.name] = numberValue;
      } else {
        payload[field.name] = value;
      }
    }

    try {
      const response = await fetch(`${API}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await readJsonResponse(response);

      if (!response.ok) {
        throw new Error(
          errorMessage(
            data.detail,
            `HTTP ${response.status} ${response.statusText}`
          )
        );
      }

      setResult(data);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Analysis failed"
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="panel p-5 space-y-4">
      <div>
        <h3 className="font-display text-lg font-semibold">{title}</h3>
        <p className="mt-1 text-xs text-slate-500">{description}</p>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {fields.map((field) => (
          <label key={field.name} className="space-y-1">
            <span className="text-[10px] text-slate-400">
              {field.label}
            </span>
            <input
              type={field.type === "number" ? "number" : "text"}
              step={field.type === "number" ? "any" : undefined}
              value={values[field.name]}
              onChange={(event) =>
                setValues((current) => ({
                  ...current,
                  [field.name]: event.target.value,
                }))
              }
              className="w-full rounded-lg border border-slate-700 bg-slate-950/70 px-3 py-2 text-xs text-slate-100 outline-none focus:border-sky-500"
            />
          </label>
        ))}
      </div>

      <button
        onClick={() => void analyse()}
        disabled={loading}
        className="rounded-lg bg-sky-500 px-4 py-2.5 text-xs font-semibold text-slate-950 hover:bg-sky-400 disabled:opacity-50"
      >
        {loading ? "Processing..." : "Run analysis"}
      </button>

      {error && (
        <div className="rounded-lg border border-rose-500/30 bg-rose-500/5 p-3 text-xs text-rose-300">
          {error}
        </div>
      )}

      {result && (
        <div className="space-y-2">
          <div className="text-xs font-semibold text-emerald-300">
            Backend response received
          </div>
          <pre className="max-h-[500px] overflow-auto rounded-lg border border-slate-800 bg-slate-950/80 p-4 text-[10px] leading-relaxed text-slate-300">
            {pretty(result)}
          </pre>
        </div>
      )}
    </section>
  );
}

export function SatelliteIntelligencePanel() {
  return (
    <div className="space-y-4">
      <div className="panel p-5">
        <div className="eyebrow mb-2">EARTH OBSERVATION</div>
        <div className="flex items-center gap-3">
          <Satellite size={23} className="text-sky-400" />
          <h2 className="font-display text-xl font-semibold">
            Satellite & Geospatial Intelligence
          </h2>
        </div>
        <p className="mt-2 text-xs text-slate-500">
          Discover satellite collections, inspect granule metadata and
          review the status of connected geospatial services.
        </p>
      </div>

      <DataPanel
        title="Satellite service status"
        description="Connection and availability information."
        endpoint="/api/health"
      />

      <DataPanel
        title="Satellite collection catalogue"
        description="NASA Earthdata collection metadata."
        endpoint="/api/nasa/collections?keyword=MODIS&page_size=10"
      />

      <DataPanel
        title="Granule search"
        description="Example search for MODIS granule metadata."
        endpoint="/api/nasa/granules?keyword=MODIS&page_size=10"
      />
    </div>
  );
}

export function ConfidenceIntelligencePanel() {
  return (
    <div className="space-y-4">
      <div className="panel p-5">
        <div className="eyebrow mb-2">EVIDENCE EVALUATION</div>
        <div className="flex items-center gap-3">
          <ShieldCheck size={23} className="text-emerald-400" />
          <h2 className="font-display text-xl font-semibold">
            Confidence Intelligence
          </h2>
        </div>
        <p className="mt-2 text-xs text-slate-500">
          Evaluate evidence consistency, source agreement, outliers and
          uncertainty using the connected analysis engine.
        </p>
      </div>

      <AnalysisPanel
        title="Evidence confidence analysis"
        description="Submit observations using the schema accepted by the backend."
        endpoint="/api/science/confidence/analyze"
        fields={[
          {
            name: "domain_id",
            label: "Scientific domain ID",
            initial: "temperature",
          },
          {
            name: "latitude",
            label: "Latitude",
            initial: "26.8467",
            type: "number",
          },
          {
            name: "longitude",
            label: "Longitude",
            initial: "80.9462",
            type: "number",
          },
        ]}
      />

      <DataPanel
        title="Confidence engine status"
        description="Confidence service availability."
        endpoint="/api/science/confidence/status"
      />
    </div>
  );
}

export function EnvironmentalAnomaliesPanel() {
  return (
    <div className="space-y-4">
      <div className="panel p-5">
        <div className="eyebrow mb-2">ENVIRONMENTAL MONITORING</div>
        <div className="flex items-center gap-3">
          <Activity size={23} className="text-amber-400" />
          <h2 className="font-display text-xl font-semibold">
            Environmental Anomaly Detection
          </h2>
        </div>
        <p className="mt-2 text-xs text-slate-500">
          Examine unusual patterns in observations using robust
          statistical methods. An anomaly is a statistical signal,
          not automatically evidence of a real-world event.
        </p>
      </div>

      <AnalysisPanel
        title="Anomaly analysis"
        description="Provide a domain and observation location for analysis."
        endpoint="/api/science/anomalies/analyze"
        fields={[
          {
            name: "domain_id",
            label: "Scientific domain ID",
            initial: "temperature",
          },
          {
            name: "latitude",
            label: "Latitude",
            initial: "26.8467",
            type: "number",
          },
          {
            name: "longitude",
            label: "Longitude",
            initial: "80.9462",
            type: "number",
          },
        ]}
      />

      <DataPanel
        title="Anomaly engine status"
        description="Environmental anomaly service availability."
        endpoint="/api/science/anomalies/status"
      />
    </div>
  );
}

export function ResearchReportsPanel() {
  const [report, setReport] = useState("");
  const [title, setTitle] = useState("GeoNOVA Earth Science Research Report");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<JsonData | null>(null);

  async function generateReport() {
    setLoading(true);
    setError("");
    setResult(null);

    try {
      let findings: unknown;

      try {
        findings = JSON.parse(report);
      } catch {
        throw new Error(
          "Enter valid JSON for findings, methodology, sources and limitations."
        );
      }

      const response = await fetch(`${API}/api/reports/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title,
          ...(
            findings &&
            typeof findings === "object" &&
            !Array.isArray(findings)
              ? findings
              : { findings }
          ),
        }),
      });

      const data = await readJsonResponse(response);

      if (!response.ok) {
        throw new Error(
          errorMessage(
            data.detail,
            `HTTP ${response.status} ${response.statusText}`
          )
        );
      }

      setResult(data);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Report generation failed"
      );
    } finally {
      setLoading(false);
    }
  }

  async function exportReport(format: "markdown" | "json" | "csv") {
    if (!result) return;

    try {
      const response = await fetch(
        `${API}/api/reports/export/${format}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(result),
        }
      );

      if (!response.ok) {
        const data = await readJsonResponse(response);
        throw new Error(
          errorMessage(
            data.detail,
            `HTTP ${response.status} ${response.statusText}`
          )
        );
      }

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `geonova-report.${format === "markdown" ? "md" : format}`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Export failed"
      );
    }
  }

  return (
    <div className="space-y-4">
      <div className="panel p-5">
        <div className="eyebrow mb-2">SCIENTIFIC DOCUMENTATION</div>
        <div className="flex items-center gap-3">
          <FileText size={23} className="text-sky-400" />
          <h2 className="font-display text-xl font-semibold">
            Research Reports
          </h2>
        </div>
        <p className="mt-2 text-xs text-slate-500">
          Generate structured reports from supplied research findings,
          methodology, sources and limitations.
        </p>
      </div>

      <DataPanel
        title="Report service status"
        description="Research report backend availability."
        endpoint="/api/reports/status"
      />

      <section className="panel space-y-4 p-5">
        <div className="text-sm font-semibold">Generate a report</div>

        <label className="block space-y-1">
          <span className="text-[10px] text-slate-400">Report title</span>
          <input
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            className="w-full rounded-lg border border-slate-700 bg-slate-950/70 px-3 py-2 text-xs text-slate-100 outline-none focus:border-sky-500"
          />
        </label>

        <label className="block space-y-1">
          <span className="text-[10px] text-slate-400">
            Research data (JSON)
          </span>
          <textarea
            value={report}
            onChange={(event) => setReport(event.target.value)}
            rows={12}
            placeholder={`{
  "findings": [],
  "sources": [],
  "methodology": [],
  "limitations": [],
  "confidence": {},
  "anomalies": []
}`}
            className="w-full rounded-lg border border-slate-700 bg-slate-950/70 p-3 font-mono text-xs text-slate-100 outline-none focus:border-sky-500"
          />
        </label>

        <button
          onClick={() => void generateReport()}
          disabled={loading || !report.trim() || !title.trim()}
          className="rounded-lg bg-sky-500 px-4 py-2.5 text-xs font-semibold text-slate-950 disabled:opacity-50"
        >
          {loading ? "Generating..." : "Generate research report"}
        </button>

        {error && (
          <div className="rounded-lg border border-rose-500/30 bg-rose-500/5 p-3 text-xs text-rose-300">
            {error}
          </div>
        )}

        {result && (
          <div className="space-y-3">
            <div className="text-xs font-semibold text-emerald-300">
              Report generated
            </div>

            <div className="flex flex-wrap gap-2">
              <button
                onClick={() => void exportReport("markdown")}
                className="flex items-center gap-2 rounded-lg border border-slate-700 px-3 py-2 text-xs text-sky-300"
              >
                <Download size={13} /> Markdown
              </button>
              <button
                onClick={() => void exportReport("json")}
                className="flex items-center gap-2 rounded-lg border border-slate-700 px-3 py-2 text-xs text-sky-300"
              >
                <Download size={13} /> JSON
              </button>
              <button
                onClick={() => void exportReport("csv")}
                className="flex items-center gap-2 rounded-lg border border-slate-700 px-3 py-2 text-xs text-sky-300"
              >
                <Download size={13} /> CSV
              </button>
            </div>

            <pre className="max-h-[500px] overflow-auto rounded-lg border border-slate-800 bg-slate-950/80 p-4 text-[10px] leading-relaxed text-slate-300">
              {pretty(result)}
            </pre>
          </div>
        )}
      </section>
    </div>
  );
}
