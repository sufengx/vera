# services/detector — Python 漂移检测器

**计划周次**：Week 2（当前为骨架占位）

职责：
- 周期性读取 ClickHouse 事件数据（FastAPI 服务）
- 检测器：KS-test / PSI（数值特征）、embedding cosine/MD 距离
- 漂移告警（阈值可配置，Slack/Email 通知）
- 升级：prompt-hash 漂移检测（Week 9，LLM 支持）
