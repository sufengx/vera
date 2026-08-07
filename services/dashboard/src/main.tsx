/**
 * Vera AI 可观测性大屏 — 单文件实现
 * 技术栈: React 18 + TypeScript + Tailwind v3 + Recharts
 * 布局: 顶部通栏 8% + 三列主体 3:4:3，1920×1080 全屏无滚动
 * 数据: 每 10s 轮询 /api/（nginx 代理 ClickHouse，同源免 CORS），窗口语义与检测器一致
 */
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { createRoot } from "react-dom/client";
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Line, LineChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import "./index.css";

/* ── 主题常量 ─────────────────────────────────────────── */
const PURPLE = "#8b5cf6";
const CYAN = "#06b6d4";
const RED = "#ef4444";
const GREEN = "#10b981";
const GRAY_LINE = "#cbd5e1";
const GRAY_BAR = "#4b5563";
const TICK = { fill: "#64748b", fontSize: 11 };
const TOOLTIP_STYLE = {
  background: "rgba(17,19,24,0.95)",
  border: "1px solid rgba(255,255,255,0.1)",
  borderRadius: 10,
  fontSize: 12,
  color: "#e2e8f0",
};
const POLL_MS = 10000;
const WINDOW = { cur: 5, off: 30, base: 30 }; // 分钟，与检测器默认参数一致

/* ── 时间工具：ClickHouse 存 UTC，展示时转浏览器本地时区 ── */
const p2 = (n: number) => String(n).padStart(2, "0");
const WEEK_ZH = ["日", "一", "二", "三", "四", "五", "六"];
const WEEK_EN = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
// 空格+Z 在老引擎会被当成本地时间，转成严格 ISO 再解析
const toLocal = (utc: string) => new Date(utc.length === 19 ? `${utc.replace(" ", "T")}Z` : utc);
const fmtLocal = (utc: string, sec = true) => {
  const d = toLocal(utc);
  return `${d.getFullYear()}-${p2(d.getMonth() + 1)}-${p2(d.getDate())} ${p2(d.getHours())}:${p2(d.getMinutes())}${sec ? `:${p2(d.getSeconds())}` : ""}`;
};

