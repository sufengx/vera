"""根因服务：对比基准/当前窗口，输出 top-K 特征与子群贡献报告。"""
import logging
import re
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException

import analyze
import narrative
import store as store_mod
from config import Config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = FastAPI()
app.state.cfg = Config()

FEATURES = store_mod.COLUMNS
_SAFE = re.compile(r"^[A-Za-z0-9_/.\-:]+$")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/v1/rootcause")
def rootcause(
    current_minutes: int | None = None,
    baseline_offset: int | None = None,
    baseline_minutes: int | None = None,
    current_from: str | None = None,
    current_to: str | None = None,
    baseline_from: str | None = None,
    baseline_to: str | None = None,
    model: str | None = None,
    route: str | None = None,
    top_k: int | None = None,
    dimensions: str | None = None,
):
    """根因报告：输入时间段/模型/路由，输出 top-K 特征差异与子群贡献。"""
    cfg = app.state.cfg
    for p, name in ((model, "model"), (route, "route")):
        if p and not _SAFE.match(p):
            raise HTTPException(400, f"invalid {name}")
    dims = [d.strip() for d in (dimensions or "").split(",") if d.strip()] or cfg.dimensions
    for d in dims:
        if d not in store_mod.DIMENSIONS:
            raise HTTPException(400, f"invalid dimension: {d}")
    current, baseline = resolve_windows(
        cfg, current_minutes, baseline_offset, baseline_minutes,
        current_from, current_to, baseline_from, baseline_to,
    )
    report = analyze_report(cfg, store_mod.Store(cfg), current, baseline, model or "", route or "",
                            top_k or cfg.top_k, dims)
    return report


def resolve_windows(cfg, cur_min=None, off=None, base_min=None,
                    cur_from=None, cur_to=None, base_from=None, base_to=None):
    """窗口解析：优先显式时间段（当前窗口缺省基准取其前等长窗口），否则按分钟参数计算。"""
    if cur_from and cur_to:
        current = (parse_ts(cur_from, "current_from"), parse_ts(cur_to, "current_to"))
        if base_from and base_to:
            baseline = (parse_ts(base_from, "baseline_from"), parse_ts(base_to, "baseline_to"))
        else:
            length = current[1] - current[0]
            baseline = (current[0] - length, current[1] - length)
    else:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        current = (now - timedelta(minutes=cur_min or cfg.current_minutes), now)
        baseline = (
            now - timedelta(minutes=(off or cfg.baseline_offset) + (base_min or cfg.baseline_minutes)),
            now - timedelta(minutes=off or cfg.baseline_offset),
        )
    return current, baseline


def parse_ts(s, name):
    """接受 ISO8601（含时区）与 ClickHouse 无时区格式，统一转 UTC 无时区。"""
    try:
        s = s.strip()
        if "T" in s:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            return dt.astimezone(timezone.utc).replace(tzinfo=None)
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        raise HTTPException(400, f"invalid {name}, expect 'YYYY-MM-DD HH:MM:SS' or ISO8601")


def analyze_report(cfg, st, current, baseline, model, route, top_k, dims):
    window = {"current": [_fmt(x) for x in current], "baseline": [_fmt(x) for x in baseline]}
    n_cur = st.count(*current, model, route)
    n_base = st.count(*baseline, model, route)
    if n_cur < cfg.min_events:
        return {"status": "insufficient_data", "window": window, "n_baseline": n_base, "n_current": n_cur}
    samples = {f: (st.series(f, *current, model, route), st.series(f, *baseline, model, route)) for f in FEATURES}
    all_feats = analyze.features(samples)
    drifted = {f["name"] for f in all_feats if f["drifted"]}
    feats = all_feats[:top_k]
    segs = analyze_segments(cfg, st, current, baseline, model, route, samples, dims, drifted, top_k)
    return {
        "status": "ok",
        "window": window,
        "n_baseline": n_base,
        "n_current": n_cur,
        "features": feats,
        "segments": segs,
        "summary": analyze.summarize(feats, segs, n_cur, n_base, window),
        "causes": narrative.possible_causes(all_feats, segs),
    }


def analyze_segments(cfg, st, current, baseline, model, route, samples, dims, drifted, top_k):
    """各维度分组对比：只对已漂移特征找集中的子群，全局取 top-K。"""
    rows = []
    for dim in dims:
        cur_g = st.segment_stats(dim, *current, model, route, cfg.segment_limit)
        base_g = st.segment_stats(dim, *baseline, model, route, cfg.segment_limit)
        if not cur_g or not base_g:
            continue
        for f in FEATURES:
            if f not in drifted:
                continue
            cur = {g: (n, s[f]) for g, (n, s) in cur_g.items() if s[f] is not None}
            base = {g: (n, s[f]) for g, (n, s) in base_g.items() if s[f] is not None}
            if not cur or not base:
                continue
            actual, expected = samples[f]
            overall = float(actual.mean() - expected.mean()) if actual.size and expected.size else 0.0
            base_mean = float(expected.mean()) if expected.size else 0.0
            for row in analyze.segments(cur, base, overall, base_mean):
                row.update(dimension=dim, feature=f)
                row["narrative"] = {"zh": narrative.segment_story(row, base_mean, "zh"),
                                    "en": narrative.segment_story(row, base_mean, "en")}
                rows.append(row)
    rows.sort(key=lambda r: (r["score"], abs(r["contribution"])), reverse=True)
    return rows[:top_k]


def _fmt(dt):
    return f"{dt:%Y-%m-%d %H:%M:%S}"
