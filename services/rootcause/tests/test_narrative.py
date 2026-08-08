"""叙事生成单元测试。"""
import narrative


def test_feature_story_zh_significant():
    f = {"name": "prediction", "psi": 0.30, "effect_size": 2.01,
         "delta_mean": 0.396, "direction": "up", "confidence": 0.95}
    zh = narrative.feature_story(f, "zh")
    assert "prediction" in zh and "显著" in zh and "升高" in zh and "大" in zh


def test_feature_story_en_moderate():
    f = {"name": "latency_ms", "psi": 0.15, "effect_size": -0.6,
         "delta_mean": -5.0, "direction": "down", "confidence": 0.5}
    en = narrative.feature_story(f, "en")
    assert "latency_ms" in en and "moderate" in en and "decreased" in en and "medium" in en


def test_feature_story_minor_spread():
    f = {"name": "confidence", "psi": 0.05, "effect_size": 0.1,
         "delta_mean": 0.01, "direction": "spread", "confidence": 0.2}
    zh = narrative.feature_story(f, "zh")
    assert "轻微" in zh


def test_segment_story_zh_new():
    s = {"dimension": "client_id", "value": "ci-7", "feature": "prediction",
         "share": 0.5, "contribution": 0.85, "new": True, "delta_mean": 30.0}
    zh = narrative.segment_story(s, 10.0, "zh")
    assert "ci-7" in zh and "新增" in zh and "85%" in zh and "30" in zh


def test_segment_story_en_existing():
    s = {"dimension": "route", "value": "/v1/predict", "feature": "latency_ms",
         "share": 0.3, "contribution": 0.45, "new": False,
         "delta_mean": 15.0, "baseline_mean": 10.0}
    en = narrative.segment_story(s, 0.0, "en")
    assert "/v1/predict" in en and "45%" in en and "10" in en and "25" in en


def test_report_story_concentrated():
    f = {"name": "prediction", "psi": 0.30, "effect_size": 2.01,
         "delta_mean": 0.396, "direction": "up", "confidence": 0.95, "drifted": True}
    feats = [{**f, "narrative": {"zh": narrative.feature_story(f, "zh"),
                                  "en": narrative.feature_story(f, "en")}}]
    segs = [{"dimension": "client_id", "value": "ci-b", "feature": "prediction",
             "share": 0.5, "contribution": 0.85, "score": 0.5, "new": False,
             "delta_mean": 0.39, "baseline_mean": 0.6,
             "narrative": {"zh": "x", "en": "x"}}]
    window = {"current": ["2026-01-02 03:10:00", "2026-01-02 03:20:00"],
              "baseline": ["2026-01-02 03:00:00", "2026-01-02 03:10:00"]}
    s = narrative.report_story(feats, segs, 300, 300, window)
    assert s["zh"].count("\n\n") >= 2
    assert "prediction" in s["zh"] and "ci-b" in s["zh"]
    assert "prediction" in s["en"] and "ci-b" in s["en"]


def test_report_story_uniform():
    f = {"name": "prediction", "psi": 0.30, "effect_size": 0.9,
         "delta_mean": 0.3, "direction": "up", "confidence": 0.9, "drifted": True}
    feats = [{**f, "narrative": {"zh": narrative.feature_story(f, "zh"),
                                  "en": narrative.feature_story(f, "en")}}]
    segs = []  # no segments = uniform drift
    window = {"current": ["2026-01-02 03:10:00", "2026-01-02 03:20:00"],
              "baseline": ["2026-01-02 03:00:00", "2026-01-02 03:10:00"]}
    s = narrative.report_story(feats, segs, 300, 300, window)
    assert s["zh"].count("\n\n") >= 2
    assert "整体" in s["zh"] or "有限" in s["zh"]


def test_possible_causes_concentrated_new():
    feats = [{"name": "prediction", "psi": 0.3, "drifted": True}]
    segs = [{"dimension": "client_id", "value": "ci-9", "feature": "prediction",
             "score": 0.5, "contribution": 0.85, "new": True}]
    causes = narrative.possible_causes(feats, segs)
    assert len(causes) >= 1
    assert any("新" in c["zh"] or "新业务" in c["zh"] for c in causes)


def test_possible_causes_latency_only():
    feats = [{"name": "latency_ms", "psi": 0.3, "drifted": True},
             {"name": "prediction", "psi": 0.05, "drifted": False}]
    causes = narrative.possible_causes(feats, [])
    assert len(causes) >= 1
    assert any("延迟" in c["zh"] or "网络" in c["zh"] for c in causes)
