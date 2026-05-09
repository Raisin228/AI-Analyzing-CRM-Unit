# AI Analyzing CRM Unit

Сервис интеллектуального анализа клиентских отзывов.

## Архитектура

```
crm_mock   (port 8000) — хранит отзывы в памяти, принимает события
analyzer   (port 8001) — поллит CRM, анализирует через LLM, детектирует паттерны

PostgreSQL 16  (port 5432) — хранилище результатов
Redis 7        (port 6379) — кеш эмбеддингов + курсор поллера
Redpanda       (port 9092) — Kafka-совместимый брокер (topic: reviews.raw)
Ollama         (port 11434) — локальный LLM (llama3.1:8b)
LangFuse       (port 3000)  — трейсинг LLM-вызовов
```

## Быстрый старт

### 1. Настройка переменных окружения

```bash
cp .env.example .env
```

После первого запуска:
1. Перейти на http://localhost:3000
2. Создать аккаунт LangFuse
3. Создать API-ключи в проекте
4. Вставить ключи в `.env`:
   ```
   LANGFUSE_PUBLIC_KEY=pk-lf-...
   LANGFUSE_SECRET_KEY=sk-lf-...
   ```

> Без LangFuse-ключей трейсинг просто выключается, всё остальное работает.

### 2. Запуск

```bash
docker-compose up --build
```

Первый запуск дольше — Ollama скачивает модель `llama3.1:8b` (~5GB)
и sentence-transformers скачивает `multilingual-e5-large` (~560MB).

### 3. Проверка

```bash
# CRM — список отзывов (200 штук)
curl http://localhost:8000/reviews | jq length

# Analyzer health
curl http://localhost:8001/health

# Входящие события (после ~30 сек работы)
curl http://localhost:8000/events | jq .
```

## Поток данных

```
crm_mock ──GET /reviews──► poller ──► Kafka (reviews.raw)
                                          │
                                          ▼
                                    llm_pipeline
                                    ├── extract_entities  (LLM)
                                    ├── classify_sentiment (LLM)
                                    ├── detect_mismatch   (Python)
                                    └── save_results      (PostgreSQL)
                                          │
                              ┌───────────┼───────────────┐
                              ▼           ▼               ▼
                         dispatcher  recurrence       anomaly
                              │       (FAISS)    (z-score / KL)
                              ▼
                       crm_mock POST /events
```

## Типы событий

| Тип | Условие |
|-----|---------|
| `critical_negative` | sentiment=negative, confidence ≥ 0.9 |
| `sentiment_mismatch` | рейтинг не совпадает с тональностью |
| `recurring_issue` | жалоба попала в открытый кластер (cosine ≥ 0.85) |
| `volume_anomaly` | z-score негативных отзывов ≥ 2.5 |
| `topic_shift` | KL-дивергенция тематик ≥ 0.5 |

## Структура репозитория

```
docker-compose.yml
pyproject.toml          — единый Poetry проект с группами зависимостей
.env.example
services/
├── crm_mock/
│   ├── Dockerfile      — poetry install --with crm_mock
│   └── app/
│       ├── main.py, models.py, seeder.py, state.py
│       └── routes/ (reviews.py, events.py)
└── analyzer/
    ├── Dockerfile      — poetry install --with analyzer
    ├── alembic.ini
    ├── alembic/versions/001_initial.py
    └── app/
        ├── main.py, config.py, db.py
        ├── poller.py, llm_pipeline.py
        ├── embeddings.py
        ├── algo_recurrence.py, algo_anomaly.py
        └── dispatcher.py
```