/* ── I18N ─────────────────────────────────────────────── */
const I18N: Record<string, Record<string, string>> = {
  zh: {
    title: "Vera AI 可观测性大屏",
    statusOk: "系统运行正常",
    statusOkSub: "所有信号处于正常范围",
    statusDrift: "检测到漂移",
    statusDriftSub: "{n}个信号行为异常",
    waitScan: "等待检测器首轮扫描…",
    scanAt: "最近扫描",
    overview: "系统概览",
    signalAnalysis: "信号漂移分析",
    trafficTrend: "请求量趋势",
    distPred: "预测值分布",
    distConf: "置信度分布",
    latencyTrend: "响应延迟趋势",
    abnormalEvents: "异常事件详情",
    viewAll: "查看全部",
    noData: "暂无数据",
    noEvents: "暂无异常事件",
    connecting: "正在连接数据源…",
    drift: "漂移",
    normal: "正常",
    threshold: "threshold",
    currentWin: "当前窗口",
    baselineWin: "基准窗口",
    metricEvents: "事件量",
    metricP50: "P50延迟",
    metricP99: "P99延迟",
    metricDrift: "漂移信号",
    helpOverview: "事件量=模型最近一小时处理的请求数；P50/P99=一半/99% 的请求在多长时间内完成；漂移信号=当前有几个行为异常。",
    helpSignals: "系统定期对比模型最近行为和基准行为：绿点=正常；红点=行为偏移超过阈值，会触发告警。",
    helpTraffic: "每分钟模型请求数。陡升陡降可能意味着流量异常或系统故障。",
    helpDistPred: "模型预测值的分布：紫色=当前窗口，灰色=基准窗口。明显错开即视为行为改变。",
    helpDistConf: "模型置信度分布。突然变得过于自信或犹豫也是异常信号。",
    helpLatency: "P50=一半请求在此时间内完成，P99=99% 的请求在此时间内完成。P99 升高说明系统在变慢。",
    helpEvents: "最近触发的漂移事件。",
  },
  en: {
    title: "Vera AI Observability & Drift Detection",
    statusOk: "System Healthy",
    statusOkSub: "All signals within normal range",
    statusDrift: "Drift Detected",
    statusDriftSub: "{n} signals behaving abnormally",
    waitScan: "Waiting for the detector's first scan…",
    scanAt: "Last scan",
    overview: "Overview",
    signalAnalysis: "Signal Drift Analysis",
    trafficTrend: "Traffic Trend",
    distPred: "Prediction Distribution",
    distConf: "Confidence Distribution",
    latencyTrend: "Latency Trend",
    abnormalEvents: "Drift Events",
    viewAll: "View all",
    noData: "No data yet",
    noEvents: "No abnormal events",
    connecting: "Connecting to data source…",
    drift: "Drifted",
    normal: "Normal",
    threshold: "threshold",
    currentWin: "Current",
    baselineWin: "Baseline",
    metricEvents: "Events",
    metricP50: "P50 Latency",
    metricP99: "P99 Latency",
    metricDrift: "Drifted",
    helpOverview: "Events = requests handled in the last hour; P50/P99 = response speed; Drifted = abnormal signals found.",
    helpSignals: "The system compares recent model behavior against a baseline. Red = behavior shifted beyond threshold, alert fired.",
    helpTraffic: "Requests per minute. Sharp spikes or drops may indicate unusual load or faults.",
    helpDistPred: "Model prediction distribution: purple = current window, gray = baseline. Clear separation means behavior change.",
    helpDistConf: "Model confidence distribution. Sudden over-confidence or hesitation is a warning sign.",
    helpLatency: "P50 = half of requests complete within this time; P99 = 99% do. A rising P99 means the system is slowing.",
    helpEvents: "Recently fired drift events.",
  },
};

/* ── 数据层：轮询 ClickHouse（经 nginx /api/ 代理） ─────── */
type Signal = { metric: string; score: number; threshold: number; drifted: boolean };
type DistRow = { label: string; current: number; baseline: number };
type DashData = {
  ev: number; evPrev: number;
  p50: number; p99: number; p50Prev: number; p99Prev: number;
  scanTs: string | null;
  signals: Signal[];
  traffic: { t: string; n: number }[];
  latency: { t: string; p50: number; p99: number }[];
  driftEvents: { time: string; metric: string }[];
  distPred: DistRow[]; distConf: DistRow[];
};

async function ch(sql: string): Promise<any[]> {
  const resp = await fetch(`/api/?query=${encodeURIComponent(sql)}&default_format=JSON`);
  if (!resp.ok) throw new Error(`clickhouse ${resp.status}`);
  const json = await resp.json();
  return json.data ?? [];
}

function windowBounds() {
  const now = Date.now();
  const fmt = (ms: number) => new Date(ms).toISOString().slice(0, 19).replace("T", " ");
  return {
    curStart: fmt(now - WINDOW.cur * 60000),
    now: fmt(now),
    baseStart: fmt(now - (WINDOW.off + WINDOW.base) * 60000),
    baseEnd: fmt(now - WINDOW.off * 60000),
  };
}

function distRows(cur: any[], base: any[]): DistRow[] {
  const bins = 24;
  const c = new Array(bins).fill(0);
  const b = new Array(bins).fill(0);
  for (const r of cur) {
    let i = Math.floor(Number(r.v) * bins);
    if (i >= bins) i = bins - 1;
    if (i < 0) i = 0;
    c[i]++;
  }
  for (const r of base) {
    let i = Math.floor(Number(r.v) * bins);
    if (i >= bins) i = bins - 1;
    if (i < 0) i = 0;
    b[i]++;
  }
  return Array.from({ length: bins }, (_, i) => ({
    label: ((i + 0.5) / bins).toFixed(2), current: c[i], baseline: b[i],
  }));
}

