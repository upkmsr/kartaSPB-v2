from app.db.models import DatasetSource, ImportRun, ImportRunStatus, OsmRelationGeometry


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
