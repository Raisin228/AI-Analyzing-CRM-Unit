"""Старт модуля анализатора. Атрошенко Б. С."""

import asyncio
import logging
import subprocess
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI

from ..research import AnomalyDetector
from .config import settings
from . import algo_recurrence
from ..agent import AIAnalyzerAgent
from ..database import DBManager
from ..kafka import KafkaManager, Consumer

from ..redis_service import RedisManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


def _run_migrations() -> None:
    """Запуск и прогон миграций."""

    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        capture_output=True, text=True,
        cwd="/app",
    )
    if result.returncode != 0:
        logger.error("Alembic failed:\n%s", result.stderr)
        raise RuntimeError("DB migration failed")
    logger.info("DB migrations applied")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Код исполняемый до/после запуска приложения"""

    # 1. DB pool
    db = DBManager(settings.database_url)
    await db.init_pool()

    # 2. Alembic migrations
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _run_migrations)

    # 3. Redis
    redis = RedisManager(settings.REDIS_URL)
    await redis.connect()

    # 4. Kafka producer
    kafka = KafkaManager(settings.KAFKA_BOOTSTRAP)
    await kafka.init_producer()

    # 5. LLM client + LangFuse
    AIAnalyzerAgent()

    # 6. Scheduler
    scheduler.add_job(kafka.poll_crm, "interval", seconds=settings.POLL_INTERVAL_SEC, id="poller")
    scheduler.add_job(AnomalyDetector.check_volume_anomaly, "interval", minutes=10, id="vol_anomaly")
    scheduler.add_job(AnomalyDetector.check_topic_shift, "interval", minutes=10, id="topic_shift")
    scheduler.add_job(algo_recurrence.close_stale_clusters, "interval", hours=1, id="close_clusters")
    scheduler.start()
    logger.info("Scheduler started")

    # 7. Kafka consumer (background task)
    consumer_task = asyncio.create_task(Consumer.loop_consume())

    yield

    # Shutdown
    consumer_task.cancel()
    try:
        await consumer_task
    except asyncio.CancelledError:
        pass
    scheduler.shutdown(wait=False)
    await kafka.close_producer()
    await redis.disconnect()
    await db.close_pool()
    logger.info("Analyzer shut down")


app = FastAPI(title="Analyzer", version="1.0.0", lifespan=lifespan)


@app.get("/health")
async def health():
    """Проверка состояния сервиса и кол-ва векторов."""

    return {"status": "ok"}
