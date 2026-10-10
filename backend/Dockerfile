# One image for API and worker: identical code, different command.
#   API:    (default CMD below)
#   Worker: python -m app.workers
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
RUN useradd --create-home --uid 10001 app

COPY pyproject.toml ./
# Install dependencies only (a layer cached until pyproject.toml changes), then the source.
RUN pip install --upgrade pip && pip install . && pip uninstall -y hotsmoothie-backend

COPY --chown=app:app . .
USER app

EXPOSE 8000
# Client IPs behind proxies are resolved by the app (CLIENT_IP_HEADER / TRUSTED_PROXY_HOPS), not by
# uvicorn's --proxy-headers, which trusts the client-controlled left end of X-Forwarded-For.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --no-proxy-headers --workers ${WEB_CONCURRENCY:-2} --no-server-header --timeout-graceful-shutdown 25"]
