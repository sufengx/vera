/**
 * Vera AI可观测性&漂移检测大屏
 * 布局参考 docs/示例.html：左状态卡 / 中请求量大图 / 右指标卡 / 底漂移条
 * 数据: 每 10s 轮询 /api/（nginx 代理 ClickHouse，同源免 CORS），窗口语义与检测器一致
 */
import { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import * as echarts from "echarts";
import "./index.css";

const POLL_MS = 10000;
const WINDOW = { cur: 5, off: 30, base: 30 }; // 分钟，与检测器默认参数一致

/* ── 时间工具：ClickHouse 存 UTC，展示转浏览器本地时区 ── */
const p2 = (n: number) => String(n).padStart(2, "0");
const toLocal = (utc: string) => new Date(utc.length === 19 ? `${utc.replace(" ", "T")}Z` : utc);
const fmtLocal = (utc: string, sec = true) => {
  const d = toLocal(utc);
  return `${d.getFullYear()}-${p2(d.getMonth() + 1)}-${p2(d.getDate())} ${p2(d.getHours())}:${p2(d.getMinutes())}${sec ? `:${p2(d.getSeconds())}` : ""}`;
};
const hhmm = (t: string) => fmtLocal(t, false).slice(11, 16);

/* ── 数据层：轮询 ClickHouse（经 nginx /api/ 代理） ─── */
type Signal = { metric: string; score: number; threshold: number; drifted: boolean };
type DashData = {
  ev: number; evPrev: number;
  p50: number; p99: number;
  scanTs: string | null;
  signals: Signal[];
  traffic: { t: string; n: number }[];
  latency: { t: string; p50: number; p99: number }[];
  distPred: number[]; distConf: number[];
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

function hist(vals: any[], bins: number): number[] {
  const h = new Array(bins).fill(0);
  for (const r of vals) {
    let i = Math.floor(Number(r.v) * bins);
    if (i >= bins) i = bins - 1;
    if (i < 0) i = 0;
    h[i]++;
  }
  return h;
}

async function fetchDashboardData(): Promise<DashData> {
  const w = windowBounds();
  const [evR, evPrevR, pR, scanR, signalsR, trafficR, latencyR, predCur, confCur] = await Promise.all([
    ch("SELECT count() AS c FROM vera.events WHERE timestamp >= now() - INTERVAL 60 MINUTE"),
    ch("SELECT count() AS c FROM vera.events WHERE timestamp >= now() - INTERVAL 120 MINUTE AND timestamp < now() - INTERVAL 60 MINUTE"),
    ch("SELECT quantile(0.5)(latency_ms) AS p50, quantile(0.99)(latency_ms) AS p99 FROM vera.events WHERE timestamp >= now() - INTERVAL 60 MINUTE"),
    ch("SELECT max(timestamp) AS t FROM vera.drift_results"),
    ch("SELECT metric, score, threshold, drifted FROM vera.drift_results WHERE scan_id = (SELECT scan_id FROM vera.drift_results ORDER BY timestamp DESC LIMIT 1)"),
    ch("SELECT toStartOfMinute(timestamp) AS t, count() AS n FROM vera.events WHERE timestamp >= now() - INTERVAL 15 MINUTE GROUP BY t ORDER BY t"),
    ch("SELECT toStartOfMinute(timestamp) AS t, quantile(0.5)(latency_ms) AS p50, quantile(0.99)(latency_ms) AS p99 FROM vera.events WHERE timestamp >= now() - INTERVAL 15 MINUTE GROUP BY t ORDER BY t"),
    ch(`SELECT toFloat64OrNull(prediction) AS v FROM vera.events WHERE timestamp >= '${w.curStart}' AND timestamp < '${w.now}' AND toFloat64OrNull(prediction) IS NOT NULL LIMIT 3000`),
    ch(`SELECT confidence AS v FROM vera.events WHERE timestamp >= '${w.curStart}' AND timestamp < '${w.now}' AND confidence IS NOT NULL LIMIT 3000`),
  ]);
  return {
    ev: Number(evR[0]?.c ?? 0),
    evPrev: Number(evPrevR[0]?.c ?? 0),
    p50: Number(pR[0]?.p50 ?? 0),
    p99: Number(pR[0]?.p99 ?? 0),
    scanTs: scanR.length ? fmtLocal(String(scanR[0].t)) : null,
    signals: signalsR.map((r) => ({
      metric: String(r.metric),
      score: Number(r.score),
      threshold: Number(r.threshold),
      drifted: Boolean(r.drifted),
    })),
    traffic: trafficR.map((r) => ({ t: hhmm(String(r.t)), n: Number(r.n) })),
    latency: latencyR.map((r) => ({ t: hhmm(String(r.t)), p50: Number(r.p50), p99: Number(r.p99) })),
    distPred: hist(predCur, 16),
    distConf: hist(confCur, 16),
  };
}

function useDashboardData(intervalMs: number, rev: number): DashData | null {
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
  }, [intervalMs, rev]);
  return data;
}

