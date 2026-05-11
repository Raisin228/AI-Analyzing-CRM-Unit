FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip wheel "poetry==2.1.1"
RUN poetry config virtualenvs.create false --local

COPY pyproject.toml poetry.lock ./
RUN poetry install --with analyzer --no-root

# Alembic
COPY services/analyzer/alembic.ini ./
COPY services/analyzer/alembic/ ./alembic/

# Service packages
COPY services/analyzer/app/ ./app/
COPY services/analyzer/database/ ./database/
COPY services/analyzer/redis_service/ ./redis_service/
COPY services/analyzer/Embeddings/ ./Embeddings/

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
