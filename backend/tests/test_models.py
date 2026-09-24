from app.db.models import (
    CatalogObject,
    CatalogRelationship,
    DatasetSource,
    ImportRun,
    ImportRunStatus,
    ObjectSource,
    OsmRelationGeometry,
)


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
        ImportRunStatus.SUCCESS,
        ImportRunStatus.FAILED,
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
