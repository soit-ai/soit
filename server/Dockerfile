# syntax=docker/dockerfile:1.7

FROM python:3.14 AS base

ENV PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app \
    UV_COMPILE_BYTECODE=1 \
    UV_HTTP_TIMEOUT=600 \
    UV_LINK_MODE=copy
WORKDIR /app/
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /uvx /bin/
RUN useradd --create-home --uid 10001 appuser
COPY ./ /app/

FROM base AS knowledge-worker

RUN --mount=type=cache,target=/root/.cache/uv \
    /bin/uv sync --frozen --no-dev --extra knowledge-worker

ENV HOME=/home/appuser
USER appuser

FROM base AS runtime

RUN --mount=type=cache,target=/root/.cache/uv \
    /bin/uv sync --frozen --no-dev

# Expose the port
EXPOSE 9200

ENV HOME=/home/appuser
USER appuser

# Run one ASGI process per container; scale with container replicas.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9200"]
