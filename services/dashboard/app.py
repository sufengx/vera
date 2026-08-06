"""Vera 仪表盘：查询 ClickHouse 展示流量与漂移状态。"""
import os
from urllib.parse import urlparse

import clickhouse_connect
import pandas as pd
import streamlit as st


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


def drift_panel(ch):
    """最近一次扫描的漂移状态。"""
    df = ch.query_df("""
        SELECT metric, score, threshold, drifted
        FROM vera.drift_results
        WHERE scan_id = (SELECT scan_id FROM vera.drift_results ORDER BY timestamp DESC LIMIT 1)
        ORDER BY score DESC
    """)
    if df.empty:
        st.caption("暂无检测结果，等待检测器首轮扫描…")
        return
    for _, row in df.iterrows():
        color = "red" if row.drifted else "green"
        st.markdown(f":{color}[●] **{row.metric}**: score={row.score:.4f} / threshold={row.threshold}")


def traffic_panel(ch):
    """最近 60 分钟的事件量与延迟趋势。"""
    vol = ch.query_df("""
        SELECT toStartOfMinute(timestamp) AS t, count() AS n
        FROM vera.events
        WHERE timestamp >= now() - INTERVAL 60 MINUTE
        GROUP BY t ORDER BY t
    """)
    lat = ch.query_df("""
        SELECT toStartOfMinute(timestamp) AS t,
               quantile(0.5)(latency_ms) AS p50,
               quantile(0.99)(latency_ms) AS p99
        FROM vera.events
        WHERE timestamp >= now() - INTERVAL 60 MINUTE
        GROUP BY t ORDER BY t
    """)
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("事件量（最近 60 分钟）")
        if vol.empty:
            st.caption("暂无数据")
        else:
            st.line_chart(vol.assign(t=pd.to_datetime(vol["t"])).set_index("t")["n"])
    with c2:
        st.subheader("延迟（最近 60 分钟）")
        if lat.empty:
            st.caption("暂无数据")
        else:
            st.line_chart(lat.assign(t=pd.to_datetime(lat["t"])).set_index("t")[["p50", "p99"]])


def events_panel(ch):
    """最近的事件样本。"""
    df = ch.query_df("""
        SELECT timestamp, model_name, model_version, prediction, confidence,
               latency_ms, input_summary_hash
        FROM vera.events
        ORDER BY timestamp DESC
        LIMIT 20
    """)
    if df.empty:
        st.caption("暂无事件")
        return
    st.dataframe(decode(df), use_container_width=True)


st.set_page_config(page_title="Vera", layout="wide")
st.title("Vera — AI Observability Dashboard")


@st.fragment(run_every=10)
def render():
    try:
        ch = client()
    except Exception:
        st.warning("无法连接 ClickHouse")
        return
    st.header("Drift Detection")
    drift_panel(ch)
    traffic_panel(ch)
    st.header("Recent Events")
    events_panel(ch)


render()
