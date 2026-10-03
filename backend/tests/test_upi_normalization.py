import copy
import json
from pathlib import Path

import pytest

from app.upi.arcgis import CompletenessError, SchemaChangedError, SourceResponseError
from app.upi.config import load_source_config
from app.upi.normalization import normalize_features, validate_schema

FIXTURE = Path("tests/fixtures/upi/toris_construction.json")


def load_fixture() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_toris_normalization_has_stable_identity_geometry_and_property_whitelist() -> None:
    fixture = load_fixture()
    normalized = normalize_features(
        tuple(fixture["features"]), fixture["metadata"], load_source_config()  # type: ignore[arg-type]
    )

    assert [feature.source_object_id for feature in normalized.features] == sorted(
        feature.source_object_id for feature in normalized.features
    )
    assert normalized.geometry_counts == {"Polygon": 3, "MultiPolygon": 1}
    assert len(normalized.schema_fingerprint) == 64
    assert len(normalized.payload_checksum) == 64
    first = normalized.features[0]
    assert first.source_object_id == "11111111-1111-4111-8111-111111111111"
    assert first.geometry["type"] == "Polygon"
    assert len(first.geometry["coordinates"]) == 2
    assert "UNAPPROVED_RAW_FIELD" not in first.properties
    assert set(first.properties) == {
        "source_row_id",
        "guid",
        "root_id",
        "address",
        "name",
        "status",
        "source_created_at",
        "cadastral_number",
        "purpose",
    }


def test_optional_ignored_metadata_field_does_not_change_fingerprint() -> None:
    fixture = load_fixture()
    metadata = fixture["metadata"]
    config = load_source_config()
    before = validate_schema(metadata, config)  # type: ignore[arg-type]
    changed = copy.deepcopy(metadata)
    changed["fields"].append(  # type: ignore[index,union-attr]
        {"name": "ANOTHER_IGNORED_FIELD", "type": "esriFieldTypeDate", "nullable": True}
    )

    assert validate_schema(changed, config) == before  # type: ignore[arg-type]


def test_schema_drift_missing_identity_and_invalid_geometry_fail_closed() -> None:
    fixture = load_fixture()
    config = load_source_config()
    drifted = copy.deepcopy(fixture["metadata"])
    drifted["fields"] = [  # type: ignore[index]
        field for field in drifted["fields"] if field["name"] != "GUID"  # type: ignore[index]
    ]
    with pytest.raises(SchemaChangedError, match="GUID"):
        validate_schema(drifted, config)  # type: ignore[arg-type]

    type_changed = copy.deepcopy(fixture["metadata"])
    for field in type_changed["fields"]:  # type: ignore[index,union-attr]
        if field["name"] == "GUID":
            field["type"] = "esriFieldTypeInteger"
    with pytest.raises(SchemaChangedError, match="type changed"):
        validate_schema(type_changed, config)  # type: ignore[arg-type]

    geometry_changed = copy.deepcopy(fixture["metadata"])
    geometry_changed["geometryType"] = "esriGeometryPoint"  # type: ignore[index]
    with pytest.raises(SchemaChangedError, match="geometry type"):
        validate_schema(geometry_changed, config)  # type: ignore[arg-type]

    missing_identity = copy.deepcopy(fixture["features"])
    del missing_identity[0]["attributes"]["GUID"]  # type: ignore[index]
    with pytest.raises((SchemaChangedError, CompletenessError)):
        normalize_features(
            tuple(missing_identity), fixture["metadata"], config  # type: ignore[arg-type]
        )

    invalid_geometry = copy.deepcopy(fixture["features"])
    invalid_geometry[0]["geometry"] = {"rings": [[[30.0, 59.0], [30.1, 59.1]]]}  # type: ignore[index]
    with pytest.raises(SourceResponseError, match="ring"):
        normalize_features(
            tuple(invalid_geometry), fixture["metadata"], config  # type: ignore[arg-type]
        )


def test_duplicate_business_guid_fails_closed() -> None:
    fixture = load_fixture()
    features = copy.deepcopy(fixture["features"])
    features[1]["attributes"]["GUID"] = features[0]["attributes"]["GUID"]  # type: ignore[index]

    with pytest.raises(CompletenessError, match="Duplicate"):
        normalize_features(
            tuple(features), fixture["metadata"], load_source_config()  # type: ignore[arg-type]
        )
