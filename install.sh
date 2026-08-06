#!/usr/bin/env bash
# Vera 零代码私有化部署：只拉 GHCR 预构建镜像，无需源码。
# 用法:
#   curl -sSL https://raw.githubusercontent.com/sufengx/vera/main/install.sh | bash
# 钉定版本:
#   VERA_REF=v0.2.0 VERA_IMAGE_TAG=0.2.0 curl -sSL .../install.sh | bash
# 自定义安装目录:
#   VERA_DIR=/opt/vera curl -sSL .../install.sh | bash
set -euo pipefail

VERA_REF="${VERA_REF:-main}"
VERA_IMAGE_TAG="${VERA_IMAGE_TAG:-latest}"
VERA_DIR="${VERA_DIR:-./vera}"
BASE="https://raw.githubusercontent.com/sufengx/vera/${VERA_REF}"
FILES="infra/docker-compose/docker-compose.release.yml infra/docker-compose/init/001_events.sql infra/docker-compose/init/002_drift.sql"

command -v docker >/dev/null 2>&1 || { echo "错误：未找到 docker，请先安装 Docker"; exit 1; }
docker compose version >/dev/null 2>&1 || { echo "错误：需要 docker compose v2"; exit 1; }

mkdir -p "${VERA_DIR}/init"
for f in ${FILES}; do
  curl -fsSL "${BASE}/${f}" -o "${VERA_DIR}/${f}"
done

cd "${VERA_DIR}"
export VERA_IMAGE_TAG
docker compose -f docker-compose.release.yml pull
docker compose -f docker-compose.release.yml up -d

cat <<EOF

Vera 已启动：
  监控大屏   http://localhost:8501
  推理网关   http://localhost:8080/v1/predict
  ClickHouse http://localhost:8123 (default/vera)
管理：
  停止   cd ${VERA_DIR} && docker compose -f docker-compose.release.yml down
  日志   cd ${VERA_DIR} && docker compose -f docker-compose.release.yml logs -f detector
  卸载   cd ${VERA_DIR} && docker compose -f docker-compose.release.yml down -v
EOF
