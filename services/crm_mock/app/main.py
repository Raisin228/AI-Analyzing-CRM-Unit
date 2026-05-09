"""Точка входа в CRM_Mock. Атрошенко Б. С."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from . import state
from .routes.events import router as events_router
from .routes.reviews import router as reviews_router
from .seeder import generate_reviews

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_application: FastAPI):
    """Код исполняемый до/после запуска приложения"""

    state.reviews = generate_reviews(200)
    yield


app = FastAPI(title="CRM Mock", version="1.0.0", lifespan=lifespan)
app.include_router(reviews_router)
app.include_router(events_router)


@app.get("/health")
async def health():
    """Проверка состояния сервиса."""

    return {"status": "ok", "reviews": len(state.reviews), "events": len(state.events)}
