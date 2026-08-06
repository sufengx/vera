"""告警：漂移指标通过 webhook 通知，带防抖与冷却。"""
import json
import logging
import time
import urllib.request


class Alerter:
    """发送 Slack 兼容 webhook 告警。"""

    def __init__(self, cfg):
        self.webhook = cfg.alert_webhook
        self.cooldown = cfg.alert_cooldown_minutes * 60
        self.alerted = set()
        self.last_at = {}

    def alert(self, result):
        if not self.webhook or result.metric in self.alerted:
            return
        if result.metric in self.last_at and time.time() - self.last_at[result.metric] < self.cooldown:
            return
        self.alerted.add(result.metric)
        self.last_at[result.metric] = time.time()
        payload = {"text": f"[Vera] {result.metric} drifted: score={result.score:.4f}, "
                           f"threshold={result.threshold}"}
        try:
            req = urllib.request.Request(self.webhook, json.dumps(payload).encode(),
                                         headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=5)
            logging.info("告警已发送: %s", result.metric)
        except Exception as exc:
            logging.error("告警发送失败: %s", exc)

    def recover(self, metric):
        """指标恢复正常后允许再次告警。"""
        if metric in self.alerted:
            self.alerted.discard(metric)
            logging.info("%s 恢复正常", metric)
