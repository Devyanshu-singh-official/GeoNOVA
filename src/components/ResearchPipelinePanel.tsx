
"use client";

import { useMemo, useState } from "react";
import {
  Activity,
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Database,
  Loader2,
  Play,
  ShieldCheck,
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
  parameterLabel: string;
};

type PipelineResponse = {
  status?: string;
  research_question?: string;
  generated_at?: string;
  reading_count?: number;
  evidence?: Record<string, unknown>;
  analysis?: Record<string, unknown> | null;
  interpretation?: Record<string, unknown> | null;
  answer?: Record<string, unknown> | null;
  pipeline_notes?: string[];
};

function getDateRange(observations: Observation[]) {
  const dates = observations
    .map((item) => item.date)
    .filter(
      (date): date is string =>
        typeof date === "string" &&
        date.trim().length > 0
    )
    .sort();

  return {
    start_date: dates[0] ?? null,
    end_date: dates[dates.length - 1] ?? null,
  };
}

function getStageStatus(
  response: PipelineResponse,
  stage: "evidence" | "analysis" | "interpretation" | "answer"
) {
  if (stage === "evidence") {
    return response.evidence ? "completed" : "not_run";
  }

  if (stage === "analysis") {
    return response.analysis
      ? "completed"
      : response.status === "evidence_retrieved"
        ? "not_run"
        : "incomplete";
  }

  if (stage === "interpretation") {
    return response.interpretation
      ? "completed"
      : response.status === "analysis_incomplete" ||
          response.status === "evidence_retrieved"
        ? "not_run"
        : "incomplete";
  }

  return response.answer
    ? "completed"
    : response.status === "research_completed"
      ? "completed"
      : "not_run";
}

function StageCard({
  title,
  description,
  status,
}: {
  title: string;
  description: string;
  status: string;
}) {
  const completed = status === "completed";

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-3">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm font-semibold text-slate-200">
          {title}
        </p>

        {completed ? (
          <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />
        ) : (
          <AlertCircle className="h-4 w-4 shrink-0 text-amber-400" />
        )}
      </div>

      <p className="mt-2 text-xs leading-5 text-slate-400">
        {description}
      </p>

      <p
        className={`mt-3 text-[10px] font-semibold uppercase tracking-wider ${
          completed
            ? "text-emerald-400"
            : "text-amber-400"
        }`}
      >
        {status.replaceAll("_", " ")}
      </p>
    </div>
  );
}

