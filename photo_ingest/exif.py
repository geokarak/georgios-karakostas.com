"""Helpers for reading capture dates from photo EXIF metadata.

This module owns the logic for calling `exiftool`, parsing its JSON output,
and returning Python datetimes that the ingest flow can use.
"""

import datetime as dt
import json
import shutil
import subprocess
from pathlib import Path

EXIFTOOL_DATE_TAGS = ("ExifIFD:DateTimeOriginal", "ExifIFD:CreateDate")
EXIFTOOL_BATCH_SIZE = 200


def require_exiftool() -> str:
    """Return the local `exiftool` path or raise a clear error."""
    exiftool_path = shutil.which("exiftool")
    if exiftool_path:
        return exiftool_path

    raise RuntimeError(
        "This project requires exiftool for photo ingestion. "
        "Install exiftool and try again."
    )


def parse_exiftool_datetime(value: str) -> dt.datetime | None:
    """Parse one EXIF date string into a Python datetime."""
    normalized = value.strip()
    if not normalized:
        return None

    for date_format in ("%Y:%m:%d %H:%M:%S",):
        try:
            return dt.datetime.strptime(normalized, date_format)
        except ValueError:
            continue
    return None


def exiftool_datetime_from_metadata(metadata: dict[str, str]) -> dt.datetime | None:
    """Pick the best supported capture date from one metadata record."""
    for tag in EXIFTOOL_DATE_TAGS:
        value = metadata.get(tag)
        if not value:
            continue
        parsed = parse_exiftool_datetime(value)
        if parsed:
            return parsed

    return None


def exif_datetimes_batch(
    paths: list[Path], exiftool_path: str
) -> dict[Path, dt.datetime | None]:
    """Read EXIF capture dates for one batch of files."""
    if not paths:
        return {}

    try:
        result = subprocess.run(
            [
                exiftool_path,
                "-j",
                "-G1",
                *(f"-{tag}" for tag in EXIFTOOL_DATE_TAGS),
                *(str(path) for path in paths),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        return {path: None for path in paths}

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {path: None for path in paths}

    datetimes_by_path = {path: None for path in paths}
    path_lookup = {str(path.resolve()): path for path in paths}

    for metadata in payload:
        source_file = metadata.get("SourceFile")
        if not source_file:
            continue

        source_path = path_lookup.get(str(Path(source_file).resolve()))
        if not source_path:
            continue

        datetimes_by_path[source_path] = exiftool_datetime_from_metadata(metadata)

    return datetimes_by_path


def chunked_paths(paths: list[Path], chunk_size: int) -> list[list[Path]]:
    """Split a list of paths into smaller chunks."""
    return [
        paths[index : index + chunk_size] for index in range(0, len(paths), chunk_size)
    ]


def exif_datetimes(
    paths: list[Path], exiftool_path: str
) -> dict[Path, dt.datetime | None]:
    """Read EXIF capture dates safely, using chunking and fallback retries."""
    datetimes_by_path: dict[Path, dt.datetime | None] = {}

    for chunk in chunked_paths(paths, EXIFTOOL_BATCH_SIZE):
        chunk_results = exif_datetimes_batch(chunk, exiftool_path)
        if chunk and all(value is None for value in chunk_results.values()):
            for path in chunk:
                datetimes_by_path[path] = exif_datetimes_batch(
                    [path], exiftool_path
                ).get(path)
            continue

        datetimes_by_path.update(chunk_results)

    return datetimes_by_path
