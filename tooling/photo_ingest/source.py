"""Helpers for source files, categories, and generated photo ids.

This module covers the basic ingest questions: which files should be processed,
which category they belong to, and which id a new photo should receive.
"""

import datetime as dt
import re
import secrets
from pathlib import Path

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def slugify(value: str) -> str:
    """Turn free-form text into a simple URL-friendly slug."""
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower())
    return normalized.strip("-")


def generated_photo_id(captured_at: dt.datetime) -> str:
    """Build a photo id from the capture time plus a short random suffix."""
    return f"{captured_at.strftime('%Y-%m-%d-%H%M%S')}-{secrets.token_hex(4)}"


def get_category(source_file: Path, src_root: Path) -> str | None:
    """Read the gallery category from the source file path."""
    relative = source_file.relative_to(src_root)
    if len(relative.parts) > 1:
        return slugify(relative.parts[0])
    return None


def reserve_photo_id(
    category_dir: Path,
    photo_id: str,
    derivative_paths,
    reserved_ids: set[str] | None = None,
) -> bool:
    """Check whether a generated photo id is still unused."""
    metadata_exists = (category_dir / f"{photo_id}.json").exists()
    display_file, thumbnail_file = derivative_paths(category_dir, photo_id)
    image_exists = display_file.exists() or thumbnail_file.exists()
    already_reserved = reserved_ids is not None and photo_id in reserved_ids
    return not metadata_exists and not image_exists and not already_reserved


def unique_id(
    category_dir: Path,
    captured_at: dt.datetime,
    derivative_paths,
    reserved_ids: set[str] | None = None,
) -> str:
    """Keep generating ids until one does not clash with existing files."""
    while True:
        candidate = generated_photo_id(captured_at)
        if reserve_photo_id(
            category_dir,
            candidate,
            derivative_paths,
            reserved_ids=reserved_ids,
        ):
            return candidate


def source_images(src_dir: Path) -> list[Path]:
    """Collect supported image files from the source tree."""
    files = [
        path
        for path in src_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    return sorted(files)
