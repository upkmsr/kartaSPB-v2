# Data sources

The architecture is intended to support:

- OpenStreetMap PBF and change feeds;
- GTFS and compatible open transport data;
- official city, regional, and federal open-data portals;
- government and municipal registries;
- other open GIS datasets with suitable licensing and provenance.

## OpenStreetMap / Geofabrik

The first configured source is Geofabrik's Northwestern Federal District `.osm.pbf`. Its registry record preserves:

- provider: Geofabrik GmbH;
- dataset URL and provider MD5 URL;
- licence: Open Database License 1.0;
- attribution: `© OpenStreetMap contributors; extract provided by Geofabrik GmbH`;
- upstream timestamp/version, local immutable filename, and locally computed SHA-256.

The download writes to a `.part` file, verifies the provider MD5 when available, validates the PBF with Osmium, calculates SHA-256, fsyncs, and atomically renames. A matching registered version and SHA-256 is not downloaded again unless `--force` is used.

Region profiles live in `config/osm/regions.json`. `spb_smoke` is the fast real-data acceptance box. `spb_lo` is a coarse geographic bounding box covering Saint Petersburg and Leningrad Oblast; it is explicitly not an official administrative boundary.

Osmium's `simple` extraction strategy is used because current high OSM node IDs make `complete_ways` require more than the 4 GB reference Docker allocation. Ways crossing the bbox can therefore lack out-of-bounds node references and receive null geometry; all retained source tags and identity remain intact. Exact boundary/reference completion is deferred with administrative clipping work.

Every future source must have a registry entry with provider, URL, licence, and attribution before ingestion. A source adapter translates provider-specific records into staging and then canonical structures. Consumers must not branch on the original provider.

Downloaded immutable source files belong in `data/sources/osm/`; disposable extracts and checksum sidecars belong in `data/cache/osm/`. Both are ignored by Git apart from placeholders. Database dumps, credentials, API keys, and large formats such as `.osm.pbf`, GTFS archives, MBTiles, and PMTiles must never be committed.
