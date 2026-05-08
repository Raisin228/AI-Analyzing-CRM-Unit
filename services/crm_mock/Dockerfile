# Сборка CRMки

FROM python:3.11-slim

WORKDIR /app

# Бахнули зависимости по умолчанию, которые для всех и специфичные для CRM
RUN pip install --upgrade pip wheel "poetry==2.1.1"
RUN poetry config virtualenvs.create false --local
COPY pyproject.toml poetry.lock ./
RUN poetry install --with crm_mock --no-root

# Скопировали весь сервис и запустились
COPY services/crm_mock/app/ ./app/
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
