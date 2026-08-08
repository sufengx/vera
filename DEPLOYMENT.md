[![English](https://img.shields.io/badge/English-blue?style=for-the-badge)](DEPLOYMENT.md) [![中文](https://img.shields.io/badge/%E4%B8%AD%E6%96%87-green?style=for-the-badge)](DEPLOYMENT.zh-CN.md)

# Deployment Guide

Three ways to run Vera, from fastest to most involved:

1. **Zero-code private deployment** — pull prebuilt images, no source code.
2. **From source with Docker Compose** — clone the repo, `up --build`.
3. **Connecting a real AI model** — point the gateway at your own model.

---

## Zero-code Private Deployment

No source code needed. All Vera components ship as prebuilt images on GitHub Container Registry — deploy on any host with Docker (even air-gapped internal networks, by mirroring the images to an internal registry). Pick your platform:

### Linux

```bash
curl -sSL https://raw.githubusercontent.com/sufengx/vera/main/install.sh | bash
```

The script checks Docker, downloads a self-contained compose file and the ClickHouse init scripts into `./vera`, pulls the images and starts the stack.

### macOS

Same as Linux — `curl | bash` works out of the box (bash 3.2+ is built in).

### Windows

**Option 1 — PowerShell one-liner** (PowerShell 5.1+):

```powershell
Set-ExecutionPolicy -Scope Process Bypass
irm https://raw.githubusercontent.com/sufengx/vera/main/install.ps1 | iex
```

**Option 2 — Git Bash or WSL2**: use the Linux command above.

**Option 3 — fully manual**:

```powershell
mkdir $env:USERPROFILE\vera\init; cd $env:USERPROFILE\vera
Invoke-WebRequest -Uri https://raw.githubusercontent.com/sufengx/vera/main/infra/docker-compose/docker-compose.release.yml -OutFile docker-compose.release.yml
Invoke-WebRequest -Uri https://raw.githubusercontent.com/sufengx/vera/main/infra/docker-compose/init/001_events.sql -OutFile init\001_events.sql
Invoke-WebRequest -Uri https://raw.githubusercontent.com/sufengx/vera/main/infra/docker-compose/init/002_drift.sql -OutFile init\002_drift.sql
docker compose -f docker-compose.release.yml up -d
```

All platforms access the same endpoints:

| Component    | Address                          |
| ------------ | -------------------------------- |
| Dashboard    | http://localhost:8501            |
| Gateway      | http://localhost:8080/v1/predict |
| Root Cause   | http://localhost:8100            |
| ClickHouse   | http://localhost:8123 (`default` / `vera`) |

The release stack ships no mock or demo services — the dashboard shows only real data flowing through the gateway. Connect your model service (see [Connecting a Real AI Model](#connecting-a-real-ai-model)) and route inference calls through `http://<host>:8080/v1/predict`.

### Pin a released version

Linux / macOS:

```bash
export VERA_REF=v0.2.0 VERA_IMAGE_TAG=0.2.0 VERA_DIR=/opt/vera
curl -sSL https://raw.githubusercontent.com/sufengx/vera/main/install.sh | bash
```

Windows PowerShell:

```powershell
$env:VERA_REF = "v0.2.0"; $env:VERA_IMAGE_TAG = "0.2.0"; $env:VERA_DIR = "C:\vera"
irm https://raw.githubusercontent.com/sufengx/vera/main/install.ps1 | iex
```

Deploying in an internal network (e.g. mainland China, where `raw.githubusercontent.com` is often unreachable)? Set `VERA_SRC` to an internal HTTP mirror serving the same files — works on all three platforms.

Prebuilt images (all tagged with the released version, plus `latest` on main):

| Image                                   | Contains                         |
| --------------------------------------- | -------------------------------- |
| `ghcr.io/sufengx/vera/gateway`          | Go inference gateway             |
| `ghcr.io/sufengx/vera/detector`         | Drift detection engine           |
| `ghcr.io/sufengx/vera/rootcause`        | Root cause analysis engine       |
| `ghcr.io/sufengx/vera/dashboard`        | React big-screen dashboard       |

---

## From Source with Docker Compose

Prerequisites:

* Docker
* Docker Compose

```bash
git clone https://github.com/sufengx/vera.git
cd vera
docker compose -f infra/docker-compose/docker-compose.yml up --build
```

This starts:

* `gateway` - AI inference gateway
* `model-mock` - simulated model service (dev only)
* `loadgen` - traffic generator (dev only)
* `clickhouse` - event storage
* `detector` - drift detection engine
* `rootcause` - root cause analysis engine at http://localhost:8100
* `dashboard` - big-screen dashboard at http://localhost:8501

`model-mock` and `loadgen` are development helpers that generate synthetic traffic so you can evaluate Vera locally without a real model. They are not part of the production deployment above.

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

---

# Connecting a Real AI Model

Vera needs no SDK and no code changes. Your model keeps serving on its own URL — you point the gateway at it and route inference traffic through the gateway instead:

```text
your app ──► Vera Gateway :8080 ──► your model service (unchanged)
```

## 1. Point the gateway at your model

Set `GATEWAY_UPSTREAM` to your model service — a `.env` next to the compose file (zero-code install), or a compose override (source install):

```bash
# zero-code install: .env beside docker-compose.release.yml
echo "GATEWAY_UPSTREAM=http://your-model-host:9000" >> .env
docker compose -f docker-compose.release.yml up -d
```

```yaml
# source install: docker-compose.override.yml
services:
  gateway:
    environment:
      GATEWAY_UPSTREAM: "http://your-model-host:9000"
```

The default upstream is `http://host.docker.internal:9000` — a model running on the same host needs no configuration. The gateway proxies every request verbatim — path, headers and body — so existing clients keep working. Only the base URL changes to `http://<vera-host>:8080`.

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

## 7. What Vera covers today

Out of the box it detects distribution drift on `prediction` (PSI), `confidence` (KS) and `latency_ms` (KS), explains the drift with root-cause analysis (top-K features and segment contributions), and shows everything on a live dashboard with webhook alerts. Not yet: SDK-based application signals, embedding drift, prompt/tool tracing — see [Roadmap](README.md#roadmap).

---

# Detector Configuration

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

---

# Root Cause Analysis

When drift is detected, the root-cause engine (`services/rootcause`) compares the current window against a baseline window and ranks every feature by impact (`PSI + 0.35 × Cohen's d`), then looks for the segment (client, route, model version…) where the drift concentrates. Each feature carries a confidence score; the report is available as JSON and the dashboard renders it with an export button.

```bash
# top-K features + segments for a model, last 5 minutes by default
curl -s "http://localhost:8100/api/v1/rootcause?model=ctr&top_k=5"

# explicit windows, filter by route, choose dimensions
curl -s "http://localhost:8100/api/v1/rootcause?current_from=2026-08-08%2010:00:00&current_to=2026-08-08%2010:05:00&route=/v1/predict&dimensions=client_id,route"
```

| Environment variable  | Default                    | Meaning                              |
| --------------------- | -------------------------- | ------------------------------------ |
| `RC_CURRENT_MINUTES`  | 5                          | Current window length (min)          |
| `RC_BASELINE_OFFSET`  | 30                         | Baseline window ends 30 min ago      |
| `RC_BASELINE_MINUTES` | 30                         | Baseline window length (min)         |
| `RC_MIN_EVENTS`       | 20                         | Min events to produce a report       |
| `RC_TOP_K`            | 5                          | Features / segments in the report    |
| `RC_DIMENSIONS`       | `client_id,route,model_version` | Segment dimensions               |

---

# Dashboard Usage

The big-screen dashboard (`http://localhost:8501`) polls ClickHouse every 10 seconds and updates live:

* **Banner.** Green "System Healthy" / red "Drift Detected" with the number of drifted signals and the last scan time.
* **Overview cards.** Event count (last hour, with hour-over-hour delta), P50/P99 latency (delta vs previous hour), drifted signal count.
* **Signal analysis.** Each signal shows its score vs threshold with a progress bar; red = drifted.
* **Traffic trend** — requests per minute (15 min). **Latency trend** — P50/P99 over time.
* **Distributions** — current vs baseline histograms of prediction and confidence. Clear separation = behavior change.
* **Drift events** — most recent drifted signals with timestamps.
* **Root cause view** — toggle in the top bar: an explainable summary, ranked feature impacts (PSI / mean shift / effect size / confidence), and segment contributions with an export-JSON button.
* Hover the ⓘ icon on any panel for a plain-language explanation; the top bar toggles 中文/EN.

Want to see drift in action? See [TESTING.md](TESTING.md#drift-demo).
