"""Helpers for the all-or-nothing photo ingest transaction.

This module owns the staging and commit steps that make one photo import safe:
prepare files in a temporary area, then move them into place only when the full
set is ready.
"""

import json
import shutil
import tempfile
from pathlib import Path

from .images import DISPLAY_MAX_EDGE, THUMBNAIL_MAX_EDGE, save_web_derivative
from .pages import gallery_page_content, gallery_page_path


def commit_staged_file(staged_file: Path, destination_file: Path) -> None:
    """Move a staged file into place without overwriting an existing file."""
    if destination_file.exists():
        raise FileExistsError(f"Destination already exists: {destination_file}")
    staged_file.replace(destination_file)


def ingest_photo_atomically(
    source_file: Path,
    category: str,
    project_root: Path,
    category_dir: Path,
    metadata_file: Path,
    display_file: Path,
    thumbnail_file: Path,
    metadata: dict[str, str | bool],
) -> None:
    """Stage one photo import first, then commit it as one safe unit."""
    staging_root = Path(
        tempfile.mkdtemp(prefix=f".ingest-{metadata['id']}-", dir=category_dir.parent)
    )
    staged_category_dir = staging_root / category
    staged_display_file = staged_category_dir / display_file.name
    staged_thumbnail_file = staged_category_dir / thumbnail_file.name
    staged_metadata_file = staged_category_dir / metadata_file.name
    page_file = gallery_page_path(category, project_root)
    staged_page_file = staging_root / page_file.name
    should_create_page = not page_file.exists()
    committed_paths: list[Path] = []
    created_page = False

    try:
        staged_category_dir.mkdir(parents=True, exist_ok=True)
        save_web_derivative(source_file, staged_display_file, DISPLAY_MAX_EDGE)
        save_web_derivative(source_file, staged_thumbnail_file, THUMBNAIL_MAX_EDGE)
        staged_metadata_file.write_text(
            json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
        )

        if should_create_page:
            staged_page_file.write_text(
                gallery_page_content(category), encoding="utf-8"
            )

        category_dir.mkdir(parents=True, exist_ok=True)
        commit_staged_file(staged_display_file, display_file)
        committed_paths.append(display_file)
        commit_staged_file(staged_thumbnail_file, thumbnail_file)
        committed_paths.append(thumbnail_file)
        commit_staged_file(staged_metadata_file, metadata_file)
        committed_paths.append(metadata_file)

        if should_create_page and not page_file.exists():
            page_file.parent.mkdir(parents=True, exist_ok=True)
            commit_staged_file(staged_page_file, page_file)
            created_page = True

        source_file.unlink()
    except Exception:
        for committed_path in reversed(committed_paths):
            committed_path.unlink(missing_ok=True)
        if created_page:
            page_file.unlink(missing_ok=True)
        raise
    finally:
        shutil.rmtree(staging_root, ignore_errors=True)
