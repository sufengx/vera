"""漂移统计量单元测试。"""
from types import SimpleNamespace

import numpy as np

import drift
import metrics


def test_ks_identical_distribution():
    a = np.random.default_rng(42).normal(0.5, 0.1, 500)
    assert drift.ks_pvalue(a, a.copy()) > 0.05


def test_ks_shifted_distribution():
    rng = np.random.default_rng(42)
    a = rng.normal(0.5, 0.1, 500)
    b = rng.normal(0.9, 0.1, 500)
    assert drift.ks_pvalue(a, b) < 0.001


def test_numeric_psi_identical():
    a = np.random.default_rng(42).normal(0.5, 0.1, 500)
    assert drift.numeric_psi(a, a.copy()) < 0.05


def test_numeric_psi_shifted():
    rng = np.random.default_rng(42)
    a = rng.normal(0.5, 0.1, 500)
    b = rng.normal(0.9, 0.1, 500)
    assert drift.numeric_psi(a, b) > 0.1


def test_empty_inputs():
    assert drift.ks_pvalue([], []) == 1.0
    assert drift.numeric_psi([1.0], [1.0]) == 0.0


def test_metric_empty_baseline_is_no_drift():
    """基准窗口无数据时记为无漂移而不是跳过。"""
    cfg = SimpleNamespace(ks_threshold=0.05, psi_threshold=0.1)
    actual = np.array([0.5, 0.6, 0.7, 0.4, 0.8])
    for test, score in (("ks", 1.0), ("psi", 0.0)):
        r = metrics._compute("confidence", actual, np.array([]), test, cfg)
        assert r is not None and not r.drifted and r.score == score
