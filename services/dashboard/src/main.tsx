/**
 * Vera AI 可观测性大屏 — 单文件实现
 * 技术栈: React 18 + TypeScript + Tailwind v3 + Recharts
 * 布局: 顶部通栏 8% + 三列主体 3:4:3，1920×1080 全屏无滚动
 * 数据: 快照（见 docs/仪表盘要求.txt），后续可换成实时 API
 */
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import {
  Area, AreaChart, CartesianGrid, Line, LineChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";

/* ── 主题常量 ─────────────────────────────────────────── */
const PURPLE = "#8b5cf6";
const CYAN = "#06b6d4";
const RED = "#ef4444";
const GREEN = "#10b981";
const GRAY_LINE = "#cbd5e1";
const TICK = { fill: "#64748b", fontSize: 11 };
const TOOLTIP_STYLE = {
  background: "rgba(17,19,24,0.95)",
  border: "1px solid rgba(255,255,255,0.1)",
  borderRadius: 10,
  fontSize: 12,
  color: "#e2e8f0",
};

/* ── I18N（保留原仪表盘的中英切换功能） ────────────────── */
const I18N: Record<string, Record<string, string>> = {
  zh: {
    title: "Vera AI 可观测性与漂移检测平台",
    alertTitle: "检测到漂移",
    alertSub: "1个信号行为异常 · 最近扫描 2026-08-06 12:53:00 UTC",
    overview: "系统概览",
    signalAnalysis: "信号漂移分析",
    trafficTrend: "请求量趋势",
    distPred: "预测值分布",
    distConf: "置信度分布",
    latencyTrend: "响应延迟趋势",
    abnormalEvents: "异常事件详情",
    viewAll: "查看全部",
    noData: "暂无数据",
    drift: "漂移",
    normal: "正常",
    threshold: "threshold",
    metricEvents: "事件量",
    metricP50: "P50延迟",
    metricP99: "P99延迟",
    metricDrift: "漂移信号",
    helpOverview: "事件量=模型最近一小时处理的请求数；P50/P99=一半/99% 的请求在多长时间内完成；漂移信号=当前有几个行为异常。",
    helpSignals: "系统定期对比模型最近行为和基准行为：绿点=正常；红点=行为偏移超过阈值，会触发告警。",
    helpTraffic: "每分钟模型请求数。陡升陡降可能意味着流量异常或系统故障。",
    helpDistPred: "模型预测值的分布。当前窗口与基准明显错开即视为行为改变。",
    helpDistConf: "模型置信度分布。突然变得过于自信或犹豫也是异常信号。",
    helpLatency: "P50=一半请求在此时间内完成，P99=99% 的请求在此时间内完成。P99 升高说明系统在变慢。",
    helpEvents: "最近触发的漂移事件。",
  },
  en: {
    title: "Vera AI Observability & Drift Detection",
    alertTitle: "Drift Detected",
    alertSub: "1 signal behaving abnormally · Last scan 2026-08-06 12:53:00 UTC",
    overview: "Overview",
    signalAnalysis: "Signal Drift Analysis",
    trafficTrend: "Traffic Trend",
    distPred: "Prediction Distribution",
    distConf: "Confidence Distribution",
    latencyTrend: "Latency Trend",
    abnormalEvents: "Drift Events",
    viewAll: "View all",
    noData: "No data yet",
    drift: "Drifted",
    normal: "Normal",
    threshold: "threshold",
    metricEvents: "Events",
    metricP50: "P50 Latency",
    metricP99: "P99 Latency",
    metricDrift: "Drifted",
    helpOverview: "Events = requests handled in the last hour; P50/P99 = response speed; Drifted = abnormal signals found.",
    helpSignals: "The system compares recent model behavior against a baseline. Red = behavior shifted beyond threshold, alert fired.",
    helpTraffic: "Requests per minute. Sharp spikes or drops may indicate unusual load or faults.",
    helpDistPred: "Model prediction distribution. Clear separation from baseline means behavior change.",
    helpDistConf: "Model confidence distribution. Sudden over-confidence or hesitation is a warning sign.",
    helpLatency: "P50 = half of requests complete within this time; P99 = 99% do. A rising P99 means the system is slowing.",
    helpEvents: "Recently fired drift events.",
  },
};

/* ── 快照数据（与 2026-08-06 12:53 演示环境一致） ──────── */
const TRAFFIC = [
  { t: "12:47:00", n: 180 },
  { t: "12:47:30", n: 420 },
  { t: "12:48:00", n: 760 },
  { t: "12:48:30", n: 980 },
  { t: "12:49:00", n: 1120 },
  { t: "12:49:30", n: 1145 },
  { t: "12:50:00", n: 1130 },
  { t: "12:50:30", n: 960 },
  { t: "12:51:00", n: 420 },
];
const LATENCY = [
  { t: "12:47:00", p50: 1.2, p99: 1.9 },
  { t: "12:47:30", p50: 1.19, p99: 1.84 },
  { t: "12:48:00", p50: 1.2, p99: 1.72 },
  { t: "12:48:30", p50: 1.21, p99: 1.63 },
  { t: "12:49:00", p50: 1.2, p99: 1.57 },
  { t: "12:49:30", p50: 1.19, p99: 1.54 },
  { t: "12:50:00", p50: 1.2, p99: 1.58 },
  { t: "12:50:30", p50: 1.2, p99: 1.64 },
  { t: "12:51:00", p50: 1.21, p99: 1.68 },
];
type Signal = { name: string; score: string; threshold: string; drifted: boolean };
const SIGNALS: Signal[] = [
  { name: "latency_ms", score: "0.0001", threshold: "0.05", drifted: true },
  { name: "confidence", score: "0.1093", threshold: "0.05", drifted: false },
  { name: "prediction", score: "0.0362", threshold: "0.1", drifted: false },
];
const EVENTS = [{ time: "12:53:00", signal: "latency_ms", drifted: true }];

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
      <div className="mb-1.5 flex items-center justify-between">
        <span className="text-base opacity-80">{icon}</span>
        {badge && <span className="h-2 w-2 rounded-full bg-vera-red shadow-[0_0_8px_rgba(239,68,68,0.6)]" />}
      </div>
      <div className="font-mono text-4xl font-bold leading-none text-white">{value}</div>
      <div className="mt-2 text-[0.68rem] uppercase tracking-wider text-slate-500">{label}</div>
      {delta && <div className="mt-1 font-mono text-xs font-medium" style={{ color: deltaColor ?? "#94a3b8" }}>{delta}</div>}
    </div>
  );
}

