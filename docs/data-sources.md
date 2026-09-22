# Data sources

The architecture is intended to support:

- OpenStreetMap PBF and change feeds;
- GTFS and compatible open transport data;
- official city, regional, and federal open-data portals;
- government and municipal registries;
- other open GIS datasets with suitable licensing and provenance.

No real dataset is downloaded or imported in FOUNDATION 0.

Every future source must have a registry entry with provider, URL, licence, and attribution before ingestion. A source adapter translates provider-specific records into staging and then canonical structures. Consumers must not branch on the original provider.

Downloaded source files belong in `data/sources/`; disposable or derived artefacts belong in `data/cache/`. Both directories are ignored by Git apart from placeholders and documentation. Database dumps, credentials, API keys, and large formats such as `.osm.pbf`, GTFS archives, MBTiles, and PMTiles must never be committed.
