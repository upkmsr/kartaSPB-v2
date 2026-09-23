# Local data workspace

`sources/` is reserved for immutable or externally versioned source downloads. `cache/` is reserved for derived and disposable import artefacts.

FOUNDATION 1 stores versioned Geofabrik PBF files under `sources/osm/` and derived regional extracts plus checksum sidecars under `cache/osm/`.

Large GIS datasets are deliberately excluded from Git, including OSM PBF, change files, GTFS archives, MBTiles, and PMTiles. Only `.gitkeep` placeholders and this documentation belong in version control.
