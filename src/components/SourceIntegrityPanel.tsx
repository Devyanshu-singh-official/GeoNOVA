
"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock3,
  Database,
  Globe2,
  Loader2,
  RefreshCw,
  ShieldCheck,
  XCircle,
} from "lucide-react";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

type SourceStatus = "online" | "unavailable" | "unverified" | "unknown";

interface Source {
  id: string;
  name: string;
  category?: string;
  description?: string;
  status: SourceStatus;
  response_time_ms?: number | null;
  checked_at?: string;
  message?: string;
}

interface SourceSummary {
  total?: number;
  online?: number;
  unavailable?: number;
  unverified?: number;
}

interface SourceResponse {
  summary?: SourceSummary;
  sources?: Source[];
  timestamp?: string;
  notice?: string;
}

function statusLabel(status: SourceStatus) {
  switch (status) {
    case "online":
      return "Online";
    case "unavailable":
      return "Unavailable";
    case "unverified":
      return "Unverified";
    default:
      return "Unknown";
  }
}

function StatusIcon({ status }: { status: SourceStatus }) {
  if (status === "online") {
    return <CheckCircle2 size={17} />;
  }

  if (status === "unavailable") {
    return <XCircle size={17} />;
  }

  if (status === "unverified") {
    return <AlertTriangle size={17} />;
  }

  return <Activity size={17} />;
}

function formatTime(value?: string) {
  if (!value) return "Not available";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) return value;

  return date.toLocaleString();
}

function formatResponseTime(value?: number | null) {
  if (value === null || value === undefined) return "—";

  return `${Math.round(value)} ms`;
}

