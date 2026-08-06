"""环境变量配置。"""
import os


class Config:
    """检测器参数，均可通过环境变量覆盖。"""

    def __init__(self):
        self.clickhouse_addr = os.environ.get("CLICKHOUSE_ADDR", "http://localhost:8123")
        self.clickhouse_user = os.environ.get("CLICKHOUSE_USER", "default")
        self.clickhouse_password = os.environ.get("CLICKHOUSE_PASSWORD", "")
        self.clickhouse_db = os.environ.get("CLICKHOUSE_DB", "vera")
        self.current_minutes = int(os.environ.get("DETECTOR_CURRENT_MINUTES", "5"))
        self.baseline_offset = int(os.environ.get("DETECTOR_BASELINE_OFFSET", "30"))
        self.baseline_minutes = int(os.environ.get("DETECTOR_BASELINE_MINUTES", "30"))
        self.scan_interval = int(os.environ.get("DETECTOR_SCAN_INTERVAL", "60"))
        self.min_events = int(os.environ.get("DETECTOR_MIN_EVENTS", "50"))
        self.ks_threshold = float(os.environ.get("DETECTOR_KS_THRESHOLD", "0.05"))
        self.psi_threshold = float(os.environ.get("DETECTOR_PSI_THRESHOLD", "0.1"))
        self.alert_webhook = os.environ.get("ALERT_WEBHOOK_URL", "")
        self.alert_cooldown_minutes = int(os.environ.get("ALERT_COOLDOWN_MINUTES", "15"))
