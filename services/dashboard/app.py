"""Vera 观测仪表盘：查询 ClickHouse 展示流量与漂移状态，中英双语。"""
import os
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import clickhouse_connect
import pandas as pd
import plotly.express as px
import streamlit as st

ACCENT = "#8B7CFF"
GRAY = "#9AA3B5"

I18N = {
    "zh": {
        "title": "Vera — AI 可观测性仪表盘",
        "subtitle": "生产 AI 系统的行为监控与漂移检测",
        "status_ok": "系统正常",
        "status_drift": "检测到漂移",
        "last_scan": "最近扫描",
        "events_1h": "近 1 小时事件",
        "p50_1h": "p50 延迟（1h）",
        "p99_1h": "p99 延迟（1h）",
        "drifted_signals": "漂移信号",
        "drift_status": "漂移状态（最新一轮扫描）",
        "no_scan": "暂无检测结果，等待检测器首轮扫描…",
        "normal": "正常",
        "drifted": "漂移",
        "traffic": "事件量（最近 60 分钟）",
        "latency": "延迟（最近 60 分钟）",
        "dist_pred": "预测值分布对比（当前 vs 基准）",
        "dist_conf": "置信度分布对比（当前 vs 基准）",
        "current_win": "当前窗口",
        "baseline_win": "基准窗口",
        "recent_events": "最近事件",
        "no_data": "暂无数据",
        "ch_unreachable": "无法连接 ClickHouse",
        "refresh": "每 10 秒自动刷新",
        "utc": "UTC",
        "overview": "概览",
        "help_overview": "四个数字是系统健康速览：事件量=最近一小时模型处理了多少次请求；p50/p99=响应速度（一半 / 99% 的请求在多长时间内完成）；漂移信号=当前发现几个行为异常。小字是相对上一小时的增减。",
        "help_drift": "系统定期把模型最近几分钟的行为和更早一段时间的正常行为做对比，判断有没有明显变化。绿点=正常；红点=行为变了。分数越大变化越明显，超过阈值就会标红并发送告警。",
        "help_dist_pred": "把模型的输出画成曲线堆叠：紫色=最近时间段，灰色=基准时间段。两条曲线明显错开，说明模型的输出分布变了——这是判断模型行为是否改变的核心依据。",
        "help_dist_conf": "和预测值图类似，这里对比的是模型对自己的信心。模型突然变自信或变犹豫，也可能是行为异常的早期信号。",
        "help_traffic": "每分钟有多少次模型请求。曲线陡升或陡降，可能意味着流量异常、线上活动或者系统故障。",
        "help_latency": "模型响应速度：p50=一半请求在这时间内完成，p99=99% 的请求在这时间内完成。p99 突然上涨说明系统在变慢，用户会开始感觉到卡顿。",
        "help_events": "最近收到的模型请求样本。为保护隐私，只记录请求的摘要指纹，不保存原始数据。",
    },
    "en": {
        "title": "Vera — AI Observability Dashboard",
        "subtitle": "Behavior monitoring and drift detection for production AI",
        "status_ok": "All systems normal",
        "status_drift": "Drift detected",
        "last_scan": "Last scan",
        "events_1h": "Events (1h)",
        "p50_1h": "p50 latency (1h)",
        "p99_1h": "p99 latency (1h)",
        "drifted_signals": "Drifted signals",
        "drift_status": "Drift status (latest scan)",
        "no_scan": "No scan results yet — waiting for the detector…",
        "normal": "Normal",
        "drifted": "Drifted",
        "traffic": "Event volume (last 60 min)",
        "latency": "Latency (last 60 min)",
        "dist_pred": "Prediction distribution (current vs baseline)",
        "dist_conf": "Confidence distribution (current vs baseline)",
        "current_win": "Current window",
        "baseline_win": "Baseline window",
        "recent_events": "Recent events",
        "no_data": "No data yet",
        "ch_unreachable": "Cannot reach ClickHouse",
        "refresh": "Auto-refresh every 10s",
        "utc": "UTC",
        "overview": "Overview",
        "help_overview": "A quick health snapshot: events (1h) = how many requests the model handled in the last hour; p50/p99 = response speed (half / 99% of requests complete within this time); drifted signals = how many abnormal behaviors were found. The small numbers show change vs the previous hour.",
        "help_drift": "The system periodically compares the model's recent behavior with its past baseline and checks for significant change. Green dot = normal; red dot = behavior has shifted. A higher score means a bigger change; crossing the threshold turns red and fires an alert.",
        "help_dist_pred": "Model outputs stacked as histograms: purple = recent window, gray = baseline window. Clearly separated curves mean the output distribution has changed — the core evidence of drift.",
        "help_dist_conf": "Same comparison for the model's confidence. Sudden over-confidence or hesitation can be an early warning sign.",
        "help_traffic": "Model requests per minute. Sharp spikes or drops may indicate unusual load, a campaign, or a system fault.",
        "help_latency": "Response speed: p50 = half of requests complete within this time, p99 = 99% do. A rising p99 means the system is slowing down and users may start noticing.",
        "help_events": "Recent model request samples. Privacy-preserving: only summary fingerprints are stored, never raw data.",
    },
}


