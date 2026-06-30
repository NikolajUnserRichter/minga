# Single-service demo deployment (frontend + backend)
FROM node:20-alpine AS frontend-builder
WORKDIR /frontend
ARG VITE_AUTH_DISABLED=true
ARG VITE_API_URL=
ARG VITE_KEYCLOAK_URL=
ARG VITE_KEYCLOAK_REALM=novaerp
ARG VITE_KEYCLOAK_CLIENT_ID=novaerp-frontend
ENV VITE_AUTH_DISABLED=${VITE_AUTH_DISABLED}
ENV VITE_API_URL=${VITE_API_URL}
ENV VITE_KEYCLOAK_URL=${VITE_KEYCLOAK_URL}
ENV VITE_KEYCLOAK_REALM=${VITE_KEYCLOAK_REALM}
ENV VITE_KEYCLOAK_CLIENT_ID=${VITE_KEYCLOAK_CLIENT_ID}
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./
COPY --from=frontend-builder /frontend/dist /app/static

RUN mkdir -p /data

ENV AUTH_DISABLED=true
ENV DATABASE_URL=sqlite:////data/minga_demo.db
ENV REDIS_URL=redis://localhost:6379/0
ENV FORECASTING_SERVICE_URL=http://localhost:8001
ENV DEBUG=false

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
