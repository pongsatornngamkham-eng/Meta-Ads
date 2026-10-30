# syntax=docker/dockerfile:1
FROM node:24-bookworm-slim AS frontend-build
WORKDIR /build/frontend
ENV NEXT_TELEMETRY_DISABLED=1
COPY frontend/package.json frontend/package-lock.json ./
RUN --mount=type=secret,id=proxy_ca \
    set -e; if [ -s /run/secrets/proxy_ca ]; then \
      NODE_EXTRA_CA_CERTS=/run/secrets/proxy_ca npm ci --strict-ssl=true; \
    else npm ci --strict-ssl=true; fi
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm AS python-build
WORKDIR /build/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN --mount=type=secret,id=proxy_ca \
    set -e; if [ -s /run/secrets/proxy_ca ]; then \
      cat /etc/ssl/certs/ca-certificates.crt /run/secrets/proxy_ca > /tmp/build-ca.pem; \
      PIP_CERT=/tmp/build-ca.pem pip install --no-cache-dir 'uv==0.12.23'; \
      SSL_CERT_FILE=/tmp/build-ca.pem UV_NATIVE_TLS=true uv sync --frozen --no-dev; \
      rm -f /tmp/build-ca.pem; \
    else pip install --no-cache-dir 'uv==0.12.23' && uv sync --frozen --no-dev; fi

FROM python:3.12-slim-bookworm AS runtime
WORKDIR /app
RUN useradd --create-home --uid 10001 appuser
COPY --from=frontend-build /usr/local/bin/node /usr/local/bin/node
COPY --from=frontend-build /usr/lib/*-linux-gnu/libstdc++.so.6* /usr/lib/
COPY --from=frontend-build /usr/lib/*-linux-gnu/libgcc_s.so.1 /usr/lib/
COPY --chown=appuser:appuser --from=python-build /build/backend/.venv /app/backend/.venv
COPY --chown=appuser:appuser backend/app/ /app/backend/app/
COPY --chown=appuser:appuser fixtures/ /app/fixtures/
COPY --chown=appuser:appuser --from=frontend-build /build/frontend/.next/standalone/ /app/frontend/
COPY --chown=appuser:appuser --from=frontend-build /build/frontend/.next/static/ /app/frontend/.next/static/
COPY --chown=appuser:appuser --from=frontend-build /build/frontend/public/ /app/frontend/public/
COPY --chown=appuser:appuser deploy/serve.py /app/serve.py
ENV PATH="/app/backend/.venv/bin:$PATH" PYTHONPATH=/app/backend \
    PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 PORT=3000 DASHBOARD_LOCAL_MODE=false
USER appuser
EXPOSE 3000
CMD ["python", "/app/serve.py"]
