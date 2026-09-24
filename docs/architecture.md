# Architecture

## Product boundary

KARTASPB v2 is a desktop-first / desktop-only GIS application.

- Minimum supported viewport width: **1280 px**.
- Primary input: mouse and keyboard.
- Target resolutions include 1440×900 and 1920×1080.
- Phone and tablet-specific layouts, navigation, controls, breakpoints, touch QA, and PWA mobile UX are outside project scope.

At narrower desktop window sizes, the application may show a minimum-width notice instead of attempting a mobile layout.

## Data flow

The foundation boundary is explicit:

```text
FOUNDATION 1 — OSM raw data
nodes / ways / relations
        ↓
FOUNDATION 2 — correct GIS interpretation
multipolygons / holes / boundaries / routes / ordered members
        ↓
FOUNDATION 3A — provider-independent canonical GIS identity
objects / source bindings / relationships / provenance
        ↓
FOUNDATION 3B — application meaning
school / pharmacy / park / road / transport / ...
```

FOUNDATION 2 and 3A do not assign application categories. FOUNDATION 2 turns
the OSM relation model into validated GIS structures; FOUNDATION 3A gives
eligible features stable provider-independent identity and provenance.

```text
External open data
        ↓
Provider PBF / source adapter
        ↓
Immutable local source (`data/sources`)
        ↓
Derived extract (`data/cache`)
        ↓
Source-shaped PostGIS staging
        ↓
Derived OSM geometry and ordered relations
        ↓
Canonical GIS model
        ↓
FOUNDATION 3B categories
        ↓
PostGIS
        ↓
Domain logic
        ↓
API
        ↓
Desktop frontend / map / analytics
```

The source-to-canonical boundary is the central architectural rule. The
frontend and domain logic consume canonical objects; they must not need to know
whether a future school, park, road, or medical category came from
OpenStreetMap or an official registry.

## Components

- **Frontend:** React, TypeScript, Vite, and MapLibre GL JS. FOUNDATION 0 contains a desktop shell and a map workspace placeholder only.
- **Backend:** FastAPI exposes transport concerns. Domain code owns application meaning. The data package will own adapters, imports, and normalisation.
- **Database:** PostgreSQL/PostGIS holds the canonical spatial system of record. Alembic exclusively manages schema changes.
- **OSM data engine:** a dedicated Docker service combines pinned Osmium and osm2pgsql versions with Python orchestration. Osmium validates and extracts; osm2pgsql Flex translates OSM primitives without category filtering and assembles mature multipolygon/boundary geometry.
- **Infrastructure:** Docker Compose makes database initialisation, migrations, API startup, frontend, and data tooling deterministic.

## Dependency direction

Source-specific concepts stop at the data layer. Domain logic may depend on
canonical models, and API handlers may depend on domain services. The reverse
dependencies are not allowed. Canonicalization reads `staging` and `derived`
and writes `catalog`; it does not create school, pharmacy, park, road, or
transport categories.

## Deferred work

Category extraction, exact administrative clipping, basemap layers, routing,
and scoring remain deferred. Transport routes retain their ordered semantics in
`derived` and are deliberately excluded from generic `catalog.objects`.
