# ─── Base stage ───────────────────────────────────────────────
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libffi-dev \
    libjpeg-dev \
    libpng-dev \
    zlib1g-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ─── App stage ────────────────────────────────────────────────
FROM base AS app

COPY . .

RUN mkdir -p /app/uploads/avatars /app/uploads/items

EXPOSE 5000

CMD ["gunicorn", \
     "--worker-class", "eventlet", \
     "--workers", "1", \
     "--bind", "0.0.0.0:5000", \
     "--timeout", "120", \
     "--keep-alive", "5", \
     "--log-level", "info", \
     "wsgi:app"]

# ─── Worker stage ─────────────────────────────────────────────
FROM base AS worker

COPY . .

# Worker has no exposed port — started via celery command in compose
CMD ["celery", "-A", "celery_worker.worker", "worker", "--loglevel=info"]
