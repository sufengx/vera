// Package config 从环境变量加载网关配置。
package config

import (
	"os"
	"strconv"
	"time"
)

// Config 网关运行参数。
type Config struct {
	Addr          string
	Upstream      string
	ClickHouse    string
	DB            string
	Table         string
	ModelName     string
	ModelVersion  string
	ContainerID   string
	BatchSize     int
	BatchInterval time.Duration
	RetryMax      int
	QueueSize     int
}

// Load 读取全部配置项，缺省用默认值。
func Load() Config {
	return Config{
		Addr:          env("GATEWAY_ADDR", ":8080"),
		Upstream:      env("GATEWAY_UPSTREAM", "http://127.0.0.1:9000"),
		ClickHouse:    env("CLICKHOUSE_ADDR", "http://127.0.0.1:8123"),
		DB:            env("CLICKHOUSE_DB", "vera"),
		Table:         env("CLICKHOUSE_TABLE", "events"),
		ModelName:     env("MODEL_NAME", "ctr"),
		ModelVersion:  env("MODEL_VERSION", "v1"),
		ContainerID:   os.Getenv("CONTAINER_ID"),
		BatchSize:     envInt("BATCH_SIZE", 500),
		BatchInterval: envDur("BATCH_INTERVAL", 2*time.Second),
		RetryMax:      envInt("RETRY_MAX", 3),
		QueueSize:     envInt("QUEUE_SIZE", 10000),
	}
}

func env(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}

func envInt(key string, def int) int {
	if v := os.Getenv(key); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			return n
		}
	}
	return def
}

func envDur(key string, def time.Duration) time.Duration {
	if v := os.Getenv(key); v != "" {
		if d, err := time.ParseDuration(v); err == nil {
			return d
		}
	}
	return def
}
