import json
from pathlib import Path

import pytest

from app.upi.config import RawRetentionMode, TermsStatus, load_source_config, source_config_path


def test_toris_source_config_is_narrow_and_retention_safe() -> None:
    config = load_source_config()

    assert config.source_key == "toris-construction"
    assert config.layer_id == 3
    assert config.identity_field == "GUID"
    assert config.object_id_field == "OBJECTID"
    assert config.geometry_type == "esriGeometryPolygon"
    assert config.output_srid == 4326
    assert (config.source_wkid, config.source_latest_wkid) == (102100, 3857)
    assert config.normalization_version == "toris-construction-v1"
    assert config.terms_status is TermsStatus.PUBLIC_BUT_TERMS_UNCLEAR
    assert config.raw_retention_mode is RawRetentionMode.METADATA_ONLY
    assert config.retention_policy["live_raw_payload"] is False
    assert set(config.out_fields) == {
        "OBJECTID",
        "GUID",
        "ROOTID",
        "ADDRESSSTROYOBJECT",
        "NAZVANIEOBJECT",
        "STATUSOBJECT",
        "DATECREATE",
        "KADASTRNUMBER",
        "NAZNACHENIEOBJECT",
    }


def test_source_config_rejects_unknown_keys(tmp_path: Path) -> None:
    source = source_config_path("toris-construction")
    data = json.loads(source.read_text(encoding="utf-8"))
    data["silent_typo"] = True
    target = tmp_path / "config/upi/sources"
    target.mkdir(parents=True)
    (target / "toris_construction.json").write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ValueError, match="unexpected=.*silent_typo"):
        load_source_config(root=tmp_path)
