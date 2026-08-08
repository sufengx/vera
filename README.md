[![English](https://img.shields.io/badge/English-blue?style=for-the-badge)](README.md) [![中文](https://img.shields.io/badge/%E4%B8%AD%E6%96%87-green?style=for-the-badge)](README.zh-CN.md) [![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

# Vera

Observability platform for production AI systems.

Vera intercepts inference traffic without code changes, detects model behavior drift, and explains what changed — data distribution shifts, model degradation, or infrastructure failures. It answers one question:

> Why did my AI system become worse?

---

## Architecture

```text
AI Applications (ML Models / LLM Services / AI Agents)
                        │
                        ▼
              ┌──────────────────┐
              │  Vera Gateway    │  Go proxy, async event capture
              └────────┬─────────┘
                       ▼
              ┌──────────────────┐
              │    ClickHouse    │  event store
              └────────┬─────────┘
                       │
                 ┌─────┴─────┐
                 ▼           ▼
            Detection     Root Cause
                 └─────┬─────┘
                       ▼
            Dashboard / Alerting / Mitigation
```

---

## Features

- **Zero-code integration** — HTTP reverse-proxy gateway captures signals from any model service; async collection never blocks inference.
- **Privacy-first** — only SHA-256 input hashes are stored by default; configurable masking levels.
- **High-throughput pipeline** — batch compressed writes into ClickHouse, built for OLAP analysis at scale.
- **Drift detection** — KS test / PSI over event signals, debounced webhook alerts.
- **Root cause analysis** — top-K feature impacts and segment contributions, each with a confidence score.
- **Self-hosted** — Docker Compose or prebuilt GHCR images; zero-code install for Linux/macOS/Windows.

---

## Quick Start

```bash
git clone https://github.com/sufengx/vera.git && cd vera
docker compose -f infra/docker-compose/docker-compose.yml up --build
```

| Component  | Address               |
| ---------- | --------------------- |
| Dashboard  | http://localhost:8501 |
| Gateway    | http://localhost:8080 |
| Root Cause | http://localhost:8100 |
| ClickHouse | http://localhost:8123 |

The dev stack ships a mock model and traffic generator for local evaluation — production deployments connect your real model instead. No-code private deployment, source builds and real-model setup: [DEPLOYMENT.md](DEPLOYMENT.md).

---

## Components

| Path                   | Description                                                            | Status |
| ---------------------- | ---------------------------------------------------------------------- | ------ |
| `services/gateway`     | Go inference gateway: proxy + event collection + async ClickHouse sink | ✅     |
| `services/detector`    | Drift detection engine (KS test / PSI on event signals)                | ✅     |
| `services/rootcause`   | Root cause analysis: top-K features + segment contributions            | ✅     |
| `services/dashboard`   | Bilingual big-screen dashboard with root cause view                    | ✅     |
| `tools/simulator`      | Mock model service and traffic generator (dev only)                    | ✅     |
| `infra/docker-compose` | Local development environment                                          | ✅     |
| `sdk/python`           | Python SDK for application-level signals                               | 🚧     |
| `charts/helm`          | Kubernetes deployment templates                                        | 🚧     |

---

## Detection Signals

The detector periodically compares a *current window* (last N minutes) against a *baseline window* (an M-minute slice ending K minutes ago) and flags signals whose distribution shifted:

| Signal       | Test | Threshold      |
| ------------ | ---- | -------------- |
| `prediction` | PSI  | PSI > 0.1      |
| `confidence` | KS   | p-value < 0.05 |
| `latency_ms` | KS   | p-value < 0.05 |

Results drive the dashboard and webhook alerts. When drift is found, the root cause engine ranks features by `PSI + 0.35 × Cohen's d` and locates the client / route / version segments where the shift concentrates.

Window semantics, signal statistics, alerts and full configuration: [DEPLOYMENT.md](DEPLOYMENT.md). Benchmarks and the drift demo: [TESTING.md](TESTING.md).

---

## Roadmap

* **Phase 1 — Core observability.** ✅ Gateway collection · ✅ ClickHouse storage · ✅ Local deployment
* **Phase 2 — AI reliability.** ✅ Drift detection · ✅ Alerting · ✅ Root cause analysis · 🚧 Python SDK · 🚧 Embedding drift detection
* **Phase 3 — LLM & agent observability.** 🚧 Prompt drift · 🚧 Token sampling · 🚧 Tool-call tracing · 🚧 Agent workflows · 🚧 RAG quality
* **Phase 4 — Automated recovery.** 🚧 Model fallback · 🚧 Traffic routing · 🚧 Policy-based mitigation · 🚧 Self-healing workflows

---

## License

Apache License 2.0
