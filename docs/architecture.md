# Architecture

## Product boundary

KARTASPB v2 is a desktop-first / desktop-only GIS application.

- Minimum supported viewport width: **1280 px**.
- Primary input: mouse and keyboard.
- Target resolutions include 1440×900 and 1920×1080.
- Phone and tablet-specific layouts, navigation, controls, breakpoints, touch QA, and PWA mobile UX are outside project scope.

At narrower desktop window sizes, the application may show a minimum-width notice instead of attempting a mobile layout.

## Data flow

```text
External open data
        ↓
Source adapter
        ↓
Staging
        ↓
Normalisation
        ↓
Canonical GIS model
        ↓
PostGIS
        ↓
Domain logic
        ↓
API
        ↓
Desktop frontend / map / analytics
```

The source-to-canonical boundary is the central architectural rule. The frontend and domain logic consume canonical objects; they must not need to know whether a school, park, road, or medical facility came from OpenStreetMap or an official registry.

## Components

- **Frontend:** React, TypeScript, Vite, and MapLibre GL JS. FOUNDATION 0 contains a desktop shell and a map workspace placeholder only.
- **Backend:** FastAPI exposes transport concerns. Domain code owns application meaning. The data package will own adapters, imports, and normalisation.
- **Database:** PostgreSQL/PostGIS holds the canonical spatial system of record. Alembic exclusively manages schema changes.
- **Infrastructure:** Docker Compose makes database initialisation, migrations, API startup, and the frontend deterministic.

## Dependency direction

Source-specific concepts stop at the data layer. Domain logic may depend on canonical models, and API handlers may depend on domain services. The reverse dependencies are not allowed. No category-specific ingestion subsystems are introduced during FOUNDATION 0.

## Deferred work

OSM download/import, osm2pgsql, categories, POIs, basemap tiles, routing, and scoring belong to later foundations. In particular, FOUNDATION 1 is the OSM Data Engine and is not part of this repository state.
