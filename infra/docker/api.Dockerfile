# AI Quant Fund — API/Worker image (multi-stage, non-root)
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /workspace

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY apps/api ./apps/api
COPY services ./services
COPY db ./db
COPY alembic.ini pyproject.toml ./

ENV PYTHONPATH=/workspace/apps/api:/workspace/services

RUN useradd -m appuser && chown -R appuser /workspace
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]