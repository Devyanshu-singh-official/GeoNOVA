
"use client";

import { useState } from "react";
import {
  FileText,
  Loader2,
  CheckCircle2,
  AlertCircle,
  FileJson,
  Table2,
  ShieldCheck,
  Fingerprint,
  Database,
  ClipboardList,
} from "lucide-react";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  "http://127.0.0.1:8000";

type Observation = {
  date: string;
  [key: string]: string | number | null;
};

type Props = {
  domainId: string;
  observations: Observation[];
  parameterKey: string;
  parameterLabel: string;
  unit: string;
};

type AnalysisResult = {
  status: "success" | "failed";
  result?: Record<string, unknown>;
  error?: string;
};

type GeneratedReport = {
  report_id: string;
  title: string;
  generated_at: string;
  executive_summary: string;
  research_scope: {
    domains: string[];
    observation_count: number;
    source_record_count: number;
    finding_count: number;
  };
  analytical_results: {
    trend_analysis?: Record<string, unknown> | null;
  };
};

type ReproducibilityManifest = {
  manifest_version: string;
  generated_at: string;
  project: string;
  domain_id: string;
  parameter: {
    key: string;
    label: string;
    unit: string;
  };
  dataset: {
    observation_count: number;
    valid_date_count: number;
    first_observation_date: string | null;
    last_observation_date: string | null;
    source_identifiers: string[];
    input_fingerprint: string;
    fingerprint_algorithm: string;
  };
  preprocessing: {
    temporal_aggregation: string;
    minimum_daily_coverage_percent: number;
    precipitation_aggregation: string;
    other_variable_aggregation: string;
    missing_month_handling: string;
    monthly_record_count: number;
    valid_month_count: number;
  };
  statistical_configuration: {
    significance_level: number;
    methods: {
      name: string;
      endpoint: string;
      seasonal_adjustment?: boolean;
    }[];
  };
  reproducibility_notes: string[];
};

function parseDate(value: string): Date | null {
  const normalized = value.trim();

  let year: number;
  let month: number;
  let day: number;

  if (/^\d{8}$/.test(normalized)) {
    year = Number(normalized.slice(0, 4));
    month = Number(normalized.slice(4, 6));
    day = Number(normalized.slice(6, 8));
  } else {
    const match = normalized.match(/^(\d{4})-(\d{2})-(\d{2})/);

    if (!match) return null;

    year = Number(match[1]);
    month = Number(match[2]);
    day = Number(match[3]);
  }

  const date = new Date(Date.UTC(year, month - 1, day));

  if (
    date.getUTCFullYear() !== year ||
    date.getUTCMonth() !== month - 1 ||
    date.getUTCDate() !== day
  ) {
    return null;
  }

  return date;
}

function daysInMonth(year: number, month: number) {
  return new Date(Date.UTC(year, month, 0)).getUTCDate();
}

function aggregateMonthly(
  observations: Observation[],
  parameterKey: string,
  unit: string
) {
  const grouped = new Map<
    string,
    { year: number; month: number; values: number[] }
  >();

  const precipitation =
    /precip|rain|prectot/i.test(parameterKey) &&
    /mm\/day|mm day-1|mm d-1/i.test(unit);

  for (const observation of observations) {
    const date = parseDate(observation.date);
    if (!date) continue;

    const year = date.getUTCFullYear();
    const month = date.getUTCMonth() + 1;
    const key = `${year}-${String(month).padStart(2, "0")}`;

    if (!grouped.has(key)) {
      grouped.set(key, { year, month, values: [] });
    }

    const value = observation[parameterKey];

    if (typeof value === "number" && Number.isFinite(value)) {
      grouped.get(key)!.values.push(value);
    }
  }

  if (grouped.size === 0) return [];

  const keys = [...grouped.keys()].sort();
  const first = grouped.get(keys[0])!;
  const last = grouped.get(keys[keys.length - 1])!;

  const result: { date: string; value: number | null }[] = [];

  let year = first.year;
  let month = first.month;

  while (
    year < last.year ||
    (year === last.year && month <= last.month)
  ) {
    const key = `${year}-${String(month).padStart(2, "0")}`;
    const group = grouped.get(key);

    const expectedDays = daysInMonth(year, month);
    const validDays = group?.values.length ?? 0;
    const coverage = (validDays / expectedDays) * 100;

    let value: number | null = null;

    if (group && validDays > 0 && coverage >= 80) {
      const total = group.values.reduce(
        (sum, current) => sum + current,
        0
      );

      value = precipitation ? total : total / validDays;
    }

    result.push({
      date: `${key}-01`,
      value:
        value !== null && Number.isFinite(value)
          ? value
          : null,
    });

    month++;

    if (month > 12) {
      month = 1;
      year++;
    }
  }

  return result;
}

