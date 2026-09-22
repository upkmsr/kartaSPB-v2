from app.db.models import DatasetSource, ImportRun, ImportRunStatus


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
