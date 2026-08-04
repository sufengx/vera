# infra/docker-compose — 本地开发环境

编排组件：
- ClickHouse（事件 OLAP）
- Postgres（元数据/审计）
- gateway、detector、rootcause、Streamlit 仪表盘
- 可选：Kafka + ClickHouse Sink（配置开关）
