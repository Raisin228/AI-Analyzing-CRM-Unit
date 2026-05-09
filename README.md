# AI Analyzing CRM Unit

An intelligent service for automated analysis of customer reviews from a CRM system.

## Architecture

```
crm_mock   (port 8000) — stores reviews in memory, accepts incoming events
analyzer   (port 8001) — polls CRM, runs LLM analysis, detects patterns, fires events

PostgreSQL 16  (port 5432) — persistent storage for analysis results
Redis 7        (port 6379) — embedding cache + poller cursor
Redpanda       (port 9092) — Kafka-compatible broker (topic: reviews.raw)
Ollama         (port 11434) — local LLM inference (llama3.1:8b)
LangFuse       (port 3000)  — LLM call tracing & observability
```

## Data Flow

```
crm_mock ──GET /reviews──► poller ──► Kafka (reviews.raw)
                                          │
                                          ▼
                                    llm_pipeline (LangGraph)
                                    ├── extract_entities   (LLM)
                                    ├── classify_sentiment (LLM)
                                    ├── detect_mismatch    (Python)
                                    └── save_results       (PostgreSQL)
                                          │
                              ┌───────────┼──────────────┐
                              ▼           ▼              ▼
                         dispatcher  recurrence      anomaly
                              │        (FAISS)  (z-score / KL)
                              ▼
                       crm_mock POST /events
```

## Quick Start

### 1. Environment variables

```bash
cp .env.example .env
```

After the first run:
1. Open http://localhost:3000
2. Register a LangFuse account
3. Create a project and generate API keys
4. Put the keys into `.env`:
   ```
   LANGFUSE_PUBLIC_KEY=pk-lf-...
   LANGFUSE_SECRET_KEY=sk-lf-...
   ```

> If LangFuse keys are left as placeholders, tracing is silently disabled — everything else works normally.

### 2. Run

```bash
docker-compose up --build
```

The first run takes longer: Ollama downloads `llama3.1:8b` (~5 GB) and
sentence-transformers downloads `multilingual-e5-large` (~560 MB).
Both are cached in Docker volumes, so subsequent runs are fast.

### 3. Verify

```bash
# CRM — should return 200 reviews
curl http://localhost:8000/reviews | jq length

# Analyzer health (shows FAISS index size)
curl http://localhost:8001/health

# Incoming events (give it ~30 sec to process)
curl http://localhost:8000/events | jq .
```

## Event Types

| Type | Trigger |
|------|---------|
| `critical_negative` | sentiment = negative AND confidence ≥ 0.9 |
| `sentiment_mismatch` | rating doesn't match the detected sentiment |
| `recurring_issue` | complaint matched an open cluster (cosine ≥ 0.85) |
| `volume_anomaly` | z-score of negative reviews over 24 h ≥ 2.5 |
| `topic_shift` | KL-divergence of issue topics ≥ 0.5 |

## Development (hot reload)

`docker-compose.override.yml` is picked up automatically and mounts local source
into the containers with `--reload`:

```bash
docker-compose up          # dev mode (with override)
docker-compose -f docker-compose.yml up   # production mode (no override)
```

Any change to a `.py` file inside `services/crm_mock/app/` or `services/analyzer/app/`
is reflected in the running container within ~1 second.

## Repository Structure

```
docker-compose.yml              — infrastructure + services
docker-compose.override.yml     — dev overrides (hot reload)
pyproject.toml                  — single Poetry project with dependency groups
.env.example                    — environment variable template
services/
├── crm_mock/
│   ├── Dockerfile              — poetry install --with crm_mock
│   └── app/
│       ├── main.py
│       ├── models.py
│       ├── seeder.py
│       ├── state.py
│       └── routes/
│           ├── reviews.py
│           └── events.py
└── analyzer/
    ├── Dockerfile              — poetry install --with analyzer
    ├── alembic.ini
    ├── alembic/
    │   └── versions/
    │       └── 001_initial.py
    └── app/
        ├── main.py
        ├── config.py
        ├── db.py
        ├── poller.py
        ├── llm_pipeline.py
        ├── embeddings.py
        ├── algo_recurrence.py
        ├── algo_anomaly.py
        └── dispatcher.py
```

## Tech Stack

| Layer | Technology |
|-------|------------|
| API | FastAPI 0.136, Uvicorn |
| LLM orchestration | LangChain + LangGraph |
| Local inference | Ollama (llama3.1:8b) |
| Embeddings | intfloat/multilingual-e5-large (1024-dim) |
| Vector search | FAISS IndexFlatIP (cosine via L2 normalization) |
| Message broker | Redpanda (Kafka-compatible) |
| Async DB | asyncpg (raw SQL, no ORM) |
| Migrations | Alembic |
| Cache | Redis 7 |
| Scheduling | APScheduler |
| Observability | LangFuse |
| Seed data | Faker (ru_RU locale) |
| Packaging | Poetry 2 with dependency groups |
