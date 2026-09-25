import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal


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
class BboxRegionConfig:
    name: str
    type: Literal["bbox"]
    bbox: tuple[float, float, float, float]
    description: str


@dataclass(frozen=True)
class RelationRegionConfig:
    name: str
    type: Literal["relation"]
    relation_ids: tuple[int, ...]
    description: str


type RegionConfig = BboxRegionConfig | RelationRegionConfig


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
        profile_type = raw_value.get("type")
        description = str(raw_value.get("description", ""))
        if profile_type == "bbox":
            unexpected = set(raw_value) - {"type", "bbox", "description"}
            if unexpected:
                raise ValueError(
                    f"Region {name!r} bbox profile has incompatible fields: {sorted(unexpected)}"
                )
            raw_bbox = raw_value.get("bbox")
            if not isinstance(raw_bbox, list):
                raise ValueError(f"Region {name!r} must define a bbox")
            if len(raw_bbox) != 4:
                raise ValueError(f"Region {name!r} bbox must contain four coordinates")
            try:
                bbox = tuple(float(value) for value in raw_bbox)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Region {name!r} has an invalid bbox") from exc
            min_lon, min_lat, max_lon, max_lat = bbox
            if not (
                all(math.isfinite(value) for value in bbox)
                and -180 <= min_lon < max_lon <= 180
                and -90 <= min_lat < max_lat <= 90
            ):
                raise ValueError(f"Region {name!r} has an invalid bbox")
            regions[name] = BboxRegionConfig(
                name=name,
                type="bbox",
                bbox=(min_lon, min_lat, max_lon, max_lat),
                description=description,
            )
        elif profile_type == "relation":
            unexpected = set(raw_value) - {"type", "relation_ids", "description"}
            if unexpected:
                raise ValueError(
                    f"Region {name!r} relation profile has incompatible fields: "
                    f"{sorted(unexpected)}"
                )
            raw_relation_ids = raw_value.get("relation_ids")
            if not isinstance(raw_relation_ids, list) or not raw_relation_ids:
                raise ValueError(f"Region {name!r} must define non-empty relation_ids")
            if any(
                isinstance(relation_id, bool)
                or not isinstance(relation_id, int)
                or relation_id <= 0
                for relation_id in raw_relation_ids
            ):
                raise ValueError(f"Region {name!r} relation_ids must be positive integers")
            relation_ids = tuple(raw_relation_ids)
            if len(set(relation_ids)) != len(relation_ids):
                raise ValueError(f"Region {name!r} relation_ids must be unique")
            regions[name] = RelationRegionConfig(
                name=name,
                type="relation",
                relation_ids=relation_ids,
                description=description,
            )
        else:
            raise ValueError(f"Region {name!r} has unknown profile type {profile_type!r}")
    return regions


def load_region(name: str, root: Path | None = None) -> RegionConfig:
    try:
        return load_regions(root)[name]
    except KeyError as exc:
        raise ValueError(f"Unknown OSM region {name!r}") from exc
