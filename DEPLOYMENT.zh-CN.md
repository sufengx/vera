[![English](https://img.shields.io/badge/English-blue?style=for-the-badge)](DEPLOYMENT.md) [![中文](https://img.shields.io/badge/%E4%B8%AD%E6%96%87-green?style=for-the-badge)](DEPLOYMENT.zh-CN.md)

# 部署指南

Vera 有三种运行方式，从最快到最深度：

1. **零代码私有化部署** —— 拉取预构建镜像，不需要源码。
2. **源码 + Docker Compose** —— 克隆仓库，`up --build`。
3. **接入真实 AI 模型** —— 把网关指向你自己的模型。

---

## 零代码私有化部署

不需要源码。所有 Vera 组件都以预构建镜像发布在 GitHub Container Registry——任何装了 Docker 的主机都能部署（内网隔离环境也可先把镜像同步到内部 registry 再部署）。按平台选择方式：

### Linux

```bash
curl -sSL https://raw.githubusercontent.com/sufengx/vera/main/install.sh | bash
```

脚本会自动检查 Docker、下载自包含的 compose 文件与 ClickHouse 建表脚本到 `./vera`、拉取镜像并启动。

### macOS

与 Linux 相同——`curl | bash` 开箱即用（自带 bash 3.2+）。

### Windows

**方式一：PowerShell 一键安装**（PowerShell 5.1+）：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
irm https://raw.githubusercontent.com/sufengx/vera/main/install.ps1 | iex
```

**方式二：Git Bash 或 WSL2**——直接用上面 Linux 的命令。

**方式三：完全手动**：

```powershell
mkdir $env:USERPROFILE\vera\init; cd $env:USERPROFILE\vera
Invoke-WebRequest -Uri https://raw.githubusercontent.com/sufengx/vera/main/infra/docker-compose/docker-compose.release.yml -OutFile docker-compose.release.yml
Invoke-WebRequest -Uri https://raw.githubusercontent.com/sufengx/vera/main/infra/docker-compose/init/001_events.sql -OutFile init\001_events.sql
Invoke-WebRequest -Uri https://raw.githubusercontent.com/sufengx/vera/main/infra/docker-compose/init/002_drift.sql -OutFile init\002_drift.sql
docker compose -f docker-compose.release.yml up -d
```

三个平台的访问入口一致：

| 组件        | 地址                               |
| ----------- | ---------------------------------- |
| 监控大屏    | http://localhost:8501              |
| 推理网关    | http://localhost:8080/v1/predict   |
| 根因分析    | http://localhost:8100              |
| ClickHouse  | http://localhost:8123（`default` / `vera`） |

发布版不包含任何模拟/演示服务——大屏只展示真实流量。接入你的模型服务（见[接入真实 AI 模型](#接入真实-ai-模型)），让推理流量改走 `http://<主机>:8080/v1/predict`。

### 钉定发布版本

Linux / macOS：

```bash
export VERA_REF=v0.2.0 VERA_IMAGE_TAG=0.2.0 VERA_DIR=/opt/vera
curl -sSL https://raw.githubusercontent.com/sufengx/vera/main/install.sh | bash
```

Windows PowerShell：

```powershell
$env:VERA_REF = "v0.2.0"; $env:VERA_IMAGE_TAG = "0.2.0"; $env:VERA_DIR = "C:\vera"
irm https://raw.githubusercontent.com/sufengx/vera/main/install.ps1 | iex
```

内网环境部署（如国内网络经常无法访问 `raw.githubusercontent.com`）？把 `VERA_SRC` 指向一个提供相同文件的内网 HTTP 镜像即可，三平台通用。

预构建镜像（按发布版本打 tag，main 上另有 `latest`）：

| 镜像                                    | 内容                 |
| --------------------------------------- | -------------------- |
| `ghcr.io/sufengx/vera/gateway`          | Go 推理网关          |
| `ghcr.io/sufengx/vera/detector`         | 漂移检测引擎         |
| `ghcr.io/sufengx/vera/rootcause`        | 根因分析引擎         |
| `ghcr.io/sufengx/vera/dashboard`        | React 监控大屏       |

---

## 源码 + Docker Compose

前置要求：

* Docker
* Docker Compose

```bash
git clone https://github.com/sufengx/vera.git
cd vera
docker compose -f infra/docker-compose/docker-compose.yml up --build
```

将启动以下服务：

* `gateway` - AI 推理网关
* `model-mock` - 模拟模型服务（仅开发用）
* `loadgen` - 流量生成器（仅开发用）
* `clickhouse` - 事件存储
* `detector` - 漂移检测引擎
* `rootcause` - 根因分析引擎，地址 http://localhost:8100
* `dashboard` - 监控大屏，地址 http://localhost:8501

`model-mock` 与 `loadgen` 是开发辅助工具，用来在没有真实模型时本地生成合成流量评估 Vera，不属于上面的生产部署。

测试推理：

```bash
curl -s -X POST http://localhost:8080/v1/predict \
  -H "Content-Type: application/json" \
  -H "X-Model-Name: ctr" \
  -H "X-Model-Version: v1" \
  -H "X-Client-ID: demo" \
  -d '{"price":42.5,"user_history_len":88,"item_rating":4.2,"is_new_user":0,"hour":14}'
```

查询采集的事件：

```bash
curl -s "http://localhost:8123/?query=SELECT%20count(*)%20FROM%20vera.events%20FORMAT%20CSV"
```

---

# 接入真实 AI 模型

Vera 无需 SDK、无需改代码。你的模型继续跑在自己的地址上——只需把网关指到它，让推理流量改走网关：

```text
你的应用 ──► Vera 网关 :8080 ──► 你的模型服务（原样不动）
```

## 1. 把网关指到你的模型

将 `GATEWAY_UPSTREAM` 设为你的模型服务地址——零代码部署写在 compose 旁的 `.env`，源码部署用 compose override：

```bash
# 零代码部署：在 docker-compose.release.yml 旁边写 .env
echo "GATEWAY_UPSTREAM=http://your-model-host:9000" >> .env
docker compose -f docker-compose.release.yml up -d
```

```yaml
# 源码部署：docker-compose.override.yml
services:
  gateway:
    environment:
      GATEWAY_UPSTREAM: "http://your-model-host:9000"
```

默认上游是 `http://host.docker.internal:9000`——模型跑在同一台宿主机上就无需任何配置。网关原样转发每个请求（路径、请求头、请求体），现有客户端不用改，只需要把 base URL 换成 `http://<vera-host>:8080`。

## 2. 告诉 Vera 请求的归属（可选请求头）

| 请求头             | 含义                                 |
| ------------------ | ------------------------------------ |
| `X-Client-ID`      | 调用方 / 应用（默认取客户端 IP）      |
| `X-Model-Name`     | 模型标识（默认取 `MODEL_NAME`）       |
| `X-Model-Version`  | 模型版本（默认取 `MODEL_VERSION`）    |
| `X-Request-ID`     | 你的请求追踪 ID                       |

## 3. Vera 每次调用记录什么

* 请求体的 SHA-256 哈希——默认不存原始输入。
* 响应延迟，由网关自行计时。
* 从上游 **JSON 响应** 中解析 `prediction` 与 `confidence`——这是喂给漂移检测的两个信号，模型请按此格式返回：

```json
{"prediction": 0.73, "confidence": 0.91}
```

`prediction` 可以是字符串或数字；`confidence` 是 [0, 1] 的数字。缺失时字段记为空、检测器跳过该信号，延迟漂移仍会监控。

验证事件落库：

```bash
curl -s "http://localhost:8123/?query=SELECT%20count(*)%20FROM%20vera.events%20FORMAT%20CSV"
```

## 4. 网关配置项

| 环境变量                     | 默认值                 | 含义                     |
| ---------------------------- | ---------------------- | ------------------------ |
| `GATEWAY_ADDR`               | `:8080`                | 网关监听地址             |
| `GATEWAY_UPSTREAM`           | `http://127.0.0.1:9000`| 上游模型服务地址         |
| `MODEL_NAME`                 | `ctr`                  | 默认模型名（无请求头时） |
| `MODEL_VERSION`              | `v1`                   | 默认模型版本             |
| `CLICKHOUSE_ADDR`            | `http://127.0.0.1:8123`| ClickHouse HTTP 地址     |
| `CLICKHOUSE_USER` / `CLICKHOUSE_PASSWORD` | —           | ClickHouse 凭据          |
| `BATCH_SIZE`                 | 500                    | 每批写入事件数           |
| `BATCH_INTERVAL`             | 2s                     | 最大攒批间隔             |
| `RETRY_MAX`                  | 3                      | 写入失败重试次数         |
| `QUEUE_SIZE`                 | 10000                  | 内存事件队列（满则丢弃） |

## 5. 按你的流量调检测参数

检测器拿当前窗口（最近 N 分钟）对比基准窗口（K 分钟前结束的 M 分钟切片）。调参经验：

* **低流量**（每分钟不足 ~10 条）：拉大窗口，例如 `DETECTOR_CURRENT_MINUTES=30`、`DETECTOR_BASELINE_OFFSET=60`、`DETECTOR_BASELINE_MINUTES=120`，或调低 `DETECTOR_MIN_EVENTS`（默认 50，不足的窗口会跳过）。
* **有每日周期性**：设 `DETECTOR_BASELINE_OFFSET=1440`，基准窗口即"昨天同一时刻"。
* **告警灵敏度**：调高 `DETECTOR_KS_THRESHOLD` / `DETECTOR_PSI_THRESHOLD` 更容忍噪声，调低反应更早。

## 6. 接告警

配置一个 Slack 兼容 webhook（Slack Incoming Webhooks，或其他支持 Slack 消息格式的接收端）：

```bash
# 写在 infra/docker-compose/.env 中（不入库）
ALERT_WEBHOOK_URL=https://hooks.slack.com/services/T000/B000/XXX
```

告警防抖（一次异常期一条，恢复后重新武装），冷却 15 分钟（`ALERT_COOLDOWN_MINUTES`）。消息格式：`{"text": "[Vera] <metric> drifted: score=..., threshold=..."}`。

## 7. 目前能做什么、不能做什么

开箱即检测 `prediction`（PSI）、`confidence`（KS）、`latency_ms`（KS）的分布漂移，用根因分析解释漂移来源（top-K 特征与子群贡献），并配实时大屏与 webhook 告警。暂不支持：SDK 应用级信号、embedding 漂移、prompt/工具调用追踪——见[路线图](README.zh-CN.md#路线图)。

---

# 检测信号

每次推理请求都会在 `vera.events` 中产生一条事件。检测器周期性对比*当前窗口*（最近 N 分钟）与*基准窗口*（K 分钟前结束的 M 分钟切片），标记分布发生偏移的信号：

| 信号          | 方法  | 阈值            |
| ------------- | ----- | --------------- |
| `prediction`  | PSI   | PSI > 0.1       |
| `confidence`  | KS    | p 值 < 0.05     |
| `latency_ms`  | KS    | p 值 < 0.05     |

* **KS 检验（confidence、latency）。** 计算两个分布累计曲线的最大间距，p 值 = 两个分布来自同一分布的概率；p < 0.05 说明偏移不太可能是随机波动。
* **PSI（prediction）。** 把两个分布按相同分桶累计，逐桶求和 `(实际占比 − 期望占比) × ln(实际占比 / 期望占比)`。PSI = 0 表示分布完全一致，> 0.1 视为显著偏移。
* **空基准语义。** 基准窗口还没有事件时（如全新环境），记为*无漂移*而非跳过，保证每轮都有结果。
* **告警防抖。** 同一指标一次异常期只告警一次，恢复正常后才重新武装；另加冷却期（`ALERT_COOLDOWN_MINUTES`，默认 15 分钟），避免刷屏。

---

# 检测器配置项

| 环境变量                    | 默认值 | 含义                 |
| --------------------------- | ------ | -------------------- |
| `DETECTOR_CURRENT_MINUTES`  | 5      | 当前窗口长度（分钟） |
| `DETECTOR_BASELINE_OFFSET`  | 30     | 基准窗口结束于 30 分钟前 |
| `DETECTOR_BASELINE_MINUTES` | 30     | 基准窗口长度（分钟） |
| `DETECTOR_SCAN_INTERVAL`    | 60     | 扫描周期（秒）       |
| `DETECTOR_KS_THRESHOLD`     | 0.05   | KS 检验 p 值阈值     |
| `DETECTOR_PSI_THRESHOLD`    | 0.1    | PSI 阈值             |
| `DETECTOR_MIN_EVENTS`       | 50     | 当前窗口最小事件数，不足不检测 |
| `ALERT_WEBHOOK_URL`         | —      | Slack 兼容 webhook 地址 |
| `ALERT_COOLDOWN_MINUTES`    | 15     | 告警冷却（分钟）     |

---

# 根因分析

检测到漂移时，根因引擎（`services/rootcause`）对比当前窗口与基准窗口，按影响度量（`PSI + 0.35 × Cohen's d`）对每个特征排序，再定位漂移集中的子群（客户端、路由、模型版本……）。每个特征带置信度评分，报告以 JSON 提供，大屏渲染并支持导出。

```bash
# 某模型最近 5 分钟（默认窗口）的 top-K 特征与子群
curl -s "http://localhost:8100/api/v1/rootcause?model=ctr&top_k=5"

# 显式时间段、按路由过滤、指定维度
curl -s "http://localhost:8100/api/v1/rootcause?current_from=2026-08-08%2010:00:00&current_to=2026-08-08%2010:05:00&route=/v1/predict&dimensions=client_id,route"
```

| 环境变量               | 默认值                        | 含义                           |
| ---------------------- | ----------------------------- | ------------------------------ |
| `RC_CURRENT_MINUTES`   | 5                             | 当前窗口长度（分钟）           |
| `RC_BASELINE_OFFSET`   | 30                            | 基准窗口结束于 30 分钟前       |
| `RC_BASELINE_MINUTES`  | 30                            | 基准窗口长度（分钟）           |
| `RC_MIN_EVENTS`        | 20                            | 最小事件数，不足不产出报告     |
| `RC_TOP_K`             | 5                             | 报告中的特征 / 子群数量        |
| `RC_DIMENSIONS`        | `client_id,route,model_version` | 子群分析维度               |

---

# 大屏使用说明

监控大屏（http://localhost:8501）每 10 秒轮询一次 ClickHouse，实时刷新：

* **状态横幅。** 绿色"系统运行正常" / 红色"检测到漂移"，显示异常信号数和最近扫描时间。
* **概览卡片。** 事件量（最近一小时，含环比差值）、P50/P99 延迟（含与上一小时差值）、漂移信号数。
* **信号漂移分析。** 每个信号显示 score vs 阈值进度条，红 = 漂移。
* **请求量趋势** —— 每分钟请求数（15 分钟）。**延迟趋势** —— P50/P99 随时间变化。
* **分布对比** —— prediction / confidence 的当前窗口 vs 基准窗口直方图，明显错开即行为改变。
* **异常事件** —— 最近触发的漂移事件。
* **根因视图** —— 顶栏切换：可解释摘要、按影响排序的特征（PSI / 均值位移 / 效应量 / 置信度）、子群贡献，支持导出 JSON。
* 任意面板悬停 ⓘ 可看通俗解释；顶栏可切换中英文。

想看漂移实际发生？见 [TESTING.zh-CN.md](TESTING.zh-CN.md#漂移演示)。
