"""模拟 CTR 模型服务：接收特征，返回点击概率与置信度。"""
import json
import math
import os
import random
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# 漂移开关：启动 DRIFT_AFTER 秒后给归一化分数加 DRIFT_SHIFT 偏移
DRIFT_AFTER = float(os.environ.get("MOCK_DRIFT_AFTER", "0"))
DRIFT_SHIFT = float(os.environ.get("MOCK_DRIFT_SHIFT", "0.4"))
START = time.time()


def scale(value, lo, hi):
    return (value - lo) / (hi - lo)


class ModelHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            features = json.loads(body or b"{}")
        except json.JSONDecodeError:
            self.send_error(400, "invalid json")
            return
        score = sum([
            scale(features.get("price", 50), 0, 100),
            scale(features.get("user_history_len", 250), 0, 500),
            scale(features.get("item_rating", 3), 1, 5),
            float(features.get("is_new_user", 0)),
            scale(features.get("hour", 12), 0, 24),
        ]) / 5
        if DRIFT_AFTER and time.time() - START > DRIFT_AFTER:
            score += DRIFT_SHIFT
        pred = 1 / (1 + math.exp(-(score - 0.5) * 8))
        conf = min(0.99, 0.5 + abs(pred - 0.5) + random.uniform(-0.05, 0.05))
        response = json.dumps({
            "prediction": round(pred, 4),
            "confidence": round(conf, 4),
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    port = int(os.environ.get("MOCK_PORT", "9000"))
    ThreadingHTTPServer(("0.0.0.0", port), ModelHandler).serve_forever()
