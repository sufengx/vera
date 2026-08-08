"""环境变量配置。"""
import os


class Config:
    """根因服务参数，均可通过环境变量覆盖（RC_ 前缀）。"""

    def __init__(self):
        self.clickhouse_addr = os.environ.get("CLICKHOUSE_ADDR", "http://localhost:8123")
        self.clickhouse_user = os.environ.get("CLICKHOUSE_USER", "default")
        self.clickhouse_password = os.environ.get("CLICKHOUSE_PASSWORD", "")
        self.clickhouse_db = os.environ.get("CLICKHOUSE_DB", "vera")
        self.current_minutes = int(os.environ.get("RC_CURRENT_MINUTES", "5"))
        self.baseline_offset = int(os.environ.get("RC_BASELINE_OFFSET", "30"))
        self.baseline_minutes = int(os.environ.get("RC_BASELINE_MINUTES", "30"))
        self.min_events = int(os.environ.get("RC_MIN_EVENTS", "20"))
        self.top_k = int(os.environ.get("RC_TOP_K", "5"))
        self.dimensions = [d for d in os.environ.get("RC_DIMENSIONS", "client_id,route,model_version").split(",") if d]
        self.segment_limit = int(os.environ.get("RC_SEGMENT_LIMIT", "50"))
