# Vera — 模型监控与漂移检测平台

面向生产环境 ML/LLM 服务的可观测性平台：拦截推理请求，采集事件，检测数据/概念漂移，定位根因，并在漂移触发时执行自动缓解。

- **目标场景**：电商 CTR 预测模型（二分类），合成数据驱动
- **技术栈**：Go 网关 · Python 检测器/根因服务/SDK · ClickHouse（事件 OLAP）· Postgres（元数据/审计）· Streamlit（仪表盘）+ Grafana（监控告警）
- **隐私默认**：PII/原文不上传，仅上传 hash/摘要

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

## 目录结构

| 路径 | 职责 |
|---|---|
| `services/gateway` | Go 网关：拦截请求/响应，异步上报事件 |
| `services/detector` | Python 漂移检测器（KS/PSI、embedding） |
| `services/rootcause` | Python 根因定位引擎 |
| `sdk/python` | Python 采集 SDK：采集、脱敏、上报 |
| `infra/docker-compose` | 本地开发环境编排 |
| `charts/helm` | Kubernetes 部署模板 |
| `tools/simulator` | 合成数据与模拟生产流 |

## 路线图

- MVP：网关 + 事件存储 + 基础漂移检测 + 仪表盘
- 根因定位引擎与采集 SDK
- 企业特性：隐私/采样/审计、监控告警、Kubernetes 部署
- 扩展：LLM 信号支持、自动化缓解

## 快速开始

构建与运行说明随首个可运行版本发布后补充。

## 文档

各模块构建与使用说明见对应目录 README。
