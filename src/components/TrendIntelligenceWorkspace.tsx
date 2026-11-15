
"use client";

import { useMemo } from "react";

import {
  Activity,
  BarChart3,
  ShieldCheck,
  Waves,
  FileText,
  CalendarDays,
  Database,
  AlertTriangle,
  CheckCircle2,
} from "lucide-react";

import TrendAnalysisPanel from "./TrendAnalysisPanel";
import TemporalDependenceDiagnostics from "./TemporalDependenceDiagnostics";
import ResearchReportPanel from "./ResearchReportPanel";

// ============================================================
// TYPES
// ============================================================

type DailyObservation = {
  date: string;
  [key: string]: string | number | null;
};

type Props = {
  domainId: string;
  observations: DailyObservation[];
  parameterKey: string;
  parameterLabel: string;
  unit: string;
};

// ============================================================
// HELPERS
// ============================================================

function formatDate(date: string): string {
  const parsed = new Date(`${date}T00:00:00`);

  if (Number.isNaN(parsed.getTime())) {
    return date;
  }

  return parsed.toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

// ============================================================
// COMPONENT
// ============================================================

export default function TrendIntelligenceWorkspace({
  domainId,
  observations,
  parameterKey,
  parameterLabel,
  unit,
}: Props) {
  const dataSummary = useMemo(() => {
    const valid = observations
      .filter((observation) => {
        const value = observation[parameterKey];

        return (
          typeof value === "number" &&
          Number.isFinite(value) &&
          typeof observation.date === "string" &&
          !Number.isNaN(
            new Date(`${observation.date}T00:00:00`).getTime()
          )
        );
      })
      .sort((a, b) => a.date.localeCompare(b.date));

    const uniqueMonths = new Set(
      valid.map((item) => item.date.slice(0, 7))
    );

    const validYears = new Set(
      valid.map((item) => item.date.slice(0, 4))
    );

    const firstDate = valid[0]?.date ?? null;
    const lastDate = valid[valid.length - 1]?.date ?? null;

    const values = valid.map(
      (item) => item[parameterKey] as number
    );

    const mean =
      values.length > 0
        ? values.reduce((sum, value) => sum + value, 0) /
          values.length
        : null;

    const minimum =
      values.length > 0 ? Math.min(...values) : null;

    const maximum =
      values.length > 0 ? Math.max(...values) : null;

    const coverage =
      observations.length > 0
        ? (valid.length / observations.length) * 100
        : 0;

    return {
      total: observations.length,
      valid: valid.length,
      missing: observations.length - valid.length,
      months: uniqueMonths.size,
      years: validYears.size,
      firstDate,
      lastDate,
      coverage,
      mean,
      minimum,
      maximum,
    };
  }, [observations, parameterKey]);

  const hasEnoughData = dataSummary.valid >= 8;

  // ============================================================
  // RENDER
  // ============================================================

  return (
    <div className="space-y-6">
      {/* ======================================================
          WORKSPACE HEADER
      ====================================================== */}

      <section className="overflow-hidden rounded-2xl border border-slate-800 bg-slate-950">
        <div className="border-b border-slate-800 bg-gradient-to-r from-cyan-950/40 via-slate-950 to-violet-950/30 p-5">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="flex items-center gap-2">
                <div className="rounded-xl border border-cyan-800/60 bg-cyan-950/50 p-2">
                  <Activity
                    size={20}
                    className="text-cyan-400"
                  />
                </div>

                <div>
                  <p className="text-[10px] uppercase tracking-[0.2em] text-cyan-400">
                    GeoNOVA Scientific Intelligence
                  </p>

                  <h2 className="mt-1 text-lg font-semibold text-white">
                    Earth System Trend Detective
                  </h2>
                </div>
              </div>

              <p className="mt-3 max-w-2xl text-xs leading-relaxed text-slate-400">
                Investigate long-term Earth system changes using
                historical observations, statistical trend
                detection, seasonal analysis, temporal-dependence
                diagnostics and scientific reporting.
              </p>
            </div>

            <div className="flex items-center gap-2 self-start rounded-xl border border-emerald-900/60 bg-emerald-950/30 px-3 py-2">
              <ShieldCheck
                size={16}
                className="text-emerald-400"
              />

              <span className="text-[10px] font-medium text-emerald-300">
                Multi-method investigation
              </span>
            </div>
          </div>
        </div>

        {/* DATA CONTEXT */}

        <div className="grid grid-cols-2 divide-x divide-slate-800 sm:grid-cols-4">
          <div className="p-3">
            <p className="text-[9px] uppercase tracking-wider text-slate-500">
              Science domain
            </p>

            <p className="mt-1 truncate text-xs font-semibold text-slate-200">
              {domainId || "Not selected"}
            </p>
          </div>

          <div className="p-3">
            <p className="text-[9px] uppercase tracking-wider text-slate-500">
              Environmental variable
            </p>

            <p className="mt-1 truncate text-xs font-semibold text-slate-200">
              {parameterLabel || parameterKey || "Not selected"}
            </p>
          </div>

          <div className="p-3">
            <p className="text-[9px] uppercase tracking-wider text-slate-500">
              Valid observations
            </p>

            <p className="mt-1 text-xs font-semibold tabular-nums text-slate-200">
              {dataSummary.valid.toLocaleString()}
            </p>
          </div>

          <div className="p-3">
            <p className="text-[9px] uppercase tracking-wider text-slate-500">
              Measurement unit
            </p>

            <p className="mt-1 truncate text-xs font-semibold text-slate-200">
              {unit || "Not specified"}
            </p>
          </div>
        </div>
      </section>

      {/* ======================================================
          DATA READINESS
      ====================================================== */}

      <section className="rounded-2xl border border-slate-800 bg-slate-950 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Database
              size={16}
              className="text-cyan-400"
            />

            <h3 className="text-xs font-semibold text-white">
              Investigation data profile
            </h3>
          </div>

          <div
            className={`flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 ${
              hasEnoughData
                ? "border-emerald-900/60 bg-emerald-950/30 text-emerald-300"
                : "border-amber-900/60 bg-amber-950/30 text-amber-300"
            }`}
          >
            {hasEnoughData ? (
              <CheckCircle2 size={13} />
            ) : (
              <AlertTriangle size={13} />
            )}

            <span className="text-[9px] font-medium">
              {hasEnoughData
                ? "Minimum observation count reached"
                : "Limited observations"}
            </span>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-3">
            <p className="text-[9px] text-slate-500">
              Total records
            </p>

            <p className="mt-1 text-lg font-semibold tabular-nums text-white">
              {dataSummary.total.toLocaleString()}
            </p>
          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-3">
            <p className="text-[9px] text-slate-500">
              Valid records
            </p>

            <p className="mt-1 text-lg font-semibold tabular-nums text-emerald-300">
              {dataSummary.valid.toLocaleString()}
            </p>
          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-3">
            <p className="text-[9px] text-slate-500">
              Missing / invalid
            </p>

            <p className="mt-1 text-lg font-semibold tabular-nums text-amber-300">
              {dataSummary.missing.toLocaleString()}
            </p>
          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-3">
            <p className="text-[9px] text-slate-500">
              Distinct months
            </p>

            <p className="mt-1 text-lg font-semibold tabular-nums text-cyan-300">
              {dataSummary.months.toLocaleString()}
            </p>
          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-3">
            <p className="text-[9px] text-slate-500">
              Distinct years
            </p>

            <p className="mt-1 text-lg font-semibold tabular-nums text-violet-300">
              {dataSummary.years.toLocaleString()}
            </p>
          </div>
        </div>

        <div className="mt-4">
          <div className="flex items-center justify-between text-[10px]">
            <span className="text-slate-500">
              Valid-record share of supplied observations
            </span>

            <span className="font-semibold tabular-nums text-slate-300">
              {dataSummary.coverage.toFixed(1)}%
            </span>
          </div>

          <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-800">
            <div
              className="h-full rounded-full bg-cyan-500 transition-all"
              style={{
                width: `${Math.min(100, dataSummary.coverage)}%`,
              }}
            />
          </div>
        </div>

        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <div className="flex items-center gap-2 rounded-lg bg-slate-900/60 p-3">
            <CalendarDays
              size={15}
              className="shrink-0 text-cyan-400"
            />

            <div className="min-w-0">
              <p className="text-[9px] text-slate-500">
                Observation period
              </p>

              <p className="mt-1 truncate text-[11px] font-medium text-slate-200">
                {dataSummary.firstDate && dataSummary.lastDate
                  ? `${formatDate(dataSummary.firstDate)} — ${formatDate(dataSummary.lastDate)}`
                  : "No valid date range"}
              </p>
            </div>
          </div>

          <div className="rounded-lg bg-slate-900/60 p-3">
            <p className="text-[9px] text-slate-500">
              Descriptive statistics
            </p>

            <p className="mt-1 text-[11px] font-medium text-slate-200">
              {dataSummary.mean !== null
                ? `Mean: ${dataSummary.mean.toFixed(3)} ${unit}`
                : "Mean unavailable"}
            </p>

            <p className="mt-1 text-[10px] text-slate-400">
              {dataSummary.minimum !== null &&
              dataSummary.maximum !== null
                ? `Range: ${dataSummary.minimum.toFixed(3)} to ${dataSummary.maximum.toFixed(3)} ${unit}`
                : "Range unavailable"}
            </p>
          </div>
        </div>

        <p className="mt-3 text-[9px] leading-relaxed text-slate-500">
          Data readiness is a descriptive check, not a scientific
          validation or guarantee of trend-analysis suitability.
          Temporal gaps, sampling frequency, spatial
          representativeness and source quality still require
          examination.
        </p>
      </section>

      {/* ======================================================
          STATISTICAL TREND ANALYSIS
      ====================================================== */}

      <section>
        <div className="mb-3 flex items-center gap-2">
          <BarChart3
            size={17}
            className="text-cyan-400"
          />

          <div>
            <h3 className="text-sm font-semibold text-white">
              Statistical trend investigation
            </h3>

            <p className="mt-0.5 text-[10px] text-slate-500">
              Trend direction, significance, magnitude and
              uncertainty
            </p>
          </div>
        </div>

        <TrendAnalysisPanel
          domainId={domainId}
          observations={observations}
          parameterKey={parameterKey}
          parameterLabel={parameterLabel}
          unit={unit}
        />
      </section>

      {/* ======================================================
          TEMPORAL DEPENDENCE
      ====================================================== */}

      <section className="space-y-3">
        <div className="flex items-center gap-2">
          <Waves
            size={17}
            className="text-violet-400"
          />

          <div>
            <h3 className="text-sm font-semibold text-white">
              Time-series dependence investigation
            </h3>

            <p className="mt-0.5 text-[10px] text-slate-500">
              Serial correlation, temporal structure and
              dependence diagnostics
            </p>
          </div>
        </div>

        <TemporalDependenceDiagnostics
          observations={observations}
          parameterKey={parameterKey}
          unit={unit}
        />
      </section>

      {/* ======================================================
          METHODOLOGY OVERVIEW
      ====================================================== */}

      <section className="rounded-2xl border border-slate-800 bg-slate-950 p-4">
        <h3 className="text-xs font-semibold text-slate-200">
          Scientific analysis methodology
        </h3>

        <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-3">
            <p className="text-[10px] font-semibold text-cyan-300">
              01 · Conventional trend
            </p>

            <p className="mt-2 text-[11px] leading-relaxed text-slate-400">
              Mann–Kendall significance testing, Sen's slope
              estimation and regression-based trend assessment.
            </p>
          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-3">
            <p className="text-[10px] font-semibold text-violet-300">
              02 · Dependence-aware trend
            </p>

            <p className="mt-2 text-[11px] leading-relaxed text-slate-400">
              Additional investigation of serial dependence and
              its influence on conventional trend inference.
            </p>
          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-3">
            <p className="text-[10px] font-semibold text-amber-300">
              03 · Seasonal trend
            </p>

            <p className="mt-2 text-[11px] leading-relaxed text-slate-400">
              Calendar-month comparisons across years to
              investigate season-dependent environmental change.
            </p>
          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-3">
            <p className="text-[10px] font-semibold text-emerald-300">
              04 · Temporal diagnostics
            </p>

            <p className="mt-2 text-[11px] leading-relaxed text-slate-400">
              Autocorrelation, partial autocorrelation,
              Ljung–Box testing and effective sample-size
              diagnostics where implemented.
            </p>
          </div>
        </div>

        <div className="mt-4 rounded-xl border border-amber-900/40 bg-amber-950/10 p-3">
          <div className="flex items-start gap-2">
            <AlertTriangle
              size={14}
              className="mt-0.5 shrink-0 text-amber-400"
            />

            <p className="text-[10px] leading-relaxed text-slate-400">
              These methods provide complementary evidence and
              are not interchangeable. Statistical significance
              does not establish causation. Account for data
              quality, missing observations, temporal dependence,
              seasonality, spatial representativeness and
              methodological assumptions when interpreting
              results.
            </p>
          </div>
        </div>
      </section>

      {/* ======================================================
          RESEARCH REPORT GENERATOR
      ====================================================== */}

      <section className="space-y-3">
        <div className="flex items-center gap-2">
          <FileText
            size={17}
            className="text-emerald-400"
          />

          <div>
            <h3 className="text-sm font-semibold text-white">
              Research documentation and exports
            </h3>

            <p className="mt-0.5 text-[10px] text-slate-500">
              Document the investigation and its supporting
              evidence
            </p>
          </div>
        </div>

        <ResearchReportPanel
          domainId={domainId}
          observations={observations}
          parameterKey={parameterKey}
          parameterLabel={parameterLabel}
          unit={unit}
        />
      </section>
    </div>
  );
}
