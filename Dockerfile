FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src/ ./src/
RUN uv sync --frozen --no-dev

FROM python:3.12-slim
RUN useradd -m app
WORKDIR /app
COPY --from=builder --chown=app:app /app /app
RUN chown app:app /app
USER app
ENV PATH="/app/.venv/bin:$PATH"
CMD ["uvicorn", "chief.api:app", "--host", "0.0.0.0", "--port", "8000"]