async function fetchDashboardData(): Promise<DashData> {
  const w = windowBounds();
  const [evR, evPrevR, pR, pPrevR, scanR, signalsR, trafficR, latencyR, eventsR,
         predCur, predBase, confCur, confBase] = await Promise.all([
    ch("SELECT count() AS c FROM vera.events WHERE timestamp >= now() - INTERVAL 60 MINUTE"),
    ch("SELECT count() AS c FROM vera.events WHERE timestamp >= now() - INTERVAL 120 MINUTE AND timestamp < now() - INTERVAL 60 MINUTE"),
    ch("SELECT quantile(0.5)(latency_ms) AS p50, quantile(0.99)(latency_ms) AS p99 FROM vera.events WHERE timestamp >= now() - INTERVAL 60 MINUTE"),
    ch("SELECT quantile(0.5)(latency_ms) AS p50, quantile(0.99)(latency_ms) AS p99 FROM vera.events WHERE timestamp >= now() - INTERVAL 120 MINUTE AND timestamp < now() - INTERVAL 60 MINUTE"),
    ch("SELECT max(timestamp) AS t FROM vera.drift_results"),
    ch("SELECT metric, score, threshold, drifted FROM vera.drift_results WHERE scan_id = (SELECT scan_id FROM vera.drift_results ORDER BY timestamp DESC LIMIT 1)"),
    ch("SELECT toStartOfMinute(timestamp) AS t, count() AS n FROM vera.events WHERE timestamp >= now() - INTERVAL 15 MINUTE GROUP BY t ORDER BY t"),
    ch("SELECT toStartOfMinute(timestamp) AS t, quantile(0.5)(latency_ms) AS p50, quantile(0.99)(latency_ms) AS p99 FROM vera.events WHERE timestamp >= now() - INTERVAL 15 MINUTE GROUP BY t ORDER BY t"),
    ch("SELECT timestamp AS t, metric FROM vera.drift_results WHERE drifted = 1 ORDER BY timestamp DESC LIMIT 8"),
    ch(`SELECT toFloat64OrNull(prediction) AS v FROM vera.events WHERE timestamp >= '${w.curStart}' AND timestamp < '${w.now}' AND toFloat64OrNull(prediction) IS NOT NULL LIMIT 3000`),
    ch(`SELECT toFloat64OrNull(prediction) AS v FROM vera.events WHERE timestamp >= '${w.baseStart}' AND timestamp < '${w.baseEnd}' AND toFloat64OrNull(prediction) IS NOT NULL LIMIT 3000`),
    ch(`SELECT confidence AS v FROM vera.events WHERE timestamp >= '${w.curStart}' AND timestamp < '${w.now}' AND confidence IS NOT NULL LIMIT 3000`),
    ch(`SELECT confidence AS v FROM vera.events WHERE timestamp >= '${w.baseStart}' AND timestamp < '${w.baseEnd}' AND confidence IS NOT NULL LIMIT 3000`),
  ]);
  const hhmm = (t: string) => fmtLocal(t, false).slice(11, 16);
  return {
    ev: Number(evR[0]?.c ?? 0),
    evPrev: Number(evPrevR[0]?.c ?? 0),
    p50: Number(pR[0]?.p50 ?? 0),
    p99: Number(pR[0]?.p99 ?? 0),
    p50Prev: Number(pPrevR[0]?.p50 ?? 0),
    p99Prev: Number(pPrevR[0]?.p99 ?? 0),
    scanTs: scanR.length ? fmtLocal(String(scanR[0].t)) : null,
    signals: signalsR.map((r) => ({
      metric: String(r.metric),
      score: Number(r.score),
      threshold: Number(r.threshold),
      drifted: Boolean(r.drifted),
    })),
    traffic: trafficR.map((r) => ({ t: hhmm(String(r.t)), n: Number(r.n) })),
    latency: latencyR.map((r) => ({ t: hhmm(String(r.t)), p50: Number(r.p50), p99: Number(r.p99) })),
    driftEvents: eventsR.map((r) => ({ time: fmtLocal(String(r.t)).slice(11, 19), metric: String(r.metric) })),
    distPred: distRows(predCur, predBase),
    distConf: distRows(confCur, confBase),
  };
}

