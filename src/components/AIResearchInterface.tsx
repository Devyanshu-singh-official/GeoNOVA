
"use client";

import { useState } from "react";
import {
  BrainCircuit,
  Search,
  Database,
  Activity,
  FileSearch,
  Sparkles,
  AlertCircle,
  CheckCircle2,
  Loader2,
  ChevronDown,
  ChartNoAxesCombined,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

const DOMAINS = [
  { id: "temperature", label: "Temperature Intelligence" },
  { id: "water", label: "Water Intelligence" },
  { id: "vegetation", label: "Vegetation & Forest Intelligence" },
  { id: "atmosphere", label: "Atmospheric Intelligence" },
  { id: "ocean", label: "Ocean Intelligence" },
  { id: "soil", label: "Soil & Land Intelligence" },
  { id: "cryosphere", label: "Cryosphere Intelligence" },
  { id: "human-impact", label: "Human Impact & Land Change" },
  { id: "climate-carbon", label: "Climate & Carbon Intelligence" },
  { id: "geophysical", label: "Geophysical Intelligence" },
];

type JsonObject = Record<string, any>;

type StageStatus = "waiting" | "running" | "complete" | "error";

type Stage = {
  id: string;
  label: string;
  status: StageStatus;
  detail?: string;
};

const INITIAL_STAGES: Stage[] = [
  {
    id: "evidence",
    label: "Evidence retrieval",
    status: "waiting",
  },
  {
    id: "analysis",
    label: "Cross-source analysis",
    status: "waiting",
  },
  {
    id: "interpretation",
    label: "Scientific interpretation",
    status: "waiting",
  },
  {
    id: "llm",
    label: "AI research explanation",
    status: "waiting",
  },
];

const STAGE_ICONS: Record<string, LucideIcon> = {
  evidence: Database,
  analysis: Activity,
  interpretation: FileSearch,
  llm: Sparkles,
};

async function runUnifiedResearch(
  body: JsonObject
): Promise<JsonObject> {
  const response = await fetch(`${API_BASE}/api/ai/research`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    const detail =
      typeof data.detail === "string"
        ? data.detail
        : Array.isArray(data.detail)
          ? data.detail
              .map((item: JsonObject) => item.msg || JSON.stringify(item))
              .join("; ")
          : `Research request failed (${response.status})`;

    throw new Error(detail);
  }

  return data;
}

function getAnswerResponse(answer: any): JsonObject {
  if (!answer || typeof answer !== "object") {
    return {};
  }

  if (answer.response && typeof answer.response === "object") {
    return answer.response;
  }

  return answer;
}

function getAnswerText(answer: JsonObject): string {
  const response = getAnswerResponse(answer);

  if (typeof response.answer === "string") {
    return response.answer;
  }

  if (typeof response.response === "string") {
    return response.response;
  }

  if (typeof answer.answer === "string") {
    return answer.answer;
  }

  return "";
}

function formatDateForBackend(date: string): string | undefined {
  if (!date) return undefined;

  // Keep the compact YYYYMMDD format used by the existing
  // GeoNOVA evidence retrieval workflow.
  return date.replaceAll("-", "");
}



type ResearchPoint = { date: string; timestamp: number; value: number };
type ResearchSeries = {
  title: string;
  unit: string;
  path: string;
  points: ResearchPoint[];
};

function findResearchTimeSeries(roots: Array<[string, any]>): ResearchSeries | null {
  const excludedNumericKeys = new Set([
    "id", "latitude", "lat", "longitude", "lon", "count",
    "confidence", "sample_size", "n", "index", "row", "quality_flag",
  ]);
  const dateKeys = [
    "date", "datetime", "timestamp", "time", "observed_at",
    "observation_date", "start_date", "x",
  ];
  const candidates: Array<ResearchSeries & { score: number }> = [];
  const visited = new Set<any>();

  const parseDate = (value: any): { label: string; timestamp: number } | null => {
    if (typeof value === "number" && Number.isFinite(value)) {
      const milliseconds = value < 100000000000 ? value * 1000 : value;
      const date = new Date(milliseconds);
      return Number.isFinite(date.getTime())
        ? { label: date.toISOString().slice(0, 10), timestamp: date.getTime() }
        : null;
    }
    if (typeof value === "string" && value.trim()) {
      const parsed = Date.parse(value);
      if (Number.isFinite(parsed)) {
        return { label: value, timestamp: parsed };
      }
    }
    return null;
  };

  const walk = (value: any, path: string, depth: number) => {
    if (!value || typeof value !== "object" || depth > 7 || visited.has(value)) return;
    visited.add(value);

    if (Array.isArray(value)) {
      if (value.length >= 2 && value.length <= 1000 && value.every((row) => row && typeof row === "object" && !Array.isArray(row))) {
        const first = value.find((row) => row && typeof row === "object");
        if (first) {
          const keys = Object.keys(first);
          const dateKey = dateKeys.find((key) => keys.includes(key));
          const numericKeys = keys.filter((key) => {
            if (excludedNumericKeys.has(key.toLowerCase())) return false;
            const raw = first[key];
            if (typeof raw === "number") return Number.isFinite(raw);
            if (typeof raw === "string" && raw.trim() !== "") {
              return Number.isFinite(Number(raw));
            }
            return false;
          });
          const preferred = ["value", "y", "mean", "temperature", "precipitation", "ndvi", "lst"];
          const valueKey = preferred.find((key) => numericKeys.includes(key)) || numericKeys[0];

          if (dateKey && valueKey) {
            const points = value.flatMap((row: any) => {
              const parsed = parseDate(row?.[dateKey]);
              const rawNumeric = row?.[valueKey];
              const numeric = typeof rawNumeric === "number"
                ? rawNumeric
                : typeof rawNumeric === "string" && rawNumeric.trim() !== ""
                  ? Number(rawNumeric)
                  : Number.NaN;
              return parsed && Number.isFinite(numeric)
                ? [{ date: parsed.label, timestamp: parsed.timestamp, value: numeric }]
                : [];
            }).sort((a: ResearchPoint, b: ResearchPoint) => a.timestamp - b.timestamp);

            if (points.length >= 2) {
              const label = String(first.label || first.variable || first.parameter || valueKey);
              const unit = String(first.unit || first.units || "");
              candidates.push({
                title: label.replaceAll("_", " "),
                unit,
                path: path || "returned data",
                points,
                score: points.length + (unit ? 4 : 0) + (/observations|readings|time.?series|series/i.test(path) ? 8 : 0),
              });
            }
          }
        }
      }
      value.forEach((item, index) => walk(item, `${path}[${index}]`, depth + 1));
      return;
    }

    for (const [key, child] of Object.entries(value)) {
      if (child && typeof child === "object") walk(child, path ? `${path}.${key}` : key, depth + 1);
    }
  };

  roots.forEach(([name, root]) => walk(root, name, 0));
  candidates.sort((a, b) => b.score - a.score);
  return candidates[0] || null;
}

function StageIcon({ id }: { id: string }) {
  const Icon = STAGE_ICONS[id] || BrainCircuit;

  return <Icon size={17} />;
}

export default function AIResearchInterface() {
  const [question, setQuestion] = useState("");
  const [domain, setDomain] = useState("temperature");

  const [latitude, setLatitude] = useState("26.8467");
  const [longitude, setLongitude] = useState("80.9462");

  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  const [stages, setStages] = useState<Stage[]>(INITIAL_STAGES);
  const [running, setRunning] = useState(false);

  const [researchResult, setResearchResult] =
    useState<JsonObject | null>(null);

  const [evidence, setEvidence] = useState<JsonObject | null>(null);
  const [analysis, setAnalysis] = useState<JsonObject | null>(null);
  const [interpretation, setInterpretation] =
    useState<JsonObject | null>(null);
  const [answer, setAnswer] = useState<JsonObject | null>(null);

  const [error, setError] = useState("");

  function updateStage(
    id: string,
    status: StageStatus,
    detail?: string
  ) {
    setStages((previous) =>
      previous.map((stage) =>
        stage.id === id
          ? {
              ...stage,
              status,
              detail,
            }
          : stage
      )
    );
  }

  function resetResearch() {
    setResearchResult(null);
    setEvidence(null);
    setAnalysis(null);
    setInterpretation(null);
    setAnswer(null);

    setStages(
      INITIAL_STAGES.map((stage) => ({
        ...stage,
        status: "waiting",
        detail: undefined,
      }))
    );
  }

  async function runResearch() {
    if (question.trim().length < 5) {
      setError("Enter a research question containing at least 5 characters.");
      return;
    }

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
      setError("Enter valid latitude and longitude values.");
      return;
    }

    if (startDate && endDate && startDate > endDate) {
      setError("The start date cannot be later than the end date.");
      return;
    }

    setRunning(true);
    setError("");
    resetResearch();

    const requestBody: JsonObject = {
      question: question.trim(),
      domain_id: domain,
      latitude: lat,
      longitude: lon,
      include_observations: true,
      include_datasets: true,
    };

    const formattedStartDate = formatDateForBackend(startDate);
    const formattedEndDate = formatDateForBackend(endDate);

    if (formattedStartDate) {
      requestBody.start_date = formattedStartDate;
    }

    if (formattedEndDate) {
      requestBody.end_date = formattedEndDate;
    }

    try {
      // The backend orchestrator manages all four stages.
      // The frontend makes only one research request.

      setStages((previous) =>
        previous.map((stage, index) =>
          index === 0
            ? {
                ...stage,
                status: "running",
                detail: "Submitting request to the unified research pipeline",
              }
            : {
                ...stage,
                status: "waiting",
                detail: undefined,
              }
        )
      );

      const result = await runUnifiedResearch(requestBody);

      setResearchResult(result);

      // Populate the individual result panels from the
      // orchestrator response.

      setEvidence(
        result.evidence && typeof result.evidence === "object"
          ? result.evidence
          : null
      );

      setAnalysis(
        result.analysis && typeof result.analysis === "object"
          ? result.analysis
          : null
      );

      setInterpretation(
        result.interpretation &&
          typeof result.interpretation === "object"
          ? result.interpretation
          : null
      );

      setAnswer(
        result.answer && typeof result.answer === "object"
          ? result.answer
          : result.answer
            ? { answer: result.answer }
            : null
      );

      const pipelineNotes = Array.isArray(result.pipeline_notes)
        ? result.pipeline_notes
        : [];

      const readingCount =
        typeof result.reading_count === "number"
          ? result.reading_count
          : 0;

      // Reflect the orchestrator's returned outputs.
      // These are result indicators, not independent frontend
      // execution of the backend stages.

      updateStage(
        "evidence",
        result.evidence ? "complete" : "error",
        result.evidence
          ? "Evidence package returned by backend"
          : "No evidence package returned"
      );

      updateStage(
        "analysis",
        result.analysis ? "complete" : "waiting",
        result.analysis
          ? `${readingCount} observation readings processed`
          : "Numerical analysis was not returned"
      );

      updateStage(
        "interpretation",
        result.interpretation ? "complete" : "waiting",
        result.interpretation
          ? "Scientific interpretation returned"
          : "Interpretation not available"
      );

      updateStage(
        "llm",
        result.answer ? "complete" : "waiting",
        result.answer
          ? "Grounded research response returned"
          : "AI explanation not available"
      );

      if (
        result.status &&
        !["success", "complete", "completed"].includes(
          String(result.status).toLowerCase()
        )
      ) {
        setError(
          `Research pipeline returned status: ${result.status}`
        );
      } else if (
        !result.answer &&
        !result.analysis &&
        pipelineNotes.length > 0
      ) {
        setError(pipelineNotes.join(" "));
      }
    } catch (err) {
      const message =
        err instanceof Error
          ? err.message
          : "Research workflow failed.";

      setError(message);

      setStages((previous) => {
        const current = previous.find(
          (stage) => stage.status === "running"
        );

        if (!current) {
          return previous.map((stage) =>
            stage.status === "waiting"
              ? {
                  ...stage,
                  status: "waiting",
                }
              : stage
          );
        }

        return previous.map((stage) =>
          stage.id === current.id
            ? {
                ...stage,
                status: "error",
                detail: message,
              }
            : stage
        );
      });
    } finally {
      setRunning(false);
    }
  }

  const completedStages = stages.filter(
    (stage) => stage.status === "complete"
  ).length;

  const answerResponse = answer
    ? getAnswerResponse(answer)
    : {};

  const answerText = answer
    ? getAnswerText(answer)
    : "";

  const findings = Array.isArray(answerResponse.findings)
    ? answerResponse.findings
    : [];

  const limitations = Array.isArray(answerResponse.limitations)
    ? answerResponse.limitations
    : [];

  const missingEvidence = Array.isArray(
    answerResponse.missing_evidence
  )
    ? answerResponse.missing_evidence
    : [];

  const pipelineNotes = Array.isArray(
    researchResult?.pipeline_notes
  )
    ? researchResult.pipeline_notes
    : [];

  const researchChart = findResearchTimeSeries([
    ["orchestrator", researchResult],
    ["evidence", evidence],
    ["analysis", analysis],
    ["interpretation", interpretation],
    ["answer", answer],
  ]);

  return (
    <div className="space-y-6 text-slate-100">
      {/* HEADER */}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-cyan-300">
            <BrainCircuit size={21} />

            <span className="text-xs font-semibold uppercase tracking-[0.2em]">
              GeoNOVA Intelligence
            </span>
          </div>

          <h1 className="mt-2 text-2xl font-semibold">
            AI Research Investigator
          </h1>

          <p className="mt-1 text-sm text-slate-400">
            Evidence-grounded Earth science research and analysis
          </p>
        </div>

        <div className="rounded-lg border border-cyan-500/20 bg-cyan-500/5 px-3 py-2 text-xs text-cyan-300">
          Unified research orchestrator
        </div>
      </div>

      {/* RESEARCH CONFIGURATION */}

      <section className="panel space-y-4 p-5">
        <div className="flex items-center gap-2">
          <Search size={18} className="text-cyan-300" />

          <h2 className="font-semibold">
            Research configuration
          </h2>
        </div>

        <div>
          <label className="mb-2 block text-xs text-slate-400">
            Research question
          </label>

          <textarea
            value={question}
            onChange={(event) =>
              setQuestion(event.target.value)
            }
            placeholder="Example: How have recent temperature and precipitation observations varied at this location?"
            rows={4}
            disabled={running}
            className="w-full resize-y rounded-lg border border-slate-700 bg-slate-950/60 p-3 text-sm outline-none transition focus:border-cyan-500 disabled:opacity-60"
          />
        </div>

        <div>
          <label className="mb-2 block text-xs text-slate-400">
            Scientific domain
          </label>

          <div className="relative">
            <select
              value={domain}
              onChange={(event) =>
                setDomain(event.target.value)
              }
              disabled={running}
              className="w-full appearance-none rounded-lg border border-slate-700 bg-slate-950/60 p-3 pr-10 text-sm outline-none focus:border-cyan-500 disabled:opacity-60"
            >
              {DOMAINS.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label}
                </option>
              ))}
            </select>

            <ChevronDown
              size={16}
              className="pointer-events-none absolute right-3 top-3.5 text-slate-400"
            />
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label className="mb-2 block text-xs text-slate-400">
              Latitude
            </label>

            <input
              type="number"
              step="any"
              value={latitude}
              onChange={(event) =>
                setLatitude(event.target.value)
              }
              disabled={running}
              className="w-full rounded-lg border border-slate-700 bg-slate-950/60 p-3 text-sm outline-none focus:border-cyan-500 disabled:opacity-60"
            />
          </div>

          <div>
            <label className="mb-2 block text-xs text-slate-400">
              Longitude
            </label>

            <input
              type="number"
              step="any"
              value={longitude}
              onChange={(event) =>
                setLongitude(event.target.value)
              }
              disabled={running}
              className="w-full rounded-lg border border-slate-700 bg-slate-950/60 p-3 text-sm outline-none focus:border-cyan-500 disabled:opacity-60"
            />
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label className="mb-2 block text-xs text-slate-400">
              Start date (optional)
            </label>

            <input
              type="date"
              value={startDate}
              onChange={(event) =>
                setStartDate(event.target.value)
              }
              disabled={running}
              className="w-full rounded-lg border border-slate-700 bg-slate-950/60 p-3 text-sm outline-none focus:border-cyan-500 disabled:opacity-60"
            />
          </div>

          <div>
            <label className="mb-2 block text-xs text-slate-400">
              End date (optional)
            </label>

            <input
              type="date"
              value={endDate}
              onChange={(event) =>
                setEndDate(event.target.value)
              }
              disabled={running}
              className="w-full rounded-lg border border-slate-700 bg-slate-950/60 p-3 text-sm outline-none focus:border-cyan-500 disabled:opacity-60"
            />
          </div>
        </div>

        <button
          onClick={runResearch}
          disabled={running}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-cyan-500 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-400 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {running ? (
            <>
              <Loader2
                size={17}
                className="animate-spin"
              />

              Running unified research pipeline...
            </>
          ) : (
            <>
              <Sparkles size={17} />

              Run AI Research
            </>
          )}
        </button>
      </section>

      {/* PIPELINE STATUS */}

      <section className="panel space-y-4 p-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-semibold">
            Research pipeline
          </h2>

          <span className="text-xs text-slate-400">
            {completedStages}/{stages.length} stages completed
          </span>
        </div>

        <div className="h-1.5 overflow-hidden rounded-full bg-slate-800">
          <div
            className="h-full rounded-full bg-cyan-400 transition-all"
            style={{
              width: `${
                (completedStages / stages.length) * 100
              }%`,
            }}
          />
        </div>

        <div className="space-y-3">
          {stages.map((stage, index) => (
            <div
              key={stage.id}
              className="flex items-start gap-3 rounded-lg border border-slate-800 bg-slate-950/30 p-3"
            >
              <div className="mt-0.5 text-cyan-300">
                <StageIcon id={stage.id} />
              </div>

              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-xs text-slate-500">
                    0{index + 1}
                  </span>

                  <span className="text-sm font-medium">
                    {stage.label}
                  </span>
                </div>

                {stage.detail && (
                  <p className="mt-1 break-words text-xs text-slate-400">
                    {stage.detail}
                  </p>
                )}
              </div>

              <div>
                {stage.status === "complete" && (
                  <CheckCircle2
                    size={17}
                    className="text-emerald-400"
                  />
                )}

                {stage.status === "running" && (
                  <Loader2
                    size={17}
                    className="animate-spin text-cyan-300"
                  />
                )}

                {stage.status === "error" && (
                  <AlertCircle
                    size={17}
                    className="text-red-400"
                  />
                )}

                {stage.status === "waiting" && (
                  <div className="h-3.5 w-3.5 rounded-full border border-slate-600" />
                )}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ERRORS */}

      {error && (
        <div className="flex items-start gap-2 rounded-lg border border-red-500/30 bg-red-500/5 p-4 text-sm text-red-300">
          <AlertCircle
            size={18}
            className="mt-0.5 shrink-0"
          />

          <div>
            <p className="font-semibold">
              Research pipeline notice
            </p>

            <p className="mt-1 break-words">
              {error}
            </p>
          </div>
        </div>
      )}

      {/* PIPELINE NOTES */}

      {pipelineNotes.length > 0 && (
        <section className="panel space-y-2 p-4">
          <h2 className="text-sm font-semibold text-cyan-300">
            Pipeline notes
          </h2>

          <ul className="list-disc space-y-1 pl-5 text-xs leading-6 text-slate-400">
            {pipelineNotes.map(
              (note: any, index: number) => (
                <li key={index}>
                  {typeof note === "string"
                    ? note
                    : JSON.stringify(note)}
                </li>
              )
            )}
          </ul>
        </section>
      )}

      {/* RESEARCH ANSWER */}

      {answer && (
        <section className="panel space-y-4 p-5">
          <div className="flex items-center gap-2 text-cyan-300">
            <Sparkles size={19} />

            <h2 className="font-semibold text-slate-100">
              GeoNOVA Research Answer
            </h2>
          </div>

          {answerText ? (
            <p className="whitespace-pre-wrap text-sm leading-7 text-slate-300">
              {answerText}
            </p>
          ) : (
            <p className="text-sm text-slate-400">
              The backend returned an answer object, but no
              recognized answer text field was found. Inspect
              the raw response below.
            </p>
          )}

          {findings.length > 0 && (
            <div className="space-y-3">
              <h3 className="text-sm font-semibold">
                Evidence-supported findings
              </h3>

              {findings.map(
                (finding: JsonObject, index: number) => (
                  <div
                    key={`${index}-${finding.statement || "finding"}`}
                    className="rounded-lg border border-slate-700 bg-slate-950/40 p-3"
                  >
                    <div className="mb-2 flex flex-wrap items-center gap-2">
                      {finding.classification && (
                        <span className="rounded bg-cyan-500/10 px-2 py-1 text-xs text-cyan-300">
                          {finding.classification}
                        </span>
                      )}
                    </div>

                    <p className="text-sm leading-6 text-slate-300">
                      {finding.statement ||
                        finding.description ||
                        JSON.stringify(finding)}
                    </p>

                    {Array.isArray(finding.evidence_refs) && (
                      <p className="mt-2 break-words text-xs text-slate-500">
                        References:{" "}
                        {finding.evidence_refs.join(", ")}
                      </p>
                    )}

                    {finding.uncertainty && (
                      <p className="mt-2 text-xs text-slate-400">
                        Uncertainty: {finding.uncertainty}
                      </p>
                    )}
                  </div>
                )
              )}
            </div>
          )}

          {limitations.length > 0 && (
            <div>
              <h3 className="mb-2 text-sm font-semibold">
                Scientific limitations
              </h3>

              <ul className="list-disc space-y-1 pl-5 text-xs leading-6 text-slate-400">
                {limitations.map(
                  (item: any, index: number) => (
                    <li key={index}>
                      {typeof item === "string"
                        ? item
                        : JSON.stringify(item)}
                    </li>
                  )
                )}
              </ul>
            </div>
          )}

          {missingEvidence.length > 0 && (
            <div>
              <h3 className="mb-2 text-sm font-semibold">
                Additional evidence needed
              </h3>

              <ul className="list-disc space-y-1 pl-5 text-xs leading-6 text-slate-400">
                {missingEvidence.map(
                  (item: any, index: number) => (
                    <li key={index}>
                      {typeof item === "string"
                        ? item
                        : JSON.stringify(item)}
                    </li>
                  )
                )}
              </ul>
            </div>
          )}

          <div className="border-t border-slate-800 pt-3 text-xs text-slate-500">
            Model:{" "}
            {answer.model ||
              researchResult?.model ||
              "Configured provider"}
            {" · "}
            Backend status:{" "}
            {researchResult?.status || "Response received"}
            {" · "}
            Scientific accuracy: not independently verified
          </div>
        </section>
      )}

      {/* DATA-DRIVEN RESEARCH GRAPH */}

      {(researchResult || evidence || analysis || interpretation) && (
        <section className="panel space-y-3 p-5">
          <div className="flex items-center gap-2">
            <ChartNoAxesCombined size={19} className="text-cyan-300" />
            <div>
              <h2 className="font-semibold text-slate-100">Research Data Visualization</h2>
              <p className="text-xs text-slate-500">Plots a dated numeric series returned by the research pipeline; no synthetic values are added.</p>
            </div>
          </div>

          {researchChart ? (
            <div className="rounded-xl border border-slate-800 bg-slate-950/50 p-3">
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="text-sm font-semibold capitalize text-slate-200">{researchChart.title}</p>
                  <p className="text-[10px] text-slate-500">{researchChart.points.length} returned observations · {researchChart.unit || "unit not supplied"}</p>
                </div>
                <span className="rounded-md bg-cyan-500/10 px-2 py-1 text-[10px] text-cyan-300">Backend data</span>
              </div>
              {(() => {
                const width = 820;
                const height = 260;
                const pad = { left: 58, right: 18, top: 18, bottom: 38 };
                const values = researchChart.points.map((point) => point.value);
                const min = Math.min(...values);
                const max = Math.max(...values);
                const span = max - min || Math.max(Math.abs(max) * 0.08, 1);
                const x = (index: number) => pad.left + (index / Math.max(researchChart.points.length - 1, 1)) * (width - pad.left - pad.right);
                const y = (value: number) => pad.top + ((max + span * 0.08 - value) / (span * 1.16)) * (height - pad.top - pad.bottom);
                const polyline = researchChart.points.map((point, index) => `${x(index)},${y(point.value)}`).join(" ");
                const tickValues = [min, min + (max - min) / 2, max];
                const firstDate = researchChart.points[0]?.date || "";
                const lastDate = researchChart.points[researchChart.points.length - 1]?.date || "";
                return (
                  <div className="w-full overflow-hidden">
                    <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${researchChart.title} time-series chart`} className="h-auto w-full">
                      {tickValues.map((tick, index) => {
                        const yy = y(tick);
                        return (
                          <g key={index}>
                            <line x1={pad.left} x2={width - pad.right} y1={yy} y2={yy} stroke="#334155" strokeDasharray="4 5" />
                            <text x={pad.left - 9} y={yy + 4} fill="#94a3b8" fontSize="10" textAnchor="end">{tick.toLocaleString(undefined, { maximumFractionDigits: 2 })}</text>
                          </g>
                        );
                      })}
                      <line x1={pad.left} x2={pad.left} y1={pad.top} y2={height - pad.bottom} stroke="#475569" />
                      <line x1={pad.left} x2={width - pad.right} y1={height - pad.bottom} y2={height - pad.bottom} stroke="#475569" />
                      <polyline points={polyline} fill="none" stroke="#22d3ee" strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" />
                      {researchChart.points.map((point, index) => (
                        <circle key={`${point.timestamp}-${index}`} cx={x(index)} cy={y(point.value)} r="2.8" fill="#67e8f9" stroke="#082f49" strokeWidth="1" />
                      ))}
                      <text x={pad.left} y={height - 12} fill="#94a3b8" fontSize="10">{firstDate}</text>
                      <text x={width - pad.right} y={height - 12} fill="#94a3b8" fontSize="10" textAnchor="end">{lastDate}</text>
                    </svg>
                  </div>
                );
              })()}
              <p className="mt-2 break-all text-[10px] text-slate-600">Series path: {researchChart.path}</p>
            </div>
          ) : (
            <div className="rounded-lg border border-dashed border-slate-700 p-4 text-xs leading-6 text-slate-400">
              This AI research response did not include at least two dated numeric observations, so there is no defensible time-series to plot. To get a graph now, open <strong>Science Workspace</strong> in the left sidebar, choose a domain and parameter, set the coordinates and date range, then click <strong>Load observations</strong>. Its Scientific Visualization graph appears below the observation summary. AI Investigator will plot a graph here when its backend returns dated numeric readings; it will not invent sample values.
            </div>
          )}
        </section>
      )}

      {/* RESEARCH METADATA */}

      {researchResult && (
        <section className="panel grid gap-3 p-4 sm:grid-cols-3">
          <div>
            <p className="text-xs text-slate-500">
              Observation readings
            </p>

            <p className="mt-1 text-xl font-semibold text-cyan-300">
              {typeof researchResult.reading_count === "number"
                ? researchResult.reading_count
                : "—"}
            </p>
          </div>

          <div>
            <p className="text-xs text-slate-500">
              Research status
            </p>

            <p className="mt-1 text-sm font-semibold text-slate-200">
              {researchResult.status || "Response received"}
            </p>
          </div>

          <div>
            <p className="text-xs text-slate-500">
              Generated at
            </p>

            <p className="mt-1 break-words text-sm font-semibold text-slate-200">
              {researchResult.generated_at
                ? new Date(
                    researchResult.generated_at
                  ).toLocaleString()
                : "Not provided"}
            </p>
          </div>
        </section>
      )}

      {/* RAW PIPELINE DATA */}

      {(evidence || analysis || interpretation || answer || researchResult) && (
        <details className="panel p-4">
          <summary className="cursor-pointer text-sm font-medium text-slate-300">
            Inspect research pipeline data
          </summary>

          <div className="mt-4 space-y-4">
            {[
              ["Complete orchestrator response", researchResult],
              ["Evidence package", evidence],
              ["Cross-source analysis", analysis],
              ["Scientific interpretation", interpretation],
              ["AI research answer", answer],
            ].map(([label, data]) => {
              if (!data) return null;

              return (
                <div key={String(label)}>
                  <h3 className="mb-2 text-xs font-semibold text-cyan-300">
                    {String(label)}
                  </h3>

                  <pre className="max-h-96 overflow-auto rounded-lg bg-slate-950 p-3 text-xs leading-5 text-slate-400">
                    {JSON.stringify(data, null, 2)}
                  </pre>
                </div>
              );
            })}
          </div>
        </details>
      )}
    </div>
  );
}
