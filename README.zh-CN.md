[![English](https://img.shields.io/badge/English-blue?style=for-the-badge)](README.md) [![中文](https://img.shields.io/badge/%E4%B8%AD%E6%96%87-green?style=for-the-badge)](README.zh-CN.md)

# Vera

## 开源 AI 可观测性与可靠性平台

Vera 是面向生产环境 AI 系统的开源可观测性平台。

它以零侵入的方式采集推理信号、检测模型行为变化、分析故障根因，为可靠的 AI 运营打下基础。

Vera 致力于回答一个问题：

> 我的 AI 系统为什么变差了？

无论是数据分布变化、模型退化、提示词调整、检索问题，还是基础设施故障，Vera 都致力于为生产环境中的 AI 工作负载提供可见性与自动化响应。

---

## 亮点

- **零代码接入**
  - HTTP 反向代理网关拦截推理流量，无需修改现有应用。
  - 事件异步采集，不阻塞推理请求。

- **隐私优先设计**
  - 默认情况下，原始用户数据不出进程。
  - 仅采集摘要与 SHA-256 哈希。
  - 隐私脱敏级别可配置。

- **高吞吐事件管道**
  - 批量压缩写入 ClickHouse。
  - 面向大规模 OLAP 分析与实时检测设计。

- **企业级架构**
  - 自托管部署。
  - Docker Compose 本地环境。
  - Kubernetes 部署规划中。

---

# 架构

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

# 当前状态

端到端采集管道已经跑通：

```text
网关
   ↓
事件采集
   ↓
ClickHouse 存储
```

已验证：

* 默认启用基于 SHA-256 的隐私保护
* gzip 批量编码
* 失败事件重试机制
* ClickHouse 认证支持
* 基于 Docker Compose 的集成测试

当前开发重点：

* Python SDK
* 漂移检测引擎
* 根因分析
* LLM 可观测性支持
* 自动化修复

参见[路线图](#路线图)。

---

# 基准测试

网关基准（2026-08）：

| Benchmark             | 延迟        | 说明                             |
| --------------------- | ----------- | -------------------------------- |
| `BenchmarkHandler`    | 120.7µs/op  | 完整代理路径，含事件采集         |
| `BenchmarkBuildEvent` | 2.2µs/op    | 仅事件采集开销                   |

负载测试（vegeta，见 `tools/loadtest`）：

| 场景 | 速率       | 时长 | 请求数   | 成功率 | p99   | 事件丢失 |
| ---- | ---------- | ---- | -------- | ------ | ----- | -------- |
| A    | 200 req/s  | 30s  | 6,000    | 100%   | 2.4ms | 0        |
| B    | 1000 req/s | 30s  | 30,000   | 100%   | 3.6ms | 0        |

![负载测试：1000 req/s](assets/img/loadtest-1000rps.png)

---

# 组件

| 路径                   | 说明                                                 | 状态        |
| ---------------------- | ---------------------------------------------------- | ----------- |
| `services/gateway`     | Go 推理网关：代理 + 事件采集 + 异步 ClickHouse 写入  | ✅ 可用     |
| `tools/simulator`      | 模拟模型服务与流量生成器                             | ✅ 可用     |
| `infra/docker-compose` | 本地开发环境                                         | ✅ 可用     |
| `sdk/python`           | 应用级信号的 Python SDK                              | 🚧 规划中   |
| `services/detector`    | 漂移检测引擎（KS / PSI / embedding 距离）            | 🚧 规划中   |
| `services/rootcause`   | 根因分析引擎                                         | 🚧 规划中   |
| `charts/helm`          | Kubernetes 部署模板                                  | 🚧 规划中   |

---

# 快速开始

前置要求：

* Docker
* Docker Compose

启动 Vera：

```bash
docker compose -f infra/docker-compose/docker-compose.yml up --build
```

将启动以下服务：

* `gateway` - AI 推理网关
* `model-mock` - 模拟模型服务
* `loadgen` - 流量生成器
* `clickhouse` - 事件存储

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

# 事件模型

每次推理请求都会生成一条可观测性事件。

关键字段：

| 字段                  | 说明                       |
| --------------------- | -------------------------- |
| `event_id`            | 事件唯一标识               |
| `request_id`          | 请求追踪 ID                |
| `model_name`          | 模型标识                   |
| `model_version`       | 模型版本                   |
| `input_summary_hash`  | SHA-256 请求指纹           |
| `prediction`          | 模型输出                   |
| `confidence`          | 置信度                     |
| `latency_ms`          | 请求延迟                   |
| `privacy_mask_level`  | none / partial / full      |
| `label`               | 可选的延迟反馈             |

![ClickHouse 中的真实事件](assets/img/events.png)

事件异步上报，推理链路不会被存储故障阻塞。

---

# 目录结构

```text
services/gateway       # Go 网关（代理 + 事件采集 + ClickHouse 写入）
sdk/python             # Python SDK
services/detector      # 漂移检测
services/rootcause     # 根因分析
tools/simulator        # 模拟模型 + 流量生成器
tools/loadtest         # 压测配置
infra/docker-compose   # 本地部署
charts/helm            # Kubernetes 部署
```

---

# 路线图

## 阶段一：核心可观测性

* [x] 基于网关的采集
* [x] ClickHouse 事件存储
* [x] 本地部署环境

## 阶段二：AI 可靠性

* [ ] Python SDK
* [ ] 数据漂移检测
* [ ] Embedding 漂移检测
* [ ] 根因分析
* [ ] 告警系统

## 阶段三：LLM 与 Agent 可观测性

* [ ] 提示词漂移检测
* [ ] Token 级采样
* [ ] 工具调用追踪
* [ ] Agent 工作流监控
* [ ] RAG 质量分析

## 阶段四：自动化恢复

* [ ] 模型回退
* [ ] 流量路由
* [ ] 基于策略的修复
* [ ] 自愈 AI 工作流

---

# 为什么选择 Vera？

现代 AI 系统正变得越来越复杂：

```text
用户
 |
Agent
 |
规划器
 |
工具
 |
RAG
 |
LLM
 |
响应
```

当系统出错时，传统日志远远不够。

团队需要弄清楚：

* 什么变了？
* 哪里出的问题？
* 为什么失败？
* 如何恢复？

Vera 的目标是成为生产环境 AI 系统的可靠性层。

---

# 许可证

Apache License 2.0