function useDashboardData(intervalMs: number): DashData | null {
  const [data, setData] = useState<DashData | null>(null);
  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const d = await fetchDashboardData();
        if (alive) setData(d);
      } catch {
        /* 保留上次数据，下轮重试 */
      }
    };
    load();
    const id = setInterval(load, intervalMs);
    return () => { alive = false; clearInterval(id); };
  }, [intervalMs]);
  return data;
}

/* ── 小组件 ────────────────────────────────────────────── */
function GlassCard({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-[14px] border border-white/[0.06] bg-white/[0.03] p-5 shadow-glass backdrop-blur-[12px] transition-colors duration-300 hover:border-white/[0.12] ${className}`}>
      {children}
    </div>
  );
}

function Help({ text }: { text: string }) {
  return (
    <span className="group relative inline-flex">
      <span className="cursor-help text-xs text-slate-500 transition-colors group-hover:text-slate-300">ⓘ</span>
      <span className="pointer-events-none absolute right-0 top-5 z-50 w-64 rounded-lg border border-white/10 bg-[#131520]/95 px-3 py-2 text-xs leading-relaxed text-slate-300 opacity-0 shadow-xl backdrop-blur transition-opacity duration-150 group-hover:opacity-100">
        {text}
      </span>
    </span>
  );
}

function PanelTitle({ title, help, right }: { title: string; help?: string; right?: ReactNode }) {
  return (
    <div className="mb-3 flex items-center justify-between gap-2">
      <span className="text-sm font-semibold tracking-wide text-slate-100">{title}</span>
      <span className="flex items-center gap-3">
        {right}
        {help && <Help text={help} />}
      </span>
    </div>
  );
}

function MetricCard({ icon, value, label, delta, deltaColor, badge }: {
  icon: string; value: string; label: string; delta?: string;
  deltaColor?: string; badge?: boolean;
}) {
  return (
    <div className="relative flex flex-col rounded-xl border border-white/[0.05] bg-white/[0.02] p-4">
      <div className="flex items-center justify-between">
        <span className="font-mono text-[0.68rem] font-semibold uppercase tracking-widest text-slate-400">{icon}</span>
        <span className="text-[0.68rem] uppercase tracking-wider text-slate-500">{label}</span>
        {badge && <span className="h-2 w-2 rounded-full bg-vera-red shadow-[0_0_8px_rgba(239,68,68,0.6)]" />}
      </div>
      <div className="my-2.5 font-mono text-4xl font-bold leading-none text-white">{value}</div>
      {delta && (
        <span className="self-start rounded-full px-2 py-0.5 font-mono text-xs font-semibold"
          style={{ background: `${deltaColor ?? "#94a3b8"}22`, color: deltaColor ?? "#94a3b8" }}>{delta}</span>
      )}
    </div>
  );
}

function SignalRow({ sig, t }: { sig: Signal; t: (k: string) => string }) {
  const pct = Math.min((sig.score / Math.max(sig.threshold, 1e-9)) * 100, 100);
  const width = Math.max(pct, 2);
  const barColor = sig.drifted ? RED : GREEN;
  return (
    <div className="rounded-xl border border-white/[0.05] bg-white/[0.02] px-4 py-3.5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className={`h-2 w-2 rounded-full ${sig.drifted ? "bg-vera-red shadow-[0_0_8px_rgba(239,68,68,0.5)]" : "bg-vera-green shadow-[0_0_8px_rgba(16,185,129,0.5)]"}`} />
          <span className="text-sm font-semibold text-slate-100">{sig.metric}</span>
        </div>
        <span className={`rounded-full px-2.5 py-0.5 text-[0.65rem] font-semibold ${sig.drifted ? "bg-vera-red/15 text-vera-red" : "bg-vera-green/15 text-vera-green"}`}>
          {sig.drifted ? t("drift") : t("normal")}
        </span>
      </div>
      <div className="mt-3 font-mono text-3xl font-bold leading-none text-white">{sig.score.toFixed(4)}</div>
      <div className="mt-1.5 text-xs text-slate-500">{t("threshold")} {sig.threshold}</div>
      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
        <div className="h-full rounded-full transition-all duration-500" style={{ width: `${width}%`, background: barColor }} />
      </div>
    </div>
  );
}

function Clock({ lang }: { lang: "zh" | "en" }) {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  const week = lang === "zh" ? `周${WEEK_ZH[now.getDay()]}` : WEEK_EN[now.getDay()];
  return (
    <div className="text-right leading-tight">
      <div className="font-mono text-xs text-slate-400">
        {now.getFullYear()}-{p2(now.getMonth() + 1)}-{p2(now.getDate())} {week}
      </div>
      <div className="font-mono text-xl text-slate-100">
        {p2(now.getHours())}:{p2(now.getMinutes())}:{p2(now.getSeconds())}
      </div>
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-2.5 text-slate-600">
      <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M3 3v18h18" />
        <path d="M7 15l3-4 3 2 4-6" />
        <line x1="4" y1="20" x2="20" y2="4" strokeDasharray="2 3" />
      </svg>
      <span className="text-sm">{text}</span>
    </div>
  );
}

/* ── 图表组件 ──────────────────────────────────────────── */
function TrafficChart({ data }: { data: DashData["traffic"] }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={data} margin={{ top: 8, right: 8, left: -14, bottom: 0 }}>
        <defs>
          <linearGradient id="gradLine" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor={PURPLE} />
            <stop offset="100%" stopColor={CYAN} />
          </linearGradient>
          <linearGradient id="gradFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={PURPLE} stopOpacity={0.3} />
            <stop offset="100%" stopColor={PURPLE} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke="rgba(255,255,255,0.04)" vertical={false} />
        <XAxis dataKey="t" tick={TICK} axisLine={false} tickLine={false} minTickGap={40} />
        <YAxis tick={TICK} axisLine={false} tickLine={false} width={46} />
        <Tooltip contentStyle={TOOLTIP_STYLE} />
        <Area type="monotone" dataKey="n" stroke="url(#gradLine)" strokeWidth={2.5} fill="url(#gradFill)" />
      </AreaChart>
    </ResponsiveContainer>
  );
}

function LatencyChart({ data }: { data: DashData["latency"] }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={data} margin={{ top: 8, right: 8, left: -14, bottom: 0 }}>
        <CartesianGrid stroke="rgba(255,255,255,0.04)" vertical={false} />
        <XAxis dataKey="t" tick={TICK} axisLine={false} tickLine={false} minTickGap={40} />
        <YAxis domain={["dataMin - 0.1", "dataMax + 0.1"]} tick={TICK} axisLine={false} tickLine={false} width={46} />
        <Tooltip contentStyle={TOOLTIP_STYLE} />
        <Line type="monotone" dataKey="p50" stroke={PURPLE} strokeWidth={2.5} dot={false} />
        <Line type="monotone" dataKey="p99" stroke={GRAY_LINE} strokeWidth={2} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}

function DistChart({ rows, t }: { rows: DistRow[]; t: (k: string) => string }) {
  if (!rows || rows.every((r) => r.current === 0 && r.baseline === 0)) {
    return <EmptyState text={t("noData")} />;
  }
  const legend = (
    <span className="flex items-center gap-3 text-[0.7rem] text-slate-400">
      <span className="flex items-center gap-1.5"><span className="h-1 w-4 rounded" style={{ background: PURPLE }} />{t("currentWin")}</span>
      <span className="flex items-center gap-1.5"><span className="h-1 w-4 rounded" style={{ background: GRAY_BAR }} />{t("baselineWin")}</span>
    </span>
  );
  return (
    <>
      <div className="mb-1 flex justify-end">{legend}</div>
      <div className="h-[calc(100%-2.2rem)]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} margin={{ top: 4, right: 4, left: -18, bottom: 0 }}>
            <CartesianGrid stroke="rgba(255,255,255,0.04)" vertical={false} />
            <XAxis dataKey="label" tick={TICK} axisLine={false} tickLine={false} minTickGap={50} />
            <YAxis tick={TICK} axisLine={false} tickLine={false} width={40} />
            <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ fill: "rgba(255,255,255,0.03)" }} />
            <Bar dataKey="current" fill={PURPLE} fillOpacity={0.65} maxBarSize={14} />
            <Bar dataKey="baseline" fill={GRAY_BAR} fillOpacity={0.7} maxBarSize={14} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </>
  );
}

/* ── 三列主体 ──────────────────────────────────────────── */
function LeftColumn({ t, data }: { t: (k: string) => string; data: DashData }) {
  const nDrifted = data.signals.filter((s) => s.drifted).length;
  const fmtDelta = (cur: number, prev: number, digits: number) =>
    prev > 0 ? `${cur - prev >= 0 ? "+" : ""}${(cur - prev).toFixed(digits)}` : "—";
  const deltaColor = (cur: number, prev: number) =>
    prev > 0 ? (cur - prev > 0 ? RED : GREEN) : "#94a3b8";
  const evDelta = data.evPrev > 0
    ? `${data.ev - data.evPrev >= 0 ? "+" : ""}${(data.ev - data.evPrev).toLocaleString()}`
    : "—";
  const metrics = [
    { icon: "events", value: data.ev.toLocaleString(), label: t("metricEvents"), delta: evDelta, deltaColor: data.ev >= data.evPrev ? GREEN : RED },
    { icon: "p50", value: `${data.p50.toFixed(1)} ms`, label: t("metricP50"), delta: fmtDelta(data.p50, data.p50Prev, 1), deltaColor: deltaColor(data.p50, data.p50Prev) },
    { icon: "p99", value: `${data.p99.toFixed(1)} ms`, label: t("metricP99"), delta: fmtDelta(data.p99, data.p99Prev, 1), deltaColor: deltaColor(data.p99, data.p99Prev) },
    { icon: "drift", value: String(nDrifted), label: t("metricDrift"), badge: nDrifted > 0 },
  ];
  return (
    <div className="flex min-h-0 flex-col gap-5">
      <GlassCard>
        <PanelTitle title={t("overview")} help={t("helpOverview")} />
        <div className="grid grid-cols-2 gap-4">
          {metrics.map((m) => (
            <MetricCard key={m.label} {...m} />
          ))}
        </div>
      </GlassCard>
      <GlassCard className="min-h-0 flex-1">
        <PanelTitle title={t("signalAnalysis")} help={t("helpSignals")} />
        <div className="flex h-[calc(100%-2rem)] flex-col justify-between gap-3">
          {data.signals.length ? (
            data.signals.map((s) => <SignalRow key={s.metric} sig={s} t={t} />)
          ) : (
            <EmptyState text={t("waitScan")} />
          )}
        </div>
      </GlassCard>
    </div>
  );
}

function MiddleColumn({ t, data }: { t: (k: string) => string; data: DashData }) {
  return (
    <div className="grid min-h-0 grid-rows-[3fr_2fr] gap-5">
      <GlassCard className="min-h-0">
        <PanelTitle title={t("trafficTrend")} help={t("helpTraffic")} />
        <div className="h-[calc(100%-2rem)]">
          {data.traffic.length ? <TrafficChart data={data.traffic} /> : <EmptyState text={t("noData")} />}
        </div>
      </GlassCard>
      <div className="grid min-h-0 grid-cols-2 gap-5">
        <GlassCard className="min-h-0">
          <PanelTitle title={t("distPred")} help={t("helpDistPred")} />
          <div className="h-[calc(100%-2rem)]"><DistChart rows={data.distPred} t={t} /></div>
        </GlassCard>
        <GlassCard className="min-h-0">
          <PanelTitle title={t("distConf")} help={t("helpDistConf")} />
          <div className="h-[calc(100%-2rem)]"><DistChart rows={data.distConf} t={t} /></div>
        </GlassCard>
      </div>
    </div>
  );
}

function RightColumn({ t, data }: { t: (k: string) => string; data: DashData }) {
  return (
    <div className="grid min-h-0 grid-rows-[3fr_2fr] gap-5">
      <GlassCard className="min-h-0">
        <PanelTitle
          title={t("latencyTrend")}
          help={t("helpLatency")}
          right={
            <span className="flex items-center gap-3 text-[0.7rem] text-slate-400">
              <span className="flex items-center gap-1.5"><span className="h-1 w-4 rounded" style={{ background: PURPLE }} />P50</span>
              <span className="flex items-center gap-1.5"><span className="h-1 w-4 rounded" style={{ background: GRAY_LINE }} />P99</span>
            </span>
          }
        />
        <div className="h-[calc(100%-2rem)]">
          {data.latency.length ? <LatencyChart data={data.latency} /> : <EmptyState text={t("noData")} />}
        </div>
      </GlassCard>
      <GlassCard className="min-h-0 flex flex-col">
        <PanelTitle title={t("abnormalEvents")} help={t("helpEvents")} />
        <div className="min-h-0 flex-1 overflow-y-auto">
          {data.driftEvents.length ? (
            data.driftEvents.map((ev) => (
              <div key={ev.time + ev.metric} className="mb-2 flex items-center justify-between rounded-lg border border-white/[0.05] bg-white/[0.02] px-3.5 py-2.5">
                <div className="flex items-center gap-3">
                  <span className="font-mono text-xs text-slate-400">{ev.time}</span>
                  <span className="text-xs text-slate-200">{ev.metric}</span>
                </div>
                <span className="rounded-full bg-vera-red/15 px-2 py-0.5 text-[0.65rem] font-semibold text-vera-red">
                  {t("drift")}
                </span>
              </div>
            ))
          ) : (
            <div className="flex h-full items-center justify-center text-sm text-slate-600">{t("noEvents")}</div>
          )}
        </div>
        <button className="mt-2 self-end text-xs text-slate-500 transition-colors hover:text-slate-300">
          {t("viewAll")} →
        </button>
      </GlassCard>
    </div>
  );
}

/* ── 顶栏 ──────────────────────────────────────────────── */
function LangToggle({ lang, setLang }: { lang: string; setLang: (v: "zh" | "en") => void }) {
  const btn = (label: string, value: "zh" | "en") => (
    <button
      key={label}
      onClick={() => setLang(value)}
      className={`rounded-md px-2.5 py-1 text-xs transition-colors ${
        lang === value ? "bg-violet-500/20 text-violet-200" : "text-slate-500 hover:text-slate-300"
      }`}
    >
      {label}
    </button>
  );
  return (
    <div className="flex items-center rounded-lg border border-white/10 bg-white/[0.03] p-0.5">
      {btn("中文", "zh")}
      {btn("EN", "en")}
    </div>
  );
}

function TopBar({ t, lang, setLang, data }: {
  t: (k: string) => string; lang: string; setLang: (v: "zh" | "en") => void; data: DashData;
}) {
  const nDrifted = data.signals.filter((s) => s.drifted).length;
  let banner: ReactNode;
  if (!data.scanTs) {
    banner = (
      <div className="flex items-center gap-4 rounded-2xl border border-white/10 bg-white/[0.03] px-8 py-2.5">
        <span className="h-2.5 w-2.5 rounded-full bg-slate-500" />
        <span className="text-sm text-slate-300">{t("waitScan")}</span>
      </div>
    );
  } else if (nDrifted > 0) {
    banner = (
      <div className="flex items-center gap-4 rounded-2xl border border-vera-red/30 bg-gradient-to-r from-vera-red/15 via-vera-red/10 to-vera-red/15 px-8 py-2.5 shadow-glowRed">
        <span className="relative flex h-2.5 w-2.5">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-vera-red opacity-60" />
          <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-vera-red" />
        </span>
        <div className="text-left leading-tight">
          <div className="text-lg font-bold text-white">{t("statusDrift")}</div>
          <div className="text-xs text-red-200/80">
            {t("statusDriftSub").replace("{n}", String(nDrifted))} · {t("scanAt")} {data.scanTs}
          </div>
        </div>
      </div>
    );
  } else {
    banner = (
      <div className="flex items-center gap-4 rounded-2xl border border-vera-green/30 bg-gradient-to-r from-vera-green/10 via-vera-green/[0.06] to-vera-green/10 px-8 py-2.5">
        <span className="relative flex h-2.5 w-2.5">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-vera-green opacity-50" />
          <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-vera-green" />
        </span>
        <div className="text-left leading-tight">
          <div className="text-lg font-bold text-white">{t("statusOk")}</div>
          <div className="text-xs text-emerald-200/80">
            {t("statusOkSub")} · {t("scanAt")} {data.scanTs}
          </div>
        </div>
      </div>
    );
  }

  return (
    <header className="z-10 flex h-[8%] min-h-[64px] items-center gap-6 px-6">
      <div className="flex w-[26%] items-center gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-cyan-400 text-lg font-bold text-white shadow-[0_0_20px_rgba(139,92,246,0.4)]">
          V
        </div>
        <span className="truncate text-lg font-bold tracking-wide text-white">{t("title")}</span>
      </div>
      <div className="flex flex-1 justify-center">{banner}</div>
      <div className="flex w-[26%] items-center justify-end gap-4">
        <Clock lang={lang} />
        <LangToggle lang={lang} setLang={setLang} />
      </div>
    </header>
  );
}

/* ── 主组件 ────────────────────────────────────────────── */
function App() {
  const [lang, setLang] = useState<"zh" | "en">("zh");
  const data = useDashboardData(POLL_MS);
  const t = (k: string) => I18N[lang][k] ?? k;

  if (!data) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-vera-bg">
        <div className="flex flex-col items-center gap-4">
          <div className="flex h-12 w-12 animate-pulse items-center justify-center rounded-2xl bg-gradient-to-br from-violet-500 to-cyan-400 text-lg font-bold text-white">
            V
          </div>
          <span className="text-sm text-slate-500">{t("connecting")}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="relative flex h-screen w-screen flex-col overflow-hidden bg-vera-bg font-sans text-slate-200 antialiased">
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -left-40 -top-40 h-96 w-96 rounded-full bg-violet-600/10 blur-3xl" />
        <div className="absolute -right-40 -top-40 h-96 w-96 rounded-full bg-cyan-500/10 blur-3xl" />
        <div className="absolute -bottom-40 -left-40 h-96 w-96 rounded-full bg-cyan-500/[0.07] blur-3xl" />
        <div className="absolute -bottom-40 -right-40 h-96 w-96 rounded-full bg-violet-600/[0.08] blur-3xl" />
      </div>

      <TopBar t={t} lang={lang} setLang={setLang} data={data} />

      <main className="z-10 grid min-h-0 flex-1 grid-cols-[3fr_4fr_3fr] gap-5 px-6 pb-6">
        <LeftColumn t={t} data={data} />
        <MiddleColumn t={t} data={data} />
        <RightColumn t={t} data={data} />
      </main>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
