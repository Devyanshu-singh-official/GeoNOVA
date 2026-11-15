
"use client";

import { useMemo, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Clock3,
  Loader2,
  Play,
  RefreshCw,
  Waves,
} from "lucide-react";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  "http://127.0.0.1:8000";

type DailyObservation = {
  date: string;
  [key: string]: string | number | null;
};

type MonthlyObservation = {
  date: string;
  value: number | null;
};

type Props = {
  observations: DailyObservation[];
  parameterKey: string;
  unit: string;
};

type DiagnosticResponse = {
  status?: string;
  analysis?: Record<string, unknown>;
  temporal_dependence?: Record<string, unknown>;
  ordinary_mann_kendall?: Record<string, unknown>;
  dependence_adjusted_mann_kendall?: Record<string, unknown>;
  comparison?: Record<string, unknown>;
  diagnostics?: Record<string, unknown>;
  warnings?: unknown[];
  scientific_limitations?: unknown[];
  [key: string]: unknown;
};

// ============================================================
// HELPERS
// ============================================================

function parseDate(value: string): Date | null {
  if (!value) return null;

  let year: number;
  let month: number;
  let day: number;

  if (/^\d{8}$/.test(value)) {
    year = Number(value.slice(0, 4));
    month = Number(value.slice(4, 6));
    day = Number(value.slice(6, 8));
  } else {
    const match = value.match(/^(\d{4})-(\d{2})-(\d{2})/);
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
  observations: DailyObservation[],
  parameterKey: string,
  unit: string
): MonthlyObservation[] {
  const grouped = new Map<
    string,
    { year: number; month: number; values: number[] }
  >();

  const precipitation =
    /precip|rain|prectot/i.test(parameterKey) &&
    /mm\/day|mm day-1|mm d-1/i.test(unit);

  for (const observation of observations) {
    const parsed = parseDate(observation.date);
    if (!parsed) continue;

    const year = parsed.getUTCFullYear();
    const month = parsed.getUTCMonth() + 1;
    const key = `${year}-${String(month).padStart(2, "0")}`;

    if (!grouped.has(key)) {
      grouped.set(key, { year, month, values: [] });
    }

    const value = observation[parameterKey];

    if (typeof value === "number" && Number.isFinite(value)) {
      grouped.get(key)!.values.push(value);
    }
  }

  if (!grouped.size) return [];

  const keys = [...grouped.keys()].sort();
  const first = grouped.get(keys[0])!;
  const last = grouped.get(keys[keys.length - 1])!;

  const result: MonthlyObservation[] = [];

  let year = first.year;
  let month = first.month;

  while (
    year < last.year ||
    (year === last.year && month <= last.month)
  ) {
    const key = `${year}-${String(month).padStart(2, "0")}`;
    const group = grouped.get(key);

    const validDays = group?.values.length ?? 0;
    const expectedDays = daysInMonth(year, month);

    let value: number | null = null;

    if (
      group &&
      validDays > 0 &&
      validDays / expectedDays >= 0.8
    ) {
      const total = group.values.reduce(
        (sum, current) => sum + current,
        0
      );

      value = precipitation ? total : total / validDays;
    }

    result.push({ date: `${key}-01`, value });

    month++;
    if (month > 12) {
      month = 1;
      year++;
    }
  }

  return result;
}

function asObject(value: unknown): Record<string, unknown> {
  if (
    typeof value === "object" &&
    value !== null &&
    !Array.isArray(value)
  ) {
    return value as Record<string, unknown>;
  }

  return {};
}

function getNumber(
  object: unknown,
  keys: string[]
): number | null {
  const record = asObject(object);

  for (const key of keys) {
    const value = record[key];

    if (typeof value === "number" && Number.isFinite(value)) {
      return value;
    }
  }

  return null;
}

function getText(
  object: unknown,
  keys: string[]
): string | null {
  const record = asObject(object);

  for (const key of keys) {
    const value = record[key];
    if (typeof value === "string") return value;
  }

  return null;
}

function getArray(
  object: unknown,
  keys: string[]
): unknown[] {
  const record = asObject(object);

  for (const key of keys) {
    if (Array.isArray(record[key])) {
      return record[key] as unknown[];
    }
  }

  return [];
}

function formatNumber(value: number | null): string {
  if (value === null) return "Unavailable";

  return value.toLocaleString(undefined, {
    maximumFractionDigits: 5,
  });
}

function formatPValue(value: number | null): string {
  if (value === null) return "Unavailable";
  if (value < 0.000001) return "< 0.000001";

  return value.toFixed(6);
}

function readable(value: unknown): string {
  if (typeof value === "string") return value;

  if (value === null || value === undefined) {
    return "Unavailable";
  }

  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }

  return JSON.stringify(value, null, 2);
}