function SignalRow({ sig, t }: { sig: Signal; t: (k: string) => string }) {
  const pct = Math.min((parseFloat(sig.score) / parseFloat(sig.threshold)) * 100, 100);
  const width = Math.max(pct, 2);
  const barColor = sig.drifted ? RED : GREEN;
  return (
    <div className="rounded-xl border border-white/[0.05] bg-white/[0.02] px-4 py-3.5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className={`h-2 w-2 rounded-full ${sig.drifted ? "bg-vera-red shadow-[0_0_8px_rgba(239,68,68,0.5)]" : "bg-vera-green shadow-[0_0_8px_rgba(16,185,129,0.5)]"}`} />
          <span className="text-sm font-semibold text-slate-100">{sig.name}</span>
        </div>
        <span className={`rounded-full px-2.5 py-0.5 text-[0.65rem] font-semibold ${sig.drifted ? "bg-vera-red/15 text-vera-red" : "bg-vera-green/15 text-vera-green"}`}>
          {sig.drifted ? t("drift") : t("normal")}
        </span>
      </div>
      <div className="mt-3 font-mono text-3xl font-bold leading-none text-white">{sig.score}</div>
      <div className="mt-1.5 text-xs text-slate-500">{t("threshold")} {sig.threshold}</div>
      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
        <div className="h-full rounded-full transition-all duration-500" style={{ width: `${width}%`, background: barColor }} />
      </div>
    </div>
  );
}

function Clock() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  const p = (n: number) => String(n).padStart(2, "0");
  return (
    <span className="font-mono text-xl text-slate-100">
      {p(now.getHours())}:{p(now.getMinutes())}:{p(now.getSeconds())}
    </span>
  );
}

function EmptyState({ t }: { t: (k: string) => string }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-2.5 text-slate-600">
      <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M3 3v18h18" />
        <path d="M7 15l3-4 3 2 4-6" />
        <line x1="4" y1="20" x2="20" y2="4" strokeDasharray="2 3" />
      </svg>
      <span className="text-sm">{t("noData")}</span>
    </div>
  );
}

/* ── 三列主体 ──────────────────────────────────────────── */
function LeftColumn({ t }: { t: (k: string) => string }) {
  const metrics = [
    { icon: "📨", value: "5,687", label: t("metricEvents"), delta: "+5,687", deltaColor: RED },
    { icon: "⚡", value: "1.2 ms", label: t("metricP50") },
    { icon: "🎯", value: "1.8 ms", label: t("metricP99") },
    { icon: "🔍", value: "1", label: t("metricDrift"), badge: true },
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
          {SIGNALS.map((s) => (
            <SignalRow key={s.name} sig={s} t={t} />
          ))}
        </div>
      </GlassCard>
    </div>
  );
}

function TrafficChart() {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={TRAFFIC} margin={{ top: 8, right: 8, left: -14, bottom: 0 }}>
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
        <XAxis dataKey="t" tick={TICK} axisLine={false} tickLine={false} />
        <YAxis domain={[0, 1200]} tickCount={5} tick={TICK} axisLine={false} tickLine={false} width={46} />
        <Tooltip contentStyle={TOOLTIP_STYLE} />
        <Area type="monotone" dataKey="n" stroke="url(#gradLine)" strokeWidth={2.5} fill="url(#gradFill)" />
      </AreaChart>
    </ResponsiveContainer>
  );
}

