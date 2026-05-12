# ─ Stage 1: builder ─
# gcc/g++ нужны для компиляции asyncpg и других C-расширений.
# В финальный образ они не попадут.
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ \
    && rm -rf /var/lib/apt/lists/*

COPY services/analyzer/requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

# ─ Stage 2: runtime ─
FROM python:3.11-slim

WORKDIR /app

# Копируем только установленные пакеты — без build-tools и кэша pip
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Alembic
COPY services/analyzer/alembic.ini ./
COPY services/analyzer/alembic/ ./alembic/

# Кладём пакеты в analyzer/, чтобы from ..database / ..redis_service работали
COPY services/analyzer/__init__.py ./analyzer/__init__.py
COPY services/analyzer/utils.py ./analyzer/utils.py
COPY services/analyzer/prompts/ ./analyzer/prompts/
COPY services/analyzer/app/ ./analyzer/app/
COPY services/analyzer/database/ ./analyzer/database/
COPY services/analyzer/kafka/ ./analyzer/kafka/
COPY services/analyzer/redis_service/ ./analyzer/redis_service/
COPY services/analyzer/Embeddings/ ./analyzer/Embeddings/
COPY services/analyzer/research/ ./analyzer/research/

CMD ["uvicorn", "analyzer.app.main:app", "--host", "0.0.0.0", "--port", "8001"]
