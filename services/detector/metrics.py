"""漂移指标：定义从事件窗口提取的信号与判定规则。"""
import drift


class Result:
    """单个指标的扫描结果。"""

    def __init__(self, metric, score, threshold, drifted, details):
        self.metric = metric
        self.score = score
        self.threshold = threshold
        self.drifted = drifted
        self.details = details


# 数值信号：名称、事件列、统计方法（ks 用 p 值，psi 用指数）
METRICS = [
    ("confidence", "confidence", "ks"),
    ("prediction", "prediction", "psi"),
    ("latency_ms", "latency_ms", "ks"),
]


def compute_all(store, baseline, current, cfg):
    """计算全部数值指标的漂移结果。"""
    results = []
    for name, column, test in METRICS:
        actual = store.series(column, *current)
        expected = store.series(column, *baseline)
        res = _compute(name, actual, expected, test, cfg)
        if res:
            results.append(res)
    return results


def _compute(name, actual, expected, test, cfg):
    """计算单个数值指标的漂移结果；基准样本不足时记为无漂移。"""
    if actual.size < 2:
        return None
    if test == "ks":
        score = drift.ks_pvalue(actual, expected)
        threshold = cfg.ks_threshold
        drifted = score < threshold
    else:
        score = drift.numeric_psi(actual, expected)
        threshold = cfg.psi_threshold
        drifted = score > threshold
    return Result(name, score, threshold, drifted,
                  {"test": test, "n_baseline": int(expected.size), "n_current": int(actual.size)})
