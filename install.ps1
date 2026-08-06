# Vera 零代码私有化部署（Windows PowerShell 版）：只拉 GHCR 预构建镜像，无需源码。
# 用法（PowerShell 5.1+ / 7+）:
#   Set-ExecutionPolicy -Scope Process Bypass
#   irm https://raw.githubusercontent.com/sufengx/vera/main/install.ps1 | iex
# 钉定版本 / 自定义目录 / 内网源:
#   $env:VERA_REF = "v0.2.0"; $env:VERA_IMAGE_TAG = "0.2.0"
#   $env:VERA_DIR = "C:\vera"; $env:VERA_SRC = "http://mirror.internal"
$ErrorActionPreference = "Stop"

$VERA_REF = if ($env:VERA_REF) { $env:VERA_REF } else { "main" }
$VERA_IMAGE_TAG = if ($env:VERA_IMAGE_TAG) { $env:VERA_IMAGE_TAG } else { "latest" }
$VERA_DIR = if ($env:VERA_DIR) { $env:VERA_DIR } else { (Join-Path $PWD "vera") }
$BASE = if ($env:VERA_SRC) { $env:VERA_SRC } else { "https://raw.githubusercontent.com/sufengx/vera/$VERA_REF" }

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  Write-Host "错误：未找到 docker，请先安装 Docker Desktop（https://www.docker.com/products/docker-desktop/）"; exit 1
}
docker compose version *> $null
if ($LASTEXITCODE -ne 0) {
  Write-Host "错误：需要 docker compose v2（Docker Desktop 自带）"; exit 1
}

New-Item -ItemType Directory -Force -Path (Join-Path $VERA_DIR "init") | Out-Null
$downloads = [ordered]@{
  "infra/docker-compose/docker-compose.release.yml" = "docker-compose.release.yml"
  "infra/docker-compose/init/001_events.sql"        = "init/001_events.sql"
  "infra/docker-compose/init/002_drift.sql"         = "init/002_drift.sql"
}
foreach ($remote in $downloads.Keys) {
  $out = Join-Path $VERA_DIR $downloads[$remote]
  Write-Host "下载 $remote ..."
  Invoke-WebRequest -Uri "$BASE/$remote" -OutFile $out -UseBasicParsing
}

Push-Location $VERA_DIR
$env:VERA_IMAGE_TAG = $VERA_IMAGE_TAG
docker compose -f docker-compose.release.yml pull
docker compose -f docker-compose.release.yml up -d
Pop-Location

Write-Host ""
Write-Host "Vera 已启动："
Write-Host "  监控大屏   http://localhost:8501"
Write-Host "  推理网关   http://localhost:8080/v1/predict"
Write-Host "  ClickHouse http://localhost:8123 (default/vera)"
Write-Host "管理："
Write-Host "  停止   cd $VERA_DIR; docker compose -f docker-compose.release.yml down"
Write-Host "  日志   cd $VERA_DIR; docker compose -f docker-compose.release.yml logs -f detector"
Write-Host "  卸载   cd $VERA_DIR; docker compose -f docker-compose.release.yml down -v"
