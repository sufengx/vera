"""生成模拟 CTR 请求流，持续向网关发送特征。"""
import argparse
import json
import random
import time
import urllib.request


def make_features():
    return {
        "price": round(random.uniform(0, 100), 2),
        "user_history_len": random.randint(0, 500),
        "item_rating": round(random.uniform(1, 5), 2),
        "is_new_user": random.randint(0, 1),
        "hour": random.randint(0, 23),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--target", default="http://127.0.0.1:8080/v1/predict")
    p.add_argument("--rate", type=int, default=20, help="每秒请求数")
    p.add_argument("--duration", type=int, default=60, help="持续秒数")
    p.add_argument("--model", default="ctr")
    p.add_argument("--version", default="v1")
    args = p.parse_args()

    deadline = time.time() + args.duration
    interval = 1.0 / args.rate
    sent = 0
    while time.time() < deadline:
        data = json.dumps(make_features()).encode()
        req = urllib.request.Request(args.target, data=data, headers={
            "Content-Type": "application/json",
            "X-Model-Name": args.model,
            "X-Model-Version": args.version,
            "X-Client-ID": f"client-{random.randint(1, 100)}",
        })
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                resp.read()
            sent += 1
        except Exception as exc:
            print(f"请求失败: {exc}")
        time.sleep(interval)
    print(f"已发送 {sent} 个请求")


if __name__ == "__main__":
    main()
