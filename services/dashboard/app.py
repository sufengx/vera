"""Vera — AI 可观测性仪表盘  |  中英双语  |  深色高级主题"""
import os
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import clickhouse_connect
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ── 主题色板 ──────────────────────────────────────────────
ACCENT   = "#8B7CFF"
ACCENT2  = "#A78BFA"
GREEN    = "#10B981"
RED      = "#EF4444"
AMBER    = "#F59E0B"
BLUE     = "#3B82F6"
CYAN     = "#06B6D4"
BG_DEEP  = "#08090D"
BG_CARD  = "#111318"
BORDER   = "rgba(255,255,255,0.06)"
TEXT     = "#E8EAF2"
TEXT2    = "#94A3B8"

# ── 全局 CSS ──────────────────────────────────────────────
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}
.stApp { background: #08090D; }

/* 顶栏降噪 */
[data-testid="stHeader"] { background: rgba(8,9,13,0.85); backdrop-filter: blur(12px); }
header[data-testid="stHeader"] { visibility: hidden; }
.viewerBadge_container__r5tak { display: none; }

/* 侧边栏 */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0C0E14 0%, #08090D 100%);
    border-right: 1px solid rgba(255,255,255,0.05);
}
[data-testid="stSidebar"] .stMarkdown h3 {
    font-size: 1.4rem; font-weight: 700; letter-spacing: -0.02em;
}

/* 区块卡片容器 */
.block-card {
    background: linear-gradient(135deg, rgba(255,255,255,0.025) 0%, rgba(255,255,255,0.01) 100%);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 20px;
    padding: 24px 28px;
    margin-bottom: 18px;
    backdrop-filter: blur(12px);
    transition: border-color 0.3s;
}
.block-card:hover { border-color: rgba(255,255,255,0.1); }

