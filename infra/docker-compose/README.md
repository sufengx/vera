# infra/docker-compose — 本地开发环境

一键起 ClickHouse、网关与模拟流量：

    docker compose up -d
    docker compose run --rm loadgen
    docker compose exec clickhouse clickhouse-client --query "SELECT count() FROM vera.events"

组件：

- clickhouse：事件存储，首次启动执行 `init/` 下的建表脚本
- gateway：Go 网关，代理请求并异步上报事件
- model-mock：模拟 CTR 模型服务
- loadgen：按固定速率生成特征请求
