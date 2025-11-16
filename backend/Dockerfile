FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    gcc \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Configure pip for better SSL and retry handling
RUN pip install --upgrade pip setuptools wheel && \
    pip config set global.timeout 600 && \
    pip config set global.retries 10

# Set environment variables for better SSL and network handling
ENV PIP_DEFAULT_TIMEOUT=600
ENV PIP_RETRIES=10
ENV PYTHONUNBUFFERED=1
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt

RUN pip install --no-cache-dir poetry==2.1.3

RUN poetry config virtualenvs.create false && \
    poetry config installer.max-workers 1

WORKDIR /app

COPY pyproject.toml poetry.lock ./

# Install dependencies with retry logic
RUN for i in 1 2 3; do \
        echo "Installation attempt $i"; \
        if poetry install --only main --no-interaction --no-root; then \
            echo "Installation successful"; \
            break; \
        else \
            echo "Attempt $i failed, waiting before retry..."; \
            if [ $i -lt 3 ]; then sleep 30; fi; \
        fi; \
    done

FROM python:3.12-slim AS runtime

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

WORKDIR /app

COPY ./src .

ENV PYTHONPATH=/app

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

EXPOSE 8000
