from app.db.models import (
    AnalysisCell,
    CatalogObject,
    CatalogRelationship,
    CellMetricScore,
    CellMetricValue,
    DatasetSource,
    District,
    FacilityEntity,
    FacilityEntityMember,
    ImportRun,
    ImportRunStatus,
    MetricCurrentRun,
    MetricRun,
    MetricScoreCurrentRun,
    MetricScoreRun,
    ObjectSource,
    OsmProfileMembership,
    OsmRelationGeometry,
    StreetEntity,
    StreetEntityMember,
    UpiNormalizedFeature,
    UpiSourceHealth,
    UpiSourceProfile,
    UpiSourceSnapshot,
)


def test_analysis_cell_model_keeps_metric_and_display_geometry() -> None:
    assert AnalysisCell.__table__.schema == "analytics"
    assert {column.name for column in AnalysisCell.__table__.columns} == {
        "cell_id",
        "grid_version",
        "grid_i",
        "grid_j",
        "cell_size_m",
        "district_id",
        "center",
        "center_metric",
        "geom",
        "geom_metric",
        "created_at",
    }
    assert AnalysisCell.__table__.c.center.type.srid == 4326
    assert AnalysisCell.__table__.c.center_metric.type.srid == 32636
    assert AnalysisCell.__table__.c.geom.type.srid == 4326
    assert AnalysisCell.__table__.c.geom_metric.type.srid == 32636


def test_metric_models_separate_history_values_and_current_pointer() -> None:
    assert MetricRun.__table__.schema == "analytics"
    assert CellMetricValue.__table__.schema == "analytics"
    assert MetricCurrentRun.__table__.schema == "analytics"
    assert {column.name for column in MetricRun.__table__.columns} == {
        "run_id",
        "metric_key",
        "definition_version",
        "calculation_version",
        "grid_version",
        "definition_checksum",
        "input_fingerprint",
        "definition_snapshot",
        "run_signature",
        "cell_count",
        "min_value",
        "max_value",
        "mean_value",
        "values_checksum",
        "created_at",
    }
    assert {column.name for column in CellMetricValue.__table__.primary_key.columns} == {
        "run_id",
        "cell_id",
    }
    assert {column.name for column in MetricCurrentRun.__table__.primary_key.columns} == {
        "metric_key",
        "grid_version",
    }


def test_metric_score_models_separate_history_values_and_current_pointer() -> None:
    assert MetricScoreRun.__table__.schema == "analytics"
    assert CellMetricScore.__table__.schema == "analytics"
    assert MetricScoreCurrentRun.__table__.schema == "analytics"
    assert {column.name for column in MetricScoreRun.__table__.columns} >= {
        "score_run_id",
        "metric_run_id",
        "normalization_snapshot",
        "run_signature",
        "values_checksum",
    }
    assert {column.name for column in CellMetricScore.__table__.primary_key.columns} == {
        "score_run_id",
        "cell_id",
    }
    assert {
        column.name for column in MetricScoreCurrentRun.__table__.primary_key.columns
    } == {"metric_key", "grid_version"}


def test_dataset_source_model_uses_meta_schema() -> None:
    assert DatasetSource.__table__.schema == "meta"
    assert {column.name for column in DatasetSource.__table__.columns} >= {
        "name",
        "provider",
        "source_type",
        "source_url",
        "license",
        "attribution",
    }


def test_import_run_model_tracks_import_outcome() -> None:
    status_default = ImportRun.__table__.c.status.default

    assert ImportRun.__table__.schema == "meta"
    assert status_default is not None
    assert status_default.arg == ImportRunStatus.PENDING
    assert set(ImportRunStatus) == {
        ImportRunStatus.PENDING,
        ImportRunStatus.RUNNING,
        ImportRunStatus.STAGED,
        ImportRunStatus.SUCCESS,
        ImportRunStatus.FAILED,
    }
    assert {"profile", "authoritative_snapshot", "lifecycle_finalized_at"} <= {
        column.name for column in ImportRun.__table__.columns
    }


