FROM python:3.12-slim-bookworm

ARG OSMIUM_VERSION=1.15.0-1
ARG OSM2PGSQL_VERSION=1.8.0+ds-1

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PROJECT_ROOT=/workspace

RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
        ca-certificates \
        "osmium-tool=${OSMIUM_VERSION}" \
        "osm2pgsql=${OSM2PGSQL_VERSION}" \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace/backend
COPY backend/pyproject.toml ./pyproject.toml
COPY backend/app ./app
RUN pip install --upgrade pip && pip install .

COPY config /workspace/config

RUN useradd --create-home --uid 10001 ingest \
    && mkdir -p /workspace/data/sources/osm /workspace/data/cache/osm \
    && chown -R ingest:ingest /workspace
USER ingest

ENTRYPOINT ["python", "-m", "app.data.osm"]
CMD ["status"]
