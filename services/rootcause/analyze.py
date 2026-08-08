"""根因分析核心：特征贡献与子群贡献的启发式度量（纯函数，无 IO）。"""
import numpy as np

import drift

_FEATURE_WEIGHT = 0.35  # 合成分里均值位移的权重
_MAX_EFFECT = 3.0  # 效应量封顶


def features(samples):
    """baseline vs current 的每个数值特征差异，按贡献分降序。
    samples 为 {特征名: (当前数组, 基准数组)}；score = PSI + 0.35 × min(|Cohen's d|, 3)。
    """
    rows = []
    for name, (actual, expected) in samples.items():
        if actual.size < 2 or expected.size < 2:
            continue
        psi = drift.numeric_psi(actual, expected)
        ks = drift.ks_pvalue(actual, expected)
        effect = _effect_size(actual, expected)
        score = psi + _FEATURE_WEIGHT * min(abs(effect), _MAX_EFFECT)
        rows.append({
            "name": name,
            "psi": psi,
            "ks_pvalue": ks,
            "delta_mean": float(actual.mean() - expected.mean()),
            "delta_std": float(actual.std(ddof=1) - expected.std(ddof=1)),
            "effect_size": effect,
            "direction": _direction(actual, expected),
            "score": score,
            "confidence": _confidence(min(actual.size, expected.size), score),
            "drifted": psi > 0.1 or ks < 0.05,
        })
    rows.sort(key=lambda r: r["score"], reverse=True)
    return rows


def segments(cur, base, overall_shift, base_mean=0.0, top_n=50):
    """子群贡献：对比各群体在当前/基准窗口的占比与均值位移。
    cur/base 为 {分组: (样本数, 均值)}；按占比×|子群位移−整体位移| 排序，
    找出漂移集中的子群；漂移均匀分布时所有分数趋近 0。
    基准窗口不存在的新分组以整体基准均值兜底，标记 new=true。
    """
    if not overall_shift or abs(overall_shift) < 1e-9:
        return []
    n_total = max(sum(n for n, _ in cur.values()), 1)
    rows = []
    for g, (n, m) in cur.items():
        item = base.get(g)
        if item is None:
            if n < 2:
                continue
            nb, mb, new = 0, base_mean, True
        else:
            nb, mb = item
            if n < 2 or nb < 2:
                continue
            new = False
        shift = m - mb
        share = n / n_total
        rows.append({
            "value": g,
            "n_current": n,
            "share": round(share, 4),
            "delta_mean": shift,
            "contribution": round(max(-1.0, min(1.0, share * shift / overall_shift)), 4),
            "deviation": shift - overall_shift,
            "score": round(share * abs(shift - overall_shift) / abs(overall_shift), 4),
            "confidence": round(min(1.0, n / 200) * min(1.0, abs(share * shift / overall_shift)), 3),
            "new": new,
        })
    rows.sort(key=lambda r: (r["score"], abs(r["contribution"])), reverse=True)
    return rows[:top_n]


def summarize(features, segments, n_cur, n_base, window):
    """生成可解释报告的中英文摘要。"""
    if not features:
        return {"zh": "窗口数据不足，暂无可解释的根因分析。", "en": "Insufficient data for root cause analysis."}
    f = features[0]
    arrow = {"up": "上升", "down": "下降", "spread": "分布变宽"}[f["direction"]]
    zh = (f"当前窗口（{window['current'][0]} ~ {window['current'][1]}，{n_cur} 条事件）"
          f"对比基准窗口（{window['baseline'][0]} ~ {window['baseline'][1]}，{n_base} 条）："
          f"主要漂移来自 {f['name']}（PSI={f['psi']:.2f}，均值{arrow} {abs(f['delta_mean']):.3g}，"
          f"置信度 {f['confidence']:.0%}）")
    en = (f"Current window ({window['current'][0]} ~ {window['current'][1]}, {n_cur} events) vs "
          f"baseline ({window['baseline'][0]} ~ {window['baseline'][1]}, {n_base} events): "
          f"primary drift from {f['name']} (PSI={f['psi']:.2f}, mean {f['direction']} "
          f"{abs(f['delta_mean']):.3g}, confidence {f['confidence']:.0%})")
    if segments and segments[0]["score"] >= 0.1:
        s = segments[0]
        zh += (f"；子群分析显示 {s['feature']} 的漂移集中在 {s['dimension']}={s['value']}"
               f"（当前占比 {s['share']:.0%}，贡献 {s['contribution']:.0%}）")
        en += (f"; segment analysis: {s['feature']} drift concentrates in {s['dimension']}={s['value']}"
               f" ({s['share']:.0%} share, {s['contribution']:.0%} contribution)")
    return {"zh": zh, "en": en}


def _effect_size(a, b):
    """Cohen's d：均值差 / 合并标准差；标准差相对取值尺度可忽略时返回 0。"""
    na, nb = len(a), len(b)
    pooled = np.sqrt(((na - 1) * a.var(ddof=1) + (nb - 1) * b.var(ddof=1)) / (na + nb - 2)) if na + nb > 2 else 0.0
    scale = max(abs(float(a.mean())), abs(float(b.mean())), 1e-9)
    if pooled < 1e-12 * scale:
        return 0.0
    return float((a.mean() - b.mean()) / pooled)


def _direction(a, b):
    """漂移方向：均值位移相对取值尺度可感知时按符号，否则记为 spread。"""
    shift = float(a.mean() - b.mean())
    scale = max(abs(float(a.mean())), abs(float(b.mean())), 1e-9)
    if abs(shift) > 0.05 * scale:
        return "up" if shift > 0 else "down"
    return "spread"


def _confidence(n, score):
    """置信度 = 样本充分度 × 差异强度，0~1。"""
    return round(min(1.0, n / 200) * min(1.0, score / 0.5), 3)
