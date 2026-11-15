"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import {
  Activity, AlertTriangle, CalendarDays, ChartNoAxesCombined,
  CloudSun, Database, Droplets, Globe2, Leaf, RefreshCw,
  Satellite, Thermometer, Waves,
} from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

type Domain = {
  id: string;
  name: string;
  description?: string;
  observation_support?: boolean;
};
type Observation = { date: string; [key: string]: string | number | null };
type Series = {
  id: string; name: string; parameter: string; unit: string;
  source: string; observations: { date: string; value: number }[];
  error?: string;
};
type ChartType = "line" | "area" | "bar" | "pie" | "donut" | "scatter" | "histogram" | "heatmap";
const CHART_TYPES: { id: ChartType; label: string }[] = [
  { id: "line", label: "Line" }, { id: "area", label: "Area" },
  { id: "bar", label: "Bar" }, { id: "pie", label: "Pie" },
  { id: "donut", label: "Donut" }, { id: "scatter", label: "Scatter" },
  { id: "histogram", label: "Histogram" }, { id: "heatmap", label: "Heatmap" },
];

const ICONS = [Thermometer, Droplets, Leaf, CloudSun, Waves, Activity];
const COLORS = ["#38bdf8", "#22d3ee", "#a3e635", "#f59e0b", "#c084fc", "#fb7185"];
const fmt = (n: number, digits = 1) => Number.isFinite(n) ? n.toFixed(digits) : "—";
const mean = (values: number[]) => values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;

function MiniLine({ data, color, area = false }: { data: { date: string; value: number }[]; color: string; area?: boolean }) {
  if (data.length < 2) return <div className="flex h-28 items-center justify-center text-xs text-slate-500">Not enough observations for a trend line.</div>;
  const vals = data.map(d => d.value); const min = Math.min(...vals); const max = Math.max(...vals); const span = max - min || 1;
  const points = vals.map((v, i) => `${(i / (vals.length - 1)) * 100},${94 - ((v - min) / span) * 82}`).join(" ");
  return <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="h-28 w-full overflow-visible"><defs><linearGradient id={`fill-${color.replace('#','')}`} x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor={color} stopOpacity=".28"/><stop offset="100%" stopColor={color} stopOpacity="0"/></linearGradient></defs>{area && <polygon points={`0,100 ${points} 100,100`} fill={`url(#fill-${color.replace('#','')})`}/> }<polyline points={points} fill="none" stroke={color} strokeWidth="2" vectorEffect="non-scaling-stroke" strokeLinecap="round" strokeLinejoin="round"/></svg>;
}

function CompareBars({ previous, recent, unit }: { previous: number | null; recent: number | null; unit: string }) {
  if (previous === null || recent === null) return <p className="text-xs text-slate-500">Comparison unavailable: insufficient observations.</p>;
  const max = Math.max(Math.abs(previous), Math.abs(recent), 0.0001);
  return <div className="space-y-3">
    {[{ label: "Earlier period", value: previous, color: "#64748b" }, { label: "Recent period", value: recent, color: "#22d3ee" }].map(item => <div key={item.label}><div className="mb-1 flex justify-between text-[11px]"><span className="text-slate-400">{item.label}</span><span className="font-mono text-slate-200">{fmt(item.value)} {unit}</span></div><div className="h-2 overflow-hidden rounded-full bg-slate-800"><div className="h-full rounded-full" style={{ width: `${Math.max(2, Math.abs(item.value) / max * 100)}%`, background: item.color }}/></div></div>)}
  </div>;
}

