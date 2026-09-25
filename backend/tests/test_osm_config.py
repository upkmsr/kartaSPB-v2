import json
from pathlib import Path

import pytest

from app.data.osm.config import (
    BboxRegionConfig,
    RelationRegionConfig,
    load_region,
    load_regions,
    load_source,
    project_root,
)


def test_source_metadata_preserves_license_and_attribution() -> None:
    source = load_source()

    assert source.provider == "Geofabrik GmbH"
    assert source.source_type == "osm_pbf"
    assert source.source_url.endswith("northwestern-fed-district-latest.osm.pbf")
    assert "ODbL" in source.license
    assert "OpenStreetMap contributors" in source.attribution


def test_region_configuration_contains_bbox_and_relation_profiles() -> None:
    regions = load_regions()

    assert set(regions) >= {"spb_smoke", "spb_lo", "spb_districts"}
    assert isinstance(regions["spb_smoke"], BboxRegionConfig)
    assert regions["spb_smoke"].bbox[0] < regions["spb_smoke"].bbox[2]
    assert "not an official administrative boundary" in regions["spb_lo"].description.lower()
    assert isinstance(regions["spb_districts"], RelationRegionConfig)
    assert regions["spb_districts"].relation_ids == (337422,)


def test_invalid_region_bbox_is_rejected(tmp_path: Path) -> None:
    config_dir = tmp_path / "config/osm"
    config_dir.mkdir(parents=True)
    (config_dir / "regions.json").write_text(
        json.dumps({"bad": {"type": "bbox", "bbox": [30, 60, 20, 50]}}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid bbox"):
        load_region("bad", tmp_path)


@pytest.mark.parametrize("relation_ids", [[], [0], [-1], [True], ["337422"]])
def test_invalid_relation_ids_are_rejected(tmp_path: Path, relation_ids: list[object]) -> None:
    config_dir = tmp_path / "config/osm"
    config_dir.mkdir(parents=True)
    (config_dir / "regions.json").write_text(
        json.dumps({"bad": {"type": "relation", "relation_ids": relation_ids}}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="relation_ids"):
        load_region("bad", tmp_path)


def test_unknown_region_profile_type_is_rejected(tmp_path: Path) -> None:
    config_dir = tmp_path / "config/osm"
    config_dir.mkdir(parents=True)
    (config_dir / "regions.json").write_text(
        json.dumps({"bad": {"type": "polygon", "bbox": [30, 59, 31, 60]}}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unknown profile type"):
        load_region("bad", tmp_path)


@pytest.mark.parametrize(
    ("profile", "message"),
    [
        ({"type": "bbox", "bbox": [30, 59, 31, 60], "relation_ids": [337422]}, "bbox profile"),
        (
            {"type": "relation", "relation_ids": [337422], "bbox": [30, 59, 31, 60]},
            "relation profile",
        ),
    ],
)
def test_incompatible_region_profile_fields_are_rejected(
    tmp_path: Path, profile: dict[str, object], message: str
) -> None:
    config_dir = tmp_path / "config/osm"
    config_dir.mkdir(parents=True)
    (config_dir / "regions.json").write_text(
        json.dumps({"bad": profile}), encoding="utf-8"
    )

    with pytest.raises(ValueError, match=message):
        load_region("bad", tmp_path)


def test_flex_marks_untagged_relation_member_ways_for_stage_two() -> None:
    flex = (project_root() / "config/osm/flex.lua").read_text(encoding="utf-8")

    assert "function osm2pgsql.select_relation_members(relation)" in flex
    assert "osm2pgsql.way_member_ids(relation)" in flex


def test_flex_uses_osm2pgsql_area_assembler_for_relation_geometry() -> None:
    flex = (project_root() / "config/osm/flex.lua").read_text(encoding="utf-8")

    assert "object:as_multipolygon()" in flex
    assert "schema = 'derived'" in flex
    assert "object:as_multilinestring()" not in flex
