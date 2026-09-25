import hashlib
from pathlib import Path

import pytest
from sqlalchemy import make_url

from app.data.osm import pipeline
from app.data.osm.config import BboxRegionConfig, RelationRegionConfig, SourceConfig
from app.data.osm.pipeline import _extract_command, _osm2pgsql_connection


@pytest.mark.parametrize(
    ("name", "bbox"),
    [
        ("spb_smoke", (30.2, 59.85, 30.5, 60.08)),
        ("spb_lo", (27.5, 58.35, 35.0, 61.8)),
    ],
)
def test_bbox_extract_command_preserves_simple_strategy(
    tmp_path: Path, name: str, bbox: tuple[float, float, float, float]
) -> None:
    source = tmp_path / "source.osm.pbf"
    partial = tmp_path / f"{name}.osm.pbf.part"

    assert _extract_command(
        BboxRegionConfig(
            name=name,
            type="bbox",
            bbox=bbox,
            description="",
        ),
        source,
        partial,
    ) == [
        "osmium",
        "extract",
        "--bbox",
        ",".join(str(value) for value in bbox),
        "--strategy",
        "simple",
        "--output",
        str(partial),
        "--output-format",
        "pbf",
        str(source),
    ]


def test_relation_extract_command_uses_recursive_references(tmp_path: Path) -> None:
    source = tmp_path / "source.osm.pbf"
    partial = tmp_path / "spb_districts.osm.pbf.part"

    assert _extract_command(
        RelationRegionConfig(
            name="spb_districts",
            type="relation",
            relation_ids=(337422, 123),
            description="",
        ),
        source,
        partial,
    ) == [
        "osmium",
        "getid",
        "--add-referenced",
        "--verbose-ids",
        "--output-format",
        "pbf",
        "--output",
        str(partial),
        str(source),
        "r337422",
        "r123",
    ]


class _ConnectionContext:
    def __enter__(self) -> object:
        return object()

    def __exit__(self, *_args: object) -> None:
        return None


class _Engine:
    def begin(self) -> _ConnectionContext:
        return _ConnectionContext()


def test_extract_is_atomic_checksummed_and_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "data/sources/osm/source.osm.pbf"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"registered source")
    source_checksum = hashlib.sha256(source.read_bytes()).hexdigest()
    profile = RelationRegionConfig(
        name="spb_districts",
        type="relation",
        relation_ids=(337422,),
        description="",
    )
    commands: list[list[str]] = []

    monkeypatch.setattr(pipeline, "project_root", lambda: tmp_path)
    monkeypatch.setattr(
        pipeline,
        "load_source",
        lambda _root: SourceConfig(
            name="test",
            provider="test",
            source_type="osm_pbf",
            source_url="https://example.test/source.pbf",
            checksum_url=None,
            license="ODbL",
            attribution="test",
        ),
    )
    monkeypatch.setattr(pipeline, "load_region", lambda _name, _root: profile)
    monkeypatch.setattr(
        pipeline,
        "ensure_source",
        lambda _connection, _source: {
            "local_filename": "data/sources/osm/source.osm.pbf",
            "checksum": source_checksum,
            "version": "test-v1",
        },
    )

    def fake_run_command(command: list[str], *, env: dict[str, str] | None = None) -> None:
        del env
        commands.append(command)
        if command[:2] == ["osmium", "getid"]:
            Path(command[command.index("--output") + 1]).write_bytes(b"valid extract")

    monkeypatch.setattr(pipeline, "run_command", fake_run_command)

    output = pipeline.extract_region("spb_districts", engine=_Engine())  # type: ignore[arg-type]
    partial = output.with_name(f"{output.name}.part")
    checksum_file = output.with_suffix(f"{output.suffix}.sha256")

    assert output.read_bytes() == b"valid extract"
    assert not partial.exists()
    assert checksum_file.read_text(encoding="ascii").strip() == hashlib.sha256(
        b"valid extract"
    ).hexdigest()
    assert commands[0][commands[0].index("--output") + 1] == str(partial)
    assert commands[1][:2] == ["osmium", "fileinfo"]

    commands.clear()
    assert pipeline.extract_region("spb_districts", engine=_Engine()) == output  # type: ignore[arg-type]
    assert commands == []


def test_osm2pgsql_connection_keeps_password_out_of_arguments() -> None:
    arguments, environment = _osm2pgsql_connection(
        make_url("postgresql+psycopg://osm-user:sensitive@db:5544/osm-db")
    )

    assert arguments == [
        "--host=db",
        "--port=5544",
        "--database=osm-db",
        "--username=osm-user",
    ]
    assert "sensitive" not in " ".join(arguments)
    assert environment["PGPASSWORD"] == "sensitive"
