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

- **内建漂移检测与根因分析**
  - 基于 KS 检验与 PSI 的事件信号漂移引擎。
  - Top-K 特征影响与子群贡献，附置信度评分。
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
* 根因分析：top-K 特征与子群贡献
* 实时指标、漂移状态与根因报告的大屏仪表盘
* 基于 Docker Compose 的集成测试

当前开发重点：

* Python SDK
* Embedding 漂移检测
* LLM 可观测性支持
* 自动化修复

参见[路线图](#路线图)。

---

# 基准测试

网关延迟基准与 200/1000 req/s 负载测试（零事件丢失）——见 [TESTING.zh-CN.md](TESTING.zh-CN.md#基准测试)。

---

# 组件

| 路径                   | 说明                                                 | 状态        |
| ---------------------- | ---------------------------------------------------- | ----------- |
| `services/gateway`     | Go 推理网关：代理 + 事件采集 + 异步 ClickHouse 写入  | ✅ 可用     |
| `services/detector`    | 漂移检测引擎（事件信号的 KS 检验 / PSI）             | ✅ 可用     |
| `services/dashboard`   | 中英双语 React 大屏仪表盘：指标、图表与漂移告警      | ✅ 可用     |
| `services/rootcause`   | 根因分析：top-K 特征 + 子群贡献                      | ✅ 可用     |
| `tools/simulator`      | 模拟模型服务与流量生成器                             | ✅ 可用     |
| `infra/docker-compose` | 本地开发环境                                         | ✅ 可用     |
| `sdk/python`           | 应用级信号的 Python SDK                              | 🚧 规划中   |
| `charts/helm`          | Kubernetes 部署模板                                  | 🚧 规划中   |

---

# 快速开始

克隆并启动全栈：

```bash
git clone https://github.com/sufengx/vera.git && cd vera
docker compose -f infra/docker-compose/docker-compose.yml up --build
```

大屏：http://localhost:8501 · 网关：http://localhost:8080/v1/predict

该栈包含一个模拟模型用于本地评估——生产部署不包含它，需接入你的真实模型。完整说明——零代码安装（Linux/macOS/Windows）、源码构建、接入真实模型——见 [DEPLOYMENT.zh-CN.md](DEPLOYMENT.zh-CN.md)。

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

所有旋钮（窗口、阈值、扫描间隔、webhook）——见[检测器配置项](DEPLOYMENT.zh-CN.md#检测器配置项)。大屏使用说明——见[大屏使用说明](DEPLOYMENT.zh-CN.md#大屏使用说明)。想看漂移实际发生？见[漂移演示](TESTING.zh-CN.md#漂移演示)。

---

# 根因分析

漂移检测回答"行为是否变了"，根因引擎（`services/rootcause`）回答"什么变了、集中在哪"。

## 特征影响

引擎使用与检测器相同的当前/基准窗口，按影响度量对每个信号排序：

```
score = PSI + 0.35 × Cohen's d
```

报告中的每个特征都带 PSI、KS p 值、均值/标准差位移、效应量、漂移方向（上升/下降/分布变宽）与置信度评分（`min(1, n/200) × min(1, score/0.5)`）。

## 子群贡献

除整体位移外，引擎按维度分组——`client_id`、`route`、`model_version`——定位漂移集中的群体，例如"延迟翻了 4 倍，由客户端 ci-b 主导"：

```
score = 占比 × |子群位移 − 整体位移| / |整体位移|
```

当前窗口新出现的分组会被标记，其位移以整体基准均值衡量。只对已漂移的特征做子群分析，无漂移的信号不会产生噪声。

## 报告

API 返回机器可读报告（特征与子群排序、中英双语摘要），大屏渲染并支持导出 JSON。事件数不足的窗口返回 `insufficient_data` 而非报错。API 参考与配置——见[根因分析](DEPLOYMENT.zh-CN.md#根因分析)。

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
* [x] 根因分析
* [ ] Python SDK
* [ ] Embedding 漂移检测

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
