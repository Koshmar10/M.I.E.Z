# backend/Dockerfile
FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.23 /uv /uvx /bin/

# The venv lives outside /app so the dev bind mount (./backend:/app) doesn't hide it.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_PYTHON_DOWNLOADS=never \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/opt/venv/bin:$PATH"

RUN apt-get update && apt-get install -y postgresql-client

WORKDIR /app

# Production installs runtime deps only; docker-compose.yaml passes "" to include dev tools.
ARG UV_SYNC_ARGS="--no-dev"
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --locked $UV_SYNC_ARGS

COPY . .

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
