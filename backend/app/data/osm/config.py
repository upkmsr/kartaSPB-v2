import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SourceConfig:
    name: str
    provider: str
    source_type: str
    source_url: str
    checksum_url: str | None
    license: str
    attribution: str


@dataclass(frozen=True)
class RegionConfig:
    name: str
    type: str
    bbox: tuple[float, float, float, float]
    description: str


def project_root() -> Path:
    configured = os.getenv("PROJECT_ROOT")
    if configured:
        return Path(configured).resolve()
    return Path(__file__).resolve().parents[4]


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        value = json.load(file)
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return value


def load_source(root: Path | None = None) -> SourceConfig:
    data = _load_json((root or project_root()) / "config/osm/source.json")
    required = {
        "name",
        "provider",
        "source_type",
        "source_url",
        "license",
        "attribution",
    }
    missing = required - data.keys()
    if missing:
        raise ValueError(f"OSM source config is missing: {sorted(missing)}")
    return SourceConfig(
        name=str(data["name"]),
        provider=str(data["provider"]),
        source_type=str(data["source_type"]),
        source_url=str(data["source_url"]),
        checksum_url=str(data["checksum_url"]) if data.get("checksum_url") else None,
        license=str(data["license"]),
        attribution=str(data["attribution"]),
    )


def load_regions(root: Path | None = None) -> dict[str, RegionConfig]:
    data = _load_json((root or project_root()) / "config/osm/regions.json")
    regions: dict[str, RegionConfig] = {}
    for name, raw_value in data.items():
        if not isinstance(raw_value, dict):
            raise ValueError(f"Region {name!r} must be an object")
        raw_bbox = raw_value.get("bbox")
        if raw_value.get("type") != "bbox" or not isinstance(raw_bbox, list):
            raise ValueError(f"Region {name!r} must define a bbox")
        if len(raw_bbox) != 4:
            raise ValueError(f"Region {name!r} bbox must contain four coordinates")
        bbox = tuple(float(value) for value in raw_bbox)
        min_lon, min_lat, max_lon, max_lat = bbox
        if not (-180 <= min_lon < max_lon <= 180 and -90 <= min_lat < max_lat <= 90):
            raise ValueError(f"Region {name!r} has an invalid bbox")
        regions[name] = RegionConfig(
            name=name,
            type="bbox",
            bbox=(min_lon, min_lat, max_lon, max_lat),
            description=str(raw_value.get("description", "")),
        )
    return regions


def load_region(name: str, root: Path | None = None) -> RegionConfig:
    try:
        return load_regions(root)[name]
    except KeyError as exc:
        raise ValueError(f"Unknown OSM region {name!r}") from exc