function LatencyChart() {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={LATENCY} margin={{ top: 8, right: 8, left: -14, bottom: 0 }}>
        <CartesianGrid stroke="rgba(255,255,255,0.04)" vertical={false} />
        <XAxis dataKey="t" tick={TICK} axisLine={false} tickLine={false} />
        <YAxis domain={[1.2, 1.9]} tickCount={5} tick={TICK} axisLine={false} tickLine={false} width={46} />
        <Tooltip contentStyle={TOOLTIP_STYLE} />
        <Line type="monotone" dataKey="p50" stroke={PURPLE} strokeWidth={2.5} dot={false} />
        <Line type="monotone" dataKey="p99" stroke={GRAY_LINE} strokeWidth={2} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}

function MiddleColumn({ t }: { t: (k: string) => string }) {
  return (
    <div className="grid min-h-0 grid-rows-[3fr_2fr] gap-5">
      <GlassCard className="min-h-0">
        <PanelTitle title={t("trafficTrend")} help={t("helpTraffic")} />
        <div className="h-[calc(100%-2rem)]">
          <TrafficChart />
        </div>
      </GlassCard>
      <div className="grid min-h-0 grid-cols-2 gap-5">
        <GlassCard className="min-h-0"><PanelTitle title={t("distPred")} help={t("helpDistPred")} /><EmptyState t={t} /></GlassCard>
        <GlassCard className="min-h-0"><PanelTitle title={t("distConf")} help={t("helpDistConf")} /><EmptyState t={t} /></GlassCard>
      </div>
    </div>
  );
}

function RightColumn({ t }: { t: (k: string) => string }) {
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
          <LatencyChart />
        </div>
      </GlassCard>
      <GlassCard className="min-h-0 flex flex-col">
        <PanelTitle title={t("abnormalEvents")} help={t("helpEvents")} />
        <div className="min-h-0 flex-1 overflow-y-auto">
          {EVENTS.map((ev) => (
            <div key={ev.time} className="mb-2 flex items-center justify-between rounded-lg border border-white/[0.05] bg-white/[0.02] px-3.5 py-2.5">
              <div className="flex items-center gap-3">
                <span className="font-mono text-xs text-slate-400">{ev.time}</span>
                <span className="text-xs text-slate-200">{ev.signal}</span>
              </div>
              <span className="rounded-full bg-vera-red/15 px-2 py-0.5 text-[0.65rem] font-semibold text-vera-red">
                {t("drift")}
              </span>
            </div>
          ))}
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

function TopBar({ t, lang, setLang }: { t: (k: string) => string; lang: string; setLang: (v: "zh" | "en") => void }) {
  return (
    <header className="z-10 flex h-[8%] min-h-[64px] items-center gap-6 px-6">
      {/* 左：Logo + 名称 */}
      <div className="flex w-[26%] items-center gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-cyan-400 text-lg font-bold text-white shadow-[0_0_20px_rgba(139,92,246,0.4)]">
          V
        </div>
        <span className="truncate text-lg font-bold tracking-wide text-white">{t("title")}</span>
      </div>

      {/* 中：告警横幅 */}
      <div className="flex flex-1 justify-center">
        <div className="flex items-center gap-4 rounded-2xl border border-vera-red/30 bg-gradient-to-r from-vera-red/15 via-vera-red/10 to-vera-red/15 px-8 py-2.5 shadow-glowRed">
          <span className="relative flex h-2.5 w-2.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-vera-red opacity-60" />
            <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-vera-red" />
          </span>
          <div className="text-left leading-tight">
            <div className="text-lg font-bold text-white">{t("alertTitle")}</div>
            <div className="text-xs text-red-200/80">{t("alertSub")}</div>
          </div>
        </div>
      </div>

      {/* 右：时钟 + 刷新 + 语言切换 */}
      <div className="flex w-[26%] items-center justify-end gap-4">
        <Clock />
        <svg className="h-4 w-4 animate-[spin_3s_linear_infinite] text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <path d="M21 12a9 9 0 1 1-2.64-6.36" />
          <path d="M21 3v6h-6" />
        </svg>
        <LangToggle lang={lang} setLang={setLang} />
      </div>
    </header>
  );
}

/* ── 主组件 ────────────────────────────────────────────── */
function App() {
  const [lang, setLang] = useState<"zh" | "en">("zh");
  const t = (k: string) => I18N[lang][k] ?? k;

  return (
    <div className="relative flex h-screen w-screen flex-col overflow-hidden bg-vera-bg font-sans text-slate-200 antialiased">
      {/* 四角氛围光晕 */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -left-40 -top-40 h-96 w-96 rounded-full bg-violet-600/10 blur-3xl" />
        <div className="absolute -right-40 -top-40 h-96 w-96 rounded-full bg-cyan-500/10 blur-3xl" />
        <div className="absolute -bottom-40 -left-40 h-96 w-96 rounded-full bg-cyan-500/[0.07] blur-3xl" />
        <div className="absolute -bottom-40 -right-40 h-96 w-96 rounded-full bg-violet-600/[0.08] blur-3xl" />
      </div>

      <TopBar t={t} lang={lang} setLang={setLang} />

      <main className="z-10 grid min-h-0 flex-1 grid-cols-[3fr_4fr_3fr] gap-5 px-6 pb-6">
        <LeftColumn t={t} />
        <MiddleColumn t={t} />
        <RightColumn t={t} />
      </main>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
