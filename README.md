# Vera

面向生产环境 ML/LLM 服务的可观测性平台：拦截推理流量、采集观测事件、检测数据与概念漂移、定位根因，并在漂移触发时执行自动缓解。

- **零侵入接入**：HTTP 反向代理网关拦截模型请求/响应，应用无感，事件异步上报不阻塞推理
- **隐私默认**：原文不出进程，仅上传摘要与哈希（SHA-256），脱敏级别可配置
- **流式落库**：事件批量压缩写入 ClickHouse，支撑大规模 OLAP 与实时检测
- **一键本地编排**：docker-compose 拉起网关、模拟模型、压测流与存储，开箱即跑

## 架构

```
                    ┌──────────────┐      ┌──────────────┐
   CTR 模型服务 ───▶ │   gateway    │ ───▶ │  ClickHouse  │
   (SDK/模拟器)      │  (Go 反向代理 │      │  (事件 OLAP) │
                    │   异步上报)   │      └──────┬───────┘
                    └──────────────┘             │
                                                 ▼
                              ┌──────────────┐ ┌────────────┐
                              │  detector    │ │  rootcause │
                              │  (漂移检测)   │ │  (根因定位) │
                              └──────┬───────┘ └─────┬──────┘
                                     ▼               ▼
                              ┌─────────────────────────────┐
                              │  Dashboard + 告警 + 自动缓解  │
                              └─────────────────────────────┘
```

当前已打通并验证**网关 → 事件 → ClickHouse** 全链路：代理单请求耗时约 0.1ms（benchmark），1000 req/s 压测下请求成功率 100% 且事件零丢失；隐私字段（SHA-256 摘要、`full` 脱敏）默认生效；网关单测覆盖事件校验、gzip 批量编码、失败重试与 ClickHouse 认证；CI 包含 compose 端到端集成测试。detector / rootcause / SDK 处于规划阶段（见[路线图](#路线图)）。

## 组件

| 路径 | 说明 | 状态 |
|---|---|---|
| `services/gateway` | Go 网关：反向代理 + 事件采集 + 批量异步上报 | ✅ 已验证 |
| `tools/simulator` | 模拟 CTR 模型服务与压测流（纯标准库，零依赖） | ✅ 已验证 |
| `infra/docker-compose` | 本地环境一键编排 | ✅ 已验证 |
| `sdk/python` | Python 采集 SDK：采集、脱敏、上报 | 🚧 规划中 |
| `services/detector` | 漂移检测器：KS-test / PSI / embedding 距离 | 🚧 规划中 |
| `services/rootcause` | 根因定位：特征影响排序、子群对比 | 🚧 规划中 |
| `charts/helm` | Kubernetes 部署模板 | 🚧 规划中 |

## 快速开始

前置：Docker 与 Docker Compose。

```bash
docker compose -f infra/docker-compose/docker-compose.yml up --build
```

一次拉起四个服务：

- **gateway** `http://localhost:8080` — 推理入口，转发至模拟模型并采集事件
- **model-mock** — 模拟 CTR 模型，返回预测概率与置信度
- **loadgen** — 压测流，以 20 req/s 持续 30 秒（跑完即退出，可用下面命令补流量）
- **clickhouse** `http://localhost:8123` — 事件存储

验证端到端：

```bash
# 经网关调用一次模型
curl -s -X POST http://localhost:8080/v1/predict \
  -H "Content-Type: application/json" \
  -H "X-Model-Name: ctr" -H "X-Model-Version: v1" -H "X-Client-ID: demo" \
  -d '{"price": 42.5, "user_history_len": 88, "item_rating": 4.2, "is_new_user": 0, "hour": 14}'
# => {"prediction":0.8269,"confidence":0.9183}

# 查询已落库的事件
curl -s "http://localhost:8123/?query=SELECT%20count(*)%20FROM%20vera.events%20FORMAT%20CSV"
```

网关配置通过环境变量注入，本地单独运行示例：

```bash
cd services/gateway
GATEWAY_UPSTREAM=http://127.0.0.1:9000 \
CLICKHOUSE_ADDR=http://127.0.0.1:8123 \
go run .
```

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `GATEWAY_ADDR` | `:8080` | 网关监听地址 |
| `GATEWAY_UPSTREAM` | `http://127.0.0.1:9000` | 上游模型服务 |
| `CLICKHOUSE_ADDR` / `CLICKHOUSE_DB` / `CLICKHOUSE_TABLE` | `http://127.0.0.1:8123` / `vera` / `events` | 事件存储 |
| `CLICKHOUSE_USER` / `CLICKHOUSE_PASSWORD` | 空 | ClickHouse 认证（未配置则不发送） |
| `MODEL_NAME` / `MODEL_VERSION` | `ctr` / `v1` | 默认模型标识（可被请求头覆盖） |
| `BATCH_SIZE` / `BATCH_INTERVAL` | `500` / `2s` | 批量上报参数 |
| `RETRY_MAX` / `QUEUE_SIZE` | `3` / `10000` | 失败重试与队列上限 |

## 事件模型

每次推理生成一条事件，关键字段：

| 字段 | 说明 |
|---|---|
| `event_id` / `request_id` | 事件 UUID 与业务请求 ID |
| `model_name` / `model_version` / `route` | 模型标识与调用路径 |
| `input_summary_hash` | 请求体 SHA-256 摘要（隐私默认：不存原文） |
| `prediction` / `confidence` | 预测结果与置信度 |
| `latency_ms` | 端到端延迟 |
| `privacy_mask_level` | 脱敏级别：`none` / `partial` / `full` |
| `label` / `label_timestamp` | 延迟反馈标签（可选） |

上报链路为异步批量：队列积压（默认上限 10000）时丢弃事件而非阻塞推理路径。

## 目录结构

```
services/gateway       # Go 网关（代理 + 事件采集 + ClickHouse sink）
sdk/python             # Python 采集 SDK
services/detector      # 漂移检测
services/rootcause     # 根因定位
tools/simulator        # 模拟模型 + 压测流
tools/loadtest         # vegeta 负载测试配置
infra/docker-compose   # 本地编排
charts/helm            # Kubernetes 部署
```

## 路线图

- [x] 网关 + 事件存储 + 模拟器（可端到端运行）
- [ ] Python 采集 SDK：脱敏、批量/采样上报
- [ ] 漂移检测：KS/PSI、embedding 距离、告警通知
- [ ] 根因定位：特征影响排序、子群对比、可解释报告
- [ ] 监控告警与 Kubernetes 部署
- [ ] LLM 支持：prompt-hash 漂移、token-level 采样
- [ ] 自动化缓解

## 许可证

[Apache License 2.0](LICENSE)
