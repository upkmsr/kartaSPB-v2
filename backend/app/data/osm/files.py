import hashlib
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any, BinaryIO
from urllib.request import Request, urlopen

CHUNK_SIZE = 1024 * 1024


def file_digest(path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_file(path: Path) -> str:
    return file_digest(path, "sha256")


def md5_file(path: Path) -> str:
    # MD5 is used only to compare Geofabrik's published transport checksum.
    return file_digest(path, "md5")  # noqa: S324


def file_matches_sha256(path: Path, expected_checksum: str | None) -> bool:
    return bool(path.is_file() and expected_checksum and sha256_file(path) == expected_checksum)


def download_atomic(
    url: str,
    destination: Path,
    *,
    expected_md5: str | None = None,
    validator: Callable[[Path], None] | None = None,
    opener: Callable[[Request], BinaryIO] | None = None,
) -> tuple[str, int]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(f"{destination.name}.part")
    partial.unlink(missing_ok=True)
    open_request: Any = opener or urlopen
    size = 0
    try:
        request = Request(url, headers={"User-Agent": "KARTASPB-v2/1.0"})
        with open_request(request) as response, partial.open("wb") as output:
            while chunk := response.read(CHUNK_SIZE):
                output.write(chunk)
                size += len(chunk)
                if size % (64 * CHUNK_SIZE) == 0:
                    print(f"Downloaded {size // CHUNK_SIZE} MiB…", flush=True)
            output.flush()
            os.fsync(output.fileno())

        if size == 0:
            raise ValueError("Downloaded file is empty")
        if expected_md5 and md5_file(partial).lower() != expected_md5.lower():
            raise ValueError("Downloaded file does not match provider MD5 checksum")
        if validator:
            validator(partial)
        checksum = sha256_file(partial)
        os.replace(partial, destination)
        return checksum, size
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
