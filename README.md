[![English](https://img.shields.io/badge/English-blue?style=for-the-badge)](README.md) [![中文](https://img.shields.io/badge/%E4%B8%AD%E6%96%87-green?style=for-the-badge)](README.zh-CN.md)

# Vera

## Open-source AI Observability & Reliability Platform

Vera is an open-source observability platform for production AI systems.

It provides a zero-intrusion gateway to collect inference signals, detect model behavior changes, analyze root causes, and build a foundation for reliable AI operations.

Vera helps answer:

> Why did my AI system become worse?

Whether it is caused by data distribution changes, model degradation, prompt changes, retrieval issues, or infrastructure failures, Vera aims to provide visibility and automated response for production AI workloads.

---

## Highlights

- **Zero-code integration**
  - HTTP reverse proxy gateway intercepts inference traffic without modifying existing applications.
  - Asynchronous event collection avoids blocking inference requests.

- **Privacy-first by design**
  - Raw user data never leaves the process by default.
  - Only summaries and SHA-256 hashes are collected.
  - Configurable privacy masking levels.

- **High-throughput event pipeline**
  - Batch compressed event ingestion into ClickHouse.
  - Designed for large-scale OLAP analysis and real-time detection.

- **Built-in drift detection**
  - KS test and PSI based drift engine over event signals.
  - Webhook alerting and a big-screen live dashboard.

- **Enterprise-ready architecture**
  - Self-hosted deployment.
  - Docker Compose local environment.
  - Kubernetes deployment planned.

---

# Architecture

```text
                         AI Applications

        ┌──────────────┬──────────────┬──────────────┐
        │ ML Models    │ LLM Services │ AI Agents    │
        └──────┬───────┴──────┬───────┴──────┬───────┘
               │              │              │

               ▼              ▼              ▼

                    ┌────────────────┐
                    │ Vera Gateway   │
                    │ (Go Proxy)     │
                    │ Event Capture  │
                    └───────┬────────┘

                            ▼

                    ┌───────────────┐
                    │ ClickHouse    │
                    │ Event Store   │
                    └───────┬───────┘

                            ▼

        ┌───────────────────┴───────────────────┐
        │                                       │
        ▼                                       ▼

┌───────────────┐                    ┌────────────────┐
│ Detection     │                    │ Root Cause     │
│ Engine        │                    │ Analysis       │
└───────┬───────┘                    └───────┬────────┘

        ▼                                    ▼

              Dashboard / Alerting / Mitigation
```

---

# Current Status

The end-to-end pipeline is already working:

```text
Gateway
   ↓
Event Collection
   ↓
ClickHouse Storage
   ↓
Drift Detection → Dashboard & Alerts
```

Verified:

* SHA-256 based privacy protection enabled by default
* gzip batch encoding
* Failed event retry mechanism
* ClickHouse authentication support
* Drift detection engine (KS test / PSI) with webhook alerting
* Big-screen dashboard for live metrics and drift status
* Docker Compose based integration testing

Current development focus:

* Python SDK
* Embedding drift detection
* Root cause analysis
* LLM observability support
* Automated mitigation

See [Roadmap](#roadmap).

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

# Components

| Path                   | Description                                                            | Status      |
| ---------------------- | ---------------------------------------------------------------------- | ----------- |
| `services/gateway`     | Go inference gateway: proxy + event collection + async ClickHouse sink | ✅ Available |
| `services/detector`    | Drift detection engine (KS test / PSI on event signals)                | ✅ Available |
| `services/dashboard`   | React big-screen dashboard: bilingual, metrics, charts and drift alerts | ✅ Available |
| `tools/simulator`      | Mock model service and traffic generator                               | ✅ Available |
| `infra/docker-compose` | Local development environment                                          | ✅ Available |
| `sdk/python`           | Python SDK for application-level signals                               | 🚧 Planned  |
| `services/rootcause`   | Root cause analysis engine                                             | 🚧 Planned  |
| `charts/helm`          | Kubernetes deployment templates                                        | 🚧 Planned  |

---

# Quick Start

Prerequisites:

* Docker
* Docker Compose

Start Vera:

```bash
docker compose -f infra/docker-compose/docker-compose.yml up --build
```

This starts:

* `gateway` - AI inference gateway
* `model-mock` - simulated model service
* `loadgen` - traffic generator
* `clickhouse` - event storage
* `detector` - drift detection engine
* `dashboard` - big-screen dashboard at http://localhost:8501

Test inference:

```bash
curl -s -X POST http://localhost:8080/v1/predict \
  -H "Content-Type: application/json" \
  -H "X-Model-Name: ctr" \
  -H "X-Model-Version: v1" \
  -H "X-Client-ID: demo" \
  -d '{"price":42.5,"user_history_len":88,"item_rating":4.2,"is_new_user":0,"hour":14}'
```

Query collected events:

```bash
curl -s "http://localhost:8123/?query=SELECT%20count(*)%20FROM%20vera.events%20FORMAT%20CSV"
```

Running a real model already? See [Connecting a Real AI Model](#connecting-a-real-ai-model).

---

# Connecting a Real AI Model

Vera needs no SDK and no code changes. Your model keeps serving on its own URL — you point the gateway at it and route inference traffic through the gateway instead:

```text
your app ──► Vera Gateway :8080 ──► your model service (unchanged)
```

## 1. Point the gateway at your model

Set `GATEWAY_UPSTREAM` to your model service (a compose override, or `.env`):

```yaml
# docker-compose.override.yml
services:
  gateway:
    environment:
      GATEWAY_UPSTREAM: "http://your-model-host:9000"
```

The gateway proxies every request verbatim — path, headers and body — so existing clients keep working. Only the base URL changes to `http://<vera-host>:8080`.

## 2. Tell Vera about the request (optional headers)

| Header            | Meaning                                    |
| ----------------- | ------------------------------------------ |
| `X-Client-ID`     | Caller / application (default: client IP)  |
| `X-Model-Name`    | Model identifier (default: `MODEL_NAME`)   |
| `X-Model-Version` | Model version (default: `MODEL_VERSION`)   |
| `X-Request-ID`    | Your request trace ID                      |

## 3. What Vera records from each call

* SHA-256 hash of the request body — raw input is never stored by default.
* Response latency, measured by the gateway itself.
* `prediction` and `confidence`, parsed from the upstream **JSON response**. These are the two signals that feed drift detection, so return them from your model:

```json
{"prediction": 0.73, "confidence": 0.91}
```

`prediction` may be a string or a number; `confidence` a number in [0, 1]. If absent, the fields are recorded empty and skipped by the detector — latency drift is still monitored.

Verify events are landing:

```bash
curl -s "http://localhost:8123/?query=SELECT%20count(*)%20FROM%20vera.events%20FORMAT%20CSV"
```

## 4. Gateway configuration

| Environment variable | Default                | Meaning                                    |
| -------------------- | ---------------------- | ------------------------------------------ |
| `GATEWAY_ADDR`       | `:8080`                | Gateway listen address                     |
| `GATEWAY_UPSTREAM`   | `http://127.0.0.1:9000`| Upstream model service URL                 |
| `MODEL_NAME`         | `ctr`                  | Default model name (when no header)        |
| `MODEL_VERSION`      | `v1`                   | Default model version                      |
| `CLICKHOUSE_ADDR`    | `http://127.0.0.1:8123`| ClickHouse HTTP endpoint                   |
| `CLICKHOUSE_USER` / `CLICKHOUSE_PASSWORD` | — | ClickHouse credentials             |
| `BATCH_SIZE`         | 500                    | Events per batch write                     |
| `BATCH_INTERVAL`     | 2s                     | Max flush interval                         |
| `RETRY_MAX`          | 3                      | Sink retries before dropping               |
| `QUEUE_SIZE`         | 10000                  | In-memory event queue (drop when full)     |

## 5. Tune detection to your traffic

The detector compares the current window (last N minutes) against a baseline (M minutes ending K minutes ago). Rules of thumb:

* **Low traffic** (fewer than ~10 events/min): widen the windows, e.g. `DETECTOR_CURRENT_MINUTES=30`, `DETECTOR_BASELINE_OFFSET=60`, `DETECTOR_BASELINE_MINUTES=120`, or lower `DETECTOR_MIN_EVENTS` (default 50 — windows with fewer events are skipped).
* **Daily seasonality**: set `DETECTOR_BASELINE_OFFSET=1440` so the baseline is the same time yesterday.
* **Alarm sensitivity**: raise `DETECTOR_KS_THRESHOLD` / `DETECTOR_PSI_THRESHOLD` to tolerate more noise, lower to react earlier.

## 6. Wire alerts

Set a Slack-compatible webhook (Slack Incoming Webhooks, or any receiver speaking the Slack payload format):

```bash
# in infra/docker-compose/.env — not committed
ALERT_WEBHOOK_URL=https://hooks.slack.com/services/T000/B000/XXX
```

Alerts are debounced (one per anomaly episode, re-armed on recovery) and cooled down 15 minutes (`ALERT_COOLDOWN_MINUTES`). Payload: `{"text": "[Vera] <metric> drifted: score=..., threshold=..."}`.

## What Vera covers today

Out of the box it detects distribution drift on `prediction` (PSI), `confidence` (KS) and `latency_ms` (KS), with a live dashboard and webhook alerts. Not yet: SDK-based application signals, embedding drift, root-cause analysis, prompt/tool tracing — see [Roadmap](#roadmap).

---

# Event Model

Each inference request generates an observability event.

Important fields:

| Field                | Description                 |
| -------------------- | --------------------------- |
| `event_id`           | Unique event identifier     |
| `request_id`         | Request tracing ID          |
| `model_name`         | Model identifier            |
| `model_version`      | Model version               |
| `input_summary_hash` | SHA-256 request fingerprint |
| `prediction`         | Model output                |
| `confidence`         | Confidence score            |
| `latency_ms`         | Request latency             |
| `privacy_mask_level` | none / partial / full       |
| `label`              | Optional delayed feedback   |

![Events in ClickHouse](assets/img/events.png)

Events are uploaded asynchronously.

The inference path is never blocked by storage failures.

---

# Drift Detection

## What Vera detects

The detector (`services/detector`) periodically compares the current event window against a baseline window and flags signals whose distribution has shifted:

| Signal       | Test | Meaning                                      | Threshold      |
| ------------ | ---- | -------------------------------------------- | -------------- |
| `prediction` | PSI  | Distribution of model output values          | PSI > 0.1      |
| `confidence` | KS   | Distribution of model confidence scores      | p-value < 0.05 |
| `latency_ms` | KS   | Distribution of response latency             | p-value < 0.05 |

A signal is *drifted* when its score crosses the threshold. Results are stored in `vera.drift_results` and shown on the dashboard; drifted signals trigger alerts to a Slack-compatible webhook (`ALERT_WEBHOOK_URL`).

## How it works

* **Window semantics.** The detector keeps a *current window* (the last N minutes of events) and a *baseline window* (an M-minute slice ending K minutes ago). It compares the two every scan cycle. Window sizes are environment variables, so sensitivity is tunable.
* **KS test (confidence, latency).** Computes the largest distance between the two distributions' cumulative curves; the resulting p-value is the probability that they come from the same distribution. p < 0.05 means the shift is unlikely to be random.
* **PSI (prediction).** Buckets both distributions into the same bins and sums `(actual - expected) * ln(actual / expected)` per bin. PSI = 0 means identical distributions; > 0.1 is considered a significant shift.
* **Empty baseline.** If the baseline window has no events yet (e.g. a fresh environment), the signal is recorded as *no drift* instead of being skipped.
* **Alerting.** Alerts are debounced per metric: one alert per anomaly episode, re-armed only after the signal recovers, plus a cooldown (`ALERT_COOLDOWN_MINUTES`, default 15 min) to avoid flooding.

## Configuration

| Environment variable | Default | Meaning                                  |
| -------------------- | ------- | ---------------------------------------- |
| `DETECTOR_CURRENT_MINUTES`  | 5    | Current window length (min)              |
| `DETECTOR_BASELINE_OFFSET`  | 30   | Baseline window ends 30 min ago          |
| `DETECTOR_BASELINE_MINUTES` | 30   | Baseline window length (min)             |
| `DETECTOR_SCAN_INTERVAL`    | 60   | Scan period (seconds)                    |
| `DETECTOR_KS_THRESHOLD`     | 0.05 | KS p-value threshold                     |
| `DETECTOR_PSI_THRESHOLD`    | 0.1  | PSI threshold                            |
| `DETECTOR_MIN_EVENTS`       | 50   | Min events in the current window to test |
| `ALERT_WEBHOOK_URL`         | —    | Slack-compatible webhook endpoint        |
| `ALERT_COOLDOWN_MINUTES`    | 15   | Alert cooldown (min)                     |

## Dashboard usage

The big-screen dashboard (`http://localhost:8501`) polls ClickHouse every 10 seconds and updates live:

* **Banner.** Green "System Healthy" / red "Drift Detected" with the number of drifted signals and the last scan time.
* **Overview cards.** Event count (last hour, with hour-over-hour delta), P50/P99 latency (delta vs previous hour), drifted signal count.
* **Signal analysis.** Each signal shows its score vs threshold with a progress bar; red = drifted.
* **Traffic trend** — requests per minute (15 min). **Latency trend** — P50/P99 over time.
* **Distributions** — current vs baseline histograms of prediction and confidence. Clear separation = behavior change.
* **Drift events** — most recent drifted signals with timestamps.
* Hover the ⓘ icon on any panel for a plain-language explanation; the top bar toggles 中文/EN.

## Drift Demo

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

# Directory Structure

```text
services/gateway       # Go gateway (proxy + event collection + ClickHouse sink)
services/detector      # Drift detection engine
services/dashboard     # Big-screen dashboard (React)
sdk/python             # Python SDK
services/rootcause     # Root cause analysis
tools/simulator        # Mock model + traffic generator
tools/loadtest         # Load testing configuration
infra/docker-compose   # Local deployment
charts/helm            # Kubernetes deployment
```

---

# Roadmap

## Phase 1: Core Observability

* [x] Gateway based collection
* [x] ClickHouse event storage
* [x] Local deployment environment

## Phase 2: AI Reliability

* [x] Data drift detection
* [x] Alerting system
* [ ] Python SDK
* [ ] Embedding drift detection
* [ ] Root cause analysis

## Phase 3: LLM & Agent Observability

* [ ] Prompt drift detection
* [ ] Token-level sampling
* [ ] Tool-call tracing
* [ ] Agent workflow monitoring
* [ ] RAG quality analysis

## Phase 4: Automated Recovery

* [ ] Model fallback
* [ ] Traffic routing
* [ ] Policy-based mitigation
* [ ] Self-healing AI workflows

---

# Why Vera?

Modern AI systems are becoming increasingly complex:

```text
User
 |
Agent
 |
Planner
 |
Tools
 |
RAG
 |
LLM
 |
Response
```

When something fails, traditional logging is not enough.

Teams need to understand:

* What changed?
* Where did it fail?
* Why did it fail?
* How can it recover?

Vera aims to become the reliability layer for production AI systems.

---

# License

Apache License 2.0