// ============================================================
// ACF / PACF DISPLAY
// ============================================================

function LagDisplay({
  title,
  values,
}: {
  title: string;
  values: unknown[];
}) {
  const entries = values
    .map((item, index) => {
      if (typeof item === "number") {
        return { lag: index + 1, value: item };
      }

      const record = asObject(item);

      const lag =
        getNumber(record, ["lag", "order"]) ?? index + 1;

      const value = getNumber(record, [
        "value",
        "acf",
        "pacf",
        "correlation",
      ]);

      return value === null ? null : { lag, value };
    })
    .filter(
      (item): item is { lag: number; value: number } =>
        item !== null
    );

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
      <h4 className="text-xs font-semibold text-slate-200">
        {title}
      </h4>

      {entries.length === 0 ? (
        <p className="mt-3 text-xs text-slate-500">
          This endpoint did not return readable lag values.
        </p>
      ) : (
        <div className="mt-4 space-y-3">
          {entries.map((entry) => {
            const width = Math.min(
              100,
              Math.abs(entry.value) * 100
            );

            return (
              <div key={entry.lag}>
                <div className="mb-1 flex items-center justify-between text-[10px]">
                  <span className="text-slate-400">
                    Lag {entry.lag}
                  </span>
                  <span className="font-mono text-slate-200">
                    {entry.value.toFixed(4)}
                  </span>
                </div>

                <div className="relative h-2 overflow-hidden rounded-full bg-slate-800">
                  <div className="absolute left-1/2 top-0 h-full w-px bg-slate-500" />

                  <div
                    className={`absolute top-0 h-full rounded-full ${
                      entry.value >= 0
                        ? "bg-cyan-500"
                        : "bg-violet-500"
                    }`}
                    style={{
                      width: `${width / 2}%`,
                      left:
                        entry.value >= 0
                          ? "50%"
                          : `${50 - width / 2}%`,
                    }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ============================================================
// MAIN COMPONENT
// ============================================================

export default function TemporalDependenceDiagnostics({
  observations,
  parameterKey,
  unit,
}: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] =
    useState<DiagnosticResponse | null>(null);

  const monthlyObservations = useMemo(
    () => aggregateMonthly(observations, parameterKey, unit),
    [observations, parameterKey, unit]
  );

  const validCount = monthlyObservations.filter(
    (item) => item.value !== null
  ).length;

  const runDiagnostics = async () => {
    if (validCount < 8) {
      setError(
        "At least eight valid monthly observations are required."
      );
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await fetch(
        `${API_BASE}/api/science/dependence-aware-trends/analyze`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Accept: "application/json",
          },
          body: JSON.stringify({
            observations: monthlyObservations,
            alpha: 0.05,
          }),
        }
      );

      const responseText = await response.text();

      let payload: unknown;

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
        const detail = asObject(payload).detail;

        throw new Error(
          typeof detail === "string"
            ? detail
            : `Dependence analysis failed (HTTP ${response.status}).`
        );
      }

      setResult(asObject(payload) as DiagnosticResponse);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to run temporal-dependence diagnostics."
      );
    } finally {
      setLoading(false);
    }
  };

  const reset = () => {
    setResult(null);
    setError(null);
  };

  const temporal = asObject(result?.temporal_dependence);
  const diagnostics = asObject(result?.diagnostics);
  const comparison = asObject(result?.comparison);
  const analysis = asObject(result?.analysis);
  const adjusted = asObject(
    result?.dependence_adjusted_mann_kendall
  );
  const ordinary = asObject(result?.ordinary_mann_kendall);

  const pValue =
    getNumber(temporal, [
      "p_value",
      "ljung_box_p_value",
      "dependence_p_value",
    ]) ??
    getNumber(diagnostics, [
      "p_value",
      "ljung_box_p_value",
      "dependence_p_value",
    ]);

  const statistic =
    getNumber(temporal, [
      "statistic",
      "test_statistic",
      "q_statistic",
    ]) ??
    getNumber(diagnostics, [
      "statistic",
      "test_statistic",
      "q_statistic",
    ]);

  const effectiveN =
    getNumber(temporal, [
      "effective_n",
      "effective_sample_size",
      "n_effective",
    ]) ??
    getNumber(diagnostics, [
      "effective_n",
      "effective_sample_size",
      "n_effective",
    ]);

  const rho =
    getNumber(temporal, [
      "lag_one_autocorrelation",
      "rho",
      "ar1",
    ]) ??
    getNumber(diagnostics, [
      "lag_one_autocorrelation",
      "rho",
      "ar1",
    ]);

  const dependenceDetected =
    typeof temporal.is_significant === "boolean"
      ? temporal.is_significant
      : typeof diagnostics.is_significant === "boolean"
        ? diagnostics.is_significant
        : pValue !== null
          ? pValue < 0.05
          : null;

  const acf =
    getArray(diagnostics, ["acf", "autocorrelation"]) ||
    [];

  const pacf = getArray(diagnostics, [
    "pacf",
    "partial_autocorrelation",
  ]);

  const warnings = Array.isArray(result?.warnings)
    ? result.warnings
    : [];

  const limitations = Array.isArray(
    result?.scientific_limitations
  )
    ? result.scientific_limitations
    : [];

  const interpretation =
    getText(temporal, ["interpretation", "summary"]) ??
    getText(analysis, ["interpretation", "summary"]) ??
    getText(diagnostics, ["interpretation", "summary"]);

  return (
    <section className="space-y-4 rounded-2xl border border-slate-800 bg-slate-950 p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Waves size={19} className="text-violet-400" />
            <h3 className="text-sm font-semibold text-white">
              Temporal Dependence Diagnostics
            </h3>
          </div>

          <p className="mt-1 text-xs leading-relaxed text-slate-400">
            Evaluate serial correlation and its potential
            impact on statistical trend inference.
          </p>
        </div>

        <span className="w-fit rounded-lg border border-violet-900/60 bg-violet-950/30 px-2.5 py-1.5 text-[10px] text-violet-300">
          Monthly time series
        </span>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-3">
          <p className="text-[10px] uppercase tracking-wider text-slate-500">
            Monthly records
          </p>
          <p className="mt-1 text-lg font-semibold tabular-nums text-white">
            {monthlyObservations.length}
          </p>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-3">
          <p className="text-[10px] uppercase tracking-wider text-slate-500">
            Valid observations
          </p>
          <p className="mt-1 text-lg font-semibold tabular-nums text-white">
            {validCount}
          </p>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={runDiagnostics}
          disabled={loading || validCount < 8}
          className="inline-flex items-center gap-2 rounded-lg bg-violet-600 px-4 py-2.5 text-xs font-semibold text-white transition hover:bg-violet-500 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? (
            <Loader2 size={15} className="animate-spin" />
          ) : (
            <Play size={15} />
          )}
          {loading
            ? "Analyzing dependence..."
            : "Run dependence diagnostics"}
        </button>

        <button
          type="button"
          onClick={reset}
          disabled={loading}
          className="inline-flex items-center gap-2 rounded-lg border border-slate-700 px-3 py-2.5 text-xs text-slate-300 hover:bg-slate-900 disabled:opacity-50"
        >
          <RefreshCw size={14} />
          Reset
        </button>
      </div>

      {validCount < 8 && (
        <div className="rounded-lg border border-amber-900/50 bg-amber-950/20 p-3 text-xs text-amber-300">
          At least eight valid monthly observations are required
          by the dependence-aware trend endpoint.
        </div>
      )}

      {error && (
        <div className="flex items-start gap-2 rounded-xl border border-rose-900/60 bg-rose-950/30 p-3 text-xs text-rose-300">
          <AlertCircle size={15} className="mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {loading && (
        <div className="flex items-center gap-2 rounded-xl border border-slate-800 bg-slate-900/40 p-4 text-xs text-slate-400">
          <Loader2
            size={16}
            className="animate-spin text-violet-400"
          />
          Calculating temporal-dependence statistics...
        </div>
      )}

      {result && !loading && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-3">
              <p className="text-[10px] uppercase tracking-wider text-slate-500">
                Dependence p-value
              </p>
              <p className="mt-2 text-sm font-semibold tabular-nums text-white">
                {formatPValue(pValue)}
              </p>
            </div>

            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-3">
              <p className="text-[10px] uppercase tracking-wider text-slate-500">
                Test statistic
              </p>
              <p className="mt-2 text-sm font-semibold tabular-nums text-white">
                {formatNumber(statistic)}
              </p>
            </div>

            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-3">
              <p className="text-[10px] uppercase tracking-wider text-slate-500">
                Effective sample size
              </p>
              <p className="mt-2 text-sm font-semibold tabular-nums text-white">
                {formatNumber(effectiveN)}
              </p>
            </div>

            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-3">
              <p className="text-[10px] uppercase tracking-wider text-slate-500">
                Lag-one correlation
              </p>
              <p className="mt-2 text-sm font-semibold tabular-nums text-white">
                {formatNumber(rho)}
              </p>
            </div>
          </div>

          {dependenceDetected !== null && (
            <div
              className={`flex items-start gap-2 rounded-xl border p-3 ${
                dependenceDetected
                  ? "border-amber-800/60 bg-amber-950/20"
                  : "border-emerald-800/60 bg-emerald-950/20"
              }`}
            >
              {dependenceDetected ? (
                <AlertCircle
                  size={17}
                  className="mt-0.5 text-amber-400"
                />
              ) : (
                <CheckCircle2
                  size={17}
                  className="mt-0.5 text-emerald-400"
                />
              )}

              <div>
                <p
                  className={`text-xs font-semibold ${
                    dependenceDetected
                      ? "text-amber-300"
                      : "text-emerald-300"
                  }`}
                >
                  {dependenceDetected
                    ? "Evidence of temporal dependence"
                    : "No significant dependence detected"}
                </p>

                <p className="mt-1 text-[11px] leading-relaxed text-slate-400">
                  {dependenceDetected
                    ? "The diagnostic indicates evidence of temporal dependence. Compare the ordinary and dependence-adjusted trend results."
                    : "No statistically significant dependence was detected by the returned diagnostic. This does not prove independence."}
                </p>
              </div>
            </div>
          )}

          <div className="grid gap-3 lg:grid-cols-2">
            <LagDisplay
              title="Autocorrelation function (ACF)"
              values={acf}
            />
            <LagDisplay
              title="Partial autocorrelation function (PACF)"
              values={pacf}
            />
          </div>

          <div className="grid gap-3 lg:grid-cols-2">
            <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-3">
              <h4 className="text-xs font-semibold text-slate-200">
                Ordinary Mann–Kendall
              </h4>
              <pre className="mt-2 overflow-auto whitespace-pre-wrap break-words text-[10px] leading-relaxed text-slate-400">
                {JSON.stringify(ordinary, null, 2)}
              </pre>
            </div>

            <div className="rounded-xl border border-violet-900/50 bg-violet-950/10 p-3">
              <h4 className="text-xs font-semibold text-violet-200">
                Dependence-adjusted Mann–Kendall
              </h4>
              <pre className="mt-2 overflow-auto whitespace-pre-wrap break-words text-[10px] leading-relaxed text-slate-400">
                {JSON.stringify(adjusted, null, 2)}
              </pre>
            </div>
          </div>

          {Object.keys(comparison).length > 0 && (
            <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-3">
              <h4 className="text-xs font-semibold text-slate-200">
                Trend inference comparison
              </h4>
              <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap break-words text-[10px] leading-relaxed text-slate-400">
                {JSON.stringify(comparison, null, 2)}
              </pre>
            </div>
          )}

          {interpretation && (
            <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-3">
              <h4 className="text-xs font-semibold text-slate-200">
                Backend interpretation
              </h4>
              <p className="mt-2 text-xs leading-relaxed text-slate-400">
                {interpretation}
              </p>
            </div>
          )}

          {warnings.length > 0 && (
            <div className="rounded-xl border border-amber-900/50 bg-amber-950/20 p-3">
              <p className="text-xs font-semibold text-amber-300">
                Diagnostic warnings
              </p>
              <ul className="mt-2 space-y-1">
                {warnings.map((item, index) => (
                  <li
                    key={index}
                    className="text-[11px] leading-relaxed text-amber-100/70"
                  >
                    • {readable(item)}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {limitations.length > 0 && (
            <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-3">
              <p className="text-xs font-semibold text-slate-300">
                Scientific limitations
              </p>
              <ul className="mt-2 space-y-1">
                {limitations.map((item, index) => (
                  <li
                    key={index}
                    className="text-[11px] leading-relaxed text-slate-500"
                  >
                    • {readable(item)}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="rounded-xl border border-slate-800 bg-black/20 p-3">
            <p className="text-[10px] uppercase tracking-wider text-slate-500">
              Raw diagnostic response
            </p>
            <details className="mt-2">
              <summary className="cursor-pointer text-xs text-slate-400">
                Expand full JSON
              </summary>
              <pre className="mt-3 max-h-80 overflow-auto whitespace-pre-wrap break-words text-[10px] leading-relaxed text-slate-400">
                {JSON.stringify(result, null, 2)}
              </pre>
            </details>
          </div>
        </div>
      )}

      <div className="flex items-start gap-2 rounded-xl border border-slate-800 bg-slate-900/30 p-3">
        <Clock3
          size={15}
          className="mt-0.5 shrink-0 text-slate-500"
        />
        <p className="text-[10px] leading-relaxed text-slate-500">
          Autocorrelation can affect the significance of trend
          tests. Dependence-adjusted results should be interpreted
          alongside the ordinary test, data coverage, seasonal
          structure, and the backend's stated methodological
          limitations. An effective sample size is an approximation,
          not a replacement for examining the time series.
        </p>
      </div>
    </section>
  );
}
