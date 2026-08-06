-- 漂移检测结果表。
-- 每次扫描为每个指标写一行，score 为该指标的漂移统计量。
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
