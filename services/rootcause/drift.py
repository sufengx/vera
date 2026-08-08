"""漂移统计量：KS 检验与 PSI。"""
import numpy as np
from scipy import stats

_EPS = 1e-6


def ks_pvalue(actual, expected):
    """KS 检验 p 值，越小表示分布差异越大。"""
    if len(actual) < 2 or len(expected) < 2:
        return 1.0
    return float(stats.ks_2samp(actual, expected).pvalue)


def numeric_psi(actual, expected, bins=10):
    """数值分布 PSI。分箱边界取基准分布的分位数；
    基准为常数分布时退化为覆盖两窗口取值范围的固定分箱。"""
    if len(actual) < 2 or len(expected) < 2:
        return 0.0
    edges = _edges(actual, expected, bins)
    if len(edges) < 2:
        return 0.0
    return _psi(_hist(actual, edges), _hist(expected, edges))


def _edges(actual, expected, bins):
    edges = np.unique(np.quantile(expected, np.linspace(0, 1, bins + 1)))
    if len(edges) >= 2:
        return edges
    lo, hi = float(np.min([actual.min(), expected.min()])), float(np.max([actual.max(), expected.max()]))
    if hi - lo < 1e-12:
        return np.array([lo])
    return np.unique(np.linspace(lo, hi, bins + 1))


def _hist(values, edges):
    idx = np.clip(np.searchsorted(edges, np.asarray(values, dtype=float), side="left"), 0, len(edges) - 2)
    return np.bincount(idx, minlength=len(edges) - 1).astype(float)


def _psi(a, b):
    a = a / a.sum()
    b = b / b.sum()
    a = np.clip(a, _EPS, 1.0)
    b = np.clip(b, _EPS, 1.0)
    return float(np.sum((a - b) * np.log(a / b)))
