# sdk/python — Python 采集 SDK

**计划周次**：Week 4（当前为骨架占位）

职责：
- 采集：embedding（可选）、置信度、模型版本、token-level（Week 9，采样）
- 本地脱敏：PII 哈希模块（可配置 salt），严格模式——原文一律不出进程
- 上报：sync/async、批量/采样接口，经网关或直连事件总线
