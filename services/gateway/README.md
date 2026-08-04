# services/gateway — Go 网关

职责：
- HTTP 反向代理：拦截 CTR 模型服务的请求/响应（Gin/FastHTTP）
- 异步上报事件（non-blocking，批量 + 压缩 + 失败重试）
- 事件写入 ClickHouse（MVP）/ Kafka（配置开关）
- 隐私默认：PII/原文不上传，仅 hash/摘要

模块：`github.com/sufengx/vera/gateway`
