"""模拟 CTR 模型服务：接收特征，返回点击概率与置信度。"""
import json
import math
import os
import random
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class ModelHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            features = json.loads(body or b"{}")
        except json.JSONDecodeError:
            self.send_error(400, "invalid json")
            return
        values = [v for v in features.values() if isinstance(v, (int, float))]
        score = sum(values) / len(values) if values else 0.5
        pred = 1 / (1 + math.exp(-(score - 0.5)))
        response = json.dumps({
            "prediction": round(pred, 4),
            "confidence": round(random.uniform(0.7, 0.95), 4),
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
