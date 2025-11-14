FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir poetry==2.1.3

RUN poetry config virtualenvs.create false

WORKDIR /app

COPY pyproject.toml poetry.lock ./

RUN poetry install --only main --no-interaction --no-root

FROM python:3.12-slim AS runtime

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

WORKDIR /app

COPY ./src .

ENV PYTHONPATH=/app

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

EXPOSE 8000