def t(key):
    return I18N[st.session_state.lang].get(key, key)


def panel(text, help_key):
    """板块标题 + 问号弹层，弹层里是通俗解释。"""
    c1, c2 = st.columns([7, 1])
    c1.subheader(text)
    with c2:
        with st.popover("ⓘ"):
            st.markdown(t(help_key))


def client():
    addr = urlparse(os.environ.get("CLICKHOUSE_ADDR", "http://localhost:8123"))
    return clickhouse_connect.get_client(
        host=addr.hostname, port=addr.port or 8123,
        username=os.environ.get("CLICKHOUSE_USER", "default"),
        password=os.environ.get("CLICKHOUSE_PASSWORD", ""),
        database=os.environ.get("CLICKHOUSE_DB", "vera"),
    )


def decode(df):
    """String 列由 bytes 转 str。"""
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].map(lambda v: v.decode("utf-8", "replace") if isinstance(v, bytes) else v)
    return df


def one(ch, sql):
    """执行标量查询；多列时返回整行。"""
    row = ch.query(sql).first_row
    return row[0] if row and len(row) == 1 else row


def window_bounds():
    """当前/基准窗口，与检测器同语义（环境变量可覆盖）。"""
    cur = int(os.environ.get("DETECTOR_CURRENT_MINUTES", "5"))
    off = int(os.environ.get("DETECTOR_BASELINE_OFFSET", "30"))
    base = int(os.environ.get("DETECTOR_BASELINE_MINUTES", "30"))
    now = datetime.now(timezone.utc)
    return (now - timedelta(minutes=cur), now), (
        now - timedelta(minutes=off + base), now - timedelta(minutes=off))


def fmt_ts(ts):
    return f"{ts:%Y-%m-%d %H:%M:%S}"


def render_banner(ch):
    """顶部状态横幅：绿=正常，红=漂移。"""
    scan_ts = one(ch, "SELECT max(timestamp) FROM vera.drift_results")
    if scan_ts is None:
        st.info(t("no_scan"))
        return None
    drifted = one(ch, """
        SELECT count() FROM vera.drift_results
        WHERE scan_id = (SELECT scan_id FROM vera.drift_results ORDER BY timestamp DESC LIMIT 1)
          AND drifted
    """)
    ts = fmt_ts(pd.Timestamp(scan_ts))
    if drifted:
        st.error(f"🚨 **{t('status_drift')}** — {t('last_scan')} {ts} ({t('utc')})")
    else:
        st.success(f"✅ **{t('status_ok')}** — {t('last_scan')} {ts} ({t('utc')})")
    return drifted


def render_summary(ch, drifted):
    """四个指标卡：事件量、延迟分位、漂移信号数。"""
    panel(t("overview"), "help_overview")
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
    m1, m2, m3, m4 = st.columns(4)
    m1.metric(t("events_1h"), f"{ev1:,}", f"{ev1 - ev0:+,}")
    m2.metric(t("p50_1h"), f"{p50:.2f} ms", f"{p50 - p50p:+.2f} ms")
    m3.metric(t("p99_1h"), f"{p99:.2f} ms", f"{p99 - p99p:+.2f} ms")
    m4.metric(t("drifted_signals"), str(int(drifted or 0)))


