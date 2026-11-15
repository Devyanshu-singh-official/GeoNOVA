
"use client";

import { useMemo, useRef, useState } from "react";

import {
  Activity,
  AlertCircle,
  BarChart3,
  ChartNoAxesColumn,
  CircleDot,
  Download,
  LineChart as LineChartIcon,
  PieChart as PieChartIcon,
  TrendingUp,
  Loader2,
  CheckCircle2,
} from "lucide-react";

import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
  ReferenceLine,
  Legend,
} from "recharts";

import { exportScientificChartPNG } from "@/lib/scientificExports";

// ============================================================
// TYPES
// ============================================================

export type ScientificChartType =
  | "line"
  | "area"
  | "bar"
  | "scatter"
  | "pie"
  | "donut"
  | "histogram"
  | "anomaly";

export type ScientificChartSeries = {
  dataKey: string;
  name?: string;
  color?: string;
  unit?: string;
};

export type ScientificChartPoint = {
  [key: string]: string | number | null | undefined;
};

type ScientificChartEngineProps = {
  title?: string;
  subtitle?: string;
  chartType: ScientificChartType;
  data: ScientificChartPoint[];
  xKey?: string;
  yKey?: string;
  categoryKey?: string;
  valueKey?: string;
  series?: ScientificChartSeries[];
  height?: number;
  unit?: string;
  emptyMessage?: string;
  showLegend?: boolean;
  showGrid?: boolean;
  showTooltip?: boolean;
  showTrendReference?: boolean;
  referenceValue?: number;
  className?: string;
};

// ============================================================
// CHART COLORS
// ============================================================

const CHART_COLORS = [
  "#4ce0d2",
  "#60a5fa",
  "#a78bfa",
  "#f59e0b",
  "#fb7185",
  "#34d399",
  "#f97316",
  "#38bdf8",
];

// ============================================================
// HELPERS
// ============================================================

function isValidNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function formatValue(value: unknown, unit?: string) {
  if (!isValidNumber(value)) {
    return String(value ?? "—");
  }

  const formatted = value.toLocaleString(undefined, {
    maximumFractionDigits: 3,
  });

  return unit ? `${formatted} ${unit}` : formatted;
}

function calculateHistogram(
  data: ScientificChartPoint[],
  valueKey: string,
  requestedBins = 10
) {
  const values = data
    .map((item) => item[valueKey])
    .filter(isValidNumber);

  if (values.length === 0) return [];

  const minimum = Math.min(...values);
  const maximum = Math.max(...values);

  if (minimum === maximum) {
    return [
      {
        range: formatValue(minimum),
        frequency: values.length,
      },
    ];
  }

  const binCount = Math.min(
    requestedBins,
    Math.max(1, values.length)
  );

  const binWidth = (maximum - minimum) / binCount;

  const bins = Array.from({ length: binCount }, (_, index) => {
    const lower = minimum + index * binWidth;

    const upper =
      index === binCount - 1
        ? maximum
        : minimum + (index + 1) * binWidth;

    return {
      lower,
      upper,
      frequency: 0,
      range: `${lower.toFixed(2)} – ${upper.toFixed(2)}`,
    };
  });

  values.forEach((value) => {
    let index = Math.floor((value - minimum) / binWidth);

    index = Math.min(index, binCount - 1);
    index = Math.max(index, 0);

    bins[index].frequency += 1;
  });

  return bins;
}

function createChartFilename(title?: string) {
  const base = (title || "geonova-scientific-chart")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9-_]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");

  return `${base || "geonova-scientific-chart"}.png`;
}

// ============================================================
// CUSTOM TOOLTIP
// ============================================================

