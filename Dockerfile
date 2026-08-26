########### BASE STAGE ###########
FROM python:3.14-slim AS base

# uv binary (pinned) — replaces pip for all dependency installation
COPY --from=ghcr.io/astral-sh/uv:0.10.0 /uv /uvx /bin/

# set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
# the venv lives OUTSIDE /app: docker-compose-dev.yml bind-mounts ./app/ over /app,
# which would shadow a venv placed inside it
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
# put the venv ahead of the system interpreter so `python manage.py ...` and
# `gunicorn ...` resolve without any activation step
ENV PATH="/opt/venv/bin:$PATH"

# build + runtime libraries for mysqlclient (lxml ships manylinux wheels)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        pkg-config \
        default-libmysqlclient-dev \
        libmariadb3 \
    && rm -rf /var/lib/apt/lists/*

# dependency manifests live in their own directory so the bind-mounted /app
# cannot hide them from uv
WORKDIR /deps
COPY pyproject.toml uv.lock /deps/

EXPOSE 8000

WORKDIR /app


########### DEV STAGE ###########
FROM base AS dev

# dependency layer: cached until pyproject.toml / uv.lock change.
# --frozen fails the build if uv.lock is stale rather than silently re-resolving.
# includes the dev dependency-group (django-debug-toolbar)
RUN uv sync --frozen --no-install-project --project /deps


########### PRODUCTION STAGE ###########
FROM base AS prod

# same dependency layer, without the dev group
RUN uv sync --frozen --no-install-project --no-dev --project /deps

# create a app user
# -m creates /home/appuser: gunicorn 26's control socket falls back to
# $HOME/.gunicorn/gunicorn.ctl, and without a writable home it logs
# "Control server error: [Errno 13] Permission denied: '/home/appuser'"
RUN groupadd -r appuser && useradd -r -m -d /home/appuser -g appuser appuser

# create directory for collectstatic command
RUN mkdir /app/static_files && chown appuser:appuser /app/static_files

# copy project
COPY --chown=appuser:appuser ./app/ /app/

# the venv is built as root; hand it to the runtime user
RUN chown -R appuser:appuser /opt/venv

# change to the app user
USER appuser