/* 状态横幅 */
.status-banner {
    display: flex; align-items: center; gap: 16px;
    padding: 20px 28px; border-radius: 20px; margin-bottom: 22px;
    border: 1px solid rgba(255,255,255,0.06);
    backdrop-filter: blur(12px);
}
.status-banner.ok  { background: linear-gradient(135deg, rgba(16,185,129,0.08) 0%, rgba(16,185,129,0.02) 100%); }
.status-banner.bad  { background: linear-gradient(135deg, rgba(239,68,68,0.10) 0%, rgba(239,68,68,0.02) 100%); }
.status-dot {
    width: 12px; height: 12px; border-radius: 50%; flex-shrink: 0;
    animation: statusPulse 2s infinite;
}
.status-dot.ok { background: #10B981; box-shadow: 0 0 12px rgba(16,185,129,0.5); }
.status-dot.bad { background: #EF4444; box-shadow: 0 0 12px rgba(239,68,68,0.5); }
@keyframes statusPulse {
    0%, 100% { transform: scale(1);   opacity: 1; }
    50%      { transform: scale(1.3); opacity: 0.7; }
}
.status-text { flex: 1; }
.status-text .title   { font-size: 1.1rem; font-weight: 600; color: #F1F5F9; margin: 0; }
.status-text .sub     { font-size: 0.85rem; color: #94A3B8; margin: 2px 0 0 0; }

/* 指标卡 */
.metrics-row { display: flex; gap: 14px; margin-bottom: 22px; }
.metric-card {
    flex: 1; background: #111318;
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 18px; padding: 20px 22px;
    position: relative; overflow: hidden;
    transition: border-color 0.3s, transform 0.2s;
}
.metric-card:hover { border-color: rgba(255,255,255,0.12); transform: translateY(-1px); }
.metric-card .mc-icon  { font-size: 1.3rem; margin-bottom: 8px; }
.metric-card .mc-value { font-size: 1.8rem; font-weight: 700; color: #F1F5F9; letter-spacing: -0.02em; line-height: 1.2; }
.metric-card .mc-label { font-size: 0.82rem; color: #94A3B8; margin-top: 2px; }
.metric-card .mc-delta  { font-size: 0.8rem; font-weight: 500; margin-top: 4px; }
.metric-card .mc-bar    { position: absolute; left: 0; top: 0; bottom: 0; width: 3px; border-radius: 3px 0 0 3px; }

/* 漂移信号卡片 */
.drift-row { display: flex; gap: 12px; margin-bottom: 18px; }
.drift-sig {
    flex: 1; background: #111318;
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 16px; padding: 18px 20px;
    transition: border-color 0.3s;
}
.drift-sig:hover { border-color: rgba(255,255,255,0.1); }
.drift-sig .ds-head { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
.drift-sig .ds-dot  { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.drift-sig .ds-dot.ok  { background: #10B981; box-shadow: 0 0 8px rgba(16,185,129,0.4); }
.drift-sig .ds-dot.bad { background: #EF4444; box-shadow: 0 0 8px rgba(239,68,68,0.4); }
.drift-sig .ds-name  { font-weight: 600; color: #F1F5F9; }
.drift-sig .ds-badge { margin-left: auto; font-size: 0.72rem; font-weight: 600; padding: 3px 10px; border-radius: 20px; }
.drift-sig .ds-badge.ok  { background: rgba(16,185,129,0.12); color: #10B981; }
.drift-sig .ds-badge.bad { background: rgba(239,68,68,0.12); color: #EF4444; }
.drift-sig .ds-score { font-size: 1.3rem; font-weight: 700; color: #F1F5F9; letter-spacing: -0.02em; }
.drift-sig .ds-thresh { font-size: 0.78rem; color: #94A3B8; margin-top: 2px; }
.drift-sig .ds-bar-bg { height: 3px; background: rgba(255,255,255,0.06); border-radius: 2px; margin-top: 10px; overflow: hidden; }
.drift-sig .ds-bar-fg { height: 100%; border-radius: 2px; transition: width 0.5s ease; }

/* 图表容器 */
.chart-box {
    background: #111318; border: 1px solid rgba(255,255,255,0.05);
    border-radius: 18px; padding: 20px 22px; margin-bottom: 14px;
}

/* panel 标题行 */
.panel-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; }
.panel-row .pl-title { font-size: 1rem; font-weight: 600; color: #F1F5F9; letter-spacing: -0.01em; }
.panel-row .pl-badge { font-size: 0.7rem; color: #64748B; background: rgba(255,255,255,0.04); padding: 2px 10px; border-radius: 10px; }

/* 表格降噪 */
[data-testid="stDataFrame"] { border: 1px solid rgba(255,255,255,0.05); border-radius: 14px; overflow: hidden; }
[data-testid="stDataFrame"] th { background: rgba(255,255,255,0.03) !important; color: #94A3B8 !important; font-weight: 500 !important; font-size: 0.78rem !important; }
[data-testid="stDataFrame"] td { color: #CBD5E1 !important; font-size: 0.8rem !important; }

/* 滚动条 */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.08); border-radius: 3px; }
</style>
"""

# ── I18N ──────────────────────────────────────────────────
I18N = {
    "zh": {
        "title": "Vera",
        "subtitle": "AI 可观测性 & 漂移检测",
        "status_ok": "系统运行正常",
        "status_ok_sub": "所有信号处于正常范围",
        "status_drift": "检测到漂移",
        "status_drift_sub_n": "{} 个信号行为异常",
        "last_scan": "最近扫描",
        "online": "运行中",
        "events_1h": "事件量",
        "p50_1h": "P50 延迟",
        "p99_1h": "P99 延迟",
        "drifted_signals": "漂移信号",
        "drift_status": "信号漂移分析",
        "no_scan": "暂无检测结果，等待检测器首轮扫描…",
        "normal": "正常",
        "drifted": "漂移",
        "traffic": "请求量",
        "latency": "响应延迟",
        "dist_pred": "预测值分布",
        "dist_conf": "置信度分布",
        "current_win": "当前窗口",
        "baseline_win": "基准窗口",
        "recent_events": "最近事件",
        "no_data": "暂无数据",
        "ch_unreachable": "无法连接 ClickHouse",
        "refresh": "每 10 秒自动刷新",
        "utc": "UTC",
        "overview": "系统概览",
        "lang": "语言",
        "sidebar_status": "系统状态",
        "sidebar_events": "事件总量",
        "help_overview": "四个卡片是系统健康速览：事件量 = 最近一小时模型处理了多少次请求；P50/P99 = 一半 / 99% 的请求在多长时间内完成；漂移信号 = 当前发现几个行为异常。右下角小字是相对上一小时的变化。",
        "help_drift": "系统周期性地把模型最近几分钟的行为和更早一段时间的正常行为做统计对比。绿点 = 正常；红点 = 行为显著偏离。分数越大变化越明显，超过阈值就会标红并通过 webhook 发送告警。",
        "help_dist_pred": "模型预测值的概率分布：紫色 = 最近时间段，灰色 = 历史基准。两条曲线明显错开，说明模型输出发生偏移——这是判断模型行为是否改变的核心证据。",
        "help_dist_conf": "和预测值图类似，这里对比的是模型给出的置信度。模型突然变得过于自信或过于犹豫，也可能是异常的早期信号。",
        "help_traffic": "每分钟的模型请求数。陡升或陡降可能意味着流量异常、线上活动或者系统故障。",
        "help_latency": "模型响应耗时：P50 = 一半请求在此时间内完成；P99 = 99% 的请求在此时间内完成。P99 突然升高说明系统在变慢，用户开始感受到卡顿。",
        "help_events": "最近到达的模型请求样本。出于隐私保护，只记录请求的摘要指纹（SHA-256 前 12 位），不保存任何原始数据。",
    },
    "en": {
        "title": "Vera",
        "subtitle": "AI Observability & Drift Detection",
        "status_ok": "System Healthy",
        "status_ok_sub": "All signals within normal range",
        "status_drift": "Drift Detected",
        "status_drift_sub_n": "{} signals behaving abnormally",
        "last_scan": "Last scan",
        "online": "Online",
        "events_1h": "Events",
        "p50_1h": "P50 Latency",
        "p99_1h": "P99 Latency",
        "drifted_signals": "Drifted",
        "drift_status": "Signal Drift Analysis",
        "no_scan": "No scan results yet — waiting for the detector…",
        "normal": "Normal",
        "drifted": "Drifted",
        "traffic": "Traffic",
        "latency": "Latency",
        "dist_pred": "Prediction Distribution",
        "dist_conf": "Confidence Distribution",
        "current_win": "Current",
        "baseline_win": "Baseline",
        "recent_events": "Recent Events",
        "no_data": "No data yet",
        "ch_unreachable": "Cannot reach ClickHouse",
        "refresh": "Auto-refresh every 10s",
        "utc": "UTC",
        "overview": "Overview",
        "lang": "Language",
        "sidebar_status": "System Status",
        "sidebar_events": "Total events",
        "help_overview": "Quick health snapshot: Events = how many requests the model handled in the last hour; P50/P99 = response speed (half / 99% of requests); Drifted = how many signals are currently abnormal. Small numbers show change vs previous hour.",
        "help_drift": "The system periodically compares the model's recent behavior against a historical baseline. Green = normal; Red = significant drift detected. A higher score means a larger shift; crossing the threshold triggers a webhook alert.",
        "help_dist_pred": "Probability distribution of model predictions: purple = recent window, gray = baseline. Clearly separated curves are the core evidence of model behavior change.",
        "help_dist_conf": "Same comparison for model confidence. Sudden over-confidence or hesitation can be an early warning sign of model degradation.",
        "help_traffic": "Requests per minute. Sharp spikes or drops may indicate unusual traffic, campaigns, or system faults.",
        "help_latency": "Response time: P50 = half of requests complete within this; P99 = 99% of requests. A rising P99 means the system is slowing and users notice.",
        "help_events": "Recent request samples. Privacy-preserving: only SHA-256 fingerprint prefixes are stored, never raw data.",
    },
}

# ── 工具函数 ──────────────────────────────────────────────
def t(key, *args):
    s = I18N[st.session_state.lang].get(key, key)
    return s.format(*args) if args else s


def client():
    addr = urlparse(os.environ.get("CLICKHOUSE_ADDR", "http://localhost:8123"))
    return clickhouse_connect.get_client(
        host=addr.hostname, port=addr.port or 8123,
        username=os.environ.get("CLICKHOUSE_USER", "default"),
        password=os.environ.get("CLICKHOUSE_PASSWORD", ""),
        database=os.environ.get("CLICKHOUSE_DB", "vera"),
    )


def decode(df):
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].map(lambda v: v.decode("utf-8", "replace") if isinstance(v, bytes) else v)
    return df


def one(ch, sql):
    row = ch.query(sql).first_row
    return row[0] if row and len(row) == 1 else row


def window_bounds():
    cur = int(os.environ.get("DETECTOR_CURRENT_MINUTES", "5"))
    off = int(os.environ.get("DETECTOR_BASELINE_OFFSET", "30"))
    base = int(os.environ.get("DETECTOR_BASELINE_MINUTES", "30"))
    now = datetime.now(timezone.utc)
    return (now - timedelta(minutes=cur), now), (
        now - timedelta(minutes=off + base), now - timedelta(minutes=off))


# ── panel 标题 + ⓘ 帮助 ──────────────────────────────────
def panel(label_key, help_key):
    c1, c2 = st.columns([9, 1])
    with c1:
        st.markdown(f'<div class="pl-title">{t(label_key)}</div>', unsafe_allow_html=True)
    with c2:
        with st.popover("ⓘ", use_container_width=True):
            st.markdown(t(help_key))


# ── 状态横幅 ──────────────────────────────────────────────
def render_banner(ch):
    scan_ts = one(ch, "SELECT max(timestamp) FROM vera.drift_results")
    if scan_ts is None:
        st.info(t("no_scan"))
        return None, None
    scan_id = one(ch, "SELECT scan_id FROM vera.drift_results ORDER BY timestamp DESC LIMIT 1")
    df = ch.query_df(f"""
        SELECT metric, score, threshold, drifted FROM vera.drift_results
        WHERE scan_id = '{scan_id}'
    """)
    n_bad = int(df["drifted"].sum()) if not df.empty else 0
    ts = pd.Timestamp(scan_ts).strftime("%Y-%m-%d %H:%M:%S")
    ok = n_bad == 0
    cls = "ok" if ok else "bad"
    title = t("status_ok") if ok else t("status_drift")
    sub = t("status_ok_sub") if ok else t("status_drift_sub_n", n_bad)
    html = f"""
    <div class="status-banner {cls}">
        <div class="status-dot {cls}"></div>
        <div class="status-text">
            <div class="title">{title}</div>
            <div class="sub">{sub} &nbsp;·&nbsp; {t('last_scan')} {ts} {t('utc')}</div>
        </div>
    </div>"""
    st.markdown(html, unsafe_allow_html=True)
    return ok, df


# ── 系统概览（指标卡） ────────────────────────────────────
def render_summary(ch, ok):
    panel("overview", "help_overview")
    ev1 = one(ch, "SELECT count() FROM vera.events WHERE timestamp >= now() - INTERVAL 60 MINUTE") or 0
    ev0 = one(ch, """SELECT count() FROM vera.events
                     WHERE timestamp >= now() - INTERVAL 120 MINUTE
                       AND timestamp < now() - INTERVAL 60 MINUTE""") or 0
    p50, p99 = one(ch, """SELECT quantile(0.5)(latency_ms), quantile(0.99)(latency_ms)
                          FROM vera.events WHERE timestamp >= now() - INTERVAL 60 MINUTE""") or (0, 0)
    p50p, p99p = one(ch, """SELECT quantile(0.5)(latency_ms), quantile(0.99)(latency_ms)
                            FROM vera.events
                            WHERE timestamp >= now() - INTERVAL 120 MINUTE
                              AND timestamp < now() - INTERVAL 60 MINUTE""") or (0, 0)

    def delta_str(cur, prev):
        d = cur - prev
        if d == 0: return "—"
        return f"{d:+,.1f}" if isinstance(d, float) else f"{d:+,}"

    def delta_cls(cur, prev):
        d = cur - prev
        if d == 0: return TEXT2
        return GREEN if d < 0 else RED

    cards = [
        ("📨", f"{ev1:,}",  t("events_1h"),     delta_str(ev1, ev0),  delta_cls(ev1, ev0),  BLUE),
        ("⚡", f"{p50:.1f} ms", t("p50_1h"),     delta_str(p50, p50p), delta_cls(p50, p50p), ACCENT),
        ("🎯", f"{p99:.1f} ms", t("p99_1h"),     delta_str(p99, p99p), delta_cls(p99, p99p), AMBER),
        ("🔍", f"{0 if ok is None else (0 if ok else 1)}", t("drifted_signals"),
         "", TEXT2, GREEN if ok else RED),
    ]

    cols = st.columns(4)
    for i, (icon, val, label, delta, dcolor, bar_color) in enumerate(cards):
        with cols[i]:
            html = f"""<div class="metric-card">
                <div class="mc-bar" style="background:{bar_color}"></div>
                <div class="mc-icon">{icon}</div>
                <div class="mc-value">{val}</div>
                <div class="mc-label">{label}</div>"""
            if delta:
                html += f'<div class="mc-delta" style="color:{dcolor}">{delta}</div>'
            html += "</div>"
            st.markdown(html, unsafe_allow_html=True)


# ── 漂移信号卡片 ──────────────────────────────────────────
def render_drift(ch, df):
    panel("drift_status", "help_drift")
    if df is None or df.empty:
        st.caption(t("no_scan"))
        return
    cols = st.columns(len(df))
    for i, row in enumerate(df.itertuples()):
        drifted = bool(row.drifted)
        cls = "bad" if drifted else "ok"
        badge = t("drifted") if drifted else t("normal")
        # 柱状条：score/threshold 映射到 0-100%，封顶 3 倍阈值
        pct = min(float(row.score) / max(float(row.threshold), 1e-9) * 100 / 3, 100)
        bar_c = RED if drifted else GREEN
        html = f"""<div class="drift-sig">
            <div class="ds-head">
                <div class="ds-dot {cls}"></div>
                <span class="ds-name">{row.metric}</span>
                <span class="ds-badge {cls}">{badge}</span>
            </div>
            <div class="ds-score">{float(row.score):.4f}</div>
            <div class="ds-thresh">threshold {float(row.threshold)}</div>
            <div class="ds-bar-bg"><div class="ds-bar-fg" style="width:{pct}%;background:{bar_c}"></div></div>
        </div>"""
        with cols[i]:
            st.markdown(html, unsafe_allow_html=True)


# ── 分布对比（直方图叠加） ────────────────────────────────
def render_distribution(ch):
    cur_range, base_range = window_bounds()

    def fetch(col, start, end):
        expr = f"toFloat64OrNull({col})" if col == "prediction" else col
        sql = (f"SELECT {expr} AS v FROM vera.events "
               f"WHERE timestamp >= '{start:%Y-%m-%d %H:%M:%S}' "
               f"AND timestamp < '{end:%Y-%m-%d %H:%M:%S}' AND {expr} IS NOT NULL")
        return ch.query_df(sql)

    c1, c2 = st.columns(2)
    for col, help_k, container in (("prediction", "help_dist_pred", c1), ("confidence", "help_dist_conf", c2)):
        with container:
            panel("dist_pred" if col == "prediction" else "dist_conf", help_k)
            cur_df = fetch(col, *cur_range)
            base_df = fetch(col, *base_range)
            if cur_df.empty and base_df.empty:
                st.caption(t("no_data"))
                continue
            cur_df = cur_df.assign(window=t("current_win"))
            base_df = base_df.assign(window=t("baseline_win"))
            merged = pd.concat([cur_df, base_df])
            fig = px.histogram(merged, x="v", color="window",
                               nbins=35, barmode="overlay", opacity=0.55,
                               histnorm="probability density",
                               color_discrete_sequence=[ACCENT, "#4B5563"],
                               template="plotly_dark")
            fig.update_traces(
                marker=dict(line=dict(width=0)),
                selector=dict(type="histogram"),
            )
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color=TEXT2, size=11),
                height=260, margin=dict(l=10, r=10, t=5, b=5),
                legend=dict(orientation="h", y=1.05, x=0, font=dict(color=TEXT2, size=11)),
                xaxis=dict(gridcolor="rgba(255,255,255,0.04)", linecolor=BORDER, zeroline=False, title=""),
                yaxis=dict(gridcolor="rgba(255,255,255,0.04)", linecolor=BORDER, zeroline=False, title=""),
                bargap=0.05,
            )
            fig.update_xaxes(showgrid=False); fig.update_yaxes(showgrid=False)
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


# ── 趋势图（流量 + 延迟） ─────────────────────────────────
def render_trends(ch):
    vol = ch.query_df("""
        SELECT toStartOfMinute(timestamp) AS t, count() AS n
        FROM vera.events WHERE timestamp >= now() - INTERVAL 60 MINUTE
        GROUP BY t ORDER BY t
    """)
    lat = ch.query_df("""
        SELECT toStartOfMinute(timestamp) AS t,
               quantile(0.5)(latency_ms) AS p50, quantile(0.99)(latency_ms) AS p99
        FROM vera.events WHERE timestamp >= now() - INTERVAL 60 MINUTE
        GROUP BY t ORDER BY t
    """)

    LAYOUT = dict(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=TEXT2, size=11),
        height=280, margin=dict(l=10, r=10, t=5, b=5),
        legend=dict(orientation="h", y=1.05, font=dict(color=TEXT2, size=11)),
        xaxis=dict(gridcolor="rgba(255,255,255,0.04)", linecolor=BORDER, zeroline=False, title=""),
        yaxis=dict(gridcolor="rgba(255,255,255,0.04)", linecolor=BORDER, zeroline=False, title=""),
        hovermode="x unified",
    )

    c1, c2 = st.columns(2)
    with c1:
        panel("traffic", "help_traffic")
        if vol.empty:
            st.caption(t("no_data"))
        else:
            vold = vol.assign(t=pd.to_datetime(vol["t"]))
            fig = go.Figure(go.Scatter(
                x=vold["t"], y=vold["n"], mode="lines", line=dict(color=ACCENT, width=2.5, shape="spline"),
                fill="tozeroy", fillcolor="rgba(139,124,255,0.1)",
                hovertemplate="%{y:,} req<extra></extra>",
            ))
            fig.update_layout(**LAYOUT)
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    with c2:
        panel("latency", "help_latency")
        if lat.empty:
            st.caption(t("no_data"))
        else:
            latd = lat.assign(t=pd.to_datetime(lat["t"]))
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=latd["t"], y=latd["p50"], mode="lines", name="P50",
                line=dict(color=ACCENT, width=2.5, shape="spline"),
                hovertemplate="P50: %{y:.2f} ms<extra></extra>",
            ))
            fig.add_trace(go.Scatter(
                x=latd["t"], y=latd["p99"], mode="lines", name="P99",
                line=dict(color="#64748B", width=2.5, shape="spline"),
                hovertemplate="P99: %{y:.2f} ms<extra></extra>",
            ))
            fig.update_layout(**LAYOUT)
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


# ── 事件明细表 ────────────────────────────────────────────
def render_events(ch):
    panel("recent_events", "help_events")
    df = decode(ch.query_df("""
        SELECT timestamp, model_name, model_version, prediction, confidence,
               latency_ms, input_summary_hash
        FROM vera.events ORDER BY timestamp DESC LIMIT 20
    """))
    if df.empty:
        st.caption(t("no_data"))
        return
    df["input_summary_hash"] = df["input_summary_hash"].str[:12]
    st.dataframe(df, width="stretch", hide_index=True, column_config={
        "timestamp":          st.column_config.DatetimeColumn("timestamp", format="MM-DD HH:mm:ss"),
        "model_name":         st.column_config.TextColumn("model"),
        "model_version":      st.column_config.TextColumn("version"),
        "prediction":         st.column_config.NumberColumn("prediction", format="%.4f"),
        "confidence":         st.column_config.NumberColumn("confidence", format="%.3f"),
        "latency_ms":         st.column_config.NumberColumn("latency", format="%.2f ms"),
        "input_summary_hash": st.column_config.TextColumn("fingerprint"),
    })


# ── 侧边栏 ────────────────────────────────────────────────
def render_sidebar(ch):
    with st.sidebar:
        st.markdown("""
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:20px;">
            <div style="width:36px;height:36px;border-radius:10px;background:linear-gradient(135deg,#8B7CFF,#A78BFA);
                        display:flex;align-items:center;justify-content:center;font-size:1.2rem;">📊</div>
            <div>
                <div style="font-weight:700;font-size:1.1rem;color:#F1F5F9;line-height:1.2;">Vera</div>
                <div style="font-size:0.72rem;color:#64748B;">Observability</div>
            </div>
        </div>""", unsafe_allow_html=True)

        # 系统在线状态
        try:
            ch.ping()
            st.markdown(f"""
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:16px;padding:10px 14px;
                        background:rgba(16,185,129,0.06);border:1px solid rgba(16,185,129,0.12);border-radius:12px;">
                <div style="width:7px;height:7px;border-radius:50%;background:#10B981;
                            box-shadow:0 0 6px rgba(16,185,129,0.5);"></div>
                <span style="font-size:0.82rem;color:#10B981;font-weight:500;">{t('online')}</span>
            </div>""", unsafe_allow_html=True)
        except Exception:
            pass

        st.markdown(f'<p style="color:{TEXT2};font-size:0.75rem;font-weight:600;'
                    f'margin-bottom:4px;">{t("lang")}</p>', unsafe_allow_html=True)
        lang = st.radio("Language / 语言", ["中文", "English"],
                        index=0 if st.session_state.lang == "zh" else 1,
                        label_visibility="collapsed")
        st.session_state.lang = "zh" if lang == "中文" else "en"

        st.divider()
        st.caption(t("refresh"))


# ── 入口 ──────────────────────────────────────────────────
if "lang" not in st.session_state:
    st.session_state.lang = "zh"

st.set_page_config(page_title="Vera", page_icon="📊", layout="wide")
st.markdown(CSS, unsafe_allow_html=True)

# 首帧建连，侧边栏显示在线状态
try:
    _ch_init = client()
    render_sidebar(_ch_init)
except Exception:
    render_sidebar(None)

# 主区标题
st.markdown(f"""
<div style="margin-bottom:6px;">
    <span style="font-size:1.6rem;font-weight:700;color:#F1F5F9;letter-spacing:-0.02em;">{t('title')}</span>
    <span style="font-size:0.85rem;color:{TEXT2};margin-left:12px;">{t('subtitle')}</span>
</div>""", unsafe_allow_html=True)


# ── 自刷新片段 ────────────────────────────────────────────
@st.fragment(run_every=10)
def render():
    try:
        ch = client()
    except Exception:
        st.warning(t("ch_unreachable"))
        return
    ok, drift_df = render_banner(ch)
    render_summary(ch, ok)
    render_drift(ch, drift_df)
    render_distribution(ch)
    render_trends(ch)
    render_events(ch)


render()