function createInputFingerprint(
  observations: Observation[]
): string {
  const normalized = observations
    .map((item) => {
      const ordered: Record<string, string | number | null> = {};

      Object.keys(item)
        .sort()
        .forEach((key) => {
          ordered[key] = item[key];
        });

      return ordered;
    })
    .sort((a, b) =>
      JSON.stringify(a).localeCompare(JSON.stringify(b))
    );

  const input = JSON.stringify(normalized);
  let hash = 2166136261;

  for (let index = 0; index < input.length; index++) {
    hash ^= input.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }

  return (
    "fnv1a32-" +
    (hash >>> 0).toString(16).padStart(8, "0")
  );
}

function extractSourceIdentifiers(
  observations: Observation[]
): string[] {
  const sourceKeys = [
    "source",
    "source_name",
    "source_id",
    "dataset",
    "dataset_id",
    "dataset_name",
    "provider",
    "collection",
  ];

  const identifiers = new Set<string>();

  for (const observation of observations) {
    for (const key of sourceKeys) {
      const value = observation[key];

      if (typeof value === "string" && value.trim()) {
        identifiers.add(`${key}: ${value.trim()}`);
      }
    }
  }

  return [...identifiers].sort();
}

function getObservationDateRange(observations: Observation[]) {
  const dates = observations
    .map((item) => parseDate(item.date))
    .filter((date): date is Date => date !== null)
    .sort((a, b) => a.getTime() - b.getTime());

  if (dates.length === 0) {
    return { first: null, last: null, count: 0 };
  }

  return {
    first: dates[0].toISOString().slice(0, 10),
    last: dates[dates.length - 1].toISOString().slice(0, 10),
    count: dates.length,
  };
}

function createReproducibilityManifest(args: {
  domainId: string;
  parameterKey: string;
  parameterLabel: string;
  unit: string;
  observations: Observation[];
  monthlyObservations: {
    date: string;
    value: number | null;
  }[];
  validMonthlyCount: number;
  precipitation: boolean;
}): ReproducibilityManifest {
  const {
    domainId,
    parameterKey,
    parameterLabel,
    unit,
    observations,
    monthlyObservations,
    validMonthlyCount,
    precipitation,
  } = args;

  const dateRange = getObservationDateRange(observations);

  return {
    manifest_version: "1.0.0",
    generated_at: new Date().toISOString(),
    project: "GeoNOVA",
    domain_id: domainId,

    parameter: {
      key: parameterKey,
      label: parameterLabel,
      unit,
    },

    dataset: {
      observation_count: observations.length,
      valid_date_count: dateRange.count,
      first_observation_date: dateRange.first,
      last_observation_date: dateRange.last,
      source_identifiers: extractSourceIdentifiers(observations),
      input_fingerprint: createInputFingerprint(observations),
      fingerprint_algorithm:
        "FNV-1a 32-bit over sorted normalized observation JSON",
    },

    preprocessing: {
      temporal_aggregation: "Daily to monthly",
      minimum_daily_coverage_percent: 80,
      precipitation_aggregation: precipitation
        ? "Sum of valid daily rates within each month"
        : "Not applied",
      other_variable_aggregation: precipitation
        ? "Not applicable"
        : "Arithmetic mean of valid daily observations",
      missing_month_handling:
        "Missing calendar months retained with null values",
      monthly_record_count: monthlyObservations.length,
      valid_month_count: validMonthlyCount,
    },

    statistical_configuration: {
      significance_level: 0.05,
      methods: [
        {
          name: "Ordinary Mann-Kendall",
          endpoint: "/api/science/statistics/trend",
          seasonal_adjustment: false,
        },
        {
          name: "Dependence-aware trend analysis",
          endpoint: "/api/science/dependence-aware-trends/analyze",
        },
        {
          name: "Seasonal Mann-Kendall",
          endpoint: "/api/science/seasonal-trends/analyze",
        },
      ],
    },

    reproducibility_notes: [
      "The fingerprint identifies the normalized observation input used by this report workflow.",
      "The fingerprint is non-cryptographic and is not proof of data integrity.",
      "Source identifiers are recorded only when corresponding fields are present in observation records.",
      "No source authenticity verification is performed by this frontend component.",
      "Statistical outputs are preserved as returned by their respective API endpoints.",
      "Reproducing results requires access to the same observations and compatible backend implementations.",
    ],
  };
}

