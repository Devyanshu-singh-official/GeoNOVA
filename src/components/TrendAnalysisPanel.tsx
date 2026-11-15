
"use client";

import { useMemo, useState } from "react";

import {
  Activity,
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Clock3,
  Loader2,
  Play,
  RefreshCw,
  ShieldCheck,
  TrendingDown,
  TrendingUp,
  BarChart3,
  Waves,
} from "lucide-react";

import type { LucideIcon } from "lucide-react";

const API_BASE = (
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  "http://127.0.0.1:8000"
).replace(/\/$/, "");

// ============================================================
// TYPES
// ============================================================

type DailyObservation = {
  date: string;
  [key: string]: string | number | null;
};

type MonthlyObservation = {
  date: string;
  value: number | null;
};

type Props = {
  domainId: string;
  observations: DailyObservation[];
  parameterKey: string;
  parameterLabel: string;
  unit: string;
};

type AnalysisState = {
  loading: boolean;
  error: string | null;
  data: Record<string, unknown> | null;
};

type AnalysisKind =
  | "ordinary"
  | "advanced"
  | "dependence"
  | "seasonal";

type MonthlyAggregation = {
  observations: MonthlyObservation[];
  coverage: {
    date: string;
    expectedDays: number;
    validDays: number;
    coveragePercent: number;
  }[];
  precipitation: boolean;
};

const INITIAL_STATE: AnalysisState = {
  loading: false,
  error: null,
  data: null,
};

// ============================================================
// DATE HELPERS
// ============================================================

function parseObservationDate(value: string): Date | null {
  if (!value) return null;

  const normalized = value.trim();

  let year: number;
  let month: number;
  let day: number;

  if (/^\d{8}$/.test(normalized)) {
    year = Number(normalized.slice(0, 4));
    month = Number(normalized.slice(4, 6));
    day = Number(normalized.slice(6, 8));
  } else {
    const match = normalized.match(
      /^(\d{4})-(\d{2})-(\d{2})/
    );

    if (!match) return null;

    year = Number(match[1]);
    month = Number(match[2]);
    day = Number(match[3]);
  }

  const parsed = new Date(
    Date.UTC(year, month - 1, day)
  );

  if (
    parsed.getUTCFullYear() !== year ||
    parsed.getUTCMonth() !== month - 1 ||
    parsed.getUTCDate() !== day
  ) {
    return null;
  }

  return parsed;
}

function daysInMonth(year: number, month: number): number {
  return new Date(Date.UTC(year, month, 0)).getUTCDate();
}

// ============================================================
// MONTHLY AGGREGATION
// ============================================================

function aggregateMonthly(
  observations: DailyObservation[],
  parameterKey: string,
  unit: string
): MonthlyAggregation {
  const grouped = new Map<
    string,
    {
      values: number[];
      year: number;
      month: number;
    }
  >();

  const precipitation =
    /precip|rain|prectot/i.test(parameterKey) &&
    /mm\/day|mm day-1|mm d-1/i.test(unit);

  for (const observation of observations) {
    const parsedDate = parseObservationDate(
      observation.date
    );

    if (!parsedDate) continue;

    const year = parsedDate.getUTCFullYear();
    const month = parsedDate.getUTCMonth() + 1;

    const key = `${year}-${String(month).padStart(2, "0")}`;

    if (!grouped.has(key)) {
      grouped.set(key, {
        values: [],
        year,
        month,
      });
    }

    const rawValue = observation[parameterKey];

    if (
      typeof rawValue === "number" &&
      Number.isFinite(rawValue)
    ) {
      grouped.get(key)!.values.push(rawValue);
    }
  }

  if (grouped.size === 0) {
    return {
      observations: [],
      coverage: [],
      precipitation,
    };
  }

  const sortedKeys = [...grouped.keys()].sort();

  const first = grouped.get(sortedKeys[0])!;
  const last = grouped.get(sortedKeys[sortedKeys.length - 1])!;

  const monthlyObservations: MonthlyObservation[] = [];
  const coverage: MonthlyAggregation["coverage"] = [];

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

    const coveragePercent =
      (validDays / expectedDays) * 100;

    const sufficientCoverage =
      coveragePercent >= 80;

    let value: number | null = null;

    if (
      group &&
      sufficientCoverage &&
      validDays > 0
    ) {
      const total = group.values.reduce(
        (sum, current) => sum + current,
        0
      );

      value = precipitation
        ? total
        : total / validDays;
    }

    monthlyObservations.push({
      date: `${key}-01`,
      value:
        value !== null && Number.isFinite(value)
          ? value
          : null,
    });

    coverage.push({
      date: key,
      expectedDays,
      validDays,
      coveragePercent: Number(
        coveragePercent.toFixed(2)
      ),
    });

    month++;

    if (month > 12) {
      month = 1;
      year++;
    }
  }

  return {
    observations: monthlyObservations,
    coverage,
    precipitation,
  };
}

