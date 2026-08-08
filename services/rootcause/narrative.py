"""根因叙事的限词与文本生成（纯函数，无 IO）。"""
import math

# ── 限词 ──────────────────────────────────────────────
_PSI_TIERS = [(0.25, ("显著", "significant")), (0.1, ("中等", "moderate")), (0, ("轻微", "minor"))]
_EFFECT_TIERS = [(0.8, ("大", "large")), (0.5, ("中", "medium")), (0, ("小", "small"))]
_CONF_TIERS = [(0.8, ("高", "high")), (0, ("低", "low"))]


def _pick(tiers, v):
    for t, labels in tiers:
        if v >= t:
            return labels
    return tiers[-1][1]


def _qualify_psi(v, lang):
    return _pick(_PSI_TIERS, v)[0 if lang == "zh" else 1]


def _qualify_effect(v, lang):
    return _pick(_EFFECT_TIERS, v)[0 if lang == "zh" else 1]


def _qualify_conf(v, lang):
    return _pick(_CONF_TIERS, v)[0 if lang == "zh" else 1]


def feature_story(f, lang):
    """单个特征的叙事文本。"""
    psi_q = _qualify_psi(f["psi"], lang)
    eff_q = _qualify_effect(abs(f["effect_size"]), lang)
    conf_q = _qualify_conf(f["confidence"], lang)
    if lang == "zh":
        arrow = {"up": "升高", "down": "降低", "spread": "波动"}[f["direction"]]
        return (f"{f['name']} 分布变化{psi_q}：均值{arrow} {abs(f['delta_mean']):.3g}，"
                f"效应量{eff_q}。该特征漂移可靠性{conf_q}。")
    dir_word = {"up": "increased", "down": "decreased", "spread": "became more variable"}[f["direction"]]
    return (f"{f['name']} shows a {psi_q} distribution shift: "
            f"mean {dir_word} by {abs(f['delta_mean']):.3g}, {eff_q.lower()} effect size. "
            f"Drift confidence is {conf_q.lower()}.")


def segment_story(s, base_mean, lang):
    """单个子群的叙事文本。base_mean 为基准窗口该特征的总体均值。"""
    contrib_pct = round(s["contribution"] * 100)
    share_pct = round(s["share"] * 100)
    if s.get("new"):
        delta = abs(s["delta_mean"])
        if lang == "zh":
            body = (f"{s['dimension']}={s['value']} 是新增群体（{share_pct}% 流量），"
                    f"导致 {s['feature']} 漂移的 {contrib_pct}%。"
                    f"该群体均值为 {s['delta_mean']:.3g}，相对于整体基准 {base_mean:.3g} 偏移了 {delta:.3g}。")
        else:
            body = (f"{s['dimension']}={s['value']} is a new segment ({share_pct}% traffic), "
                    f"accounting for {contrib_pct}% of the {s['feature']} drift. "
                    f"Its mean is {s['delta_mean']:.3g}, offset from the overall baseline ({base_mean:.3g}) by {delta:.3g}.")
    else:
        bm = s.get("baseline_mean", base_mean)
        if lang == "zh":
            body = (f"{s['dimension']}={s['value']} 贡献了 {s['feature']} 漂移的 {contrib_pct}%，"
                    f"占当前流量 {share_pct}%。该群体均值从 {bm:.3g} 变为 {s['delta_mean'] + bm:.3g}。")
        else:
            body = (f"{s['dimension']}={s['value']} accounts for {contrib_pct}% of the {s['feature']} drift, "
                    f"representing {share_pct}% of traffic. "
                    f"Its mean shifted from {bm:.3g} to {s['delta_mean'] + bm:.3g}.")
    return body