async function runAnalysis(
  endpoint: string,
  body: Record<string, unknown>
): Promise<AnalysisResult> {
  try {
    const response = await fetch(`${API_BASE}${endpoint}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(body),
    });

    const text = await response.text();
    let result: unknown;

    try {
      result = text ? JSON.parse(text) : {};
    } catch {
      throw new Error(
        `Invalid server response (HTTP ${response.status}).`
      );
    }

    if (!response.ok) {
      const detail =
        typeof result === "object" &&
        result !== null &&
        "detail" in result
          ? (result as { detail?: unknown }).detail
          : null;

      throw new Error(
        typeof detail === "string"
          ? detail
          : `Request failed with HTTP ${response.status}.`
      );
    }

    return {
      status: "success",
      result:
        typeof result === "object" &&
        result !== null &&
        !Array.isArray(result)
          ? (result as Record<string, unknown>)
          : {},
    };
  } catch (error) {
    return {
      status: "failed",
      error:
        error instanceof Error
          ? error.message
          : "Analysis request failed.",
    };
  }
}

export default function ResearchReportPanel({
  domainId,
  observations,
  parameterKey,
  parameterLabel,
  unit,
}: Props) {
  const [title, setTitle] = useState(
    "GeoNOVA Earth Intelligence Research Report"
  );

  const [question, setQuestion] = useState(
    `How has ${parameterLabel} changed over time in the selected Earth system domain?`
  );

  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState<"json" | "csv" | null>(
    null
  );
  const [error, setError] = useState("");
  const [report, setReport] = useState<GeneratedReport | null>(
    null
  );
  const [manifest, setManifest] =
    useState<ReproducibilityManifest | null>(null);

  const validObservations = observations.filter(
    (item) =>
      item &&
      typeof item.date === "string" &&
      item.date.length > 0
  );

  const monthlyObservations = aggregateMonthly(
    validObservations,
    parameterKey,
    unit
  );

  const validMonthlyCount = monthlyObservations.filter(
    (item) => item.value !== null
  ).length;

  const precipitation =
    /precip|rain|prectot/i.test(parameterKey) &&
    /mm\/day|mm day-1|mm d-1/i.test(unit);

  async function buildPayload() {
    const alpha = 0.05;

    const currentManifest = createReproducibilityManifest({
      domainId,
      parameterKey,
      parameterLabel,
      unit,
      observations: validObservations,
      monthlyObservations,
      validMonthlyCount,
      precipitation,
    });

    const analysisBody = {
      observations: monthlyObservations,
      alpha,
    };

    const [ordinary, dependence, seasonal] = await Promise.all([
      runAnalysis("/api/science/statistics/trend", {
        domain_id: domainId,
        parameter_key: parameterKey,
        unit,
        observations: monthlyObservations,
        seasonal_adjustment: false,
        alpha,
      }),

      runAnalysis(
        "/api/science/dependence-aware-trends/analyze",
        analysisBody
      ),

      runAnalysis(
        "/api/science/seasonal-trends/analyze",
        analysisBody
      ),
    ]);

    const trendAnalysis = {
      analysis_configuration: {
        domain_id: domainId,
        parameter_key: parameterKey,
        parameter_label: parameterLabel,
        unit,
        significance_level: alpha,
        seasonal_adjustment_in_ordinary_test: false,
        monthly_aggregation: true,
        minimum_daily_coverage_percent: 80,
        monthly_observation_count: monthlyObservations.length,
        valid_month_count: validMonthlyCount,
      },

      ordinary_mann_kendall: ordinary,
      dependence_aware_trend: dependence,
      seasonal_mann_kendall: seasonal,

      analysis_completeness: {
        successful_methods: [ordinary, dependence, seasonal].filter(
          (item) => item.status === "success"
        ).length,
        total_methods: 3,
        complete: [ordinary, dependence, seasonal].every(
          (item) => item.status === "success"
        ),
      },
    };

    const methodology = [
      "Daily observations were aggregated into monthly records.",
      "Monthly records require at least 80% daily coverage.",
      precipitation
        ? "Precipitation variables identified as daily rates are aggregated as monthly totals."
        : "Other variables are aggregated as monthly means.",
      "Missing calendar months are retained as null observations.",
      "Ordinary Mann-Kendall, dependence-aware trend and Seasonal Mann-Kendall endpoints were independently requested.",
      "The significance threshold for this report's analysis requests is alpha = 0.05.",
      "The actual API response from each statistical endpoint is preserved in the report.",
      "A reproducibility manifest records the input fingerprint, date range, source identifiers when available, preprocessing configuration and statistical methods.",
      `Reproducibility manifest: ${JSON.stringify(currentManifest)}`,
    ];

    const body = {
      title,
      research_question: question,
      domains: [domainId],
      sources: currentManifest.dataset.source_identifiers,
      observations: validObservations,
      findings: [],
      confidence_analysis: null,
      anomaly_analysis: null,
      trend_analysis: trendAnalysis,
      reproducibility_manifest: currentManifest,
      methodology,
      limitations: [
        "The report service does not independently verify source authenticity.",
        "Statistical endpoint failures are recorded and do not count as successful analyses.",
        "The dependence-aware endpoint uses an approximate AR(1) adjustment.",
        "The seasonal Mann-Kendall endpoint does not itself correct for serial correlation.",
        "No confidence analysis or anomaly analysis is attached by this report workflow.",
        "Statistical significance does not establish causation.",
        "Point observations must not automatically be interpreted as regional averages.",
        "The FNV-1a 32-bit input fingerprint is a change-detection aid, not a cryptographic integrity guarantee.",
        "Source identifiers are extracted from observation fields when available; missing identifiers are not inferred.",
        "Reproducibility depends on access to the same input data and compatible statistical endpoint implementations.",
      ],
    };

    return { body, manifest: currentManifest };
  }

  async function generateReport() {
    if (title.trim().length < 3) {
      setError("Report title must contain at least 3 characters.");
      return;
    }

    if (question.trim().length < 5) {
      setError("Please enter a research question of at least 5 characters.");
      return;
    }

    if (validObservations.length === 0) {
      setError("No valid observation records are available.");
      return;
    }

    if (validMonthlyCount < 3) {
      setError(
        "At least three valid monthly observations are required to generate the statistical report."
      );
      return;
    }

    setLoading(true);
    setError("");
    setReport(null);
    setManifest(null);

    try {
      const { body, manifest: currentManifest } =
        await buildPayload();

      const response = await fetch(
        `${API_BASE}/api/reports/generate`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }
      );

      const result = await response.json();

      if (!response.ok) {
        throw new Error(
          result.detail ||
            result.message ||
            "Report generation failed."
        );
      }

      if (!result.report) {
        throw new Error("The API returned no report.");
      }

      setReport(result.report);
      setManifest(currentManifest);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to generate the research report."
      );
    } finally {
      setLoading(false);
    }
  }

  async function exportReport(format: "json" | "csv") {
    setExporting(format);
    setError("");

    try {
      const { body, manifest: currentManifest } =
        await buildPayload();

      const response = await fetch(
        `${API_BASE}/api/reports/export/${format}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }
      );

      if (!response.ok) {
        let message = "Export failed.";

        try {
          const result = await response.json();
          message = result.detail || message;
        } catch {
          // Retain fallback message.
        }

        throw new Error(message);
      }

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");

      anchor.href = url;
      anchor.download =
        format === "json"
          ? "geonova_research_report.json"
          : "geonova_observations.csv";

      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();

      window.setTimeout(() => URL.revokeObjectURL(url), 1000);

      setManifest(currentManifest);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to export the report."
      );
    } finally {
      setExporting(null);
    }
  }

  const analysis =
    report?.analytical_results?.trend_analysis;

  const completeness = analysis?.analysis_completeness as
    | {
        successful_methods?: number;
        total_methods?: number;
        complete?: boolean;
      }
    | undefined;

  return (
    <section className="space-y-5 rounded-2xl border border-slate-800 bg-slate-950/60 p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <FileText className="h-5 w-5 text-cyan-400" />
            <h2 className="text-lg font-semibold text-slate-100">
              Scientific Research Reports
            </h2>
          </div>

          <p className="mt-1 text-sm text-slate-400">
            Generate research reports with statistical results,
            data provenance and reproducibility metadata.
          </p>
        </div>

        <span className="rounded-full border border-cyan-800/60 bg-cyan-950/40 px-3 py-1 text-xs text-cyan-300">
          Research Report Engine
        </span>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-3">
          <p className="text-xs text-slate-500">Daily records</p>
          <p className="mt-1 text-xl font-semibold text-slate-100">
            {validObservations.length.toLocaleString()}
          </p>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-3">
          <p className="text-xs text-slate-500">
            Valid monthly records
          </p>
          <p className="mt-1 text-xl font-semibold text-slate-100">
            {validMonthlyCount.toLocaleString()}
          </p>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-3">
          <p className="text-xs text-slate-500">
            Selected variable
          </p>
          <p className="mt-1 truncate text-sm font-semibold text-slate-100">
            {parameterLabel}
          </p>
        </div>
      </div>

      <div className="space-y-2">
        <label className="text-xs font-medium text-slate-300">
          Report title
        </label>
        <input
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          maxLength={200}
          className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-3 text-sm text-slate-100 outline-none focus:border-cyan-500"
        />
      </div>

      <div className="space-y-2">
        <label className="text-xs font-medium text-slate-300">
          Research question
        </label>
        <textarea
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          rows={3}
          maxLength={3000}
          className="w-full resize-y rounded-lg border border-slate-700 bg-slate-900 px-3 py-3 text-sm text-slate-100 outline-none focus:border-cyan-500"
          placeholder="Enter the scientific question..."
        />
      </div>

      <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-3">
        <p className="text-xs font-semibold text-slate-200">
          Statistical engines included
        </p>
        <ul className="mt-2 space-y-1 text-xs text-slate-400">
          <li>• Ordinary Mann–Kendall trend analysis</li>
          <li>• Dependence-aware trend analysis</li>
          <li>• Seasonal Mann–Kendall analysis</li>
        </ul>
        <p className="mt-2 text-[10px] leading-relaxed text-slate-500">
          Generating or exporting a report runs these three
          endpoints again using alpha = 0.05. Failed methods
          are recorded rather than hidden.
        </p>
      </div>

      <div className="rounded-xl border border-cyan-900/50 bg-cyan-950/10 p-3">
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-cyan-400" />
          <p className="text-xs font-semibold text-cyan-200">
            Reproducibility and provenance
          </p>
        </div>

        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <div className="flex items-start gap-2">
            <Fingerprint className="mt-0.5 h-4 w-4 text-slate-400" />
            <div>
              <p className="text-xs text-slate-200">
                Input fingerprint
              </p>
              <p className="mt-1 text-[10px] text-slate-500">
                Deterministic fingerprint of normalized observation records
              </p>
            </div>
          </div>

          <div className="flex items-start gap-2">
            <Database className="mt-0.5 h-4 w-4 text-slate-400" />
            <div>
              <p className="text-xs text-slate-200">
                Source identifiers
              </p>
              <p className="mt-1 text-[10px] text-slate-500">
                Captured from available dataset and observation metadata
              </p>
            </div>
          </div>

          <div className="flex items-start gap-2">
            <ClipboardList className="mt-0.5 h-4 w-4 text-slate-400" />
            <div>
              <p className="text-xs text-slate-200">
                Method configuration
              </p>
              <p className="mt-1 text-[10px] text-slate-500">
                Statistical endpoints, alpha and preprocessing rules
              </p>
            </div>
          </div>

          <div className="flex items-start gap-2">
            <FileJson className="mt-0.5 h-4 w-4 text-slate-400" />
            <div>
              <p className="text-xs text-slate-200">
                Structured manifest
              </p>
              <p className="mt-1 text-[10px] text-slate-500">
                Included in the report request and methodology metadata
              </p>
            </div>
          </div>
        </div>
      </div>

      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          onClick={generateReport}
          disabled={
            loading ||
            exporting !== null ||
            validMonthlyCount < 3
          }
          className="inline-flex items-center gap-2 rounded-lg bg-cyan-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-cyan-500 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <FileText className="h-4 w-4" />
          )}
          {loading
            ? "Running analyses and generating..."
            : "Generate Research Report"}
        </button>

        <button
          type="button"
          onClick={() => exportReport("json")}
          disabled={
            loading ||
            exporting !== null ||
            validMonthlyCount < 3
          }
          className="inline-flex items-center gap-2 rounded-lg border border-slate-700 px-4 py-3 text-sm text-slate-200 hover:bg-slate-800 disabled:opacity-50"
        >
          {exporting === "json" ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <FileJson className="h-4 w-4" />
          )}
          Export JSON
        </button>

        <button
          type="button"
          onClick={() => exportReport("csv")}
          disabled={
            loading ||
            exporting !== null ||
            validMonthlyCount < 3
          }
          className="inline-flex items-center gap-2 rounded-lg border border-slate-700 px-4 py-3 text-sm text-slate-200 hover:bg-slate-800 disabled:opacity-50"
        >
          {exporting === "csv" ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Table2 className="h-4 w-4" />
          )}
          Export CSV
        </button>
      </div>

      {error && (
        <div className="flex items-start gap-2 rounded-lg border border-red-900/60 bg-red-950/30 p-3 text-sm text-red-300">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          {error}
        </div>
      )}

      {manifest && (
        <div className="space-y-3 rounded-xl border border-cyan-900/50 bg-slate-900/70 p-4">
          <div className="flex items-center gap-2">
            <Fingerprint className="h-4 w-4 text-cyan-400" />
            <h3 className="text-sm font-semibold text-slate-100">
              Reproducibility manifest
            </h3>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <p className="text-[10px] uppercase tracking-wide text-slate-500">
                Input fingerprint
              </p>
              <p className="mt-1 break-all font-mono text-xs text-cyan-300">
                {manifest.dataset.input_fingerprint}
              </p>
            </div>

            <div>
              <p className="text-[10px] uppercase tracking-wide text-slate-500">
                Manifest version
              </p>
              <p className="mt-1 text-xs text-slate-200">
                {manifest.manifest_version}
              </p>
            </div>

            <div>
              <p className="text-[10px] uppercase tracking-wide text-slate-500">
                Observation date range
              </p>
              <p className="mt-1 text-xs text-slate-200">
                {manifest.dataset.first_observation_date || "Unavailable"}
                {" — "}
                {manifest.dataset.last_observation_date || "Unavailable"}
              </p>
            </div>

            <div>
              <p className="text-[10px] uppercase tracking-wide text-slate-500">
                Source identifiers found
              </p>
              <p className="mt-1 text-xs text-slate-200">
                {manifest.dataset.source_identifiers.length}
              </p>
            </div>
          </div>

          {manifest.dataset.source_identifiers.length > 0 ? (
            <div>
              <p className="mb-2 text-[10px] uppercase tracking-wide text-slate-500">
                Recorded sources
              </p>
              <div className="flex flex-wrap gap-2">
                {manifest.dataset.source_identifiers.map((source) => (
                  <span
                    key={source}
                    className="rounded-md border border-slate-700 bg-slate-950 px-2 py-1 text-[10px] text-slate-300"
                  >
                    {source}
                  </span>
                ))}
              </div>
            </div>
          ) : (
            <p className="text-xs text-amber-300">
              No source identifiers were present in the supplied
              observation records. Source provenance is therefore
              incomplete.
            </p>
          )}

          <details className="rounded-lg border border-slate-800 bg-slate-950/70 p-3">
            <summary className="cursor-pointer text-xs font-medium text-slate-300">
              View complete manifest JSON
            </summary>
            <pre className="mt-3 max-h-80 overflow-auto whitespace-pre-wrap break-words text-[10px] leading-5 text-slate-400">
              {JSON.stringify(manifest, null, 2)}
            </pre>
          </details>

          <p className="text-[10px] leading-relaxed text-slate-500">
            The fingerprint is a non-cryptographic change-detection
            identifier. It does not authenticate the dataset or
            independently validate scientific results.
          </p>
        </div>
      )}

      {report && (
        <div className="space-y-4 rounded-xl border border-emerald-800/50 bg-emerald-950/10 p-4">
          <div className="flex items-center gap-2 text-emerald-300">
            <CheckCircle2 className="h-5 w-5" />
            <span className="font-semibold">
              Research report generated
            </span>
          </div>

          <div>
            <p className="text-xs text-slate-500">Report ID</p>
            <p className="mt-1 font-mono text-sm text-slate-200">
              {report.report_id}
            </p>
          </div>

          <div>
            <p className="text-xs text-slate-500">
              Executive summary
            </p>
            <p className="mt-2 text-sm leading-7 text-slate-300">
              {report.executive_summary}
            </p>
          </div>

          {completeness && (
            <div className="rounded-lg border border-slate-800 bg-slate-900/70 p-3">
              <p className="text-xs font-semibold text-slate-200">
                Statistical analysis completeness
              </p>
              <p className="mt-2 text-lg font-semibold text-white">
                {String(completeness.successful_methods)} /{" "}
                {String(completeness.total_methods)}
              </p>
              <p className="text-xs text-slate-400">
                Statistical methods successfully executed
              </p>
            </div>
          )}

          <div className="grid gap-3 sm:grid-cols-3">
            {[
              {
                label: "Ordinary Mann–Kendall",
                key: "ordinary_mann_kendall",
              },
              {
                label: "Dependence-aware",
                key: "dependence_aware_trend",
              },
              {
                label: "Seasonal Mann–Kendall",
                key: "seasonal_mann_kendall",
              },
            ].map((item) => {
              const method = analysis?.[item.key] as
                | AnalysisResult
                | undefined;

              return (
                <div
                  key={item.key}
                  className="rounded-lg border border-slate-800 bg-slate-900/70 p-3"
                >
                  <p className="text-xs text-slate-300">
                    {item.label}
                  </p>
                  <p
                    className={`mt-2 text-xs font-semibold ${
                      method?.status === "success"
                        ? "text-emerald-400"
                        : "text-amber-400"
                    }`}
                  >
                    {method?.status === "success"
                      ? "Completed"
                      : "Failed"}
                  </p>
                  {method?.error && (
                    <p className="mt-2 break-words text-[10px] text-amber-300">
                      {method.error}
                    </p>
                  )}
                </div>
              );
            })}
          </div>

          <p className="text-xs text-slate-500">
            Generated:{" "}
            {new Date(report.generated_at).toLocaleString()}
          </p>

          <p className="text-xs leading-5 text-amber-300/80">
            Statistical outputs are included as returned by the
            backend. This report does not independently validate
            their scientific correctness.
          </p>
        </div>
      )}
    </section>
  );
}