export default function SourceIntegrityPanel() {
  const [data, setData] = useState<SourceResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [lastUpdated, setLastUpdated] = useState("");

  const loadSources = useCallback(async (manual = false) => {
    if (manual) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }

    setError("");

    try {
      const response = await fetch(
        `${API_BASE}/api/science/sources`,
        { cache: "no-store" }
      );

      if (!response.ok) {
        throw new Error(
          `Source observatory returned HTTP ${response.status}`
        );
      }

      const result: SourceResponse = await response.json();

      setData(result);
      setLastUpdated(new Date().toISOString());
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to retrieve source information."
      );
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void loadSources();
  }, [loadSources]);

  const sources = data?.sources ?? [];
  const summary = data?.summary ?? {};

  const onlineCount =
    summary.online ??
    sources.filter((source) => source.status === "online").length;

  const unavailableCount =
    summary.unavailable ??
    sources.filter((source) => source.status === "unavailable").length;

  const unverifiedCount =
    summary.unverified ??
    sources.filter((source) => source.status === "unverified").length;

  const totalCount = summary.total ?? sources.length;

  return (
    <section className="space-y-5">
      <div className="panel p-5">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="eyebrow mb-2 flex items-center gap-2">
              <ShieldCheck size={14} />
              DATA TRUST & RELIABILITY
            </div>

            <h2 className="font-display text-xl font-semibold">
              Source Integrity Observatory
            </h2>

            <p className="muted mt-1 text-sm">
              Monitor connectivity across GeoNOVA&apos;s scientific data
              providers.
            </p>
          </div>

          <button
            type="button"
            onClick={() => void loadSources(true)}
            disabled={loading || refreshing}
            className="flex items-center justify-center gap-2 rounded-lg border border-white/10 bg-white/5 px-4 py-2.5 text-sm transition hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <RefreshCw
              size={15}
              className={refreshing ? "animate-spin" : ""}
            />
            {refreshing ? "Checking..." : "Refresh sources"}
          </button>
        </div>

        <div className="mt-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
          <div className="data-card p-4">
            <div className="muted flex items-center gap-2 text-xs">
              <Database size={14} />
              Registered sources
            </div>
            <div className="mt-2 font-display text-2xl font-semibold">
              {loading ? "—" : totalCount}
            </div>
          </div>

          <div className="data-card p-4">
            <div className="muted flex items-center gap-2 text-xs">
              <CheckCircle2 size={14} />
              Online
            </div>
            <div className="mt-2 font-display text-2xl font-semibold text-emerald-400">
              {loading ? "—" : onlineCount}
            </div>
          </div>

          <div className="data-card p-4">
            <div className="muted flex items-center gap-2 text-xs">
              <XCircle size={14} />
              Unavailable
            </div>
            <div className="mt-2 font-display text-2xl font-semibold text-rose-400">
              {loading ? "—" : unavailableCount}
            </div>
          </div>

          <div className="data-card p-4">
            <div className="muted flex items-center gap-2 text-xs">
              <AlertTriangle size={14} />
              Unverified
            </div>
            <div className="mt-2 font-display text-2xl font-semibold text-amber-400">
              {loading ? "—" : unverifiedCount}
            </div>
          </div>
        </div>
      </div>

      {error && (
        <div className="flex items-start gap-3 rounded-xl border border-rose-400/20 bg-rose-400/5 p-4 text-sm">
          <AlertTriangle className="mt-0.5 shrink-0 text-rose-400" size={18} />
          <div>
            <p className="font-medium text-rose-300">
              Could not load source information
            </p>
            <p className="muted mt-1">{error}</p>
            <button
              type="button"
              onClick={() => void loadSources(true)}
              className="mt-2 text-cyan-300 hover:underline"
            >
              Try again
            </button>
          </div>
        </div>
      )}

      <div className="panel overflow-hidden">
        <div className="flex flex-col gap-2 border-b border-white/10 p-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h3 className="font-display font-semibold">
              Provider Connectivity
            </h3>
            <p className="muted mt-1 text-xs">
              Individual provider connection checks
            </p>
          </div>

          <div className="muted flex items-center gap-2 text-xs">
            <Clock3 size={13} />
            Last dashboard check: {formatTime(lastUpdated)}
          </div>
        </div>

        {loading && !data ? (
          <div className="flex items-center justify-center gap-3 p-12 text-sm">
            <Loader2 className="animate-spin text-cyan-400" size={19} />
            Checking registered providers...
          </div>
        ) : sources.length === 0 ? (
          <div className="muted p-10 text-center text-sm">
            No source records were returned by the backend.
          </div>
        ) : (
          <div className="divide-y divide-white/5">
            {sources.map((source) => (
              <div
                key={source.id}
                className="flex flex-col gap-3 p-4 transition hover:bg-white/[0.025] sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="flex min-w-0 items-start gap-3">
                  <div className="mt-1 rounded-lg border border-white/10 bg-white/5 p-2">
                    <Globe2 size={17} className="text-cyan-300" />
                  </div>

                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h4 className="text-sm font-semibold">
                        {source.name}
                      </h4>

                      <span className="rounded-md border border-white/10 px-2 py-0.5 text-[10px] text-slate-400">
                        {source.category ?? "Scientific data"}
                      </span>
                    </div>

                    {source.description && (
                      <p className="muted mt-1 text-xs">
                        {source.description}
                      </p>
                    )}

                    {source.message && (
                      <p className="muted mt-1 text-xs">
                        {source.message}
                      </p>
                    )}

                    <p className="muted mt-2 text-[11px]">
                      Checked: {formatTime(source.checked_at)}
                    </p>
                  </div>
                </div>

                <div className="flex shrink-0 items-center gap-5 pl-12 sm:pl-0">
                  <div className="text-right">
                    <p className="muted text-[10px]">Response time</p>
                    <p className="mt-1 font-mono text-xs">
                      {formatResponseTime(source.response_time_ms)}
                    </p>
                  </div>

                  <div
                    className={`flex min-w-[112px] items-center justify-center gap-2 rounded-lg border px-3 py-2 text-xs ${
                      source.status === "online"
                        ? "border-emerald-400/20 bg-emerald-400/5 text-emerald-300"
                        : source.status === "unavailable"
                        ? "border-rose-400/20 bg-rose-400/5 text-rose-300"
                        : "border-amber-400/20 bg-amber-400/5 text-amber-300"
                    }`}
                  >
                    <StatusIcon status={source.status} />
                    {statusLabel(source.status)}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="panel flex items-start gap-3 p-4">
        <ShieldCheck size={18} className="mt-0.5 shrink-0 text-cyan-300" />
        <div>
          <h4 className="text-sm font-medium">
            Understanding source integrity
          </h4>
          <p className="muted mt-1 text-xs leading-relaxed">
            An online status confirms that a provider endpoint responded to
            a connectivity check. It does not independently verify scientific
            accuracy, dataset completeness, licensing, or download access.
            Unverified means the connection could not be conclusively tested.
          </p>
        </div>
      </div>
    </section>
  );
}