export default function ResearchPipelinePanel({
  domainId,
  observations,
  parameterLabel,
}: Props) {
  const [question, setQuestion] = useState(
    `What does the available Earth science evidence reveal about changes in ${parameterLabel}, and how consistent are the findings across sources?`
  );

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [response, setResponse] =
    useState<PipelineResponse | null>(null);

  const [showRawResponse, setShowRawResponse] =
    useState(false);

  const dateRange = useMemo(
    () => getDateRange(observations),
    [observations]
  );

  async function runPipeline() {
    if (question.trim().length < 5) {
      setError(
        "Enter a research question containing at least 5 characters."
      );
      return;
    }

    setLoading(true);
    setError("");
    setResponse(null);
    setShowRawResponse(false);

    try {
      const payload = {
        question: question.trim(),
        domain_id: domainId || null,
        start_date: dateRange.start_date,
        end_date: dateRange.end_date,
        include_observations: true,
        include_datasets: true,
      };

      const result = await fetch(
        `${API_BASE}/api/ai/research`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Accept: "application/json",
          },
          body: JSON.stringify(payload),
        }
      );

      const text = await result.text();

      let data: unknown;

      try {
        data = text ? JSON.parse(text) : {};
      } catch {
        throw new Error(
          `The research service returned an invalid response (HTTP ${result.status}).`
        );
      }

      if (!result.ok) {
        const detail =
          typeof data === "object" &&
          data !== null &&
          "detail" in data
            ? (data as { detail?: unknown }).detail
            : null;

        throw new Error(
          typeof detail === "string"
            ? detail
            : typeof detail === "object" && detail !== null
              ? JSON.stringify(detail)
              : `Research pipeline failed with HTTP ${result.status}.`
        );
      }

      if (
        typeof data !== "object" ||
        data === null ||
        Array.isArray(data)
      ) {
        throw new Error(
          "The research service returned an unexpected response format."
        );
      }

      setResponse(data as PipelineResponse);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to execute the research pipeline."
      );
    } finally {
      setLoading(false);
    }
  }

  const pipelineCompleted =
    response?.status === "research_completed";

  return (
    <section className="space-y-5 rounded-2xl border border-slate-800 bg-slate-950/60 p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <Activity className="h-5 w-5 text-cyan-400" />

            <h2 className="text-lg font-semibold text-slate-100">
              Unified AI Research Pipeline
            </h2>
          </div>

          <p className="mt-1 max-w-2xl text-sm leading-6 text-slate-400">
            Execute GeoNOVA's evidence retrieval, observation
            extraction, cross-source analysis, scientific
            interpretation, and grounded-answer workflow.
          </p>
        </div>

        <span className="rounded-full border border-cyan-800/60 bg-cyan-950/40 px-3 py-1 text-xs text-cyan-300">
          Five-stage pipeline
        </span>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-3">
          <p className="text-xs text-slate-500">
            Selected domain
          </p>

          <p className="mt-1 truncate text-sm font-semibold text-slate-100">
            {domainId}
          </p>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-3">
          <p className="text-xs text-slate-500">
            Available local records
          </p>

          <p className="mt-1 text-xl font-semibold text-slate-100">
            {observations.length.toLocaleString()}
          </p>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-3">
          <p className="text-xs text-slate-500">
            Observation date range
          </p>

          <p className="mt-1 text-sm font-semibold text-slate-100">
            {dateRange.start_date && dateRange.end_date
              ? `${dateRange.start_date} – ${dateRange.end_date}`
              : "Not available"}
          </p>
        </div>
      </div>

      <div className="space-y-2">
        <label
          htmlFor="geonova-research-question"
          className="text-xs font-medium text-slate-300"
        >
          Research question
        </label>

        <textarea
          id="geonova-research-question"
          value={question}
          onChange={(event) =>
            setQuestion(event.target.value)
          }
          rows={4}
          maxLength={2000}
          disabled={loading}
          className="w-full resize-y rounded-lg border border-slate-700 bg-slate-900 px-3 py-3 text-sm leading-6 text-slate-100 outline-none transition focus:border-cyan-500 disabled:opacity-60"
          placeholder="Enter the scientific research question..."
        />

        <p className="text-right text-[10px] text-slate-500">
          {question.length} / 2000 characters
        </p>
      </div>

      <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-3">
        <div className="flex items-center gap-2">
          <Database className="h-4 w-4 text-cyan-400" />

          <p className="text-xs font-semibold text-slate-200">
            Pipeline execution stages
          </p>
        </div>

        <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <StageCard
            title="1. Evidence retrieval"
            description="Retrieves available evidence using the research question and selected domain."
            status={
              response
                ? getStageStatus(response, "evidence")
                : "not_run"
            }
          />

          <StageCard
            title="2. Observation extraction"
            description="Extracts structured readings containing source, parameter, value, unit, and timestamp."
            status={
              response
                ? response.reading_count &&
                  response.reading_count > 0
                  ? "completed"
                  : "incomplete"
                : "not_run"
            }
          />

          <StageCard
            title="3. Cross-source analysis"
            description="Sends extracted readings to the evidence-analysis service."
            status={
              response
                ? getStageStatus(response, "analysis")
                : "not_run"
            }
          />

          <StageCard
            title="4. Scientific interpretation"
            description="Requests an interpretation of the cross-source analysis."
            status={
              response
                ? getStageStatus(response, "interpretation")
                : "not_run"
            }
          />

          <StageCard
            title="5. Grounded AI answer"
            description="Generates an answer grounded in the evidence and interpretation."
            status={
              response
                ? getStageStatus(response, "answer")
                : "not_run"
            }
          />
        </div>
      </div>

      <button
        type="button"
        onClick={runPipeline}
        disabled={loading || question.trim().length < 5}
        className="inline-flex items-center gap-2 rounded-lg bg-cyan-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-cyan-500 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {loading ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <Play className="h-4 w-4" />
        )}

        {loading
          ? "Executing research pipeline..."
          : "Run Unified Research Pipeline"}
      </button>

      {error && (
        <div className="flex items-start gap-2 rounded-lg border border-red-900/60 bg-red-950/30 p-3 text-sm text-red-300">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <p className="break-words">{error}</p>
        </div>
      )}

      {response && (
        <div className="space-y-4 rounded-xl border border-slate-800 bg-slate-900/50 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              {pipelineCompleted ? (
                <CheckCircle2 className="h-5 w-5 text-emerald-400" />
              ) : (
                <AlertCircle className="h-5 w-5 text-amber-400" />
              )}

              <p className="font-semibold text-slate-100">
                {pipelineCompleted
                  ? "Research pipeline completed"
                  : "Research pipeline returned an incomplete result"}
              </p>
            </div>

            <span
              className={`rounded-full border px-3 py-1 text-xs ${
                pipelineCompleted
                  ? "border-emerald-800 bg-emerald-950/40 text-emerald-300"
                  : "border-amber-800 bg-amber-950/40 text-amber-300"
              }`}
            >
              {(response.status || "unknown").replaceAll("_", " ")}
            </span>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-3">
              <p className="text-xs text-slate-500">
                Extracted scientific readings
              </p>

              <p className="mt-1 text-2xl font-semibold text-slate-100">
                {(response.reading_count ?? 0).toLocaleString()}
              </p>
            </div>

            <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-3">
              <p className="text-xs text-slate-500">
                Pipeline status
              </p>

              <p className="mt-2 text-sm font-semibold text-slate-100">
                {(response.status || "unknown").replaceAll("_", " ")}
              </p>
            </div>
          </div>

          {response.pipeline_notes &&
            response.pipeline_notes.length > 0 && (
              <div className="space-y-2">
                <p className="text-xs font-semibold text-slate-300">
                  Pipeline notes
                </p>

                {response.pipeline_notes.map((note, index) => (
                  <div
                    key={index}
                    className="rounded-lg border border-amber-900/40 bg-amber-950/20 p-3 text-xs leading-5 text-amber-200"
                  >
                    {note}
                  </div>
                ))}
              </div>
            )}

          {response.answer && (
            <div className="rounded-xl border border-cyan-900/50 bg-cyan-950/20 p-4">
              <div className="flex items-center gap-2">
                <ShieldCheck className="h-4 w-4 text-cyan-400" />

                <p className="text-sm font-semibold text-cyan-200">
                  Grounded AI answer
                </p>
              </div>

              <pre className="mt-3 whitespace-pre-wrap break-words text-xs leading-6 text-slate-200">
                {JSON.stringify(response.answer, null, 2)}
              </pre>
            </div>
          )}

          <div className="overflow-hidden rounded-lg border border-slate-800">
            <button
              type="button"
              onClick={() =>
                setShowRawResponse((current) => !current)
              }
              className="flex w-full items-center justify-between gap-3 bg-slate-900 px-3 py-3 text-left text-xs font-semibold text-slate-300 hover:bg-slate-800"
            >
              Complete pipeline response

              {showRawResponse ? (
                <ChevronUp className="h-4 w-4" />
              ) : (
                <ChevronDown className="h-4 w-4" />
              )}
            </button>

            {showRawResponse && (
              <pre className="max-h-[500px] overflow-auto bg-slate-950 p-3 text-[10px] leading-5 text-slate-300">
                {JSON.stringify(response, null, 2)}
              </pre>
            )}
          </div>

          <p className="text-[10px] leading-5 text-slate-500">
            Pipeline completion indicates that the configured
            services returned successful responses. It does not
            independently establish scientific validity, source
            accuracy, or causation.
          </p>
        </div>
      )}

      <p className="text-[10px] leading-5 text-slate-500">
        The research endpoint uses its backend-defined default
        coordinates unless location parameters are explicitly
        added to this component. The date range is derived from
        the available observation records.
      </p>
    </section>
  );
}
