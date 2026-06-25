"""Helpers for the Dropbox download phase.

This module owns the first workflow phase: list remote inbox files, download
them locally, and write a manifest that remembers which Dropbox source file
produced which staged file.
"""

from pathlib import Path, PurePosixPath

from .api import download_remote_file, list_remote_images
from .auth import require_access_token
from .manifests import write_manifest_file
from .paths import relative_dropbox_path


def download_dropbox_inbox(
    staging_dir: Path,
    inbox_root: PurePosixPath,
    manifest_file: Path,
) -> int:
    """Download inbox files and write a manifest for later finalization."""
    staging_dir.mkdir(parents=True, exist_ok=True)

    token = require_access_token()
    files = list_remote_images(token, inbox_root)

    if not files:
        write_manifest_file(manifest_file, [])
        print(f"No Dropbox images found in {inbox_root.as_posix()}")
        return 0

    downloaded = 0
    manifest_entries = []
    for entry in files:
        source_path = entry["path_display"]
        relative_path = relative_dropbox_path(source_path, inbox_root)
        destination = staging_dir.joinpath(*relative_path.parts)

        download_remote_file(token, source_path, destination)
        manifest_entries.append(
            {
                "source_path": source_path,
                "staging_path": str(destination.resolve()),
            }
        )

        downloaded += 1
        print(f"Staged {source_path} -> {destination}")

    write_manifest_file(manifest_file, manifest_entries)
    print(f"Wrote download manifest -> {manifest_file}")

    print(f"Done. Downloaded: {downloaded}")
    return downloaded