def report_story(features, segments, n_cur, n_base, window):
    """多段叙事报告（中英双语）。"""
    if not features:
        return {"zh": "窗口数据不足，暂无可解释的根因分析。", "en": "Insufficient data for root cause analysis."}
    f = features[0]

    def _zh():
        cur_range = f"{window['current'][0][11:16]} ~ {window['current'][1][11:16]}"
        base_range = f"{window['baseline'][0][11:16]} ~ {window['baseline'][1][11:16]}"
        p1 = f"在 {cur_range} 期间（{n_cur} 条事件），对比基准窗口 {base_range}（{n_base} 条），检测到模型行为变化："
        p2 = feature_story(f, "zh")
        # 模式解读
        top_seg = segments[0] if segments else None
        if top_seg and top_seg["score"] >= 0.1:
            contrib = abs(top_seg["contribution"])
            if top_seg["new"]:
                p3 = f"该变化由新出现的子群 {top_seg['dimension']}={top_seg['value']} 主导，可能是新业务或新客户端接入。"
            elif contrib >= 0.7:
                p3 = (f"该变化集中在 {top_seg['dimension']}={top_seg['value']}"
                      f"（贡献 {round(contrib * 100)}%），可能是该群体的输入数据或行为发生了变化。")
            else:
                p3 = (f"该变化在多个子群中均有分布，最大贡献来自 {top_seg['dimension']}={top_seg['value']}"
                      f"（{round(contrib * 100)}%），可能是上游数据或模型层面的整体变化。")
            p4 = segment_story(top_seg, 0, "zh")
        else:
            drifted_names = [x["name"] for x in features if x["drifted"]]
            if len(drifted_names) >= 2:
                p3 = "多个信号同时出现漂移，变化范围较广，可能是模型或上游数据发生整体变化。"
            elif f["name"] == "latency_ms":
                p3 = "仅延迟出现漂移而模型输出不变，可能是基础设施或网络延迟。"
            else:
                p3 = f"仅 {f['name']} 出现漂移，其他信号正常，变化范围有限。"
            p4 = ""
        parts = [p1, p2, p3]
        if p4:
            parts.append(p4)
        return "\n\n".join(parts)

    def _en():
        cur_range = f"{window['current'][0][11:16]} ~ {window['current'][1][11:16]}"
        base_range = f"{window['baseline'][0][11:16]} ~ {window['baseline'][1][11:16]}"
        p1 = f"During {cur_range} ({n_cur} events) vs baseline {base_range} ({n_base} events), a behavior change was detected:"
        p2 = feature_story(f, "en")
        top_seg = segments[0] if segments else None
        if top_seg and top_seg["score"] >= 0.1:
            contrib = abs(top_seg["contribution"])
            if top_seg["new"]:
                p3 = f"The change is driven by a new segment {top_seg['dimension']}={top_seg['value']}, likely from a new client or workload."
            elif contrib >= 0.7:
                p3 = (f"The change concentrates in {top_seg['dimension']}={top_seg['value']}"
                      f" ({round(contrib * 100)}% contribution), suggesting a shift in this segment's data distribution.")
            else:
                p3 = (f"The change is distributed across multiple segments, "
                      f"with the largest contribution from {top_seg['dimension']}={top_seg['value']}"
                      f" ({round(contrib * 100)}%), suggesting a model-level or upstream data change.")
            p4 = segment_story(top_seg, 0, "en")
        else:
            drifted_names = [x["name"] for x in features if x["drifted"]]
            if len(drifted_names) >= 2:
                p3 = "Multiple signals drifted simultaneously — the change is broad, likely from a model update or upstream data shift."
            elif f["name"] == "latency_ms":
                p3 = "Only latency drifted while model output stayed normal — likely infrastructure or network latency."
            else:
                p3 = f"Only {f['name']} drifted while other signals remained normal — the impact is limited in scope."
            p4 = ""
        parts = [p1, p2, p3]
        if p4:
            parts.append(p4)
        return "\n\n".join(parts)

    return {"zh": _zh(), "en": _en()}


def possible_causes(features, segments):
    """基于漂移模式生成可能原因列表。"""
    drifted = [f for f in features if f["drifted"]]
    if not drifted:
        return []
    top_seg = segments[0] if segments else None
    causes = []
    names = [f["name"] for f in drifted]

    # 子群集中模式
    if top_seg and top_seg["score"] >= 0.1:
        if top_seg["new"]:
            causes.append({
                "zh": f"{top_seg['dimension']}={top_seg['value']} 是新出现的群体，可能是新业务或新客户端接入",
                "en": f"{top_seg['dimension']}={top_seg['value']} is a new segment, likely from a new client or workload onboarding",
            })
        elif abs(top_seg["contribution"]) >= 0.7:
            causes.append({
                "zh": f"{top_seg['dimension']}={top_seg['value']} 的输入数据或行为模式可能发生了变化",
                "en": f"{top_seg['dimension']}={top_seg['value']} may have experienced a data distribution or behavior shift",
            })
    elif len(names) >= 2:
        causes.append({
            "zh": "多个信号同时漂移，可能是模型版本更新或上游数据整体变化",
            "en": "Multiple signals drifted simultaneously — likely a model version update or upstream data distribution shift",
        })
    else:
        if names[0] == "latency_ms":
            causes.append({
                "zh": "仅延迟漂移而模型输出正常，可能是基础设施或网络延迟",
                "en": "Only latency drifted while model output stayed normal — likely infrastructure or network latency",
            })
        elif names[0] == "confidence":
            causes.append({
                "zh": "模型置信度分布发生变化，可能是输入数据质量或难度分布发生了改变",
                "en": "Model confidence distribution changed — input data quality or difficulty distribution may have shifted",
            })
        elif names[0] == "prediction":
            causes.append({
                "zh": "模型预测值分布发生变化，可能是输入特征分布漂移或模型版本更新",
                "en": "Model prediction distribution shifted — possible input feature drift or model version update",
            })
    return causes[:3]