def render_drift(ch):
    """最新一轮扫描的漂移信号列表。"""
    panel(t("drift_status"), "help_drift")
    df = ch.query_df("""
        SELECT metric, score, threshold, drifted
        FROM vera.drift_results
        WHERE scan_id = (SELECT scan_id FROM vera.drift_results ORDER BY timestamp DESC LIMIT 1)
        ORDER BY score DESC
    """)
    if df.empty:
        st.caption(t("no_scan"))
        return
    for row in df.itertuples():
        ok = not row.drifted
        color = "green" if ok else "red"
        status = t("normal") if ok else t("drifted")
        st.markdown(f":{color}[●] **{row.metric}** — `{row.score:.4f}` / threshold `{row.threshold}` · {status}")


def render_distribution(ch):
    """预测/置信度分布的当前窗口 vs 基准窗口对比。"""
    current, baseline = window_bounds()

    def series(column, start, end):
        expr = f"toFloat64OrNull({column})" if column == "prediction" else column
        sql = (f"SELECT {expr} AS v FROM vera.events "
               f"WHERE timestamp >= '{start:%Y-%m-%d %H:%M:%S}' "
               f"AND timestamp < '{end:%Y-%m-%d %H:%M:%S}' AND {expr} IS NOT NULL")
        return ch.query_df(sql)

    c1, c2 = st.columns(2)
    for col, key in (("prediction", "dist_pred"), ("confidence", "dist_conf")):
        cur_df = series(col, *current).assign(window=t("current_win"))
        base_df = series(col, *baseline).assign(window=t("baseline_win"))
        with c1 if col == "prediction" else c2:
            panel(t(key), "help_dist_pred" if col == "prediction" else "help_dist_conf")
            if cur_df.empty and base_df.empty:
                st.caption(t("no_data"))
                continue
            fig = px.histogram(pd.concat([cur_df, base_df]), x="v", color="window",
                               nbins=30, barmode="overlay", opacity=0.65,
                               color_discrete_sequence=[ACCENT, GRAY], template="plotly_dark",
                               labels={"v": col, "window": ""})
            fig.update_layout(height=260, margin=dict(l=10, r=10, t=10, b=10),
                              legend=dict(orientation="h", y=1.05))
            st.plotly_chart(fig, width="stretch")


def render_trends(ch):
    """事件量与延迟趋势。"""
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
    c1, c2 = st.columns(2)
    with c1:
        panel(t("traffic"), "help_traffic")
        if vol.empty:
            st.caption(t("no_data"))
        else:
            fig = px.area(vol.assign(t=pd.to_datetime(vol["t"])), x="t", y="n",
                          template="plotly_dark", color_discrete_sequence=[ACCENT],
                          labels={"t": "", "n": ""})
            fig.update_layout(height=280, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig, width="stretch")
    with c2:
        panel(t("latency"), "help_latency")
        if lat.empty:
            st.caption(t("no_data"))
        else:
            df = lat.assign(t=pd.to_datetime(lat["t"]))
            fig = px.line(df, x="t", y=["p50", "p99"], template="plotly_dark",
                          color_discrete_sequence=[ACCENT, GRAY],
                          labels={"t": "", "value": "ms", "variable": ""})
            fig.update_layout(height=280, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig, width="stretch")


def render_events(ch):
    """最近的事件样本。"""
    panel(t("recent_events"), "help_events")
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
        "timestamp": st.column_config.DatetimeColumn("timestamp", format="MM-DD HH:mm:ss"),
        "confidence": st.column_config.NumberColumn("confidence", format="%.3f"),
        "latency_ms": st.column_config.NumberColumn("latency_ms", format="%.2f"),
    })


if "lang" not in st.session_state:
    st.session_state.lang = "zh"

st.set_page_config(page_title="Vera", page_icon="📊", layout="wide")

with st.sidebar:
    lang = st.radio("Language / 语言", ["中文", "English"],
                    index=0 if st.session_state.lang == "zh" else 1)
    st.session_state.lang = "zh" if lang == "中文" else "en"
    st.caption(t("refresh"))

st.title(t("title"))
st.caption(t("subtitle"))


@st.fragment(run_every=10)
def render():
    try:
        ch = client()
    except Exception:
        st.warning(t("ch_unreachable"))
        return
    drifted = render_banner(ch)
    render_summary(ch, drifted)
    render_drift(ch)
    render_distribution(ch)
    render_trends(ch)
    render_events(ch)


render()
