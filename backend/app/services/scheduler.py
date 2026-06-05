import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import get_settings
from app.database import SessionLocal
from app.services.monitor import MonitorService


settings = get_settings()
scheduler = AsyncIOScheduler()
monitor = MonitorService()


async def scan_due_stocks() -> None:
    db = SessionLocal()
    try:
        stock_ids = monitor.due_stock_ids(db)
    finally:
        db.close()

    for stock_id in stock_ids:
        db = SessionLocal()
        try:
            await monitor.scan_stock(db, stock_id, force=False)
        finally:
            db.close()
        await asyncio.sleep(1)


def start_scheduler() -> None:
    if not settings.scheduler_enabled or scheduler.running:
        return
    scheduler.add_job(scan_due_stocks, "interval", seconds=settings.scheduler_interval_seconds, id="scan_stocks")
    scheduler.start()


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown()
