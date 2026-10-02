FROM postgres:17.5-bookworm@sha256:fbcea1bd13b6a882cd6caa6b58db3ae5c102efe50ec625b3e2a5cbc50db5bfe4

ARG POSTGIS_VERSION=3.6.4+dfsg-2.pgdg12+1

RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
        "postgresql-17-postgis-3=${POSTGIS_VERSION}" \
        "postgresql-17-postgis-3-scripts=${POSTGIS_VERSION}" \
    && rm -rf /var/lib/apt/lists/*

LABEL org.opencontainers.image.title="KARTASPB PostgreSQL/PostGIS" \
      org.opencontainers.image.description="Native multi-arch PostgreSQL 17.5 with PostGIS 3.6.4"
