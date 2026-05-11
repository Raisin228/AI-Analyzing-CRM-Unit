"""Точка входа в CRM_Mock. Атрошенко Б. С."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from . import state
from .api.router import router as reviews_router
from .seeder import GeneratorFakeUserReviews

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_application: FastAPI):
    """Код исполняемый до/после запуска приложения"""

    state.reviews.extend(GeneratorFakeUserReviews.generate_reviews(50))
    yield


app = FastAPI(title="CRM Mock", version="1.0.0", lifespan=lifespan)
app.include_router(reviews_router)
