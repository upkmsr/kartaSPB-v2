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

Region profiles live in `config/osm/regions.json`. `spb_smoke` is the fast real-data acceptance box. `spb_lo` is a coarse geographic bounding box covering Saint Petersburg and Leningrad Oblast; it is explicitly not an official administrative boundary. Both bbox profiles retain Osmium's `simple` extraction strategy.

`spb_districts` is a separate relation-rooted profile for the Saint Petersburg administrative hierarchy. It selects root relation `r337422` and uses `osmium getid --add-referenced --verbose-ids`, preserving child relations and the referenced ways and nodes needed by the existing geometry assembler. The root's `role=subarea` members are the production source of district identities; names and the documented list of 18 relations are acceptance evidence only. A validated run from registered source version `20260921T231045Z` contained all 18 `admin_level=5` districts with complete references, valid assembled geometry, and canonical source bindings.

The district extract must use the same registered immutable source version as the normal OSM profile being complemented. Extract paths include that source version, and import metadata points to the same source registry row; do not combine district and bbox extracts from different versions.

Osmium's `simple` extraction strategy is used for bbox profiles because current high OSM node IDs make `complete_ways` require more than the 4 GB reference Docker allocation. Ways crossing a bbox can therefore lack out-of-bounds node references and receive null geometry; all retained source tags and identity remain intact. FOUNDATION 2 exposes these cases as `partial` or `incomplete` instead of silently presenting them as complete geometry. Relation-rooted profiles provide reference completion only for their explicitly selected hierarchy.

Every future source must have a registry entry with provider, URL, licence, and attribution before ingestion. A source adapter translates provider-specific records into staging and then canonical structures. Consumers must not branch on the original provider.

Downloaded immutable source files belong in `data/sources/osm/`; disposable extracts and checksum sidecars belong in `data/cache/osm/`. Both are ignored by Git apart from placeholders. Database dumps, credentials, API keys, and large formats such as `.osm.pbf`, GTFS archives, MBTiles, and PMTiles must never be committed.
