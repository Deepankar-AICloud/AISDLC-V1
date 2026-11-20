# AISDLC Portal: one container serving the API and the built React app.
# Build from apps/intake-portal:  docker build -t aisdlc-portal .

# ---- frontend build ---------------------------------------------------------
FROM node:22.12.0-alpine3.20 AS web
# Optional package mirrors, e.g. --build-arg NPM_CONFIG_REGISTRY=https://mirror/npm/
ARG NPM_CONFIG_REGISTRY=https://registry.npmjs.org/
ENV NPM_CONFIG_REGISTRY=${NPM_CONFIG_REGISTRY}
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---- runtime ----------------------------------------------------------------
FROM python:3.12.8-slim-bookworm AS runtime
ARG PIP_INDEX_URL=https://pypi.org/simple
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    APP_ENV=production \
    AUTH_MODE=entra \
    GITHUB_MODE=app \
    EXTRACTION_ISOLATION=process \
    SERVE_FRONTEND_DIR=/app/static \
    DATA_DIR=/app/var \
    PORT=8000

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin portal
WORKDIR /app
COPY backend/requirements.lock ./
RUN pip install --index-url "${PIP_INDEX_URL}" --require-hashes --no-deps -r requirements.lock
COPY backend/app ./app
COPY --from=web /web/dist ./static
RUN mkdir -p /app/var && chown -R portal:portal /app/var

USER portal
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import os,urllib.request,sys; sys.exit(0 if urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/healthz', timeout=4).status == 200 else 1)"

# App Service terminates TLS in front of the container and sets X-Forwarded-* headers.
CMD ["sh", "-c", "exec python -m uvicorn app.main:create_app --factory --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*' --no-server-header"]
