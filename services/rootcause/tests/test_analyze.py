"""根因分析核心单元测试：特征贡献与子群贡献。"""
import numpy as np

import analyze


def _rng(seed):
    return np.random.default_rng(seed)


def test_feature_identical():
    a = _rng(42).normal(0.5, 0.1, 400)
    row = analyze.features({"confidence": (a, a.copy())})[0]
    assert row["psi"] < 0.05
    assert row["direction"] == "spread"
    assert row["confidence"] < 0.5


def test_feature_shift_direction():
    rng = _rng(42)
    a = rng.normal(0.5, 0.1, 400)
    b = rng.normal(0.9, 0.1, 400)
    row = analyze.features({"confidence": (b, a)})[0]
    assert row["effect_size"] > 2
    assert row["direction"] == "up"


def test_ranks_known_drift_top3():
    """验收：已知故障的合成数据能正确定位 top-3 相关特征。"""
    rng = _rng(7)
    n = 600
    base = {
        "confidence": rng.normal(0.6, 0.1, n),
        "latency_ms": rng.exponential(10, n),
        "prediction": rng.normal(0.5, 0.1, n),
    }
    is7 = rng.random(n) < 0.8
    cur = {
        "confidence": rng.normal(0.9, 0.1, n),  # 整体均值 +0.3
        "latency_ms": np.where(is7, rng.exponential(25, n), rng.exponential(10, n)),  # 集中于 80% 流量
        "prediction": rng.normal(0.5, 0.1, n),  # 不变
    }
    rows = analyze.features({
        "confidence": (cur["confidence"], base["confidence"]),
        "latency_ms": (cur["latency_ms"], base["latency_ms"]),
        "prediction": (cur["prediction"], base["prediction"]),
    })
    top3 = [r["name"] for r in rows[:3]]
    assert top3[0] == "confidence"
    assert "latency_ms" in top3[:2]
    assert all(r["confidence"] > 0.5 for r in rows[:2])


def test_feature_drifted_flag():
    rng = _rng(1)
    a = rng.normal(0.5, 0.1, 400)
    b = rng.normal(0.9, 0.1, 400)
    rows = analyze.features({"confidence": (b, a), "latency_ms": (a, a.copy())})
    by = {r["name"]: r for r in rows}
    assert by["confidence"]["drifted"] is True
    assert by["latency_ms"]["drifted"] is False


def test_empty_and_small_inputs():
    assert analyze.features({}) == []
    rows = analyze.features({"latency_ms": (np.array([1.0]), np.array([1.0, 2.0]))})
    assert rows == []


def test_segment_locates_concentrated_drift():
    """验收：漂移集中于某子群时能定位到该子群。"""
    base = {f"client-{i}": (8, 10.0) for i in range(100)}  # 800 条事件
    cur = {f"client-{i}": (8, 11.0) for i in range(100)}
    cur["client-7"] = (640, 40.0)  # 80% 流量且均值位移远大于整体
    overall = (640 * 40.0 + 99 * 8 * 11.0) / (640 + 99 * 8) - 10.0
    rows = analyze.segments(cur, base, overall)
    assert rows[0]["value"] == "client-7"
    assert rows[0]["contribution"] > 0.5
    assert rows[0]["confidence"] > 0.5


def test_segments_uniform_drift_none_stands_out():
    """漂移均匀分布时不应突出任何子群。"""
    base = {f"client-{i}": (10, 10.0) for i in range(10)}
    cur = {f"client-{i}": (10, 15.0) for i in range(10)}
    assert all(r["score"] < 0.01 for r in analyze.segments(cur, base, 5.0))


def test_segments_zero_overall_shift():
    base = {"a": (10, 10.0), "b": (10, 12.0)}
    cur = {"a": (10, 12.0), "b": (10, 10.0)}  # 均值抵消
    assert analyze.segments(cur, base, 0.0) == []


def test_segment_new_group_uses_baseline_mean_fallback():
    """基准窗口不存在的新分组：以整体基准均值兜底并标记 new。"""
    base = {"a": (60, 10.0), "b": (60, 10.0)}
    cur = {"a": (60, 10.0), "b": (60, 10.0), "c": (60, 40.0)}
    rows = analyze.segments(cur, base, 10.0, base_mean=10.0)
    assert rows[0]["value"] == "c"
    assert rows[0]["new"] is True
    assert rows[0]["contribution"] > 0.9


def test_feature_constant_shift_still_visible():
    """常数分布的整体位移：PSI 退化为固定分箱后仍能识别。"""
    base = np.full(60, 0.6)
    cur = np.full(120, 0.9)
    row = analyze.features({"confidence": (cur, base)})[0]
    assert row["psi"] > 1.0
    assert row["direction"] == "up"


def test_summarize_mentions_top_feature_and_segment():
    rng = _rng(5)
    a = rng.normal(0.5, 0.1, 300)
    b = rng.normal(0.9, 0.1, 300)
    feats = analyze.features({"confidence": (b, a)})
    segs = [{"feature": "confidence", "dimension": "client_id", "value": "client-7",
             "share": 0.8, "contribution": 0.9, "score": 0.5, "confidence": 0.9,
             "new": False, "delta_mean": 0.4, "baseline_mean": 0.5}]
    window = {"current": ["2026-01-02 03:10:00", "2026-01-02 03:20:00"],
              "baseline": ["2026-01-02 03:00:00", "2026-01-02 03:10:00"]}
    s = analyze.summarize(feats, segs, 300, 300, window)
    assert "confidence" in s["zh"] and "confidence" in s["en"]
    assert "client-7" in s["zh"] and "client-7" in s["en"]


def test_summarize_omits_noise_segment():
    """贡献微小的子群不进摘要，避免误导。"""
    rng = _rng(5)
    a = rng.normal(0.5, 0.1, 300)
    b = rng.normal(0.9, 0.1, 300)
    feats = analyze.features({"confidence": (b, a)})
    segs = [{"feature": "confidence", "dimension": "client_id", "value": "client-14",
             "share": 0.02, "contribution": 0.03, "score": 0.011, "confidence": 0.1,
             "new": False, "delta_mean": 0.01, "baseline_mean": 0.5}]
    window = {"current": ["2026-01-02 03:10:00", "2026-01-02 03:20:00"],
              "baseline": ["2026-01-02 03:00:00", "2026-01-02 03:10:00"]}
    s = analyze.summarize(feats, segs, 300, 300, window)
    assert "client-14" not in s["zh"]
    assert "client-14" not in s["en"]


def test_summarize_empty():
    s = analyze.summarize([], [], 5, 0, {"current": ["a", "b"], "baseline": ["c", "d"]})
    assert "数据不足" in s["zh"] and "Insufficient" in s["en"]
