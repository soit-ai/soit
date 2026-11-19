# Dependencies are resolved in the full Python image, which carries the
# compilers an sdist may need, and only the finished virtualenv and the
# application source reach the slim runtime images.
ARG PYTHON_VERSION=3.12

FROM python:${PYTHON_VERSION} AS builder

# No uv cache: it would land in a layer, and the cache mount that avoids
# that needs BuildKit, which not every Docker install has.
ENV UV_COMPILE_BYTECODE=1 \
    UV_NO_CACHE=1 \
    UV_LINK_MODE=copy \
    UV_HTTP_TIMEOUT=600 \
    UV_PYTHON_DOWNLOADS=0
WORKDIR /app/
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /bin/

# Lock and manifest first, so a source-only change reuses the dependency layer.
COPY pyproject.toml uv.lock README.md ./

FROM builder AS runtime-deps
RUN uv sync --frozen --no-dev --no-install-project
COPY ./ /app/
RUN uv sync --frozen --no-dev

FROM python:${PYTHON_VERSION}-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app
WORKDIR /app/
# libmagic backs python-magic's upload type detection.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libmagic1 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 appuser

FROM base AS runtime

COPY --from=runtime-deps /app /app

EXPOSE 9200

ENV HOME=/home/appuser
USER appuser

# Run one ASGI process per container; scale with container replicas.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9200"]

# The knowledge worker comes last: the classic builder builds every stage up
# to its target, so a `--target runtime` build never pays for document OCR.
FROM builder AS knowledge-worker-deps
RUN uv sync --frozen --no-dev --extra knowledge-worker --no-install-project
COPY ./ /app/
RUN uv sync --frozen --no-dev --extra knowledge-worker

FROM base AS knowledge-worker

# OpenCV, which document OCR loads, links against libGL and GLib.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=knowledge-worker-deps /app /app

ENV HOME=/home/appuser
USER appuser
