# Crypto-screener backend: FastAPI + LightGBM (CPU).
FROM python:3.11-slim

# libgomp1 is required by LightGBM at runtime; curl is used by the healthcheck.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Copy project metadata and application code, then install.
COPY pyproject.toml ./
COPY app ./app
RUN pip install --upgrade pip && pip install .

# Persisted models + SQLite live here (mount a volume in production).
RUN mkdir -p /app/models /data
ENV SCREENER_MODEL_DIR=/app/models \
    SCREENER_DATABASE_URL=sqlite:////data/screener.db

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=5 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