// ============================================================
// RESPONSE HELPERS
// ============================================================

function asObject(
  value: unknown
): Record<string, unknown> {
  if (
    typeof value === "object" &&
    value !== null &&
    !Array.isArray(value)
  ) {
    return value as Record<string, unknown>;
  }

  return {};
}

function getNested(
  object: unknown,
  path: string[]
): unknown {
  let current: unknown = object;

  for (const key of path) {
    current = asObject(current)[key];
  }

  return current;
}

function firstAvailable(
  ...values: unknown[]
): unknown {
  return values.find(
    (value) => value !== undefined && value !== null
  );
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) {
    return "Not available";
  }

  if (typeof value === "boolean") {
    return value ? "Yes" : "No";
  }

  if (typeof value === "number") {
    return Number.isFinite(value)
      ? value.toLocaleString(undefined, {
          maximumFractionDigits: 6,
        })
      : "Not available";
  }

  if (typeof value === "string") {
    return value.replaceAll("_", " ");
  }

  return String(value);
}

function formatPValue(value: unknown): string {
  if (
    typeof value !== "number" ||
    !Number.isFinite(value)
  ) {
    return "Not available";
  }

  if (value < 0.000001) {
    return "< 0.000001";
  }

  return value.toFixed(6);
}

function getErrorMessage(
  error: unknown,
  fallback: string
): string {
  return error instanceof Error
    ? error.message
    : fallback;
}

function extractWarnings(
  data: Record<string, unknown>
): unknown[] {
  if (Array.isArray(data.warnings)) {
    return data.warnings;
  }

  const nested = getNested(data, [
    "data_validation",
    "warnings",
  ]);

  return Array.isArray(nested) ? nested : [];
}

// ============================================================
// RESULT CARD
// ============================================================

