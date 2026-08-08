[![English](https://img.shields.io/badge/English-blue?style=for-the-badge)](README.md) [![中文](https://img.shields.io/badge/%E4%B8%AD%E6%96%87-green?style=for-the-badge)](README.zh-CN.md) [![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

# Vera

面向生产环境 AI 系统的可观测性平台。

Vera 无需改代码即可拦截推理流量、检测模型行为漂移，并解释什么变了——数据分布变化、模型退化，还是基础设施故障。它致力于回答一个问题：

> 我的 AI 系统为什么变差了？

---

## 架构

```text
AI 应用（ML 模型 / LLM 服务 / AI Agent）
                        │
                        ▼
              ┌──────────────────┐
              │  Vera 网关        │  Go 反向代理，异步事件采集
              └────────┬─────────┘
                       ▼
              ┌──────────────────┐
              │    ClickHouse    │  事件存储
              └────────┬─────────┘
                       │
                 ┌─────┴─────┐
                 ▼           ▼
              漂移检测      根因分析
                 └─────┬─────┘
                       ▼
            大屏 / 告警 / 自动化修复
```

---

## 特性

- **零代码接入** —— HTTP 反向代理网关从任意模型服务采集信号；异步采集不阻塞推理。
- **隐私优先** —— 默认只存 SHA-256 输入哈希；脱敏级别可配置。
- **高吞吐管道** —— 批量压缩写入 ClickHouse，面向大规模 OLAP 分析设计。
- **漂移检测** —— 事件信号的 KS 检验 / PSI，webhook 告警带防抖。
- **根因分析** —— top-K 特征影响与子群贡献，每个都带置信度评分。
- **自托管** —— Docker Compose 或 GHCR 预构建镜像；Linux/macOS/Windows 零代码安装。

---

## 快速开始

```bash
git clone https://github.com/sufengx/vera.git && cd vera
docker compose -f infra/docker-compose/docker-compose.yml up --build
```

| 组件        | 地址                    |
| ----------- | ----------------------- |
| 监控大屏    | http://localhost:8501   |
| 推理网关    | http://localhost:8080   |
| 根因分析    | http://localhost:8100   |
| ClickHouse  | http://localhost:8123   |

开发栈自带模拟模型与流量生成器用于本地评估——生产部署接入你的真实模型。零代码私有化部署、源码构建与真实模型接入：见 [DEPLOYMENT.zh-CN.md](DEPLOYMENT.zh-CN.md)。

---

## 组件

| 路径                   | 说明                                                       | 状态 |
| ---------------------- | ---------------------------------------------------------- | ---- |
| `services/gateway`     | Go 推理网关：代理 + 事件采集 + 异步 ClickHouse 写入        | ✅   |
| `services/detector`    | 漂移检测引擎（事件信号的 KS 检验 / PSI）                   | ✅   |
| `services/rootcause`   | 根因分析：top-K 特征 + 子群贡献                            | ✅   |
| `services/dashboard`   | 中英双语大屏仪表盘，含根因视图                             | ✅   |
| `tools/simulator`      | 模拟模型服务与流量生成器（仅开发用）                       | ✅   |
| `infra/docker-compose` | 本地开发环境                                               | ✅   |
| `sdk/python`           | 应用级信号的 Python SDK                                    | 🚧   |
| `charts/helm`          | Kubernetes 部署模板                                        | 🚧   |

---

## 检测信号

检测器周期性对比*当前窗口*（最近 N 分钟）与*基准窗口*（K 分钟前结束的 M 分钟切片），标记分布发生偏移的信号：

| 信号          | 方法  | 阈值            |
| ------------- | ----- | --------------- |
| `prediction`  | PSI   | PSI > 0.1       |
| `confidence`  | KS    | p 值 < 0.05     |
| `latency_ms`  | KS    | p 值 < 0.05     |

结果驱动大屏与 webhook 告警。检测到漂移后，根因引擎按 `PSI + 0.35 × Cohen's d` 对特征排序，并定位漂移集中的客户端 / 路由 / 版本子群。

窗口语义、统计原理、告警与完整配置：见 [DEPLOYMENT.zh-CN.md](DEPLOYMENT.zh-CN.md)。基准测试与漂移演示：见 [TESTING.zh-CN.md](TESTING.zh-CN.md)。

---

## 路线图

* **阶段一：核心可观测性。** ✅ 网关采集 · ✅ ClickHouse 存储 · ✅ 本地部署
* **阶段二：AI 可靠性。** ✅ 漂移检测 · ✅ 告警系统 · ✅ 根因分析 · 🚧 Python SDK · 🚧 Embedding 漂移检测
* **阶段三：LLM 与 Agent 可观测性。** 🚧 提示词漂移 · 🚧 Token 采样 · 🚧 工具调用追踪 · 🚧 Agent 工作流 · 🚧 RAG 质量
* **阶段四：自动化恢复。** 🚧 模型回退 · 🚧 流量路由 · 🚧 策略化修复 · 🚧 自愈工作流

---

## 许可证

Apache License 2.0
