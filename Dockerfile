# Both base indexes were resolved from their official registries on 2026-11-18.
FROM ghcr.io/astral-sh/uv:0.10.10@sha256:cbe0a44ba994e327b8fe7ed72beef1aaa7d2c4c795fd406d1dbf328bacb2f1c5 AS uv
FROM python:3.13.12-slim-bookworm@sha256:a58daefb915e1e03ad48f3ca4df8832065412c5c35cacb9d39f4229184de12b6
COPY --from=uv /uv /usr/local/bin/uv
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy PATH=/app/.venv/bin:$PATH
WORKDIR /app
COPY pyproject.toml uv.lock ./
# Official locked sync pattern: https://docs.astral.sh/uv/guides/integration/docker/
RUN uv sync --locked --no-dev --no-default-groups --no-install-project
COPY src ./src
COPY workbench ./workbench
COPY deploy/image_verify.py ./deploy/image_verify.py
COPY image-manifest.json ./image-manifest.json
RUN uv sync --locked --no-dev --no-default-groups --no-editable && python deploy/image_verify.py && useradd --uid 10001 --create-home appuser
USER 10001:10001
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "pricing_web.api:production_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-access-log"]
