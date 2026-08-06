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

Gateway latency benchmarks and 200/1000 req/s load tests (zero event loss) — see [TESTING.md](TESTING.md#benchmarks).

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

Clone and start the full stack:

```bash
git clone https://github.com/sufengx/vera.git && cd vera
docker compose -f infra/docker-compose/docker-compose.yml up --build
```

Dashboard: http://localhost:8501 · Gateway: http://localhost:8080/v1/predict

Full instructions — zero-code install (Linux/macOS/Windows), source build, connecting a real model — in [DEPLOYMENT.md](DEPLOYMENT.md).

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

All knobs (windows, thresholds, scan interval, webhook) — see [Detector Configuration](DEPLOYMENT.md#detector-configuration). Dashboard walk-through — [Dashboard Usage](DEPLOYMENT.md#dashboard-usage). See drift in action with the [Drift Demo](TESTING.md#drift-demo).

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