function ScientificTooltip({
  active,
  payload,
  label,
  unit,
}: {
  active?: boolean;
  payload?: Array<{
    name?: string;
    value?: number | string;
    color?: string;
    dataKey?: string;
  }>;
  label?: string | number;
  unit?: string;
}) {
  if (!active || !payload?.length) return null;

  return (
    <div className="min-w-36 rounded-xl border border-slate-700 bg-[#101824] p-3 shadow-xl">
      {label !== undefined && (
        <div className="mb-2 text-xs text-slate-400">
          {label}
        </div>
      )}

      <div className="space-y-2">
        {payload.map((item, index) => (
          <div
            key={`${item.dataKey || item.name || "series"}-${index}`}
            className="flex items-center justify-between gap-4"
          >
            <div className="flex min-w-0 items-center gap-2">
              <span
                className="h-2 w-2 shrink-0 rounded-full"
                style={{
                  backgroundColor: item.color || "#4ce0d2",
                }}
              />

              <span className="truncate text-xs text-slate-300">
                {item.name || item.dataKey || "Value"}
              </span>
            </div>

            <span className="text-xs font-semibold text-white">
              {formatValue(item.value, unit)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ============================================================
// MAIN COMPONENT
// ============================================================

export default function ScientificChartEngine({
  title,
  subtitle,
  chartType,
  data,
  xKey = "date",
  yKey = "value",
  categoryKey = "name",
  valueKey = "value",
  series,
  height = 320,
  unit,
  emptyMessage = "No valid scientific observations are available.",
  showLegend = false,
  showGrid = true,
  showTooltip = true,
  showTrendReference = false,
  referenceValue,
  className = "",
}: ScientificChartEngineProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);

  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState("");
  const [exportSuccess, setExportSuccess] = useState(false);

  const validData = useMemo(() => {
    return data.filter(
      (item) => item !== null && item !== undefined
    );
  }, [data]);

  const activeSeries = useMemo(() => {
    if (series?.length) return series;

    return [
      {
        dataKey: yKey,
        name: yKey,
        color: CHART_COLORS[0],
        unit,
      },
    ];
  }, [series, yKey, unit]);

  const histogramData = useMemo(() => {
    return calculateHistogram(validData, valueKey);
  }, [validData, valueKey]);

  const hasData = useMemo(() => {
    if (chartType === "pie" || chartType === "donut") {
      return validData.some((item) =>
        isValidNumber(item[valueKey])
      );
    }

    if (chartType === "histogram") {
      return histogramData.length > 0;
    }

    if (chartType === "scatter") {
      return validData.some(
        (item) =>
          isValidNumber(item[xKey]) &&
          isValidNumber(item[yKey])
      );
    }

    return validData.some((item) =>
      activeSeries.some((itemSeries) =>
        isValidNumber(item[itemSeries.dataKey])
      )
    );
  }, [
    chartType,
    validData,
    histogramData,
    activeSeries,
    valueKey,
    xKey,
    yKey,
  ]);

  const chartData = useMemo(() => {
    if (chartType !== "anomaly") return validData;

    return validData.map((item) => ({
      ...item,
      __anomaly:
        item.__anomaly === true ||
        item.is_anomaly === true ||
        item.anomaly === true,
    }));
  }, [chartType, validData]);

  const headerIcon = {
    line: LineChartIcon,
    area: Activity,
    bar: ChartNoAxesColumn,
    scatter: CircleDot,
    pie: PieChartIcon,
    donut: PieChartIcon,
    histogram: BarChart3,
    anomaly: TrendingUp,
  }[chartType];

  const HeaderIcon = headerIcon;

  const tooltip = showTooltip ? (
    <Tooltip
      content={<ScientificTooltip unit={unit} />}
      cursor={{
        stroke: "rgba(148,163,184,0.35)",
        strokeDasharray: "3 3",
      }}
    />
  ) : null;

  const grid = showGrid ? (
    <CartesianGrid
      stroke="rgba(148,163,184,0.12)"
      strokeDasharray="3 3"
    />
  ) : null;

  const axisStyle = {
    fill: "#8492a6",
    fontSize: 10,
  };

  // ==========================================================
  // PNG EXPORT
  // ==========================================================

  async function handleExportPNG() {
    if (!hasData || exporting) return;

    setExporting(true);
    setExportError("");
    setExportSuccess(false);

    try {
      await exportScientificChartPNG(
        chartContainerRef.current,
        createChartFilename(title)
      );

      setExportSuccess(true);
    } catch (error) {
      setExportError(
        error instanceof Error
          ? error.message
          : "Chart export failed."
      );
    } finally {
      setExporting(false);
    }
  }

  // ==========================================================
  // CHART RENDERER
  // ==========================================================

  function renderChart() {
    if (!hasData) {
      return (
        <div className="flex h-full flex-col items-center justify-center px-5 text-center">
          <Activity
            size={28}
            className="mb-3 text-slate-600"
          />

          <p className="text-sm text-slate-300">
            No chart data available
          </p>

          <p className="mt-2 max-w-sm text-xs text-slate-500">
            {emptyMessage}
          </p>
        </div>
      );
    }

    switch (chartType) {
      // ------------------------------------------------------
      // LINE CHART
      // ------------------------------------------------------

      case "line":
        return (
          <LineChart data={validData}>
            {grid}

            <XAxis
              dataKey={xKey}
              tick={axisStyle}
              minTickGap={25}
            />

            <YAxis
              tick={axisStyle}
              width={65}
            />

            {tooltip}

            {showLegend && <Legend />}

            {activeSeries.map((item, index) => (
              <Line
                key={item.dataKey}
                type="monotone"
                dataKey={item.dataKey}
                name={item.name || item.dataKey}
                stroke={
                  item.color ||
                  CHART_COLORS[index % CHART_COLORS.length]
                }
                strokeWidth={2}
                dot={false}
                connectNulls={false}
                activeDot={{ r: 4 }}
              />
            ))}

            {showTrendReference &&
              isValidNumber(referenceValue) && (
                <ReferenceLine
                  y={referenceValue}
                  stroke="#f59e0b"
                  strokeDasharray="5 5"
                  label={{
                    value: "Reference",
                    fill: "#f59e0b",
                    fontSize: 10,
                  }}
                />
              )}
          </LineChart>
        );

      // ------------------------------------------------------
      // AREA CHART
      // ------------------------------------------------------

      case "area":
        return (
          <AreaChart data={validData}>
            {grid}

            <XAxis
              dataKey={xKey}
              tick={axisStyle}
              minTickGap={25}
            />

            <YAxis
              tick={axisStyle}
              width={65}
            />

            {tooltip}

            {showLegend && <Legend />}

            {activeSeries.map((item, index) => (
              <Area
                key={item.dataKey}
                type="monotone"
                dataKey={item.dataKey}
                name={item.name || item.dataKey}
                stroke={
                  item.color ||
                  CHART_COLORS[index % CHART_COLORS.length]
                }
                fill={
                  item.color ||
                  CHART_COLORS[index % CHART_COLORS.length]
                }
                fillOpacity={0.15}
                strokeWidth={2}
                connectNulls={false}
              />
            ))}
          </AreaChart>
        );

      // ------------------------------------------------------
      // BAR CHART
      // ------------------------------------------------------

      case "bar":
        return (
          <BarChart data={validData}>
            {grid}

            <XAxis
              dataKey={xKey}
              tick={axisStyle}
              minTickGap={20}
            />

            <YAxis
              tick={axisStyle}
              width={65}
            />

            {tooltip}

            {showLegend && <Legend />}

            {activeSeries.map((item, index) => (
              <Bar
                key={item.dataKey}
                dataKey={item.dataKey}
                name={item.name || item.dataKey}
                fill={
                  item.color ||
                  CHART_COLORS[index % CHART_COLORS.length]
                }
                radius={[4, 4, 0, 0]}
              />
            ))}
          </BarChart>
        );

      // ------------------------------------------------------
      // SCATTER / CORRELATION CHART
      // ------------------------------------------------------

      case "scatter":
        return (
          <ScatterChart>
            {grid}

            <XAxis
              type="number"
              dataKey={xKey}
              name={xKey}
              tick={axisStyle}
            />

            <YAxis
              type="number"
              dataKey={yKey}
              name={yKey}
              tick={axisStyle}
              width={65}
            />

            <ZAxis range={[45, 45]} />

            {tooltip}

            <Scatter
              name={`${xKey} vs ${yKey}`}
              data={validData.filter(
                (item) =>
                  isValidNumber(item[xKey]) &&
                  isValidNumber(item[yKey])
              )}
              fill={CHART_COLORS[0]}
            />
          </ScatterChart>
        );

      // ------------------------------------------------------
      // PIE / DONUT CHART
      // ------------------------------------------------------

      case "pie":
      case "donut":
        return (
          <PieChart>
            <Pie
              data={validData.filter((item) =>
                isValidNumber(item[valueKey])
              )}
              dataKey={valueKey}
              nameKey={categoryKey}
              cx="50%"
              cy="50%"
              outerRadius="78%"
              innerRadius={chartType === "donut" ? "48%" : 0}
              paddingAngle={2}
              labelLine={false}
              label={({ name, percent }) =>
                `${String(name || "")} ${
                  typeof percent === "number"
                    ? `${(percent * 100).toFixed(1)}%`
                    : ""
                }`
              }
            >
              {validData.map((_, index) => (
                <Cell
                  key={`slice-${index}`}
                  fill={
                    CHART_COLORS[index % CHART_COLORS.length]
                  }
                />
              ))}
            </Pie>

            {tooltip}

            {showLegend && <Legend />}
          </PieChart>
        );

      // ------------------------------------------------------
      // HISTOGRAM
      // ------------------------------------------------------

      case "histogram":
        return (
          <BarChart data={histogramData}>
            {grid}

            <XAxis
              dataKey="range"
              tick={axisStyle}
              interval="preserveStartEnd"
            />

            <YAxis
              tick={axisStyle}
              allowDecimals={false}
            />

            {tooltip}

            <Bar
              dataKey="frequency"
              name="Frequency"
              fill={CHART_COLORS[1]}
              radius={[4, 4, 0, 0]}
            />
          </BarChart>
        );

      // ------------------------------------------------------
      // ANOMALY CHART
      // ------------------------------------------------------

      case "anomaly":
        return (
          <ComposedChart data={chartData}>
            {grid}

            <XAxis
              dataKey={xKey}
              tick={axisStyle}
              minTickGap={25}
            />

            <YAxis
              tick={axisStyle}
              width={65}
            />

            {tooltip}

            <Line
              type="monotone"
              dataKey={yKey}
              name="Observed value"
              stroke={CHART_COLORS[0]}
              strokeWidth={2}
              dot={false}
              connectNulls={false}
            />

            <Scatter
              name="Detected anomaly"
              data={chartData.filter(
                (item) => item.__anomaly === true
              )}
              dataKey={yKey}
              fill="#fb7185"
              shape="circle"
            />
          </ComposedChart>
        );

      default:
        return null;
    }
  }

  // ==========================================================
  // COMPONENT UI
  // ==========================================================

  return (
    <section
      className={`panel space-y-4 p-4 sm:p-5 ${className}`}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          {title && (
            <h3 className="text-sm font-semibold text-slate-100">
              {title}
            </h3>
          )}

          {subtitle && (
            <p className="mt-1 text-xs text-slate-400">
              {subtitle}
            </p>
          )}
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleExportPNG}
            disabled={!hasData || exporting}
            title="Export chart as high-resolution PNG"
            className="flex items-center gap-2 rounded-lg border border-cyan-500/30 bg-cyan-500/10 px-3 py-2 text-xs font-medium text-cyan-300 transition hover:bg-cyan-500/20 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {exporting ? (
              <Loader2
                size={15}
                className="animate-spin"
              />
            ) : (
              <Download size={15} />
            )}

            {exporting ? "Exporting..." : "Export PNG"}
          </button>

          <div className="shrink-0 rounded-lg bg-cyan-400/10 p-2">
            <HeaderIcon
              size={18}
              className="text-cyan-300"
            />
          </div>
        </div>
      </div>

      {/* CHART CONTAINER */}

      <div
        ref={chartContainerRef}
        className="w-full bg-[#0b1220] p-2"
        style={{ height }}
      >
        <ResponsiveContainer width="100%" height="100%">
          {renderChart() || <></>}
        </ResponsiveContainer>
      </div>

      {/* EXPORT FEEDBACK */}

      {exportSuccess && (
        <div className="flex items-center gap-2 rounded-lg border border-emerald-500/20 bg-emerald-500/5 px-3 py-2 text-xs text-emerald-300">
          <CheckCircle2 size={15} />
          Chart PNG export completed.
        </div>
      )}

      {exportError && (
        <div className="flex items-start gap-2 rounded-lg border border-red-500/20 bg-red-500/5 px-3 py-2 text-xs text-red-300">
          <AlertCircle size={15} className="mt-0.5 shrink-0" />
          <span>{exportError}</span>
        </div>
      )}

      {/* CHART METADATA */}

      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-800 pt-3">
        <span className="text-[10px] uppercase tracking-wider text-slate-500">
          {chartType} visualization
        </span>

        {unit && (
          <span className="text-[10px] text-slate-400">
            Unit: {unit}
          </span>
        )}

        <span className="text-[10px] text-slate-500">
          {validData.length.toLocaleString()} records
        </span>
      </div>
    </section>
  );
}
