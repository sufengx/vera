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

- **内建漂移检测**
  - 基于 KS 检验与 PSI 的事件信号漂移引擎。
  - Webhook 告警与实时大屏仪表盘。

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

端到端管道已经跑通：

```text
网关
   ↓
事件采集
   ↓
ClickHouse 存储
   ↓
漂移检测 → 仪表盘与告警
```

已验证：

* 默认启用基于 SHA-256 的隐私保护
* gzip 批量编码
* 失败事件重试机制
* ClickHouse 认证支持
* 漂移检测引擎（KS 检验 / PSI）与 webhook 告警
* 实时指标与漂移状态的大屏仪表盘
* 基于 Docker Compose 的集成测试

当前开发重点：

* Python SDK
* Embedding 漂移检测
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
| `services/detector`    | 漂移检测引擎（事件信号的 KS 检验 / PSI）             | ✅ 可用     |
| `services/dashboard`   | 中英双语 React 大屏仪表盘：指标、图表与漂移告警      | ✅ 可用     |
| `tools/simulator`      | 模拟模型服务与流量生成器                             | ✅ 可用     |
| `infra/docker-compose` | 本地开发环境                                         | ✅ 可用     |
| `sdk/python`           | 应用级信号的 Python SDK                              | 🚧 规划中   |
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
* `detector` - 漂移检测引擎
* `dashboard` - 监控大屏，地址 http://localhost:8501

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

# 漂移检测

## 目前可以检测什么

检测器（`services/detector`）周期性对比当前事件窗口与基准窗口，标记分布发生偏移的信号：

| 信号                  | 方法  | 含义                         | 阈值            |
| --------------------- | ----- | ---------------------------- | --------------- |
| `prediction`          | PSI   | 模型输出值的分布             | PSI > 0.1       |
| `confidence`          | KS    | 模型置信度的分布             | p 值 < 0.05     |
| `latency_ms`          | KS    | 响应延迟的分布               | p 值 < 0.05     |

统计量超过阈值即判定漂移。结果写入 `vera.drift_results` 并在仪表盘展示；漂移信号会通过 Slack 兼容 webhook 发送告警（`ALERT_WEBHOOK_URL`）。

## 原理

* **窗口语义。** 检测器维护两个窗口：*当前窗口*（最近 N 分钟的事件）与*基准窗口*（更早 offset 之前的 M 分钟切片），每个扫描周期对比两者。窗口大小均为环境变量，灵敏度可调。
* **KS 检验（confidence、latency）。** 计算两个分布累计曲线的最大间距，得到 p 值 = 两个分布来自同一分布的概率；p < 0.05 说明偏移不太可能是随机波动。
* **PSI（prediction）。** 把两个分布按相同分桶累计，逐桶求和 `(实际占比 - 期望占比) × ln(实际占比/期望占比)`。PSI = 0 表示分布完全一致，> 0.1 视为显著偏移。
* **空基准语义。** 基准窗口还没有事件时（如全新环境），记为*无漂移*而非跳过，保证每轮都有结果。
* **告警防抖。** 同一指标一次异常期只告警一次，恢复正常后才重新武装；另加冷却期（`ALERT_COOLDOWN_MINUTES`，默认 15 分钟），避免刷屏。

## 配置项

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

## 大屏使用说明

监控大屏（http://localhost:8501）每 10 秒轮询一次 ClickHouse，实时刷新：

* **状态横幅。** 绿色"系统运行正常" / 红色"检测到漂移"，显示异常信号数和最近扫描时间。
* **概览卡片。** 事件量（最近一小时，含环比差值）、P50/P99 延迟（含与上一小时差值）、漂移信号数。
* **信号漂移分析。** 每个信号显示 score vs 阈值进度条，红 = 漂移。
* **请求量趋势** —— 每分钟请求数（15 分钟）。**延迟趋势** —— P50/P99 随时间变化。
* **分布对比** —— prediction / confidence 的当前窗口 vs 基准窗口直方图，明显错开即行为改变。
* **异常事件** —— 最近触发的漂移事件。
* 任意面板悬停 ⓘ 可看通俗解释；顶栏可切换中英文。

## 漂移演示

以漂移模拟模式启动全栈——模拟模型会在启动 60 秒后偏移输出分布：

```bash
docker compose -f infra/docker-compose/docker-compose.yml \
  -f infra/docker-compose/docker-compose.drift-demo.yml up --build
```

打开 http://localhost:8501 观察完整周期：

1. 前 60 秒左右 —— 全绿，流量逐渐爬升。
2. 约 90–120 秒 —— 模拟模型发生偏移，`prediction`、`confidence`、`latency_ms` 变红，横幅转红并触发 webhook 告警。
3. 随后 —— 基准窗口滚过漂移点，信号恢复绿色。那是"新常态"，不是误报。

直接查询漂移结果：

```bash
curl -s -u default:vera "http://localhost:8123/?query=SELECT+metric,score,threshold,drifted+FROM+vera.drift_results+ORDER+BY+timestamp+DESC+FORMAT+CSV"
```

演示结束后重置环境：

```bash
docker compose -f infra/docker-compose/docker-compose.yml down -v
```

---

# 目录结构

```text
services/gateway       # Go 网关（代理 + 事件采集 + ClickHouse 写入）
services/detector      # 漂移检测引擎
services/dashboard     # 大屏仪表盘 (React)
sdk/python             # Python SDK
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

* [x] 数据漂移检测
* [x] 告警系统
* [ ] Python SDK
* [ ] Embedding 漂移检测
* [ ] 根因分析

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
