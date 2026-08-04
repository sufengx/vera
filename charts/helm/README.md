# charts/helm — Kubernetes 部署模板

**计划周次**：Week 8（当前为骨架占位）

为每个服务提供独立 chart：gateway、detector、rootcause、sdk-demo。
- Liveness/readiness probes、resource requests/limits、HPA 示例
- RBAC / NetworkPolicy / ingress TLS 示例
- 目标：`helm install` 一键部署（开发/生产 values）
