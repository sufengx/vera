"""ClickHouse 读取：根因分析的窗口查询。"""
from urllib.parse import urlparse

import clickhouse_connect
import numpy as np

COLUMNS = ("confidence", "latency_ms", "prediction")
DIMENSIONS = ("client_id", "model_name", "model_version", "route")


class Store:
    def __init__(self, cfg):
        addr = urlparse(cfg.clickhouse_addr)
        self.client = clickhouse_connect.get_client(
            host=addr.hostname, port=addr.port or 8123,
            username=cfg.clickhouse_user, password=cfg.clickhouse_password,
            database=cfg.clickhouse_db,
        )

    def _where(self, start, end, model, route):
        conds = [
            f"timestamp >= '{start:%Y-%m-%d %H:%M:%S}'",
            f"timestamp < '{end:%Y-%m-%d %H:%M:%S}'",
        ]
        if model:
            conds.append(f"model_name = '{model}'")
        if route:
            conds.append(f"route = '{route}'")
        return " AND ".join(conds)

    def count(self, start, end, model="", route=""):
        sql = f"SELECT count() FROM vera.events WHERE {self._where(start, end, model, route)}"
        return int(self.client.query(sql).first_row[0])

    def series(self, column, start, end, model="", route=""):
        """窗口内数值列，返回 numpy 数组；prediction 为字符串列需转换。"""
        col = column if column != "prediction" else "toFloat64OrNull(prediction) AS v"
        sql = f"SELECT {col} FROM vera.events WHERE {self._where(start, end, model, route)}"
        rows = self.client.query(sql).result_rows
        return np.array([r[0] for r in rows if r[0] is not None], dtype=float)

    def segment_stats(self, dimension, start, end, model="", route="", limit=50):
        """按维度分组统计：样本数与各特征均值，返回 {分组: (样本数, {特征: 均值})}。"""
        sql = (
            "SELECT {0} AS g, count() AS n, avg(confidence) AS c, avg(latency_ms) AS l, "
            "avg(toFloat64OrNull(prediction)) AS p FROM vera.events WHERE {1} "
            "GROUP BY g ORDER BY n DESC LIMIT {2}"
        ).format(dimension, self._where(start, end, model, route), limit)
        stats = {}
        for g, n, c, l, p in self.client.query(sql).result_rows:
            g = g.decode("utf-8", "replace") if isinstance(g, bytes) else str(g)
            stats[g] = (int(n), {"confidence": _num(c), "latency_ms": _num(l), "prediction": _num(p)})
        return stats


def _num(v):
    """ClickHouse avg 全 NULL 时返回 NaN，转 None 表示该组无此特征值。"""
    if v is None:
        return None
    v = float(v)
    return None if np.isnan(v) else v
