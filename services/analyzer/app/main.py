import asyncio
import logging
import subprocess
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI

from .config import settings
from . import embeddings, poller, algo_anomaly, algo_recurrence
from analyzer.database import DBManager
from .llm_pipeline import consume_loop, init_llm
from ..redis_service import redis_manager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

database = DBManager(settings.database_url)


def _run_migrations() -> None:
    """Прогон миграций в отдельном подпроцессе."""

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
    await database.init_pool(settings.database_url)

    # 2. Alembic migrations (runs in thread pool to avoid event-loop conflict)
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _run_migrations)

    # 3. Redis + embeddings
    await redis_manager.connect(settings.REDIS_URL)
    await embeddings.rebuild_index()

    # 4. Kafka producer
    await poller.init_producer()

    # 5. LLM client + LangFuse
    init_llm()

    # 6. Scheduler
    scheduler.add_job(poller.poll_crm, "interval", seconds=settings.POLL_INTERVAL_SEC, id="poller")
    scheduler.add_job(algo_anomaly.check_volume_anomaly, "interval", minutes=10, id="vol_anomaly")
    scheduler.add_job(algo_anomaly.check_topic_shift, "interval", minutes=10, id="topic_shift")
    scheduler.add_job(algo_recurrence.close_stale_clusters, "interval", hours=1, id="close_clusters")
    scheduler.start()
    logger.info("Scheduler started")

    # 7. Kafka consumer (background task)
    consumer_task = asyncio.create_task(consume_loop())

    yield

    # Shutdown
    consumer_task.cancel()
    try:
        await consumer_task
    except asyncio.CancelledError:
        pass
    scheduler.shutdown(wait=False)
    await poller.close_producer()
    await database.close_pool()
    await embeddings.close_redis()
    logger.info("Analyzer shut down")


app = FastAPI(title="Analyzer", version="1.0.0", lifespan=lifespan)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "faiss_vectors": embeddings._index.ntotal if embeddings._index else 0,
    }
