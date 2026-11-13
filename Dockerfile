FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --group api --no-install-project
COPY harness ./harness
COPY models ./models
COPY specs ./specs
COPY scripts ./scripts
RUN uv sync --frozen --no-dev --group api && uv run --no-sync python scripts/fetch_data.py
EXPOSE 8000
CMD ["uv", "run", "--no-sync", "uvicorn", "harness.api:app", "--host", "0.0.0.0", "--port", "8000"]