/* ── ECharts 封装 ── */
function useEChart(option: echarts.EChartsOption) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current) return;
    const c = echarts.init(ref.current);
    const ro = new ResizeObserver(() => c.resize());
    ro.observe(ref.current);
    return () => { ro.disconnect(); c.dispose(); };
  }, []);
  useEffect(() => {
    echarts.getInstanceByDom(ref.current!)?.setOption(option, true);
  }, [option]);
  return ref;
}

/* ── 左侧状态卡 ── */
type State = "normal" | "warn" | "error";
const STATE_TEXT: Record<State, string> = { normal: "正常", warn: "警告", error: "异常" };

// KS 信号 p 值越小越漂移，风险方向与 PSI 相反；下限 4% 保证条可见
const riskOf = (s?: Signal) => {
  if (!s) return 0;
  const r = s.metric === "prediction" ? s.score / s.threshold : s.threshold / s.score;
  return Math.min(Math.max(r, 0.04), 1);
};
const stateOf = (s?: Signal): State => {
  if (!s) return "normal";
  if (s.drifted) return "error";
  return riskOf(s) >= 0.8 ? "warn" : "normal";
};

function StatusCard({ state, val, label, ratio }: { state: State; val: string; label: string; ratio: number }) {
  const cls = state === "error" ? "bar-red" : state === "warn" ? "bar-orange" : "bar-green";
  return (
    <div className="card-status">
      <span className={`tag ${state}`}>{STATE_TEXT[state]}</span>
      <div className="val">{val}</div>
      <div className="label">{label}</div>
      <div className="mini-bar"><div className={cls} style={{ width: `${Math.min(Math.max(ratio, 0), 1) * 100}%` }} /></div>
    </div>
  );
}

function LeftColumn({ data }: { data: DashData }) {
  const sig = (m: string) => data.signals.find((s) => s.metric === m);
  const lat = sig("latency_ms");
  const pred = sig("prediction");
  const conf = sig("confidence");
  return (
    <div className="left-col">
      <div className="col-label">系统状态</div>
      <StatusCard
        state={data.ev > 0 ? "normal" : "warn"}
        val={data.ev.toLocaleString()}
        label="事件量"
        ratio={data.evPrev > 0 ? data.ev / (data.ev + data.evPrev) : 0.5}
      />
      <StatusCard state={stateOf(lat)} val={lat ? lat.score.toFixed(4) : "—"} label="latency_ms 延迟漂移" ratio={riskOf(lat)} />
      <StatusCard state={stateOf(pred)} val={pred ? pred.score.toFixed(4) : "—"} label="prediction 预测漂移" ratio={riskOf(pred)} />
      <StatusCard state={stateOf(conf)} val={conf ? conf.score.toFixed(4) : "—"} label="confidence 置信度漂移" ratio={riskOf(conf)} />
    </div>
  );
}

/* ── 图表组件 ── */
function MainChart({ traffic }: { traffic: DashData["traffic"] }) {
  const ref = useEChart({
    backgroundColor: "transparent",
    tooltip: {
      trigger: "axis",
      backgroundColor: "rgba(20,20,45,0.92)",
      borderColor: "#555599",
      textStyle: { color: "#e8e8ff", fontSize: 12 },
    },
    grid: { left: "4%", right: "4%", top: "12%", bottom: "14%" },
    xAxis: {
      type: "category",
      data: traffic.map((p) => p.t),
      axisLine: { lineStyle: { color: "#444470" } },
      axisLabel: { color: "#999" },
    },
    yAxis: {
      type: "value",
      splitLine: { lineStyle: { color: "#2c2c50" } },
      axisLabel: { color: "#999" },
    },
    series: [{
      name: "请求量",
      type: "line",
      smooth: true,
      areaStyle: { color: "rgba(142,95,255,0.32)" },
      lineStyle: { color: "#b48aff", width: 2 },
      data: traffic.map((p) => p.n),
    }],
  });
  return <div ref={ref} className="main-chart" />;
}

const MINI_COLORS = ["#72d8ff", "#b888ff", "#ff7898", "#ffbc42"];