function ResultCard({
  title,
  subtitle,
  icon: Icon,
  state,
  accent,
  unit,
}: {
  title: string;
  subtitle: string;
  icon: LucideIcon;
  state: AnalysisState;
  accent: string;
  unit: string;
}) {
  const [expanded, setExpanded] = useState(false);

  const data = state.data ?? {};

  const results = asObject(data.results);
  const analysis = asObject(data.analysis);

  const mannKendall = asObject(
    firstAvailable(
      results.mann_kendall,
      results.seasonal_mann_kendall,
      results.ordinary_mann_kendall,
      data.mann_kendall
    )
  );

  const senSlope = asObject(
    firstAvailable(
      results.sen_slope,
      results.seasonal_sen_slope,
      data.sen_slope
    )
  );

  const dependenceComparison = asObject(
    data.comparison
  );

  const pValue = firstAvailable(
    mannKendall.p_value,
    analysis.p_value,
    analysis.mann_kendall_p_value,
    results.p_value,
    getNested(data, ["statistics", "p_value"]),
    getNested(data, ["trend", "p_value"])
  );

  const slope = firstAvailable(
    senSlope.slope_per_year,
    senSlope.slope,
    senSlope.value,
    results.sen_slope_per_year,
    analysis.sen_slope,
    analysis.slope_per_year,
    getNested(data, ["trend", "sen_slope"]),
    getNested(data, ["trend", "slope"])
  );

  const direction = firstAvailable(
    mannKendall.direction,
    analysis.direction,
    results.direction,
    getNested(data, ["trend", "direction"]),
    getNested(data, ["results", "ordinary", "direction"])
  );

  const significant = firstAvailable(
    mannKendall.is_significant,
    analysis.is_significant,
    results.is_significant,
    getNested(data, ["trend", "is_significant"])
  );

  const quality = firstAvailable(
    getNested(data, [
      "data_validation",
      "quality",
      "score",
    ]),
    getNested(data, [
      "data_validation",
      "quality_score",
    ]),
    data.quality_score
  );

  const confidenceInterval = firstAvailable(
    senSlope.confidence_interval,
    results.confidence_interval,
    getNested(data, [
      "trend",
      "confidence_interval",
    ])
  );

  const warnings = extractWarnings(data);

  const hasSummary =
    pValue !== undefined ||
    slope !== undefined ||
    direction !== undefined;

  return (
    <section className="overflow-hidden rounded-2xl border border-slate-800 bg-slate-950">
      <div className="flex items-start justify-between gap-3 border-b border-slate-800 p-4">
        <div className="flex items-start gap-3">
          <div
            className={`rounded-xl border p-2 ${accent}`}
          >
            <Icon size={19} />
          </div>

          <div>
            <h3 className="text-sm font-semibold text-slate-100">
              {title}
            </h3>

            <p className="mt-1 text-xs leading-relaxed text-slate-400">
              {subtitle}
            </p>
          </div>
        </div>

        {state.loading ? (
          <Loader2
            size={18}
            className="animate-spin text-cyan-400"
          />
        ) : state.error ? (
          <AlertCircle
            size={18}
            className="text-rose-400"
          />
        ) : state.data ? (
          <CheckCircle2
            size={18}
            className="text-emerald-400"
          />
        ) : (
          <Clock3
            size={18}
            className="text-slate-500"
          />
        )}
      </div>

      <div className="p-4">
        {state.loading && (
          <div className="flex items-center gap-2 py-5 text-sm text-slate-400">
            <Loader2
              size={16}
              className="animate-spin"
            />
            Running analysis...
          </div>
        )}

        {!state.loading && state.error && (
          <div className="rounded-xl border border-rose-900/60 bg-rose-950/30 p-3">
            <p className="text-xs font-semibold text-rose-300">
              Analysis unavailable
            </p>

            <p className="mt-1 break-words text-xs text-rose-200/80">
              {state.error}
            </p>
          </div>
        )}

        {!state.loading && !state.error && !state.data && (
          <p className="py-4 text-xs text-slate-500">
            Run the analysis to see results.
          </p>
        )}

        {!state.loading && state.data && (
          <>
            {!hasSummary && (
              <p className="mb-3 text-xs text-amber-300">
                The server returned a response, but its result
                fields could not be mapped to the summary.
                Open the full response below.
              </p>
            )}

            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-3">
                <p className="text-[10px] uppercase tracking-wider text-slate-500">
                  P-value
                </p>

                <p className="mt-2 text-lg font-semibold tabular-nums text-white">
                  {formatPValue(pValue)}
                </p>
              </div>

              <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-3">
                <p className="text-[10px] uppercase tracking-wider text-slate-500">
                  Trend direction
                </p>

                <p className="mt-2 text-sm font-semibold capitalize text-white">
                  {formatValue(direction)}
                </p>
              </div>

              <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-3">
                <p className="text-[10px] uppercase tracking-wider text-slate-500">
                  Sen slope / year
                </p>

                <p className="mt-2 text-sm font-semibold tabular-nums text-white">
                  {formatValue(slope)}
                </p>

                {unit && (
                  <p className="mt-1 text-[9px] text-slate-500">
                    {unit} per year
                  </p>
                )}
              </div>

              <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-3">
                <p className="text-[10px] uppercase tracking-wider text-slate-500">
                  Data quality score
                </p>

                <p className="mt-2 text-sm font-semibold tabular-nums text-white">
                  {formatValue(quality)}
                </p>
              </div>
            </div>

            {typeof significant === "boolean" && (
              <div
                className={`mt-3 flex items-center gap-2 rounded-xl border p-3 ${
                  significant
                    ? "border-emerald-800/70 bg-emerald-950/30 text-emerald-300"
                    : "border-amber-800/70 bg-amber-950/20 text-amber-300"
                }`}
              >
                {significant ? (
                  <CheckCircle2 size={16} />
                ) : (
                  <AlertCircle size={16} />
                )}

                <span className="text-xs font-medium">
                  {significant
                    ? "Statistically significant at the selected threshold"
                    : "Not statistically significant at the selected threshold"}
                </span>
              </div>
            )}

            {confidenceInterval !== undefined && (
              <div className="mt-3 rounded-xl border border-slate-800 bg-slate-900/60 p-3">
                <p className="text-[10px] uppercase tracking-wider text-slate-500">
                  Slope confidence interval
                </p>

                <p className="mt-2 break-words text-xs text-slate-200">
                  {Array.isArray(confidenceInterval)
                    ? confidenceInterval
                        .map(formatValue)
                        .join(" to ")
                    : formatValue(confidenceInterval)}
                </p>
              </div>
            )}

            {warnings.length > 0 && (
              <div className="mt-3 rounded-xl border border-amber-900/50 bg-amber-950/20 p-3">
                <p className="mb-2 text-xs font-semibold text-amber-300">
                  Analysis warnings
                </p>

                <ul className="space-y-1">
                  {warnings.slice(0, 6).map((warning, index) => (
                    <li
                      key={index}
                      className="break-words text-xs leading-relaxed text-amber-200/80"
                    >
                      • {formatValue(warning)}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <button
              type="button"
              onClick={() =>
                setExpanded((current) => !current)
              }
              className="mt-4 flex w-full items-center justify-between rounded-lg border border-slate-800 px-3 py-2 text-xs text-slate-300 transition hover:bg-slate-900"
            >
              <span>Full analysis response</span>

              {expanded ? (
                <ChevronUp size={15} />
              ) : (
                <ChevronDown size={15} />
              )}
            </button>

            {expanded && (
              <pre className="mt-3 max-h-96 overflow-auto rounded-xl border border-slate-800 bg-black/40 p-3 text-[10px] leading-relaxed text-slate-300">
                {JSON.stringify(data, null, 2)}
              </pre>
            )}
          </>
        )}
      </div>
    </section>
  );
}

// ============================================================
// MAIN COMPONENT
// ============================================================

export default function TrendAnalysisPanel({
  domainId,
  observations,
  parameterKey,
  parameterLabel,
  unit,
}: Props) {
  const [alpha, setAlpha] = useState("0.05");

  const [seasonalAdjustment, setSeasonalAdjustment] =
    useState(false);

  const [ordinary, setOrdinary] =
    useState<AnalysisState>(INITIAL_STATE);

  const [advanced, setAdvanced] =
    useState<AnalysisState>(INITIAL_STATE);

  const [dependence, setDependence] =
    useState<AnalysisState>(INITIAL_STATE);

  const [seasonal, setSeasonal] =
    useState<AnalysisState>(INITIAL_STATE);

  const [lastRun, setLastRun] = useState<string | null>(
    null
  );

  const [globalError, setGlobalError] = useState<
    string | null
  >(null);

  const monthlyData = useMemo(
    () =>
      aggregateMonthly(
        observations,
        parameterKey,
        unit
      ),
    [observations, parameterKey, unit]
  );

  const validMonthlyCount =
    monthlyData.observations.filter(
      (item) => item.value !== null
    ).length;

  const overallCoverage = useMemo(() => {
    const expected = monthlyData.coverage.reduce(
      (sum, item) => sum + item.expectedDays,
      0
    );

    const valid = monthlyData.coverage.reduce(
      (sum, item) => sum + item.validDays,
      0
    );

    return expected > 0
      ? (valid / expected) * 100
      : 0;
  }, [monthlyData]);

  const running =
    ordinary.loading ||
    advanced.loading ||
    dependence.loading ||
    seasonal.loading;

  // ==========================================================
  // API REQUEST
  // ==========================================================

  async function postAnalysis(
    url: string,
    body: Record<string, unknown>
  ): Promise<Record<string, unknown>> {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(body),
    });

    const responseText = await response.text();

    let payload: unknown = {};

    try {
      payload = responseText
        ? JSON.parse(responseText)
        : {};
    } catch {
      throw new Error(
        `Invalid server response (HTTP ${response.status}).`
      );
    }

    if (!response.ok) {
      const errorObject = asObject(payload);
      const detail = errorObject.detail;

      let message = `Request failed with HTTP ${response.status}.`;

      if (typeof detail === "string") {
        message = detail;
      } else if (Array.isArray(detail)) {
        message = detail
          .map((item) => {
            const entry = asObject(item);
            return String(
              entry.msg ?? entry.message ?? "Validation error"
            );
          })
          .join("; ");
      }

      throw new Error(message);
    }

    return asObject(payload);
  }

  // ==========================================================
  // RUN ALL ANALYSES
  // ==========================================================

  async function runAnalysis() {
    if (!domainId || !parameterKey) {
      setGlobalError(
        "Select a valid science domain and parameter first."
      );
      return;
    }

    if (monthlyData.observations.length === 0) {
      setGlobalError(
        "No valid dated observations are available."
      );
      return;
    }

    if (validMonthlyCount < 8) {
      setGlobalError(
        "At least eight valid monthly observations are required for this investigation."
      );
      return;
    }

    const parsedAlpha = Number(alpha);

    if (
      !Number.isFinite(parsedAlpha) ||
      parsedAlpha <= 0 ||
      parsedAlpha >= 0.5
    ) {
      setGlobalError(
        "Invalid significance threshold."
      );
      return;
    }

    setGlobalError(null);
    setLastRun(null);

    const setLoading = (kind: AnalysisKind) => {
      const state: AnalysisState = {
        loading: true,
        error: null,
        data: null,
      };

      if (kind === "ordinary") setOrdinary(state);
      if (kind === "advanced") setAdvanced(state);
      if (kind === "dependence") setDependence(state);
      if (kind === "seasonal") setSeasonal(state);
    };

    const setResult = (
      kind: AnalysisKind,
      state: AnalysisState
    ) => {
      if (kind === "ordinary") setOrdinary(state);
      if (kind === "advanced") setAdvanced(state);
      if (kind === "dependence") setDependence(state);
      if (kind === "seasonal") setSeasonal(state);
    };

    const kinds: AnalysisKind[] = [
      "ordinary",
      "advanced",
      "dependence",
      "seasonal",
    ];

    kinds.forEach(setLoading);

    const monthlyObservations =
      monthlyData.observations;

    const requests: {
      kind: AnalysisKind;
      url: string;
      body: Record<string, unknown>;
    }[] = [
      // Existing conventional statistical endpoint
      {
        kind: "ordinary",
        url: `${API_BASE}/api/science/statistics/trend`,
        body: {
          domain_id: domainId,
          parameter_key: parameterKey,
          unit,
          observations: monthlyObservations,
          seasonal_adjustment: seasonalAdjustment,
          alpha: parsedAlpha,
        },
      },

      // New Task 51 trend statistics engine
      {
        kind: "advanced",
        url: `${API_BASE}/api/science/trends/analyze`,
        body: {
          observations: monthlyObservations,
          alpha: parsedAlpha,
        },
      },

      // Existing dependence-aware endpoint
      {
        kind: "dependence",
        url: `${API_BASE}/api/science/dependence-aware-trends/analyze`,
        body: {
          observations: monthlyObservations,
          alpha: parsedAlpha,
        },
      },

      // Existing seasonal Mann-Kendall endpoint
      {
        kind: "seasonal",
        url: `${API_BASE}/api/science/seasonal-trends/analyze`,
        body: {
          observations: monthlyObservations,
          alpha: parsedAlpha,
        },
      },
    ];

    await Promise.all(
      requests.map(async ({ kind, url, body }) => {
        try {
          const data = await postAnalysis(url, body);

          setResult(kind, {
            loading: false,
            error: null,
            data,
          });
        } catch (error) {
          setResult(kind, {
            loading: false,
            error: getErrorMessage(
              error,
              "Unable to complete this analysis."
            ),
            data: null,
          });
        }
      })
    );

    setLastRun(new Date().toLocaleString());
  }

  // ==========================================================
  // RESET
  // ==========================================================

  function resetResults() {
    setOrdinary(INITIAL_STATE);
    setAdvanced(INITIAL_STATE);
    setDependence(INITIAL_STATE);
    setSeasonal(INITIAL_STATE);

    setLastRun(null);
    setGlobalError(null);
  }

  // ==========================================================
  // RENDER
  // ==========================================================

  return (
    <div className="space-y-5">
      {/* HEADER */}

      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Activity
              size={19}
              className="text-cyan-400"
            />

            <h2 className="text-base font-semibold text-white">
              Advanced Trend Analysis
            </h2>
          </div>

          <p className="mt-1 text-xs leading-relaxed text-slate-400">
            Compare conventional statistical tests,
            the enhanced trend engine, temporal-dependence
            analysis and seasonal trend methods.
          </p>
        </div>

        <div className="flex items-center gap-2 rounded-lg border border-slate-800 bg-slate-900/60 px-3 py-2">
          <ShieldCheck
            size={15}
            className="text-emerald-400"
          />

          <span className="text-[10px] text-slate-300">
            Independent method results
          </span>
        </div>
      </div>

      {/* DATA SUMMARY */}

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <div className="rounded-xl border border-slate-800 bg-slate-950 p-3">
          <p className="text-[10px] uppercase tracking-wider text-slate-500">
            Parameter
          </p>

          <p className="mt-1 truncate text-sm font-medium text-slate-100">
            {parameterLabel || parameterKey}
          </p>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-950 p-3">
          <p className="text-[10px] uppercase tracking-wider text-slate-500">
            Monthly records
          </p>

          <p className="mt-1 text-sm font-semibold tabular-nums text-slate-100">
            {monthlyData.observations.length}
          </p>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-950 p-3">
          <p className="text-[10px] uppercase tracking-wider text-slate-500">
            Valid months
          </p>

          <p className="mt-1 text-sm font-semibold tabular-nums text-slate-100">
            {validMonthlyCount}
          </p>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-950 p-3">
          <p className="text-[10px] uppercase tracking-wider text-slate-500">
            Daily data coverage
          </p>

          <p className="mt-1 text-sm font-semibold tabular-nums text-slate-100">
            {overallCoverage.toFixed(1)}%
          </p>
        </div>
      </div>

      {/* CONFIGURATION */}

      <section className="rounded-2xl border border-slate-800 bg-slate-950 p-4">
        <div className="mb-4 flex items-center gap-2">
          <BarChart3
            size={16}
            className="text-cyan-400"
          />

          <h3 className="text-sm font-semibold text-white">
            Analysis configuration
          </h3>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <label className="space-y-2">
            <span className="block text-xs text-slate-400">
              Significance threshold (α)
            </span>

            <select
              value={alpha}
              onChange={(event) =>
                setAlpha(event.target.value)
              }
              disabled={running}
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2.5 text-sm text-white outline-none focus:border-cyan-500"
            >
              <option value="0.10">
                0.10 (90% confidence)
              </option>

              <option value="0.05">
                0.05 (95% confidence)
              </option>

              <option value="0.01">
                0.01 (99% confidence)
              </option>
            </select>
          </label>

          <div className="flex items-center justify-between gap-3 rounded-lg border border-slate-800 bg-slate-900/60 px-3 py-3">
            <div>
              <p className="text-xs font-medium text-slate-200">
                Seasonal adjustment
              </p>

              <p className="mt-1 text-[10px] text-slate-500">
                Apply calendar-month adjustment in ordinary analysis
              </p>
            </div>

            <button
              type="button"
              role="switch"
              aria-checked={seasonalAdjustment}
              disabled={running}
              onClick={() =>
                setSeasonalAdjustment(
                  (current) => !current
                )
              }
              className={`relative h-6 w-11 shrink-0 rounded-full transition ${
                seasonalAdjustment
                  ? "bg-cyan-600"
                  : "bg-slate-700"
              }`}
            >
              <span
                className={`absolute top-1 h-4 w-4 rounded-full bg-white transition ${
                  seasonalAdjustment
                    ? "left-6"
                    : "left-1"
                }`}
              />
            </button>
          </div>
        </div>

        <div className="mt-3 rounded-lg border border-slate-800 bg-slate-900/40 p-3 text-[11px] leading-relaxed text-slate-400">
          {monthlyData.precipitation
            ? "Precipitation is aggregated as a monthly total. Months with less than 80% daily coverage are excluded."
            : "Other variables are aggregated as monthly daily means. Months with less than 80% daily coverage are excluded."}
        </div>

        {globalError && (
          <div className="mt-3 flex items-start gap-2 rounded-lg border border-rose-900/60 bg-rose-950/30 p-3 text-xs text-rose-300">
            <AlertCircle
              size={15}
              className="mt-0.5 shrink-0"
            />

            {globalError}
          </div>
        )}

        <div className="mt-4 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={runAnalysis}
            disabled={running || validMonthlyCount < 8}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-cyan-600 px-4 py-2.5 text-xs font-semibold text-white transition hover:bg-cyan-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {running ? (
              <Loader2
                size={15}
                className="animate-spin"
              />
            ) : (
              <Play size={15} />
            )}

            {running
              ? "Running analyses..."
              : "Run all four analyses"}
          </button>

          <button
            type="button"
            onClick={resetResults}
            disabled={running}
            className="inline-flex items-center gap-2 rounded-lg border border-slate-700 px-4 py-2.5 text-xs text-slate-300 transition hover:bg-slate-900 disabled:opacity-50"
          >
            <RefreshCw size={14} />
            Reset
          </button>
        </div>

        {lastRun && (
          <p className="mt-3 text-[10px] text-slate-500">
            Last run: {lastRun}
          </p>
        )}
      </section>

      {/* RESULTS */}

      <section className="space-y-3">
        <div>
          <h3 className="text-sm font-semibold text-white">
            Statistical analysis results
          </h3>

          <p className="mt-1 text-xs text-slate-500">
            Each method runs independently. An unavailable
            endpoint does not prevent the other results from
            appearing.
          </p>
        </div>

        <ResultCard
          title="Conventional Mann–Kendall"
          subtitle="Existing conventional trend test with Sen slope and validation information."
          icon={TrendingUp}
          state={ordinary}
          accent="border-cyan-800/60 bg-cyan-950/30 text-cyan-300"
          unit={unit}
        />

        <ResultCard
          title="Enhanced Trend Statistics Engine · Task 51"
          subtitle="New trend engine using Mann–Kendall, Sen slope and regression-based trend estimation."
          icon={BarChart3}
          state={advanced}
          accent="border-sky-800/60 bg-sky-950/30 text-sky-300"
          unit={unit}
        />

        <ResultCard
          title="Dependence-Aware Trend"
          subtitle="Compares ordinary and approximate AR(1)-adjusted Mann–Kendall results."
          icon={Waves}
          state={dependence}
          accent="border-violet-800/60 bg-violet-950/30 text-violet-300"
          unit={unit}
        />

        <ResultCard
          title="Seasonal Mann–Kendall"
          subtitle="Compares observations within the same calendar month across different years."
          icon={TrendingDown}
          state={seasonal}
          accent="border-amber-800/60 bg-amber-950/30 text-amber-300"
          unit={unit}
        />
      </section>

      {/* SCIENTIFIC LIMITATIONS */}

      <section className="rounded-2xl border border-amber-900/50 bg-amber-950/20 p-4">
        <div className="flex items-center gap-2">
          <AlertCircle
            size={16}
            className="text-amber-400"
          />

          <h3 className="text-xs font-semibold text-amber-300">
            Scientific interpretation requirements
          </h3>
        </div>

        <ul className="mt-3 space-y-2 text-[11px] leading-relaxed text-amber-100/70">
          <li>
            • The enhanced Task 51 engine's conventional
            statistical results do not automatically correct
            for serial correlation or seasonality.
          </li>

          <li>
            • The dependence-aware endpoint uses an approximate
            AR(1) adjustment; its assumptions must be considered.
          </li>

          <li>
            • Seasonal testing and ordinary trend testing answer
            related but different statistical questions.
          </li>

          <li>
            • Multiple testing, missing-data patterns, source
            provenance and measurement uncertainty require
            consideration.
          </li>

          <li>
            • Statistical significance does not establish
            causation or practical environmental importance.
          </li>
        </ul>
      </section>
    </div>
  );
}
