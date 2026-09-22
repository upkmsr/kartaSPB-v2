# Local data workspace

`sources/` is reserved for immutable or externally versioned source downloads. `cache/` is reserved for derived and disposable import artefacts.

Large GIS datasets are deliberately excluded from Git, including OSM PBF, change files, GTFS archives, MBTiles, and PMTiles. Keep only `.gitkeep` placeholders in these directories during FOUNDATION 0.