def test_osm_profile_membership_separates_scope_from_identity() -> None:
    assert OsmProfileMembership.__table__.schema == "meta"
    assert {column.name for column in OsmProfileMembership.__table__.primary_key.columns} == {
        "source_id",
        "profile",
        "source_object_type",
        "source_object_id",
    }


def test_relation_geometry_model_uses_derived_schema() -> None:
    assert OsmRelationGeometry.__table__.schema == "derived"
    assert {column.name for column in OsmRelationGeometry.__table__.columns} >= {
        "source_id",
        "relation_id",
        "relation_type",
        "geometry_kind",
        "assembly_method",
        "assembly_status",
        "diagnostics",
        "geom",
    }


def test_catalog_models_use_provider_independent_schema() -> None:
    assert CatalogObject.__table__.schema == "catalog"
    assert ObjectSource.__table__.schema == "catalog"
    assert CatalogRelationship.__table__.schema == "catalog"
    assert {column.name for column in CatalogObject.__table__.columns} >= {
        "id",
        "object_kind",
        "lifecycle_status",
        "search_name",
        "search_name_v2",
        "geom",
        "name_source_id",
        "geometry_source_id",
        "revision",
    }
    assert {column.name for column in ObjectSource.__table__.columns} >= {
        "source_id",
        "source_object_type",
        "source_object_id",
        "payload_hash",
        "first_seen_import_run_id",
        "last_seen_import_run_id",
        "last_changed_import_run_id",
    }


def test_district_model_keeps_geometry_in_catalog() -> None:
    assert District.__table__.schema == "domain"
    assert {column.name for column in District.__table__.columns} == {
        "id",
        "canonical_object_id",
        "name",
        "slug",
        "display_order",
        "enabled",
        "created_at",
        "updated_at",
    }


def test_logical_facility_models_reference_canonical_objects() -> None:
    assert FacilityEntity.__table__.schema == "domain"
    assert FacilityEntityMember.__table__.schema == "domain"
    assert {column.name for column in FacilityEntity.__table__.columns} >= {
        "category_key",
        "representative_object_id",
        "display_object_id",
        "analysis_object_id",
        "lifecycle_status",
        "link_method",
        "evidence",
    }
    assert {column.name for column in FacilityEntityMember.__table__.primary_key.columns} == {
        "facility_entity_id",
        "canonical_object_id",
    }


def test_logical_street_models_reference_canonical_road_members() -> None:
    assert StreetEntity.__table__.schema == "domain"
    assert StreetEntityMember.__table__.schema == "domain"
    assert {column.name for column in StreetEntity.__table__.columns} >= {
        "display_name",
        "search_name",
        "geom",
        "representative_point",
        "lifecycle_status",
        "link_method",
        "evidence",
    }
    assert {column.name for column in StreetEntityMember.__table__.primary_key.columns} == {
        "street_entity_id",
        "canonical_object_id",
    }


def test_upi_models_are_separate_from_catalog_and_keep_evidence_contract() -> None:
    assert UpiSourceProfile.__table__.schema == "upi"
    assert UpiSourceSnapshot.__table__.schema == "upi"
    assert UpiNormalizedFeature.__table__.schema == "upi"
    assert UpiSourceHealth.__table__.schema == "upi"
    assert {column.name for column in UpiNormalizedFeature.__table__.columns} >= {
        "source_id",
        "snapshot_id",
        "source_object_id",
        "normalization_version",
        "properties",
        "payload_hash",
        "geom",
    }
    assert {column.name for column in UpiSourceSnapshot.__table__.columns} >= {
        "import_run_id",
        "retrieved_at",
        "config_version",
        "schema_fingerprint",
        "payload_checksum",
        "source_crs",
        "raw_payload",
        "raw_evidence_locator",
    }
