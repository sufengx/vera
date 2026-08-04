-- 推理观测事件表。
-- 隐私默认：仅存摘要/哈希，不存原文；TTL 90 天自动过期。
CREATE TABLE IF NOT EXISTS vera.events (
    event_id UUID,
    timestamp DateTime64(3),
    request_id String,
    model_name String,
    model_version String,
    route String,
    client_id String,
    input_summary_hash String,
    input_features String,
    input_embedding_ref String,
    prediction String,
    confidence Float64,
    latency_ms Float64,
    server_hostname String,
    container_id String,
    label Nullable(String),
    label_timestamp Nullable(DateTime64(3)),
    sampling_flag Bool,
    privacy_mask_level Enum8('none' = 0, 'partial' = 1, 'full' = 2)
) ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (model_name, timestamp)
TTL toDateTime(timestamp) + INTERVAL 90 DAY
