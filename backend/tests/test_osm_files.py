import hashlib
import io
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request

import pytest

from app.data.osm.files import download_atomic, file_matches_sha256, sha256_file


def test_checksum_and_current_file_detection(tmp_path: Path) -> None:
    source = tmp_path / "source.osm.pbf"
    source.write_bytes(b"osm fixture")
    checksum = hashlib.sha256(b"osm fixture").hexdigest()

    assert sha256_file(source) == checksum
    assert file_matches_sha256(source, checksum)
    assert not file_matches_sha256(source, "0" * 64)


def test_atomic_download_validates_then_renames(tmp_path: Path) -> None:
    payload = b"valid pbf stand-in"
    destination = tmp_path / "source.osm.pbf"
    validated: list[Path] = []

    def opener(_request: Request) -> io.BytesIO:
        return io.BytesIO(payload)

    checksum, size = download_atomic(
        "https://example.test/source.osm.pbf",
        destination,
        expected_md5=hashlib.md5(payload).hexdigest(),  # noqa: S324
        validator=validated.append,
        opener=opener,
    )

    assert size == len(payload)
    assert checksum == hashlib.sha256(payload).hexdigest()
    assert destination.read_bytes() == payload
    assert validated[0].name.endswith(".part")
    assert not destination.with_name(f"{destination.name}.part").exists()


def test_interrupted_download_leaves_no_partial_or_final_file(tmp_path: Path) -> None:
    destination = tmp_path / "source.osm.pbf"

    class InterruptedResponse(io.BytesIO):
        def read(self, size: int = -1) -> bytes:
            if self.tell() > 0:
                raise ConnectionError("connection interrupted")
            return super().read(4 if size < 0 else min(size, 4))

    def opener(_request: Request) -> InterruptedResponse:
        return InterruptedResponse(b"partial payload")

    with pytest.raises(ConnectionError, match="interrupted"):
        download_atomic("https://example.test/source.osm.pbf", destination, opener=opener)

    assert not destination.exists()
    assert not destination.with_name(f"{destination.name}.part").exists()


def test_bad_url_leaves_no_files(tmp_path: Path) -> None:
    destination = tmp_path / "source.osm.pbf"

    def opener(_request: Request) -> io.BytesIO:
        raise URLError("not found")

    with pytest.raises(URLError, match="not found"):
        download_atomic("https://example.test/missing.osm.pbf", destination, opener=opener)

    assert not destination.exists()
    assert not destination.with_name(f"{destination.name}.part").exists()


def test_invalid_payload_is_not_published(tmp_path: Path) -> None:
    destination = tmp_path / "source.osm.pbf"

    def reject(_path: Path) -> None:
        raise ValueError("invalid PBF")

    with pytest.raises(ValueError, match="invalid PBF"):
        download_atomic(
            "https://example.test/invalid.osm.pbf",
            destination,
            validator=reject,
            opener=lambda _request: io.BytesIO(b"invalid"),
        )

    assert not destination.exists()
    assert not destination.with_name(f"{destination.name}.part").exists()
