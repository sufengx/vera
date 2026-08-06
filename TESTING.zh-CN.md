[![English](https://img.shields.io/badge/English-blue?style=for-the-badge)](TESTING.md) [![中文](https://img.shields.io/badge/%E4%B8%AD%E6%96%87-green?style=for-the-badge)](TESTING.zh-CN.md)

# 测试指南

如何验证 Vera 是否正常工作：基准测试、负载测试与完整的漂移检测演示。

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

# 漂移演示

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

# 单元测试

Go 网关测试：

```bash
cd services/gateway && go test ./...
```

Python 检测器测试：

```bash
cd services/detector && pytest tests -q
```

CI 执行 lint、单元测试、全部镜像的 Docker 构建，以及完整的 docker-compose 集成测试（断言事件与漂移结果写入 ClickHouse，见 `.github/workflows/ci.yml`）。