function MiniBar({ data }: { data: number[] }) {
  const ref = useEChart({
    backgroundColor: "transparent",
    grid: { left: 0, right: 0, top: 0, bottom: 0 },
    xAxis: { type: "category", show: false, data: data.map((_, i) => i) },
    yAxis: { type: "value", show: false },
    series: [{
      type: "bar",
      barWidth: "45%",
      data,
      itemStyle: { color: (p: any) => MINI_COLORS[p.dataIndex % 4] },
    }],
  });
  return <div ref={ref} className="mini-chart" />;
}

function MiniLine({ lat }: { lat: DashData["latency"] }) {
  const ref = useEChart({
    backgroundColor: "transparent",
    grid: { left: 0, right: 0, top: 0, bottom: 0 },
    xAxis: { type: "category", show: false, data: lat.map((p) => p.t) },
    yAxis: { type: "value", show: false },
    series: [
      {
        type: "line", smooth: true,
        data: lat.map((p) => p.p50),
        lineStyle: { color: "#b48aff" },
        areaStyle: { color: "rgba(142,95,255,0.15)" },
      },
      {
        type: "line", smooth: true,
        data: lat.map((p) => p.p99),
        lineStyle: { color: "#48d8d0" },
        areaStyle: { color: "rgba(72,216,208,0.12)" },
      },
    ],
  });
  return <div ref={ref} className="mini-chart" />;
}

/* ── 底部漂移条 ── */
function BottomBar({ title, detail, state, ratio }: { title: string; detail: string; state: State; ratio: number }) {
  const grad = state === "error"
    ? "linear-gradient(90deg,#ff6699,#ef4444)"
    : state === "warn"
      ? "linear-gradient(90deg,#fb923c,#ff6699)"
      : "linear-gradient(90deg,#4ade80,#32c8dd)";
  return (
    <div className="bottom-bar">
      <div className="fill" style={{ width: `${Math.min(Math.max(ratio, 0), 1) * 100}%`, background: grad }} />
      <div className="bt-label">
        <span>{title}</span>
        <span>{detail}</span>
      </div>
    </div>
  );
}

/* ── 主组件 ── */
function App() {
  const [rev, setRev] = useState(0);
  const data = useDashboardData(POLL_MS, rev);
  const pred = data?.signals.find((s) => s.metric === "prediction");
  const conf = data?.signals.find((s) => s.metric === "confidence");

  return (
    <div className="page">
      <div className="page-title">Vera AI可观测性&漂移检测</div>
      {!data ? (
        <div className="loading">正在连接数据源…</div>
      ) : (
        <>
          <div className="main-wrap">
            <LeftColumn data={data} />
            <div className="center-col">
              <div className="chart-header">
                <h4>关键链分析 <span>请求量</span></h4>
                <button className="btn-refresh" title="刷新" onClick={() => setRev((r) => r + 1)}>↻</button>
              </div>
              <MainChart traffic={data.traffic} />
            </div>
            <div className="right-col">
              <div className="card-metric">
                <h5>性能指标 · P50 延迟</h5>
                <div className="total-num">{data.p50.toFixed(1)} ms</div>
                <MiniLine lat={data.latency} />
              </div>
              <div className="card-metric">
                <h5>任务指标 · 15分钟请求量</h5>
                <div className="total-num">{data.traffic.reduce((s, p) => s + p.n, 0).toLocaleString()}</div>
                <MiniBar data={data.traffic.map((p) => p.n)} />
              </div>
              <div className="card-metric">
                <h5>模型预测 · 当前窗口分布</h5>
                <div className="total-num">{data.distPred.reduce((s, n) => s + n, 0).toLocaleString()}</div>
                <MiniBar data={data.distPred} />
              </div>
              <div className="card-metric">
                <h5>辅助模块 · 置信度分布</h5>
                <div className="total-num">{data.distConf.reduce((s, n) => s + n, 0).toLocaleString()}</div>
                <MiniBar data={data.distConf} />
              </div>
            </div>
          </div>
          <div className="bottom-area">
            <BottomBar
              title="预测漂移 PSI"
              detail={pred ? `${pred.score.toFixed(3)} / 阈值 ${pred.threshold} · 扫描 ${data.scanTs?.slice(11, 16) ?? "—"}` : "等待首轮扫描"}
              state={stateOf(pred)}
              ratio={riskOf(pred)}
            />
            <BottomBar
              title="置信度漂移 KS"
              detail={conf ? `${conf.score.toFixed(3)} / 阈值 ${conf.threshold}` : "等待首轮扫描"}
              state={stateOf(conf)}
              ratio={riskOf(conf)}
            />
          </div>
        </>
      )}
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
