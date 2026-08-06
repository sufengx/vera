"""检测器服务：周期扫描事件窗口，计算漂移指标并写入 ClickHouse。"""
import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI

import alert
import metrics
from config import Config
from store import Store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def scan_once(cfg, st, alerter):
    """执行一轮扫描：对比基准/当前窗口，写结果并触发告警。"""
    now = datetime.now(timezone.utc)
    current = (now - timedelta(minutes=cfg.current_minutes), now)
    baseline = (
        now - timedelta(minutes=cfg.baseline_offset + cfg.baseline_minutes),
        now - timedelta(minutes=cfg.baseline_offset),
    )
    if st.count(*current) < cfg.min_events:
        logging.info("当前窗口事件不足，跳过本轮扫描")
        return []
    scan_id = uuid.uuid4()
    results = metrics.compute_all(st, baseline, current, cfg)
    for r in results:
        st.write_result(scan_id, now.replace(tzinfo=None), r, *current)
        if r.drifted:
            alerter.alert(r)
        else:
            alerter.recover(r.metric)
    logging.info("扫描完成: 指标 %d 个, 漂移 %d 个", len(results), sum(r.drifted for r in results))
    return results


async def scan_loop(cfg):
    """后台循环：按配置间隔反复扫描，失败后下一轮重试。"""
    alerter = alert.Alerter(cfg)
    st = None
    while True:
        try:
            st = st or Store(cfg)
            scan_once(cfg, st, alerter)
        except Exception as exc:
            logging.error("扫描失败: %s", exc)
        await asyncio.sleep(cfg.scan_interval)


@asynccontextmanager
async def lifespan(app):
    task = asyncio.create_task(scan_loop(app.state.cfg))
    yield
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)


app = FastAPI(lifespan=lifespan)
app.state.cfg = Config()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/metrics")
def latest_metrics():
    """返回最近一次扫描的漂移结果。"""
    return Store(app.state.cfg).latest_results()
