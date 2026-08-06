"""ClickHouse 读写：事件窗口查询与漂移结果写入。"""
import json
from urllib.parse import urlparse

import clickhouse_connect
import numpy as np


def _to_float(v):
    """兼容 bytes/str/float 的数值转换，失败返回 None。"""
    if isinstance(v, bytes):
        v = v.decode("utf-8", "replace")
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _as_str(v):
    return v.decode("utf-8", "replace") if isinstance(v, bytes) else str(v)


class Store:
    def __init__(self, cfg):
        addr = urlparse(cfg.clickhouse_addr)
        self.cfg = cfg
        self.client = clickhouse_connect.get_client(
            host=addr.hostname, port=addr.port or 8123,
            username=cfg.clickhouse_user, password=cfg.clickhouse_password,
            database=cfg.clickhouse_db,
        )
        self.ensure_schema()

    def ensure_schema(self):
        """确保漂移结果表存在，兼容已有数据卷的旧环境。"""
        self.client.command("""
            CREATE TABLE IF NOT EXISTS vera.drift_results (
                scan_id UUID,
                timestamp DateTime64(3),
                metric String,
                score Float64,
                threshold Float64,
                drifted Bool,
                details String,
                window_start DateTime64(3),
                window_end DateTime64(3)
            ) ENGINE = MergeTree
            ORDER BY (metric, timestamp)
            PARTITION BY toYYYYMM(timestamp)
            TTL toDateTime(timestamp) + INTERVAL 180 DAY
        """)

    def series(self, column, start, end):
        """窗口内数值列，返回 numpy 数组；prediction 解析为浮点。"""
        sql = (
            f"SELECT {column} AS v FROM vera.events "
            f"WHERE timestamp >= '{start:%Y-%m-%d %H:%M:%S}' "
            f"AND timestamp < '{end:%Y-%m-%d %H:%M:%S}'"
        )
        rows = self.client.query(sql).result_rows
        if column == "prediction":
            return np.array([v for v in (_to_float(r[0]) for r in rows) if v is not None])
        return np.array([r[0] for r in rows], dtype=float)

    def count(self, start, end):
        """窗口内事件总数。"""
        sql = (
            "SELECT count() FROM vera.events "
            f"WHERE timestamp >= '{start:%Y-%m-%d %H:%M:%S}' "
            f"AND timestamp < '{end:%Y-%m-%d %H:%M:%S}'"
        )
        return int(self.client.query(sql).first_row[0])

    def write_result(self, scan_id, ts, result, wstart, wend):
        """写入一条漂移扫描结果。"""
        self.client.insert(
            "vera.drift_results",
            [[scan_id, ts, result.metric, result.score, result.threshold,
              result.drifted, json.dumps(result.details), wstart, wend]],
            column_names=["scan_id", "timestamp", "metric", "score", "threshold",
                          "drifted", "details", "window_start", "window_end"],
        )

    def latest_results(self):
        """最近一次扫描的全部指标结果。"""
        sql = (
            "SELECT metric, score, threshold, drifted, details FROM vera.drift_results "
            "WHERE scan_id = (SELECT scan_id FROM vera.drift_results ORDER BY timestamp DESC LIMIT 1) "
            "ORDER BY score DESC"
        )
        return [
            {"metric": _as_str(m), "score": s, "threshold": t, "drifted": bool(d), "details": _as_str(det)}
            for m, s, t, d, det in self.client.query(sql).result_rows
        ]
