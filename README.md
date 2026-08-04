# Vera — 模型监控与漂移检测平台

面向生产环境 ML/LLM 服务的可观测性平台：拦截推理请求，采集事件，检测数据/概念漂移，定位根因，并在漂移触发时执行自动缓解。

- **目标场景（MVP）**：电商 CTR 预测模型（二分类），内部模拟数据驱动
- **技术栈**：Go 网关 · Python 检测器/根因服务/SDK · ClickHouse（事件 OLAP）· Postgres（元数据/审计）· Streamlit（MVP 仪表盘）+ Grafana（长期监控）
- **隐私默认**：严格模式——PII/原文一律不上传，仅上传 hash/摘要

## 架构

```
                    ┌──────────────┐      ┌──────────────────┐
   CTR 模型服务 ───▶ │  gateway     │ ───▶ │  ClickHouse      │
   (SDK 采集)        │  (Go, 异步)  │      │  (事件 OLAP)     │
                    └──────┬───────┘      └────────┬─────────┘
                           │                       │
                           └─── (可选 Kafka) ───────┤
                                                   ▼
                              ┌──────────────┐ ┌────────────┐
                              │  detector    │ │  rootcause │
                              │  (漂移检测)   │ │  (根因定位) │
                              └──────┬───────┘ └─────┬──────┘
                                     ▼               ▼
                              ┌─────────────────────────────┐
                              │  Streamlit Dashboard + 告警  │
                              └─────────────────────────────┘
```

## 目录结构（mono-repo）

| 路径 | 职责 | 计划周次 |
|---|---|---|
| `services/gateway` | Go 网关：拦截请求/响应，异步上报事件 | Week 1 |
| `services/detector` | Python 检测器：KS/PSI、embedding 漂移 | Week 2 |
| `services/rootcause` | Python 根因定位引擎（启发式） | Week 3 |
| `sdk/python` | Python SDK：采集、脱敏、上报 | Week 4 |
| `infra/docker-compose` | 本地开发环境编排 | Week 1 |
| `charts/helm` | 生产 Kubernetes 部署模板 | Week 8 |
| `tools/simulator` | 合成数据生成与模拟生产流（CTR） | Week 1–2 |
| `docs` | PRD、部署指南、隐私白皮书等 | 持续 |

## 路线图（12 周，全量交付）

- **Week 0（当前）**：仓库骨架 + PRD ✅
- **Week 1–2**：MVP——网关 + ClickHouse + 两个基础检测器 + Streamlit 仪表盘（可演示）
- **Week 3–4**：根因定位引擎 + Python SDK
- **Week 5–6**：隐私/采样/审计包 + 性能基准与容量规划
- **Week 7–8**：Kafka 集成 + Prometheus/Grafana + Helm 部署模板
- **Week 9–10**：LLM 专属支持 + 自动化缓解策略原型
- **Week 11–12**：安全审计、文档、试点部署与 v0.1 release

## 快速开始

（Week 1 交付后补充：docker-compose 一键起 ClickHouse + 网关，模拟流写入，查询事件）

## 文档

- `docs/` 目录为内部文档，不入库（见 `.gitignore`）
