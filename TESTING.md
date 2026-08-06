[![English](https://img.shields.io/badge/English-blue?style=for-the-badge)](TESTING.md) [![中文](https://img.shields.io/badge/%E4%B8%AD%E6%96%87-green?style=for-the-badge)](TESTING.zh-CN.md)

# Testing Guide

How to verify Vera works: benchmarks, load tests, and the full drift-detection demo.

---

# Benchmarks

Gateway benchmarks (2026-08):

| Benchmark             | Latency     | Note                                      |
| --------------------- | ----------- | ----------------------------------------- |
| `BenchmarkHandler`    | 120.7µs/op  | Full proxy path, including event collection |
| `BenchmarkBuildEvent` | 2.2µs/op    | Event collection overhead only            |

Load tests (vegeta, see `tools/loadtest`):

| Scenario | Rate       | Duration | Requests | Success | p99   | Event loss |
| -------- | ---------- | -------- | -------- | ------- | ----- | ---------- |
| A        | 200 req/s  | 30s      | 6,000    | 100%    | 2.4ms | 0          |
| B        | 1000 req/s | 30s      | 30,000   | 100%    | 3.6ms | 0          |

![Load test: 1000 req/s](assets/img/loadtest-1000rps.png)

---

# Drift Demo

Start the stack with drift simulation — the mock model shifts its output distribution 60 seconds after startup:

```bash
docker compose -f infra/docker-compose/docker-compose.yml \
  -f infra/docker-compose/docker-compose.drift-demo.yml up --build
```

Open http://localhost:8501 and watch the cycle:

1. First ~60 s — everything green, traffic building up.
2. ~90–120 s — the mock model drifts; `prediction`, `confidence` and `latency_ms` turn red, the banner switches to red and webhook alerts fire.
3. Later — the baseline window rolls past the drift point and signals recover to green. That is the *new normal*, not a false alarm.

Query drift results directly:

```bash
curl -s -u default:vera "http://localhost:8123/?query=SELECT+metric,score,threshold,drifted+FROM+vera.drift_results+ORDER+BY+timestamp+DESC+FORMAT+CSV"
```

Reset the environment afterwards:

```bash
docker compose -f infra/docker-compose/docker-compose.yml down -v
```

---

# Unit Tests

Run the Go gateway tests:

```bash
cd services/gateway && go test ./...
```

Run the Python detector tests:

```bash
cd services/detector && pytest tests -q
```

CI runs lint, unit tests, a Docker build of all images, and a full docker-compose integration test that asserts events and drift results land in ClickHouse (see `.github/workflows/ci.yml`).