function DistributionDonut({ data, color, variant = "donut" }: { data: { value: number }[]; color: string; variant?: "pie" | "donut" }) {
  if (data.length < 3) return <div className="flex h-28 items-center justify-center text-xs text-slate-500">Distribution needs more observations.</div>;
  const values = data.map(d => d.value);
  const min = Math.min(...values);
  const span = Math.max(...values) - min || 1;
  const counts = [0, 0, 0];
  values.forEach(value => { counts[Math.min(2, Math.max(0, Math.floor(((value - min) / span) * 3)))] += 1; });
  const total = counts.reduce((a,b)=>a+b,0) || 1; const circumference = 2 * Math.PI * 34;
  const firstPct = counts[0] / total * 100;
  const secondPct = firstPct + counts[1] / total * 100;
  if (variant === "pie") return <div className="flex items-center gap-4"><div className="h-28 w-28 shrink-0 rounded-full" style={{ background: `conic-gradient(#64748b 0 ${firstPct}%, ${color} ${firstPct}% ${secondPct}%, #f59e0b ${secondPct}% 100%)` }}/><div className="space-y-2 text-[10px] text-slate-400"><div>Lower third · {fmt(counts[0] / total * 100)}%</div><div>Middle third · {fmt(counts[1] / total * 100)}%</div><div>Upper third · {fmt(counts[2] / total * 100)}%</div><p className="max-w-28 text-slate-600">Ranked value thirds, not risk categories.</p></div></div>;
  let offset = 0;
  const segments = counts.map((count, i) => { const length = count / total * circumference; const item = { length, offset, color: ["#64748b", color, "#f59e0b"][i] }; offset += length; return item; });
  return <div className="flex items-center gap-4"><svg viewBox="0 0 100 100" className="h-28 w-28 -rotate-90"><circle cx="50" cy="50" r="34" fill="none" stroke="#1e293b" strokeWidth="13"/>{segments.map((s,i)=><circle key={i} cx="50" cy="50" r="34" fill="none" stroke={s.color} strokeWidth="13" strokeDasharray={`${s.length} ${circumference-s.length}`} strokeDashoffset={-s.offset}/>)}</svg><div className="space-y-2 text-[10px] text-slate-400"><div><span className="mr-2 inline-block h-2 w-2 rounded-full bg-slate-500"/>Lower third</div><div><span className="mr-2 inline-block h-2 w-2 rounded-full" style={{background:color}}/>Middle third</div><div><span className="mr-2 inline-block h-2 w-2 rounded-full bg-amber-400"/>Upper third</div><p className="max-w-28 text-slate-600">Relative distribution within this dataset, not climate risk categories.</p></div></div>;
}

