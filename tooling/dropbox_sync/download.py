"""Helpers for the Dropbox download phase.

This module owns the first workflow phase: list Dropbox inbox files, download
them locally, and write a manifest that remembers which Dropbox source file
produced which staged file.

The staged directory is just a temporary local workspace. Its job is to give
the existing ingest pipeline normal filesystem paths to read from. The download
manifest is what ties that temporary local staging area back to the original
Dropbox inbox paths.
"""

from pathlib import Path, PurePosixPath

from .api import download_dropbox_file, list_dropbox_images
from .auth import require_access_token
from .manifests import write_manifest_file
from .paths import relative_dropbox_path


def download_dropbox_inbox(
    staging_dir: Path,
    inbox_root: PurePosixPath,
    manifest_file: Path,
) -> int:
    """Download inbox files and map each Dropbox path to one staged file path."""
    staging_dir.mkdir(parents=True, exist_ok=True)

    access_token = require_access_token()
    dropbox_files = list_dropbox_images(access_token, inbox_root)

    if not dropbox_files:
        write_manifest_file(manifest_file, [])
        print(f"No Dropbox images found in {inbox_root.as_posix()}")
        return 0

    downloaded = 0
    manifest_entries = []
    for dropbox_file in dropbox_files:
        dropbox_source_path = dropbox_file["path_display"]
        relative_path = relative_dropbox_path(dropbox_source_path, inbox_root)
        staged_file_path = staging_dir.joinpath(*relative_path.parts)

        download_dropbox_file(access_token, dropbox_source_path, staged_file_path)
        # The download manifest is the bridge between Dropbox and local ingest.
        #
        # `source_path` is the original Dropbox inbox file.
        # `staging_path` is the temporary local file that `ingest_photos` will
        # read and later report back in its result manifest.
        manifest_entries.append(
            {
                "source_path": dropbox_source_path,
                "staging_path": str(staged_file_path.resolve()),
            }
        )

        downloaded += 1
        print(f"Staged {dropbox_source_path} -> {staged_file_path}")

    write_manifest_file(manifest_file, manifest_entries)
    print(f"Wrote download manifest -> {manifest_file}")

    print(f"Done. Downloaded: {downloaded}")
    return downloaded
