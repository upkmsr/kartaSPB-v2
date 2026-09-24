import json
from pathlib import Path

import pytest

from app.data.osm.config import load_region, load_regions, load_source, project_root


def test_source_metadata_preserves_license_and_attribution() -> None:
    source = load_source()

    assert source.provider == "Geofabrik GmbH"
    assert source.source_type == "osm_pbf"
    assert source.source_url.endswith("northwestern-fed-district-latest.osm.pbf")
    assert "ODbL" in source.license
    assert "OpenStreetMap contributors" in source.attribution


def test_region_configuration_contains_smoke_and_full_profiles() -> None:
    regions = load_regions()

    assert set(regions) >= {"spb_smoke", "spb_lo"}
    assert regions["spb_smoke"].bbox[0] < regions["spb_smoke"].bbox[2]
    assert "not an official administrative boundary" in regions["spb_lo"].description.lower()


def test_invalid_region_bbox_is_rejected(tmp_path: Path) -> None:
    config_dir = tmp_path / "config/osm"
    config_dir.mkdir(parents=True)
    (config_dir / "regions.json").write_text(
        json.dumps({"bad": {"type": "bbox", "bbox": [30, 60, 20, 50]}}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid bbox"):
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