export default function MissionControl({ mapContent }: { mapContent: ReactNode }) {
  const [domains, setDomains] = useState<Domain[]>([]);
  const [series, setSeries] = useState<Series[]>([]);
  const [latitude, setLatitude] = useState("20.5937");
  const [longitude, setLongitude] = useState("78.9629");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [lastUpdated, setLastUpdated] = useState("");
  const [selected, setSelected] = useState("");
  const [chartType, setChartType] = useState<ChartType>("line");

  const load = useCallback(async () => {
    const lat = Number(latitude); const lon = Number(longitude);
    if (!Number.isFinite(lat) || lat < -90 || lat > 90 || !Number.isFinite(lon) || lon < -180 || lon > 180) { setError("Enter valid latitude (-90 to 90) and longitude (-180 to 180)."); return; }
    setLoading(true); setError("");
    try {
      const domainResponse = await fetch(`${API_BASE}/api/science/domains`);
      if (!domainResponse.ok) throw new Error(`Science domains API returned HTTP ${domainResponse.status}`);
      const domainPayload = await domainResponse.json();
      const supported: Domain[] = (domainPayload.domains || []).filter((d: Domain) => d.observation_support);
      setDomains(supported);
      if (!supported.length) throw new Error("The backend returned no domains with observation support.");
      const end = new Date(); const start = new Date(end); start.setUTCDate(start.getUTCDate() - 365);
      const params = new URLSearchParams({ latitude: String(lat), longitude: String(lon), start_date: start.toISOString().slice(0,10).replaceAll("-", ""), end_date: end.toISOString().slice(0,10).replaceAll("-", "") });
      const domainResults = await Promise.all(supported.map(async (domain) => {
        try {
          const response = await fetch(`${API_BASE}/api/science/observations/${encodeURIComponent(domain.id)}?${params}`);
          if (!response.ok) throw new Error(`HTTP ${response.status}`);
          return { domain, payload: await response.json(), error: undefined as string | undefined };
        } catch (e) {
          return { domain, error: e instanceof Error ? e.message : "Request failed", payload: null };
        }
      }));
      const results: Series[] = [];
      for (const item of domainResults) {
        if (!item.payload) {
          results.push({ id: `${item.domain.id}::unavailable`, name: item.domain.name, parameter: "Unavailable", unit: "", source: "Unavailable", observations: [], error: item.error });
          continue;
        }
        const rows: Observation[] = item.payload.observations || [];
        const metadata = item.payload.metadata?.parameters || {};
        const keys = new Set<string>(Object.keys(metadata));
        rows.forEach(row => Object.entries(row).forEach(([key, value]) => {
          if (!["date", "time", "id"].includes(key) && value !== null && value !== "" && Number.isFinite(Number(value))) keys.add(key);
        }));
        for (const parameter of keys) {
          const meta = metadata[parameter] || {};
          const observations = rows.map(row => ({ date: String(row.date || row.time || ""), raw: row[parameter] }))
            .filter(point => point.date && point.raw !== null && point.raw !== undefined && point.raw !== "" && Number.isFinite(Number(point.raw)))
            .map(point => ({ date: point.date, value: Number(point.raw) }))
            .sort((a, b) => a.date.localeCompare(b.date));
          results.push({
            id: `${item.domain.id}::${parameter}`, name: item.domain.name,
            parameter: meta.label || meta.name || parameter.replaceAll("_", " "),
            unit: meta.unit || "", source: item.payload.source?.name || "Source not supplied",
            observations, error: observations.length ? undefined : "No numeric observations returned for this parameter.",
          });
        }
      }
      setSeries(results);
      setSelected(current => results.some(s => s.id === current && s.observations.length) ? current : (results.find(s => s.observations.length)?.id || results[0]?.id || ""));
      setLastUpdated(new Date().toLocaleString());
    } catch (e) { setError(e instanceof Error ? e.message : "Unable to load Mission Control data."); setSeries([]); }
    finally { setLoading(false); }
  }, [latitude, longitude]);

  useEffect(() => { void load(); /* load once on mount; manual refresh uses current coordinates */ }, []);
  const active = series.find(s=>s.id===selected) || series.find(s=>s.observations.length) || null;
  const comparison = useMemo(() => {
    if (!active || active.observations.length < 2) return { previous: null, recent: null, change: null };
    const split = Math.floor(active.observations.length / 2); const previous = mean(active.observations.slice(0,split).map(p=>p.value)); const recent = mean(active.observations.slice(split).map(p=>p.value));
    return { previous, recent, change: previous !== null && recent !== null ? recent - previous : null };
  }, [active]);
  const totalObservations = series.reduce((n,s)=>n+s.observations.length,0);
  const successful = series.filter(s=>s.observations.length).length;

  return <div className="space-y-4">
    <section className="relative overflow-hidden rounded-2xl border border-sky-500/20 bg-gradient-to-br from-slate-950 via-slate-900 to-cyan-950/50 p-5 md:p-6">
      <div className="pointer-events-none absolute -right-16 -top-20 h-64 w-64 rounded-full border border-cyan-400/10"/><div className="pointer-events-none absolute -right-5 -top-9 h-44 w-44 rounded-full border border-cyan-400/10"/>
      <div className="relative flex flex-col justify-between gap-5 lg:flex-row lg:items-end"><div><div className="mb-2 flex items-center gap-2 text-[10px] font-semibold tracking-[.22em] text-cyan-300"><Globe2 size={14}/> GEONOVA / EARTH INTELLIGENCE CENTRE</div><h3 className="font-display text-2xl font-semibold md:text-3xl">Mission Control</h3><p className="mt-2 max-w-xl text-xs leading-relaxed text-slate-400">A live research console for available environmental observations, regional conditions and historical comparisons.</p></div><div className="flex flex-wrap items-end gap-2"><label className="text-[10px] text-slate-400">Latitude<input value={latitude} onChange={e=>setLatitude(e.target.value)} className="mt-1 block w-28 rounded-lg border border-slate-700 bg-slate-950/80 px-3 py-2 text-xs text-white outline-none focus:border-cyan-400"/></label><label className="text-[10px] text-slate-400">Longitude<input value={longitude} onChange={e=>setLongitude(e.target.value)} className="mt-1 block w-28 rounded-lg border border-slate-700 bg-slate-950/80 px-3 py-2 text-xs text-white outline-none focus:border-cyan-400"/></label><button onClick={()=>void load()} disabled={loading} className="flex items-center gap-2 rounded-lg border border-cyan-400/30 bg-cyan-400/10 px-3 py-2.5 text-xs font-semibold text-cyan-200 hover:bg-cyan-400/20 disabled:opacity-50"><RefreshCw size={14} className={loading?"animate-spin":""}/>{loading?"Loading":"Refresh data"}</button></div></div>
    </section>

    {error && <div className="flex items-start gap-2 rounded-xl border border-rose-500/20 bg-rose-500/5 p-3 text-xs text-rose-300"><AlertTriangle size={15} className="mt-0.5 shrink-0"/>{error}</div>}

    <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
      {[{label:"Available parameters",value:successful.toLocaleString(),sub:"Parameters with numeric records",Icon:Database},{label:"Parameter records",value:totalObservations.toLocaleString(),sub:"Numeric values returned by APIs",Icon:Activity},{label:"Comparison window",value:"365 days",sub:"Requested historical period",Icon:CalendarDays},{label:"Data refresh",value:lastUpdated?"Updated":"Pending",sub:lastUpdated||"Waiting for backend",Icon:Satellite}].map(({label,value,sub,Icon})=><div key={label} className="rounded-xl border border-slate-800 bg-slate-900/65 p-4"><div className="flex items-center justify-between"><span className="text-[10px] uppercase tracking-wider text-slate-500">{label}</span><Icon size={16} className="text-cyan-300"/></div><div className="mt-3 font-display text-2xl font-semibold text-slate-100">{value}</div><p className="mt-1 text-[10px] text-slate-500">{sub}</p></div>)}
    </div>

    <section className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900/60 p-3">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2 px-1">
        <div><div className="text-sm font-semibold text-slate-100">Global climate maps</div><p className="mt-1 text-[10px] text-slate-500">Use both the original flat satellite map and the separate rotating 3D globe. Both retain the same selectable environmental layers.</p></div>
        <span className="rounded-md border border-cyan-400/20 bg-cyan-400/5 px-2 py-1 text-[9px] text-cyan-200">NASA GIBS / MODIS / GPM</span>
      </div>
      <div className="relative h-[760px] overflow-hidden rounded-lg md:h-[510px]">{mapContent}</div>
    </section>

    <div className="grid gap-4 xl:grid-cols-[1.45fr_1fr]">
      <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-4"><div className="mb-4 flex items-center justify-between"><div><div className="text-sm font-semibold text-slate-100">Climate signal explorer</div><p className="mt-1 text-[10px] text-slate-500">Actual observations returned for the selected coordinates</p></div><ChartNoAxesCombined size={18} className="text-cyan-300"/></div>
        <div className="mb-4 flex flex-wrap gap-2">{series.filter(s=>s.observations.length).map((s,i)=><button key={s.id} onClick={()=>setSelected(s.id)} className={`rounded-lg border px-3 py-2 text-[10px] ${selected===s.id?"border-cyan-400/40 bg-cyan-400/10 text-cyan-200":"border-slate-700 bg-slate-950/50 text-slate-400"}`}>{s.name} · {s.parameter}</button>)}</div>
        {active ? <><div className="mb-2 flex flex-wrap items-end justify-between gap-2"><div><div className="text-xs font-semibold text-slate-200">{active.parameter}</div><div className="mt-1 text-[10px] text-slate-500">{active.name} · {active.unit || "unit not supplied"}</div></div><div className="text-right"><div className="font-mono text-xl text-cyan-200">{active.observations.length?fmt(active.observations[active.observations.length-1].value):"—"}</div><div className="text-[9px] text-slate-500">Latest returned value</div></div></div><div className="mb-3 flex flex-wrap gap-1.5">{CHART_TYPES.map(chart=><button key={chart.id} onClick={()=>setChartType(chart.id)} className={`rounded-md border px-2.5 py-2 text-[10px] ${chartType===chart.id?"border-cyan-400/40 bg-cyan-400/10 text-cyan-200":"border-slate-700 bg-slate-950/50 text-slate-400"}`}>{chart.label}</button>)}</div>
        {chartType === "line" || chartType === "area" ? <MiniLine data={active.observations} color="#22d3ee" area={chartType === "area"}/> : null}
        {chartType === "pie" || chartType === "donut" ? <DistributionDonut data={active.observations} color="#22d3ee" variant={chartType}/> : null}
        {chartType === "bar" ? <div className="flex h-36 items-end gap-1 border-b border-slate-700 px-2">{active.observations.slice(-24).map((point,i)=>{const max=Math.max(...active.observations.slice(-24).map(p=>Math.abs(p.value)),0.0001);return <div key={`${point.date}-${i}`} title={`${point.date}: ${point.value} ${active.unit}`} className="min-w-0 flex-1 rounded-t bg-cyan-400/80" style={{height:`${Math.max(2,Math.abs(point.value)/max*100)}%`}}/>})}</div> : null}
        {chartType === "scatter" ? <svg viewBox="0 0 600 180" className="h-40 w-full">{active.observations.map((point,i)=>{const vals=active.observations.map(p=>p.value),min=Math.min(...vals),span=Math.max(...vals)-min||1;return <circle key={`${point.date}-${i}`} cx={30+i/Math.max(1,vals.length-1)*540} cy={160-(point.value-min)/span*140} r="3" fill="#22d3ee"/>})}</svg> : null}
        {chartType === "histogram" || chartType === "heatmap" ? (()=>{const vals=active.observations.map(p=>p.value),min=Math.min(...vals),span=Math.max(...vals)-min||1,bins=Array(10).fill(0);vals.forEach(v=>bins[Math.min(9,Math.floor((v-min)/span*10))]++);const max=Math.max(...bins,1);return <div className={chartType==="heatmap"?"grid grid-cols-10 gap-1":"flex h-36 items-end gap-1 border-b border-slate-700"}>{bins.map((count,i)=><div key={i} title={`Bin ${i+1}: ${count}`} className={chartType==="heatmap"?"aspect-square rounded":"min-w-0 flex-1 rounded-t"} style={{background:`rgba(34,211,238,${0.15+count/max*0.8})`,height:chartType==="heatmap"?undefined:`${Math.max(3,count/max*100)}%`}}/>)}</div>})() : null}<div className="mt-2 flex justify-between text-[9px] text-slate-600"><span>{active.observations[0]?.date||"No start date"}</span><span>{active.observations[active.observations.length-1]?.date||"No latest date"}</span></div><div className="mt-4 border-t border-slate-800 pt-3"><div className="mb-3 text-[10px] font-semibold uppercase tracking-wider text-slate-500">Earlier period vs recent period</div><CompareBars previous={comparison.previous} recent={comparison.recent} unit={active.unit}/><p className="mt-3 text-[10px] text-slate-500">Change: {comparison.change===null?"—":`${comparison.change>=0?"+":""}${fmt(comparison.change)} ${active.unit}`} · Periods are split from the returned time series, not calendar-month aggregates.</p></div></> : <div className="py-12 text-center text-xs text-slate-500">{loading?"Loading observations…":"No observation series available."}</div>}
      </section>
      <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-4"><div className="mb-3 flex items-center justify-between"><div><div className="text-sm font-semibold text-slate-100">Observation distribution</div><p className="mt-1 text-[10px] text-slate-500">Relative thirds within the selected dataset</p></div><Activity size={18} className="text-amber-300"/></div>{active?<DistributionDonut data={active.observations} color="#22d3ee"/>:<p className="py-12 text-center text-xs text-slate-500">No distribution to display.</p>}<div className="mt-4 rounded-lg border border-amber-500/15 bg-amber-500/5 p-3 text-[10px] leading-relaxed text-amber-200/80">This donut shows the lower, middle and upper thirds of the selected observations. It is a statistical distribution, not a classification of safe, moderate or dangerous climate conditions.</div></section>
    </div>

    <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-4"><div className="mb-4 flex items-center justify-between"><div><div className="text-sm font-semibold text-slate-100">Environmental parameter availability</div><p className="mt-1 text-[10px] text-slate-500">Availability is based on actual API responses, not placeholder status values.</p></div><Globe2 size={18} className="text-sky-300"/></div><div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{series.map((s,i)=>{const Icon=ICONS[i%ICONS.length];return <div key={s.id} className="rounded-lg border border-slate-800 bg-slate-950/50 p-3"><div className="flex items-center justify-between"><div className="flex items-center gap-2"><Icon size={16} style={{color:COLORS[i%COLORS.length]}}/><span className="text-xs font-semibold text-slate-200">{s.name}</span></div><span className={`h-2 w-2 rounded-full ${s.observations.length?"bg-emerald-400":"bg-amber-400"}`}/></div><div className="mt-3 text-[10px] text-slate-500">{s.observations.length?`${s.observations.length} observations · ${s.unit||"unit unavailable"}`:s.error||"No observations"}</div><div className="mt-2 truncate text-[9px] text-slate-600">Source: {s.source}</div></div>;})}</div></section>
    <p className="px-1 text-[10px] leading-relaxed text-slate-600">Data note: this workspace requests a 365-day observation window for the selected point. It displays only numeric values returned by the configured Science API. A latest value is not necessarily real-time; source latency and temporal resolution depend on the underlying dataset. This view is point-based and does not replace the global satellite map.</p>
  </div>;
}
